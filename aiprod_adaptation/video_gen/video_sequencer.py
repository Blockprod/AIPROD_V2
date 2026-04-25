from __future__ import annotations

import structlog

from aiprod_adaptation.image_gen.image_request import StoryboardOutput
from aiprod_adaptation.models.schema import AIPRODOutput, Shot
from aiprod_adaptation.video_gen.video_adapter import VideoAdapter
from aiprod_adaptation.video_gen.video_request import (
    VideoClipResult,
    VideoOutput,
    VideoRequest,
)

logger = structlog.get_logger(__name__)


def _shot_map(output: AIPRODOutput) -> dict[str, Shot]:
    return {shot.shot_id: shot for ep in output.episodes for shot in ep.shots}


def _prompt_image_source(image_url: str, image_b64: str) -> str:
    if image_url:
        return image_url
    if image_b64:
        return f"data:image/png;base64,{image_b64}"
    return ""


class VideoSequencer:
    def __init__(
        self,
        adapter: VideoAdapter,
        base_seed: int | None = None,
    ) -> None:
        self._adapter = adapter
        self._base_seed = base_seed

    def build_requests(
        self,
        storyboard: StoryboardOutput,
        output: AIPRODOutput,
    ) -> list[VideoRequest]:
        shots = _shot_map(output)
        requests: list[VideoRequest] = []
        for i, frame in enumerate(storyboard.frames):
            shot = shots.get(frame.shot_id)
            if shot is None:
                raise ValueError(
                    f"Storyboard frame references unknown shot_id: {frame.shot_id}"
                )
            requests.append(
                VideoRequest(
                    shot_id=frame.shot_id,
                    scene_id=shot.scene_id,
                    image_url=_prompt_image_source(frame.image_url, frame.image_b64),
                    prompt=shot.prompt,
                    action=shot.action,
                    duration_sec=shot.duration_sec,
                    seed=self._base_seed + i if self._base_seed is not None else None,
                )
            )
        return requests

    def generate(
        self,
        storyboard: StoryboardOutput,
        output: AIPRODOutput,
    ) -> VideoOutput:
        requests = self.build_requests(storyboard, output)
        clips: list[VideoClipResult] = []

        for i, request in enumerate(requests):
            # Intra-scene last_frame chaining: inject previous clip's last_frame
            if i > 0 and requests[i - 1].scene_id == request.scene_id:
                prev_last = clips[i - 1].last_frame_url
                if prev_last:
                    request = request.model_copy(update={"last_frame_hint_url": prev_last})
            try:
                clip = self._adapter.generate(request)
            except Exception as exc:
                logger.warning(
                    "video_generation_failed",
                    shot_id=request.shot_id,
                    scene_id=request.scene_id,
                    error=str(exc),
                )
                clip = VideoClipResult(
                    shot_id=request.shot_id,
                    video_url="error://generation-failed",
                    duration_sec=request.duration_sec,
                    model_used="error",
                    latency_ms=0,
                )
            clips.append(clip)

        return VideoOutput(
            title=storyboard.title,
            clips=clips,
            total_shots=len(requests),
            generated=sum(1 for c in clips if c.model_used != "error"),
        )
