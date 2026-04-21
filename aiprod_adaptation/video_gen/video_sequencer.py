from __future__ import annotations

from typing import Dict, List, Optional

from aiprod_adaptation.image_gen.image_request import StoryboardOutput
from aiprod_adaptation.models.schema import AIPRODOutput, Shot
from aiprod_adaptation.video_gen.video_adapter import VideoAdapter
from aiprod_adaptation.video_gen.video_request import (
    VideoClipResult,
    VideoOutput,
    VideoRequest,
)


def _shot_map(output: AIPRODOutput) -> Dict[str, Shot]:
    return {shot.shot_id: shot for ep in output.episodes for shot in ep.shots}


class VideoSequencer:
    def __init__(
        self,
        adapter: VideoAdapter,
        base_seed: Optional[int] = None,
    ) -> None:
        self._adapter = adapter
        self._base_seed = base_seed

    def build_requests(
        self,
        storyboard: StoryboardOutput,
        output: AIPRODOutput,
    ) -> List[VideoRequest]:
        shots = _shot_map(output)
        requests: List[VideoRequest] = []
        for i, image in enumerate(storyboard.images):
            shot = shots.get(image.shot_id)
            duration = shot.duration_sec if shot is not None else 4
            requests.append(
                VideoRequest(
                    shot_id=image.shot_id,
                    scene_id=shot.scene_id if shot is not None else "",
                    image_url=image.image_url,
                    prompt=shot.prompt if shot is not None else "",
                    duration_sec=duration,
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
        clips: List[VideoClipResult] = []

        for i, request in enumerate(requests):
            # Intra-scene last_frame chaining: inject previous clip's last_frame
            if i > 0 and requests[i - 1].scene_id == request.scene_id:
                prev_last = clips[i - 1].last_frame_url
                if prev_last:
                    request = request.model_copy(update={"last_frame_hint_url": prev_last})
            try:
                clip = self._adapter.generate(request)
            except Exception:
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
