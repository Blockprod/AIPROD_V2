from __future__ import annotations

import os
import time

from aiprod_adaptation.video_gen.video_adapter import VideoAdapter
from aiprod_adaptation.video_gen.video_request import VideoClipResult, VideoRequest


class RunwayAdapter(VideoAdapter):
    """Runway Gen-3 Alpha Turbo image-to-video adapter.

    Requires: RUNWAY_API_TOKEN env var
    Excluded from mypy and CI — integration only.
    Docs: https://docs.dev.runwayml.com/
    """

    MODEL: str = "gen3a_turbo"

    def __init__(self, api_token: str | None = None) -> None:
        self._token = api_token or os.environ.get("RUNWAY_API_TOKEN", "")

    def generate(self, request: VideoRequest) -> VideoClipResult:
        import runwayml

        t0 = time.monotonic()
        client = runwayml.RunwayML(api_key=self._token)
        task = client.image_to_video.create(
            model=self.MODEL,
            prompt_image=request.image_url,
            prompt_text=request.prompt,
            duration=request.duration_sec,
            ratio="1280:768",
            seed=request.seed,
        )
        # Poll until complete
        import time as _time
        while task.status not in ("SUCCEEDED", "FAILED"):
            _time.sleep(2)
            task = client.tasks.retrieve(task.id)

        if task.status == "FAILED":
            raise RuntimeError(f"Runway task {task.id} failed")

        latency = int((time.monotonic() - t0) * 1000)
        return VideoClipResult(
            shot_id=request.shot_id,
            video_url=task.output[0],
            duration_sec=request.duration_sec,
            model_used=self.MODEL,
            latency_ms=latency,
        )
