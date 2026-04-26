"""
flux_kontext_adapter.py — Flux Kontext Dev adapter for per-shot character consistency.

Uses ComfyUIAdapter with an embedded Flux Kontext workflow (BFL flux1-dev-kontext
fp8 checkpoint).  The Kontext pattern preserves character appearance while
changing background/location between shots.

Kontext prompt pattern (BFL-documented):
    "Change the background to [location] while keeping the person in the exact
     same position, scale, and pose, preserving facial features"

Requires:
    - COMFYUI_API_URL env var pointing to a running ComfyUI instance
    - models/diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors
    - models/clip/clip_l.safetensors
    - models/clip/t5xxl_fp8_e4m3fn_scaled.safetensors
    - models/vae/ae.safetensors
    - Node 11 must support LoadImageFromURL (custom ComfyUI node or equivalent)

Excluded from mypy strict and CI integration suites — integration only.
"""

from __future__ import annotations

import copy
from typing import Any

from aiprod_adaptation.image_gen.comfyui_adapter import ComfyUIAdapter
from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult

# ---------------------------------------------------------------------------
# Flux Kontext workflow template (ComfyUI API format)
#
# Node layout:
#   "1"  — Load Diffusion Model (flux1-dev-kontext)
#   "2"  — DualCLIPLoader
#   "3"  — Load VAE
#   "6"  — CLIPTextEncode (positive prompt)          ← node_text_id
#   "11" — LoadImageFromURL (character reference)    ← node_image_id
#   "12" — Kontext conditioning node (image+text)
#   "25" — KSampler                                   ← node_seed_id
#   "26" — EmptySD3LatentImage
#   "27" — VAEDecode
#   "9"  — SaveImage (output)                         ← output_node_id
# ---------------------------------------------------------------------------

_FLUX_KONTEXT_WORKFLOW_TEMPLATE: dict[str, Any] = {
    "1": {
        "class_type": "UNETLoader",
        "inputs": {
            "unet_name": "flux1-dev-kontext_fp8_scaled.safetensors",
            "weight_dtype": "fp8_e4m3fn",
        },
    },
    "2": {
        "class_type": "DualCLIPLoader",
        "inputs": {
            "clip_name1": "clip_l.safetensors",
            "clip_name2": "t5xxl_fp8_e4m3fn_scaled.safetensors",
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
    "12": {
        "class_type": "FluxKontextImageEncode",
        "inputs": {
            "vae": ["3", 0],
            "image": ["11", 0],
            "conditioning": ["6", 0],
        },
    },
    "25": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["1", 0],
            "positive": ["12", 0],
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
    "27": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["25", 0], "vae": ["3", 0]},
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {
            "images": ["27", 0],
            "filename_prefix": "aiprod_kontext",
        },
    },
}

_KONTEXT_PRESERVATION_CLAUSE = (
    "while keeping the person in the exact same position, scale, and pose, "
    "preserving facial features"
)


class FluxKontextAdapter(ComfyUIAdapter):
    """
    Flux Kontext Dev adapter for background-swap with character consistency.

    When request.reference_image_url is set, the reference image is loaded
    into the Kontext conditioning node so the character appearance is preserved
    while the background/location changes according to request.prompt.

    If request.prompt already contains the preservation clause, it is not
    duplicated.  Otherwise the clause is appended automatically.
    """

    MODEL_NAME: str = "flux-kontext"

    def __init__(self, api_url: str | None = None) -> None:
        super().__init__(
            workflow_template=copy.deepcopy(_FLUX_KONTEXT_WORKFLOW_TEMPLATE),
            api_url=api_url,
            node_text_id="6",
            node_image_id="11",
            node_seed_id="25",
            output_node_id="9",
        )

    def generate(self, request: ImageRequest) -> ImageResult:
        prompt = request.prompt
        if _KONTEXT_PRESERVATION_CLAUSE not in prompt:
            prompt = f"{prompt.rstrip('. ')}. {_KONTEXT_PRESERVATION_CLAUSE}."
        patched = request.model_copy(update={"prompt": prompt})
        return super().generate(patched)

    @staticmethod
    def build_location_prompt(location_description: str) -> str:
        """
        Build a Kontext-style prompt for a location change.

        Args:
            location_description: Plain-language description of the new location.

        Returns:
            Kontext prompt string ready to pass as request.prompt.
        """
        return (
            f"Change the background to {location_description} "
            f"{_KONTEXT_PRESERVATION_CLAUSE}."
        )
