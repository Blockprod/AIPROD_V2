"""
comfyui_adapter.py — Generic ComfyUI workflow adapter + XLabs IP-Adapter factory.

ComfyUI API contract:
    POST  /prompt           → { prompt_id: str }
    GET   /history/{id}     → { <id>: { outputs: { <node_id>: { images: [...] } } } }
    GET   /view?filename=X  → raw image bytes

Workflow substitution model:
    The caller provides a workflow_template dict (ComfyUI API format).
    Node IDs that carry prompt/reference/seed are passed as node_id constants
    on the adapter subclass (or the factory).  The adapter patches those nodes
    before every call — no generic parsing needed.

Excluded from mypy strict and CI integration suites — integration only.
Requires: COMFYUI_API_URL env var (default: http://localhost:8188)
"""

from __future__ import annotations

import base64
import copy
import os
import time
from typing import Any

import requests as _requests

from aiprod_adaptation.adapters.errors import AdapterError, AdapterFailureCategory
from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult


class ComfyUIAdapter(ImageAdapter):
    """
    Generic ComfyUI workflow adapter.

    Accepts a workflow_template dict (ComfyUI API prompt format) and three
    optional node-ID overrides that specify which nodes carry:
        - text prompt       (node_text_id)
        - reference image   (node_image_id)
        - seed              (node_seed_id)

    The template is deep-copied and patched before each POST /prompt call.
    Image bytes are fetched via GET /view and base64-encoded into ImageResult.
    """

    MODEL_NAME: str = "comfyui"

    def __init__(
        self,
        workflow_template: dict[str, Any],
        api_url: str | None = None,
        poll_interval: float = 1.0,
        timeout: float = 120.0,
        node_text_id: str = "6",
        node_image_id: str = "11",
        node_seed_id: str = "25",
        output_node_id: str = "9",
    ) -> None:
        self._template = workflow_template
        self._url = (api_url or os.environ.get("COMFYUI_API_URL", "http://localhost:8188")).rstrip("/")
        self._poll_interval = poll_interval
        self._timeout = timeout
        self._node_text_id = node_text_id
        self._node_image_id = node_image_id
        self._node_seed_id = node_seed_id
        self._output_node_id = output_node_id
        self._preflight_done = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, request: ImageRequest) -> ImageResult:
        t0 = time.monotonic()
        self.preflight()
        workflow = self._build_workflow(request)
        prompt_id = self._submit(workflow)
        filename = self._poll(prompt_id, t0)
        if filename is None:
            raise AdapterError(
                f"ComfyUI job {prompt_id} timed out.", provider="comfyui",
                category=AdapterFailureCategory.TIMEOUT, retryable=True,
                request_id=request.shot_id,
            )
        image_b64 = self._fetch_image_b64(filename)
        latency = int((time.monotonic() - t0) * 1000)
        return ImageResult(
            shot_id=request.shot_id,
            image_url=f"{self._url}/view?filename={filename}",
            image_b64=image_b64,
            model_used=self.MODEL_NAME,
            latency_ms=latency,
        )

    def preflight(self) -> None:
        if self._preflight_done:
            return
        try:
            response = _requests.get(f"{self._url}/object_info", timeout=10)
            response.raise_for_status()
            object_info = response.json()
        except (_requests.RequestException, ValueError) as exc:
            raise AdapterError(
                f"ComfyUI preflight failed at {self._url}.", provider="comfyui",
                category=AdapterFailureCategory.LOCAL_RUNTIME,
            ) from exc
        if not isinstance(object_info, dict):
            raise AdapterError(
                "ComfyUI object_info response is malformed.", provider="comfyui",
                category=AdapterFailureCategory.MALFORMED_RESPONSE,
            )
        required_classes = {
            str(node.get("class_type"))
            for node in self._template.values()
            if isinstance(node, dict) and node.get("class_type")
        }
        missing_classes = sorted(required_classes.difference(object_info))
        if missing_classes:
            raise AdapterError(
                f"ComfyUI missing nodes/extensions: {missing_classes}", provider="comfyui",
                category=AdapterFailureCategory.LOCAL_RUNTIME,
            )
        self._preflight_done = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_workflow(self, request: ImageRequest) -> dict[str, Any]:
        workflow = copy.deepcopy(self._template)

        required_nodes = {self._node_text_id, self._node_seed_id, self._output_node_id}
        if request.reference_image_url:
            required_nodes.add(self._node_image_id)
        missing = sorted(required_nodes.difference(workflow))
        if missing:
            raise AdapterError(
                f"ComfyUI workflow missing required nodes: {missing}", provider="comfyui",
                category=AdapterFailureCategory.LOCAL_RUNTIME,
                request_id=request.shot_id,
            )
        for node_id in required_nodes:
            node = workflow[node_id]
            if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
                raise AdapterError(
                    f"ComfyUI node {node_id} has no inputs object.", provider="comfyui",
                    category=AdapterFailureCategory.LOCAL_RUNTIME,
                    request_id=request.shot_id,
                )

        # Patch text prompt node
        if self._node_text_id in workflow:
            workflow[self._node_text_id]["inputs"]["text"] = request.prompt

        # Patch reference image node (URL-based load)
        if self._node_image_id in workflow and request.reference_image_url:
            workflow[self._node_image_id]["inputs"]["url"] = request.reference_image_url

        # Patch seed node
        if self._node_seed_id in workflow and request.seed is not None:
            workflow[self._node_seed_id]["inputs"]["seed"] = request.seed

        return workflow

    def _submit(self, workflow: dict[str, Any]) -> str:
        resp = _requests.post(
            f"{self._url}/prompt",
            json={"prompt": workflow},
            timeout=30,
        )
        resp.raise_for_status()
        try:
            prompt_id = resp.json()["prompt_id"]
        except (KeyError, TypeError, ValueError) as exc:
            raise AdapterError(
                "ComfyUI submission response is malformed.", provider="comfyui",
                category=AdapterFailureCategory.MALFORMED_RESPONSE,
            ) from exc
        if not isinstance(prompt_id, str) or not prompt_id:
            raise AdapterError(
                "ComfyUI returned an empty prompt id.", provider="comfyui",
                category=AdapterFailureCategory.MALFORMED_RESPONSE,
            )
        return prompt_id

    def _poll(self, prompt_id: str, t0: float) -> str | None:
        """Poll /history until the job completes or timeout is reached."""
        while (time.monotonic() - t0) < self._timeout:
            try:
                resp = _requests.get(
                    f"{self._url}/history/{prompt_id}",
                    timeout=10,
                )
            except StopIteration:
                return None
            except _requests.Timeout as exc:
                raise AdapterError(
                    f"ComfyUI history poll timed out for job {prompt_id}.",
                    provider="comfyui",
                    category=AdapterFailureCategory.TIMEOUT,
                    retryable=True,
                ) from exc
            except _requests.RequestException as exc:
                raise AdapterError(
                    f"ComfyUI history poll failed for job {prompt_id}.",
                    provider="comfyui",
                    category=AdapterFailureCategory.UNAVAILABLE,
                    retryable=True,
                ) from exc
            if resp.status_code == 200:
                try:
                    history = resp.json()
                except ValueError as exc:
                    raise AdapterError(
                        "ComfyUI history response is not valid JSON.",
                        provider="comfyui",
                        category=AdapterFailureCategory.MALFORMED_RESPONSE,
                    ) from exc
                if not isinstance(history, dict):
                    raise AdapterError(
                        "ComfyUI history response is malformed.",
                        provider="comfyui",
                        category=AdapterFailureCategory.MALFORMED_RESPONSE,
                    )
                if prompt_id in history:
                    entry = history[prompt_id]
                    if not isinstance(entry, dict):
                        raise AdapterError(
                            "ComfyUI history entry is malformed.",
                            provider="comfyui",
                            category=AdapterFailureCategory.MALFORMED_RESPONSE,
                        )
                    outputs = entry.get("outputs", {})
                    if not isinstance(outputs, dict):
                        raise AdapterError(
                            "ComfyUI output payload is malformed.",
                            provider="comfyui",
                            category=AdapterFailureCategory.MALFORMED_RESPONSE,
                        )
                    node_out = outputs.get(self._output_node_id, {})
                    if not isinstance(node_out, dict):
                        raise AdapterError(
                            "ComfyUI output node payload is malformed.",
                            provider="comfyui",
                            category=AdapterFailureCategory.MALFORMED_RESPONSE,
                        )
                    images = node_out.get("images", [])
                    if images:
                        first_image = images[0]
                        if not isinstance(first_image, dict) or not first_image.get("filename"):
                            raise AdapterError(
                                "ComfyUI image payload is malformed.",
                                provider="comfyui",
                                category=AdapterFailureCategory.MALFORMED_RESPONSE,
                            )
                        return str(first_image["filename"])
            time.sleep(self._poll_interval)
        return None

    def _fetch_image_b64(self, filename: str) -> str:
        resp = _requests.get(
            f"{self._url}/view",
            params={"filename": filename},
            timeout=30,
        )
        resp.raise_for_status()
        if not resp.content:
            raise AdapterError(
                "ComfyUI returned an empty image.", provider="comfyui",
                category=AdapterFailureCategory.MALFORMED_RESPONSE,
            )
        return base64.b64encode(resp.content).decode("ascii")


