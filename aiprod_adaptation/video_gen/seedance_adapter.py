from __future__ import annotations

import os
import time

from aiprod_adaptation.video_gen.video_adapter import VideoAdapter
from aiprod_adaptation.video_gen.video_request import VideoClipResult, VideoRequest

_SEEDANCE_COST_PER_SEC: dict[str, float] = {
    "480p": 0.08,
    "720p": 0.18,
    "1080p": 0.45,
}


class SeedanceAdapter(VideoAdapter):
    """Seedance 2.0 (ByteDance) video adapter via Replicate.

    Requires: REPLICATE_API_TOKEN env var
    Excluded from mypy and CI — integration only.
    Docs: https://replicate.com/bytedance/seedance-2.0

    Routing modes:
      - character_reference_urls present → reference_images mode (character consistency)
      - image_url present              → image-to-video mode (first frame anchor)
    Note: reference_images and first/last frame images cannot be combined (Seedance 2.0 API limit).
    """

    MODEL: str = "bytedance/seedance-2.0"

    def __init__(
        self,
        api_token: str | None = None,
        resolution: str = "720p",
    ) -> None:
        self._token = api_token or os.environ.get("REPLICATE_API_TOKEN", "")
        self._resolution = resolution

    def generate(self, request: VideoRequest) -> VideoClipResult:
        import replicate

        t0 = time.monotonic()

        input_params: dict = {
            "prompt": request.prompt,
            "duration": request.duration_sec,
            "resolution": self._resolution,
            "aspect_ratio": "16:9",
            "generate_audio": False,
        }

        if request.seed is not None:
            input_params["seed"] = request.seed

        if request.character_reference_urls:
            # Reference mode: character consistency via reference_images.
            # Cannot be combined with first/last frame — characters take priority.
            input_params["reference_images"] = request.character_reference_urls
        elif request.image_url:
            # I2V mode: animate from location master plate (first frame).
            input_params["image"] = request.image_url
            if request.last_frame_hint_url:
                input_params["last_frame_image"] = request.last_frame_hint_url

        out = replicate.run(self.MODEL, input=input_params)
        video_url = str(out)

        latency = int((time.monotonic() - t0) * 1000)
        cost = _SEEDANCE_COST_PER_SEC.get(self._resolution, 0.18) * request.duration_sec

        return VideoClipResult(
            shot_id=request.shot_id,
            video_url=video_url,
            duration_sec=request.duration_sec,
            model_used=self.MODEL,
            latency_ms=latency,
            cost_usd=cost,
        )
