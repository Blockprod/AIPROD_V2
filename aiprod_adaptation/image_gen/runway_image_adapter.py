from __future__ import annotations

import os
import time

from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult

DEFAULT_MODEL = "gen4_image"


def _runway_image_ratio(width: int, height: int, model: str = DEFAULT_MODEL) -> str:
    if model == "gemini_2.5_flash":
        if width > height:
            return "1536:672"
        if height > width:
            return "832:1248"
        return "1024:1024"
    if width > height:
        return "1280:720"
    if height > width:
        return "720:1280"
    return "1024:1024"


class RunwayImageAdapter(ImageAdapter):
    """Production adapter: Runway text-to-image."""

    MODEL_NAME = "runway-image"

    def __init__(
        self,
        api_token: str | None = None,
        model: str | None = None,
    ) -> None:
        self._token = api_token or os.environ.get("RUNWAY_API_TOKEN", "")
        self._model = model or os.environ.get("RUNWAY_IMAGE_MODEL", DEFAULT_MODEL)

    def generate(self, request: ImageRequest) -> ImageResult:
        if not self._token:
            raise ValueError("RUNWAY_API_TOKEN is required for Runway image generation.")

        import runwayml

        client = runwayml.RunwayML(api_key=self._token)
        t0 = time.monotonic()
        task = client.text_to_image.create(
            model=self._model,
            prompt_text=request.prompt,
            ratio=_runway_image_ratio(request.width, request.height, self._model),
            seed=request.seed,
        )
        result = task.wait_for_task_output()
        latency_ms = int((time.monotonic() - t0) * 1000)

        return ImageResult(
            shot_id=request.shot_id,
            image_url=result.output[0],
            image_b64="",
            model_used=self._model,
            latency_ms=latency_ms,
        )