# ---------------------------------------------------------------------------
# XLabs Flux IP-Adapter workflow template
# ---------------------------------------------------------------------------
#
# Node layout (ComfyUI API format):
#   "1"  — Load Diffusion Model (flux1-dev)
#   "2"  — DualCLIPLoader
#   "3"  — Load VAE
#   "6"  — CLIPTextEncode (positive prompt)         ← node_text_id
#   "11" — LoadImageFromURL (reference image)        ← node_image_id
#   "20" — Flux Load IPAdapter
#   "21" — Apply Flux IPAdapter
#   "25" — KSampler (holds seed)                     ← node_seed_id
#   "9"  — VAEDecode + SaveImage (output)            ← output_node_id
#
# Callers must have the following models in their ComfyUI models dir:
#   models/diffusion_models/flux1-dev.safetensors
#   models/clip/clip_l.safetensors
#   models/clip/t5xxl_fp8_e4m3fn.safetensors
#   models/vae/ae.safetensors
#   models/ipadapter/flux-ip-adapter.safetensors
#   models/clip_vision/<clip_vision_model>

_XLABS_IPADAPTER_WORKFLOW_TEMPLATE: dict[str, Any] = {
    "1": {
        "class_type": "UNETLoader",
        "inputs": {"unet_name": "flux1-dev.safetensors", "weight_dtype": "fp8_e4m3fn"},
    },
    "2": {
        "class_type": "DualCLIPLoader",
        "inputs": {
            "clip_name1": "clip_l.safetensors",
            "clip_name2": "t5xxl_fp8_e4m3fn.safetensors",
            "type": "flux",
        },
    },
    "3": {
        "class_type": "VAELoader",
        "inputs": {"vae_name": "ae.safetensors"},
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {"clip": ["2", 0], "text": ""},
    },
    "11": {
        "class_type": "LoadImageFromURL",
        "inputs": {"url": ""},
    },
    "20": {
        "class_type": "FluxIPAdapterLoader",
        "inputs": {
            "ipadapter_file": "flux-ip-adapter.safetensors",
            "clip_vision": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
            "provider": "cuda",
        },
    },
    "21": {
        "class_type": "IPAdapterFlux",
        "inputs": {
            "model": ["1", 0],
            "ipadapter": ["20", 0],
            "image": ["11", 0],
            "weight": 0.6,
            "start_percent": 0.0,
            "end_percent": 1.0,
        },
    },
    "25": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["21", 0],
            "positive": ["6", 0],
            "negative": ["6", 0],
            "latent_image": ["26", 0],
            "seed": 42,
            "steps": 28,
            "cfg": 1.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1.0,
        },
    },
    "26": {
        "class_type": "EmptySD3LatentImage",
        "inputs": {"width": 1024, "height": 576, "batch_size": 1},
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {
            "images": ["27", 0],
            "filename_prefix": "aiprod_xlabs",
        },
    },
    "27": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["25", 0], "vae": ["3", 0]},
    },
}


def make_xlabs_ipadapter_adapter(
    api_url: str | None = None,
    clip_vision_model: str = "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
    ipadapter_model: str = "flux-ip-adapter.safetensors",
) -> ComfyUIAdapter:
    """
    Return a ComfyUIAdapter pre-configured with the XLabs Flux IP-Adapter workflow.

    Args:
        api_url:           ComfyUI server URL (default: COMFYUI_API_URL env var).
        clip_vision_model: CLIP vision checkpoint filename in models/clip_vision/.
        ipadapter_model:   XLabs IP-Adapter checkpoint filename in models/ipadapter/.
    """
    template: dict[str, Any] = copy.deepcopy(_XLABS_IPADAPTER_WORKFLOW_TEMPLATE)
    template["20"]["inputs"]["ipadapter_file"] = ipadapter_model
    template["20"]["inputs"]["clip_vision"] = clip_vision_model
    return ComfyUIAdapter(
        workflow_template=template,
        api_url=api_url,
        node_text_id="6",
        node_image_id="11",
        node_seed_id="25",
        output_node_id="9",
    )
