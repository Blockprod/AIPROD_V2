from __future__ import annotations

import base64
import io
import os
import time
from typing import Any

from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult

# FLUX.1-schnell: fast distilled model, 4 steps, no guidance needed.
# FLUX.1-dev: higher quality, needs HF Pro for serverless inference.
DEFAULT_HF_MODEL = "black-forest-labs/FLUX.1-schnell"

# FLUX.1-schnell: distilled — 4 steps, no CFG, ignore negative prompt.
_SCHNELL_MAX_STEPS = 4
_SCHNELL_GUIDANCE = 0.0

# SDXL-based models (Juggernaut XL, RealVisXL…): need 1024×1024 native res,
# more steps, CFG ~7, and benefit strongly from negative prompts.
_SDXL_MODELS = (
    "juggernaut",
    "realvisxl",
    "dreamshaper-xl",
    "sdxl",
    "xl-1.0",
    "xl_base",
)
_SDXL_STEPS = 35
_SDXL_GUIDANCE = 7.0
_SDXL_NATIVE_SIZE = 1024  # SDXL native square; we'll keep aspect ratio

# Strong negative prompt for SDXL photorealistic portraits — has major impact.
_SDXL_NEGATIVE = (
    "cartoon, anime, illustration, painting, 3D render, CGI, digital art, "
    "plastic skin, wax figure, mannequin, doll, airbrushed, smooth skin, "
    "deformed, asymmetric face, bad anatomy, extra limbs, missing limbs, "
    "blurry, out of focus, watermark, text, logo, signature, "
    "oversaturated, flat lighting, stock photo, ugly, bad proportions"
)

# FLUX.1-dev (guidance-distilled): 20-50 steps, guidance ~3.5, no neg prompt.
_FLUX_DEV_STEPS = 28
_FLUX_DEV_GUIDANCE = 3.5


def _build_hf_client(token: str) -> Any:
    from huggingface_hub import InferenceClient

    return InferenceClient(token=token)


def _is_sdxl(model: str) -> bool:
    return any(k in model.lower() for k in _SDXL_MODELS)


def _is_flux_dev(model: str) -> bool:
    return "flux" in model.lower() and "dev" in model.lower()


def _sdxl_size(width: int, height: int) -> tuple[int, int]:
    """Scale to SDXL native ~1024 while preserving aspect ratio."""
    ratio = width / height
    if ratio >= 1.0:
        return 1024, max(512, int(1024 / ratio // 64) * 64)
    return max(512, int(1024 * ratio // 64) * 64), 1024


class HuggingFaceImageAdapter(ImageAdapter):
    """Free image generation via HuggingFace Inference API (FLUX.1-schnell by default).

    Requirements:
        pip install huggingface_hub pillow
        HF_TOKEN environment variable (read access, free account sufficient)

    Optional environment variables:
        HF_IMAGE_MODEL   HuggingFace model ID (default: black-forest-labs/FLUX.1-schnell)

    Rate limits:
        Free tier: ~1 req/s, ~1000 req/day. Sufficient for pilot runs.
        No cost for FLUX.1-schnell on serverless inference (free tier).

    Quality:
        FLUX.1-schnell quality is excellent for storyboard validation.
        Step count is capped at 4 for schnell (distilled model architecture).
        Negative prompts are not forwarded (FLUX.1-schnell ignores them).
    """

    MODEL_NAME = "huggingface"

    def generate(self, request: ImageRequest) -> ImageResult:
        token = os.environ.get("HF_TOKEN", "")
        if not token:
            raise OSError(
                "HuggingFaceImageAdapter: HF_TOKEN environment variable is not set. "
                "Generate a free token at https://huggingface.co/settings/tokens"
            )

        model = os.environ.get("HF_IMAGE_MODEL", DEFAULT_HF_MODEL)
        client = _build_hf_client(token)

        # FLUX.1-schnell is a distilled model: 4 steps, no classifier-free guidance.
        # For other models (SDXL, FLUX.1-dev), use the request values.
        is_schnell = "schnell" in model.lower()
        num_steps = _SCHNELL_MAX_STEPS if is_schnell else min(request.num_steps, 50)
        guidance = _SCHNELL_GUIDANCE if is_schnell else request.guidance_scale

        kwargs: dict[str, Any] = {
            "num_inference_steps": num_steps,
            "width": request.width,
            "height": request.height,
        }
        if not is_schnell:
            kwargs["guidance_scale"] = guidance
        if request.seed is not None:
            kwargs["seed"] = request.seed

        t0 = time.monotonic()
        pil_image = client.text_to_image(
            prompt=request.prompt,
            model=model,
            **kwargs,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        # Convert PIL Image → base64 PNG
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        return ImageResult(
            shot_id=request.shot_id,
            image_url="",
            image_b64=b64,
            model_used=model,
            latency_ms=latency_ms,
            cost_usd=0.0,  # Free tier
        )
