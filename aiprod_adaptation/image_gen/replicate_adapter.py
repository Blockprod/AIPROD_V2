from __future__ import annotations

import os
import time
from typing import Any

from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult

SCHNELL_MODEL: str = "black-forest-labs/flux-schnell"
ULTRA_MODEL: str = "black-forest-labs/flux-1.1-pro-ultra"
# No version suffix — official docs show "nightmareai/real-esrgan" directly
UPSCALE_MODEL: str = "nightmareai/real-esrgan"

_ULTRA_PREFIXES = ("black-forest-labs/flux-1.1-pro-ultra", "black-forest-labs/flux-pro")

# Portrait shot types — prompt begins with these framing labels (from _SHOT_TYPE_LABELS)
_PORTRAIT_PROMPT_PREFIXES = ("Close-up portrait", "Extreme close-up portrait")

# FLUX.1-dev is a distilled CFG model: guidance 3.5 is optimal; negative_prompt is ineffective
_FLUX_DEV_GUIDANCE = 3.5


def _is_ultra(model: str) -> bool:
    return any(model.startswith(p) for p in _ULTRA_PREFIXES)


def _is_flux_dev(model: str) -> bool:
    return "flux" in model.lower() and "dev" in model.lower()


def _is_schnell(model: str) -> bool:
    return "schnell" in model.lower()


def _is_http_url(value: str) -> bool:
    """Return True only for HTTP(S) URLs — Replicate rejects data URIs."""
    return value.startswith("http://") or value.startswith("https://")


def _is_local_path(value: str) -> bool:
    """Return True if value is an existing local filesystem path."""
    if not value or value.startswith("http") or value.startswith("data:"):
        return False
    from pathlib import Path
    return Path(value).exists()


def _aspect_ratio_str(portrait: bool) -> str:
    return "2:3" if portrait else "16:9"


def _is_portrait(prompt: str) -> bool:
    return any(prompt.startswith(p) for p in _PORTRAIT_PROMPT_PREFIXES)


def _build_input(model: str, request: ImageRequest) -> dict[str, Any]:
    """Build model-specific input dict for Replicate API."""
    portrait = _is_portrait(request.prompt)
    if _is_ultra(model):
        data: dict[str, Any] = {
            "prompt": request.prompt,
            "aspect_ratio": _aspect_ratio_str(portrait),
            "output_format": "png",
            "output_quality": 100,
            "safety_tolerance": 6,
            "raw": True,   # raw photographic mode — less stylised, more cinema
        }
        if request.seed is not None:
            data["seed"] = request.seed
        # Character reference via HTTP(S) URL — subtle guidance (0.15)
        if _is_http_url(request.reference_image_url):
            data["image_prompt"] = request.reference_image_url
            data["image_prompt_strength"] = 0.15
        return data
    if _is_schnell(model):
        # schnell: aspect_ratio API (not width/height), max 4 steps, no guidance, no negative
        data = {
            "prompt": request.prompt,
            "aspect_ratio": _aspect_ratio_str(portrait),
            "num_inference_steps": 4,
            "output_format": "webp",
        }
        if request.seed is not None:
            data["seed"] = request.seed
        return data
    # flux-dev / other FLUX variants
    # Portrait close-ups: 768×1024 (3:4 vertical). Wide/medium: 1024×576 (16:9).
    width = 768 if portrait else request.width
    height = 1024 if portrait else request.height
    flux_dev = _is_flux_dev(model)
    guidance = _FLUX_DEV_GUIDANCE if flux_dev else request.guidance_scale
    data = {
        "prompt": request.prompt,
        "width": width,
        "height": height,
        "num_inference_steps": request.num_steps,
        "guidance": guidance,
        "output_format": "webp",
    }
    if not flux_dev:
        data["negative_prompt"] = request.negative_prompt
    if request.seed is not None:
        data["seed"] = request.seed
    if _is_http_url(request.reference_image_url):
        data["image"] = request.reference_image_url
    return data


def _extract_url(output: Any) -> str:
    """Extract image URL from replicate output — handles list or single FileOutput."""
    first = output[0] if isinstance(output, (list, tuple)) and output else output
    if first is None:
        return ""
    url_attr = getattr(first, "url", None)
    if url_attr is not None:
        return str(url_attr)
    return str(first)


def _download_to_b64(url: str) -> str:
    """Download ephemeral Replicate URL and return base64-encoded PNG bytes.

    Replicate delivery URLs expire in minutes — must download immediately.
    """
    import base64
    import urllib.request

    with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310
        raw = resp.read()
    return base64.b64encode(raw).decode("ascii")


def _upscale_to_4k(client: Any, image_b64: str) -> str:
    """Real AI upscale 2× via Real-ESRGAN per official Replicate docs.

    Input images are 2752×1536 (height > 1440p max). Pre-downscale to 1440px
    height first, then 2× upscale → ~5160×2880 (5K+).
    Passes base64 data URI as input (supported per official docs).
    Output read via output[0].read() per official docs.
    """
    import base64
    import io

    from PIL import Image as _PILImage

    raw = base64.b64decode(image_b64)
    img = _PILImage.open(io.BytesIO(raw))
    w, h = img.size
    # Pre-downscale to fit within Real-ESRGAN GPU pixel budget.
    # Hardware limit: 2,096,704 px but GPU needs ~3.8 GiB at 2M px → CUDA OOM.
    # 1,440,000 px leaves enough VRAM headroom (~2.8 GiB).
    max_upscale_pixels = 1_440_000  # ~1440×1000 — safe on 14 GiB GPU with other allocations
    if w * h > max_upscale_pixels:
        ratio = (max_upscale_pixels / (w * h)) ** 0.5
        img = img.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), _PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw = buf.getvalue()
    b64_input = base64.b64encode(raw).decode("ascii")
    output = client.run(
        UPSCALE_MODEL,
        input={
            "image": f"data:image/png;base64,{b64_input}",
            "scale": 2,
            "face_enhance": False,
        },
    )
    # output.read() — single FileOutput per official docs (JS: output.url() / output)
    # Guard against SDK returning a list for backward compat
    fo = output[0] if isinstance(output, (list, tuple)) else output
    return base64.b64encode(fo.read()).decode("ascii")


