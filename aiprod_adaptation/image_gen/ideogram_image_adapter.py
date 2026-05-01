from __future__ import annotations

import base64
import io
import os
import time
from typing import Any

from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult

_API_URL_V3 = "https://api.ideogram.ai/v1/ideogram-v3/generate"

# Ideogram v3 aspect ratio enum values
# For close-up portraits: 2:3 (portrait) gives the best face framing
# For cinematic wide/medium shots: 16:9 landscape
_ASPECT_PORTRAIT = "ASPECT_2_3"
_ASPECT_LANDSCAPE = "ASPECT_16_9"

# style_type=REALISTIC is Ideogram's anti-AI-look mode — trained specifically
# to produce photographic results rather than illustrated/digital-art ones.
_STYLE_REALISTIC = "REALISTIC"

# magic_prompt=OFF: we pass precise cinematic prompts, disable auto-expansion
_MAGIC_PROMPT_OFF = "OFF"

# Negative prompt for REALISTIC portraits — Ideogram v3 supports it natively
_NEGATIVE_PORTRAIT = (
    "cartoon, anime, illustration, painting, 3D render, CGI, digital art, "
    "plastic skin, wax figure, airbrushed, overly smooth, uncanny valley, "
    "deformed face, asymmetric eyes, bad anatomy, watermark, text, logo"
)

_NEGATIVE_CINEMATIC = (
    "cartoon, anime, illustration, 3D render, CGI, video game, watermark, "
    "text, logo, blurry, low quality, flat lighting"
)


def _is_portrait_prompt(prompt: str) -> bool:
    p = prompt.lower()
    return "close-up portrait" in p or "extreme close-up portrait" in p


def _download_image(url: str) -> bytes:
    import urllib.request
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
        return resp.read()


class IdeogramImageAdapter(ImageAdapter):
    """Ideogram v3 API adapter — style_type REALISTIC for photographic quality.

    Ideogram v3 REALISTIC mode is purpose-built to eliminate the AI look:
    it targets photographic / editorial output rather than digital illustration.

    Requirements:
        IDEOGRAM_API_KEY environment variable
        pip install requests  (or stdlib urllib, already used here)

    Pricing (Ideogram v3, Turbo rendering):
        ~$0.005/image on API (0.5 credits per image, API credits purchased separately)
        New accounts may receive free API credits on signup.

    Environment variables:
        IDEOGRAM_API_KEY     Required. From https://developer.ideogram.ai
        IDEOGRAM_SPEED       Rendering speed: FLASH, TURBO (default), DEFAULT, QUALITY
    """

    MODEL_NAME = "ideogram"

    def generate(self, request: ImageRequest) -> ImageResult:
        api_key = os.environ.get("IDEOGRAM_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "IdeogramImageAdapter: IDEOGRAM_API_KEY environment variable is not set. "
                "Get a free API key at https://developer.ideogram.ai"
            )

        speed = os.environ.get("IDEOGRAM_SPEED", "TURBO")
        is_portrait = _is_portrait_prompt(request.prompt)
        aspect_ratio = _ASPECT_PORTRAIT if is_portrait else _ASPECT_LANDSCAPE
        negative = _NEGATIVE_PORTRAIT if is_portrait else _NEGATIVE_CINEMATIC

        fields: dict[str, Any] = {
            "prompt": request.prompt,
            "style_type": _STYLE_REALISTIC,
            "magic_prompt": _MAGIC_PROMPT_OFF,
            "aspect_ratio": aspect_ratio,
            "negative_prompt": negative,
            "rendering_speed": speed,
        }
        if request.seed is not None:
            fields["seed"] = str(request.seed)

        t0 = time.monotonic()
        image_url = _call_ideogram_api(api_key, fields)
        image_bytes = _download_image(image_url)
        latency_ms = int((time.monotonic() - t0) * 1000)

        b64 = base64.b64encode(image_bytes).decode("ascii")

        return ImageResult(
            shot_id=request.shot_id,
            image_url="",
            image_b64=b64,
            model_used="ideogram-v3",
            latency_ms=latency_ms,
            cost_usd=0.0,
        )


def _call_ideogram_api(api_key: str, fields: dict[str, Any]) -> str:
    """POST multipart/form-data to Ideogram v3 API, return ephemeral image URL."""
    import urllib.request
    import urllib.parse
    import json

    boundary = "----AIPRODBoundary7MA4YWxkTrZu0gW"
    body_parts: list[bytes] = []
    for key, value in fields.items():
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    body_parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(body_parts)

    req = urllib.request.Request(
        _API_URL_V3,
        data=body,
        headers={
            "Api-Key": api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        payload = json.loads(resp.read())

    data = payload.get("data", [])
    if not data:
        raise RuntimeError(f"Ideogram API returned no image data: {payload}")

    return data[0]["url"]
