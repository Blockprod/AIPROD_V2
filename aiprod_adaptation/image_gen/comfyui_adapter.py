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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, request: ImageRequest) -> ImageResult:
        t0 = time.monotonic()
        workflow = self._build_workflow(request)
        prompt_id = self._submit(workflow)
        filename = self._poll(prompt_id, t0)
        if filename is None:
            return ImageResult(
                shot_id=request.shot_id,
                image_url="error://comfyui-timeout",
                image_b64="",
                model_used="error",
                latency_ms=int((time.monotonic() - t0) * 1000),
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_workflow(self, request: ImageRequest) -> dict[str, Any]:
        workflow = copy.deepcopy(self._template)

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
        return str(resp.json()["prompt_id"])

    def _poll(self, prompt_id: str, t0: float) -> str | None:
        """Poll /history until the job completes or timeout is reached."""
        while (time.monotonic() - t0) < self._timeout:
            resp = _requests.get(
                f"{self._url}/history/{prompt_id}",
                timeout=10,
            )
            if resp.status_code == 200:
                history = resp.json()
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    node_out = outputs.get(self._output_node_id, {})
                    images = node_out.get("images", [])
                    if images:
                        return str(images[0]["filename"])
            time.sleep(self._poll_interval)
        return None

    def _fetch_image_b64(self, filename: str) -> str:
        resp = _requests.get(
            f"{self._url}/view",
            params={"filename": filename},
            timeout=30,
        )
        if resp.status_code == 200:
            return base64.b64encode(resp.content).decode("ascii")
        return ""


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
