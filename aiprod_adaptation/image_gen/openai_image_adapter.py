from __future__ import annotations

import io
import os
import re
import time
from typing import Any, Literal, cast

from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult

DEFAULT_MODEL = "gpt-image-1-mini"
DEFAULT_QUALITY = "high"
OpenAIImageQuality = Literal["low", "medium", "high", "auto"]

_OPENAI_IMAGE_COST_USD: dict[str, dict[str, dict[str, float]]] = {
    # gpt-image-2 is aliased by OpenAI to gpt-image-1-2025-04-23 in billing.
    # Use gpt-image-1 pricing which matches actual invoiced amounts.
    "gpt-image-2": {
        "low": {"1024x1024": 0.011, "1536x1024": 0.016, "1024x1536": 0.016},
        "medium": {"1024x1024": 0.042, "1536x1024": 0.063, "1024x1536": 0.063},
        "high": {"1024x1024": 0.167, "1536x1024": 0.250, "1024x1536": 0.250},
    },
    "gpt-image-1.5": {
        "low": {"1024x1024": 0.009, "1536x1024": 0.013, "1024x1536": 0.013},
        "medium": {"1024x1024": 0.034, "1536x1024": 0.05, "1024x1536": 0.05},
        "high": {"1024x1024": 0.133, "1536x1024": 0.2, "1024x1536": 0.2},
    },
    "gpt-image-1": {
        "low": {"1024x1024": 0.011, "1536x1024": 0.016, "1024x1536": 0.016},
        "medium": {"1024x1024": 0.042, "1536x1024": 0.063, "1024x1536": 0.063},
        "high": {"1024x1024": 0.167, "1536x1024": 0.25, "1024x1536": 0.25},
    },
    "gpt-image-1-mini": {
        "low": {"1024x1024": 0.005, "1536x1024": 0.006, "1024x1536": 0.006},
        "medium": {"1024x1024": 0.011, "1536x1024": 0.015, "1024x1536": 0.015},
        "high": {"1024x1024": 0.036, "1536x1024": 0.052, "1024x1536": 0.052},
    },
}


def _build_openai_client(api_key: str) -> Any:
    from openai import OpenAI

    return OpenAI(api_key=api_key)


def _openai_image_size(width: int, height: int) -> str:
    if width > height:
        return "1536x1024"
    if height > width:
        return "1024x1536"
    return "1024x1024"


def _estimate_openai_image_cost(
    model: str,
    size: str,
    quality: OpenAIImageQuality,
) -> float:
    if quality == "auto":
        return 0.0

    # Normalize versioned aliases e.g. "gpt-image-1-2025-04-23" → "gpt-image-1"
    normalized = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model)
    pricing = _OPENAI_IMAGE_COST_USD.get(normalized) or _OPENAI_IMAGE_COST_USD.get(model, {})
    return pricing.get(quality, {}).get(size, 0.0)


class OpenAIImageAdapter(ImageAdapter):
    """Production adapter: OpenAI image generation.

    Requires:
        pip install openai
        OPENAI_API_KEY environment variable

    Optional environment variables:
        OPENAI_IMAGE_MODEL   Defaults to gpt-image-1-mini for low-cost smoke tests.
        OPENAI_IMAGE_QUALITY Defaults to high.

    Cost tracking:
        Returns an estimated cost_usd for supported GPT Image models/sizes using
        the published OpenAI pricing table. Unknown model/quality pairs fall back to 0.0.
    """

    MODEL_NAME = "openai-image"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        quality: OpenAIImageQuality | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model or os.environ.get("OPENAI_IMAGE_MODEL", DEFAULT_MODEL)
        _raw_quality = quality or os.environ.get("OPENAI_IMAGE_QUALITY", DEFAULT_QUALITY)
        self._quality = cast(OpenAIImageQuality, _raw_quality)

    def generate(self, request: ImageRequest) -> ImageResult:
        client = _build_openai_client(self._api_key)
        t0 = time.monotonic()
        size = _openai_image_size(request.width, request.height)

        # Always use images.generate — reference_image_url informs the prompt via
        # character_prepass canonical text, not via images.edit (which requires RGBA
        # and doesn't support the quality parameter).
        response = client.images.generate(
            model=self._model,
            prompt=request.prompt,
            size=size,
            quality=self._quality,
        )

        latency_ms = int((time.monotonic() - t0) * 1000)

        image_b64 = response.data[0].b64_json or ""
        image_url = response.data[0].url or ""

        return ImageResult(
            shot_id=request.shot_id,
            image_url=image_url,
            image_b64=image_b64,
            model_used=self.MODEL_NAME,
            latency_ms=latency_ms,
            cost_usd=_estimate_openai_image_cost(self._model, size, self._quality),
        )

    def generate_edit(self, request: ImageRequest, reference_rgba: bytes) -> ImageResult:
        """Generate a shot using images.edit with an RGBA character edit-base.

        The RGBA bytes must have:
          - Alpha=255 (opaque)  → character pixels to PRESERVE
          - Alpha=0 (transparent) → background to REGENERATE from prompt

        OpenAI images.edit fills the transparent region according to request.prompt
        while keeping the opaque character pixels, guaranteeing face consistency.

        Note: images.edit uses the same size/quality parameters as images.generate
        for gpt-image-2.
        """
        client = _build_openai_client(self._api_key)
        t0 = time.monotonic()
        size = _openai_image_size(request.width, request.height)

        image_file = io.BytesIO(reference_rgba)
        image_file.name = "character.png"

        response = client.images.edit(
            model=self._model,
            image=image_file,
            prompt=request.prompt,
            size=size,
            quality=self._quality,
        )

        latency_ms = int((time.monotonic() - t0) * 1000)
        image_b64 = response.data[0].b64_json or ""
        image_url = response.data[0].url or ""

        return ImageResult(
            shot_id=request.shot_id,
            image_url=image_url,
            image_b64=image_b64,
            model_used=f"{self.MODEL_NAME}-edit",
            latency_ms=latency_ms,
            cost_usd=_estimate_openai_image_cost(self._model, size, self._quality),
        )
