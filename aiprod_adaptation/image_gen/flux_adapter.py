from __future__ import annotations

import os
import time
from typing import Any, cast

from aiprod_adaptation.adapters.errors import AdapterError, AdapterFailureCategory
from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult


class FluxAdapter(ImageAdapter):
    """Connects to a local Flux / A1111-compatible REST server.

    Requires: FLUX_API_URL env var (default: http://localhost:7860)
    Excluded from mypy and CI — integration only.
    """

    def __init__(self, api_url: str | None = None) -> None:
        self._url = api_url or os.environ.get("FLUX_API_URL", "http://localhost:7860")

    def generate(self, request: ImageRequest) -> ImageResult:
        import requests

        t0 = time.monotonic()
        payload = {
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "width": request.width,
            "height": request.height,
            "num_inference_steps": request.num_steps,
            "guidance_scale": request.guidance_scale,
            "seed": request.seed if request.seed is not None else -1,
        }
        if request.reference_image_url:
            payload["alwayson_scripts"] = {
                "IP-Adapter": {
                    "args": [{"image": request.reference_image_url, "weight": 0.6, "enabled": True}]
                }
            }
        resp = requests.post(
            f"{self._url}/sdapi/v1/txt2img", json=cast(Any, payload), timeout=120
        )
        resp.raise_for_status()
        try:
            data = resp.json()
            images = data["images"]
            image_b64 = images[0]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AdapterError(
                "Flux/A1111 response is malformed or contains no image.", provider="flux",
                category=AdapterFailureCategory.MALFORMED_RESPONSE,
                request_id=request.shot_id,
            ) from exc
        if not isinstance(image_b64, str) or not image_b64:
            raise AdapterError(
                "Flux/A1111 returned an empty image.", provider="flux",
                category=AdapterFailureCategory.MALFORMED_RESPONSE,
                request_id=request.shot_id,
            )
        latency = int((time.monotonic() - t0) * 1000)
        return ImageResult(
            shot_id=request.shot_id,
            image_url="",
            image_b64=image_b64,
            model_used="flux.1",
            latency_ms=latency,
        )
