from __future__ import annotations

import os
import time
from typing import Literal

from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult

DEFAULT_MODEL = "gpt-image-1-mini"
DEFAULT_QUALITY = "low"
OpenAIImageQuality = Literal["low", "medium", "high", "auto"]

_OPENAI_IMAGE_COST_USD: dict[str, dict[str, dict[str, float]]] = {
    "gpt-image-2": {
        "low": {"1024x1024": 0.006, "1536x1024": 0.005, "1024x1536": 0.005},
        "medium": {"1024x1024": 0.053, "1536x1024": 0.041, "1024x1536": 0.041},
        "high": {"1024x1024": 0.211, "1536x1024": 0.165, "1024x1536": 0.165},
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


def _build_openai_client(api_key: str) -> object:
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

    return _OPENAI_IMAGE_COST_USD.get(model, {}).get(quality, {}).get(size, 0.0)


class OpenAIImageAdapter(ImageAdapter):
    """Production adapter: OpenAI image generation.

    Requires:
        pip install openai
        OPENAI_API_KEY environment variable

    Optional environment variables:
        OPENAI_IMAGE_MODEL   Defaults to gpt-image-1-mini for low-cost smoke tests.
        OPENAI_IMAGE_QUALITY Defaults to low.

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
        self._quality: OpenAIImageQuality = quality or os.environ.get(
            "OPENAI_IMAGE_QUALITY",
            DEFAULT_QUALITY,
        )

    def generate(self, request: ImageRequest) -> ImageResult:
        client = _build_openai_client(self._api_key)
        t0 = time.monotonic()
        size = _openai_image_size(request.width, request.height)
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