DEV_MODEL: str = "black-forest-labs/flux-dev"

# Approximate Replicate billing per prediction (USD).
# Source: https://replicate.com/pricing (as of 2026-04)
_REPLICATE_IMAGE_COST_USD: dict[str, float] = {
    "black-forest-labs/flux-1.1-pro-ultra": 0.06,
    "black-forest-labs/flux-pro": 0.055,
    "black-forest-labs/flux-dev": 0.003,
    "black-forest-labs/flux-schnell": 0.003,
    "nightmareai/real-esrgan": 0.002,
}


def _estimate_replicate_cost(model: str, upscaled: bool = False) -> float:
    """Return estimated cost in USD for one Replicate prediction."""
    base = _REPLICATE_IMAGE_COST_USD.get(model, 0.0)
    upscale_cost = _REPLICATE_IMAGE_COST_USD.get(UPSCALE_MODEL, 0.0) if upscaled else 0.0
    return base + upscale_cost


class ReplicateAdapter(ImageAdapter):
    """Connects to Replicate.com with automatic portrait/wide-shot model routing.

    Portrait shots (close-up / extreme close-up):
        → REPLICATE_PORTRAIT_MODEL  (default: flux-1.1-pro-ultra)
          raw=True photographic mode, 2:3 aspect ratio, ~$0.06/image

    Wide / medium shots:
        → REPLICATE_WIDE_MODEL  (default: flux-dev)
          guidance 3.5, 1024×576, ~$0.003/image

    Override both with REPLICATE_IMAGE_MODEL (forces a single model for all shots).

    Requires: REPLICATE_API_TOKEN env var
    Excluded from mypy and CI — integration only.
    """

    DEFAULT_PORTRAIT_MODEL: str = ULTRA_MODEL
    DEFAULT_WIDE_MODEL: str = DEV_MODEL

    def __init__(
        self,
        api_token: str | None = None,
        model: str | None = None,
        portrait_model: str | None = None,
        wide_model: str | None = None,
    ) -> None:
        self._token = api_token or os.environ.get("REPLICATE_API_TOKEN", "")
        # If a single override model is set (legacy / env), use it for everything.
        single = model or os.environ.get("REPLICATE_IMAGE_MODEL", "")
        if single:
            self._portrait_model = single
            self._wide_model = single
        else:
            self._portrait_model = portrait_model or os.environ.get(
                "REPLICATE_PORTRAIT_MODEL", self.DEFAULT_PORTRAIT_MODEL
            )
            self._wide_model = wide_model or os.environ.get(
                "REPLICATE_WIDE_MODEL", self.DEFAULT_WIDE_MODEL
            )

    def _select_model(self, request: ImageRequest) -> str:
        """Route portrait close-ups to the high-quality model; wide/medium to the fast model."""
        return self._portrait_model if _is_portrait(request.prompt) else self._wide_model

    def generate(self, request: ImageRequest) -> ImageResult:
        import replicate as _replicate

        model = self._select_model(request)
        client = _replicate.Client(api_token=self._token)
        input_data = _build_input(model, request)

        # Retry on 429 with exponential backoff — Replicate throttles new/low-credit accounts
        max_retries = 5
        base_wait = 12  # seconds — Replicate rate limit window is ~10s
        upscale = os.environ.get("REPLICATE_UPSCALE", "").lower() in ("1", "true", "yes")
        # Open local composition reference — must stay open during client.run() call
        # per official docs: open("file.jpg", "rb") is the correct approach
        _local_fh = None
        if _is_local_path(request.reference_image_url) and _is_ultra(model):
            _local_fh = open(request.reference_image_url, "rb")  # noqa: WPS515, SIM115
            input_data["image_prompt"] = _local_fh
            input_data["image_prompt_strength"] = 0.50
        last_exc: Exception | None = None
        try:
            for attempt in range(max_retries):
                try:
                    t0 = time.monotonic()
                    output = client.run(model, input=input_data)
                    image_url = _extract_url(output)
                    # Replicate delivery URLs are ephemeral (expire in minutes).
                    # Download immediately and store as base64 so the result is permanent.
                    image_b64 = _download_to_b64(image_url) if _is_http_url(image_url) else ""
                    # Real AI upscale to 5K+ via Real-ESRGAN (REPLICATE_UPSCALE=true)
                    if upscale and image_b64:
                        image_b64 = _upscale_to_4k(client, image_b64)
                    latency = int((time.monotonic() - t0) * 1000)
                    return ImageResult(
                        shot_id=request.shot_id,
                        image_url=image_url,
                        image_b64=image_b64,
                        model_used=model,
                        latency_ms=latency,
                        cost_usd=_estimate_replicate_cost(model, upscale and bool(image_b64)),
                    )
                except Exception as exc:
                    last_exc = exc
                    if "429" not in str(exc) and "throttled" not in str(exc).lower():
                        raise
                    wait = base_wait * (2 ** attempt)
                    time.sleep(wait)
            raise RuntimeError(
                f"Replicate 429 after {max_retries} retries for {request.shot_id}"
            ) from last_exc
        finally:
            if _local_fh is not None:
                _local_fh.close()
