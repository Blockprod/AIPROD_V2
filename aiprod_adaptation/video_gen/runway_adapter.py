from __future__ import annotations

import os
import time
from typing import Any

from aiprod_adaptation.video_gen.video_adapter import VideoAdapter
from aiprod_adaptation.video_gen.video_request import VideoClipResult, VideoRequest

_RUNWAY_VIDEO_CREDITS_PER_SECOND: dict[str, int] = {
    "gen4.5": 12,
    "gen4_turbo": 5,
    "gen4_aleph": 15,
    "gen3a_turbo": 5,
    "act_two": 5,
    "veo3": 40,
    "veo3.1": 40,
    "veo3.1_fast": 15,
}

_I2V_MODELS: frozenset[str] = frozenset(
    {"gen4.5", "gen4_turbo", "gen3a_turbo", "veo3", "veo3.1", "veo3.1_fast"}
)
_V2V_ALEPH_MODELS: frozenset[str] = frozenset({"gen4_aleph"})


def _build_runway_client(api_key: str) -> Any:
    import runwayml

    return runwayml.RunwayML(api_key=api_key)


def _estimate_runway_video_cost(model: str, duration_sec: int) -> float:
    credits_per_second = _RUNWAY_VIDEO_CREDITS_PER_SECOND.get(model)
    if credits_per_second is None:
        return 0.0
    return credits_per_second * duration_sec * 0.01


class RunwayAdapter(VideoAdapter):
    """Runway image-to-video adapter.

    Requires: RUNWAY_API_TOKEN env var
    Excluded from mypy and CI — integration only.
    Docs: https://docs.dev.runwayml.com/
    """

    DEFAULT_MODEL: str = "gen4_turbo"

    def __init__(self, api_token: str | None = None, model: str | None = None) -> None:
        self._token = (
            api_token if api_token is not None else os.environ.get("RUNWAY_API_TOKEN", "")
        )
        self._model = (
            model if model is not None else os.environ.get("RUNWAY_VIDEO_MODEL", self.DEFAULT_MODEL)
        )

    def generate(self, request: VideoRequest) -> VideoClipResult:
        if not self._token:
            raise ValueError("RUNWAY_API_TOKEN is required for Runway video generation.")
        if self._model in _V2V_ALEPH_MODELS:
            return self._generate_aleph(request)
        return self._generate_i2v(request)

    def _generate_i2v(self, request: VideoRequest) -> VideoClipResult:
        t0 = time.monotonic()
        client = _build_runway_client(self._token)

        # Guard: Runway rejects any image_url that is not https://, runway://, or data:image/
        image_url = request.image_url
        _valid_prefixes = ("https://", "runway://", "data:image/")
        valid_image = any(image_url.startswith(p) for p in _valid_prefixes)
        if not valid_image:
            url_preview = repr(image_url[:80])
            raise ValueError(
                f"RunwayAdapter: invalid prompt_image URL for shot {request.shot_id!r}: "
                f"{url_preview}. Must start with https://, runway://, or data:image/."
            )

        if self._model == "gen3a_turbo" and request.last_frame_hint_url:
            prompt_image: object = [
                {"position": "first", "uri": image_url},
                {"position": "last", "uri": request.last_frame_hint_url},
            ]
        else:
            prompt_image = image_url

        create_kwargs: dict[str, object] = {
            "model": self._model,
            "prompt_image": prompt_image,
            "prompt_text": request.prompt,
            "duration": request.duration_sec,
            "ratio": "1280:720",
        }
        if request.seed is not None:
            create_kwargs["seed"] = request.seed

        task = client.image_to_video.create(**create_kwargs)
        result = task.wait_for_task_output()

        latency = int((time.monotonic() - t0) * 1000)
        return VideoClipResult(
            shot_id=request.shot_id,
            video_url=result.output[0],
            duration_sec=request.duration_sec,
            model_used=self._model,
            latency_ms=latency,
            cost_usd=_estimate_runway_video_cost(self._model, request.duration_sec),
        )

    def _generate_aleph(self, request: VideoRequest) -> VideoClipResult:
        t0 = time.monotonic()
        client = _build_runway_client(self._token)

        create_kwargs: dict[str, object] = {
            "model": "gen4_aleph",
            "video_uri": request.image_url,
            "prompt_text": request.prompt,
        }
        if request.character_reference_urls:
            create_kwargs["references"] = [
                {"type": "image", "uri": url}
                for url in request.character_reference_urls
                if url
            ]
        if request.seed is not None:
            create_kwargs["seed"] = request.seed

        task = client.video_to_video.create(**create_kwargs)
        result = task.wait_for_task_output()

        latency = int((time.monotonic() - t0) * 1000)
        return VideoClipResult(
            shot_id=request.shot_id,
            video_url=result.output[0],
            duration_sec=request.duration_sec,
            model_used="gen4_aleph",
            latency_ms=latency,
            cost_usd=_estimate_runway_video_cost("gen4_aleph", request.duration_sec),
        )
