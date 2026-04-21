from __future__ import annotations

import os
import time

from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult


class ReplicateAdapter(ImageAdapter):
    """Connects to Replicate.com — black-forest-labs/flux-schnell by default.

    Requires: REPLICATE_API_TOKEN env var
    Excluded from mypy and CI — integration only.
    """

    MODEL: str = "black-forest-labs/flux-schnell"

    def __init__(self, api_token: str | None = None) -> None:
        self._token = api_token or os.environ.get("REPLICATE_API_TOKEN", "")

    def generate(self, request: ImageRequest) -> ImageResult:
        import replicate as _replicate  # type: ignore[import-untyped]

        t0 = time.monotonic()
        output = _replicate.run(
            self.MODEL,
            input={
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "width": request.width,
                "height": request.height,
                "num_inference_steps": request.num_steps,
                "guidance": request.guidance_scale,
                "seed": request.seed,
                "output_format": "webp",
            },
        )
        latency = int((time.monotonic() - t0) * 1000)
        return ImageResult(
            shot_id=request.shot_id,
            image_url=str(output[0]),
            image_b64="",
            model_used=self.MODEL,
            latency_ms=latency,
        )
