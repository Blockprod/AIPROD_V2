from __future__ import annotations

from abc import ABC, abstractmethod

from aiprod_adaptation.video_gen.video_request import VideoClipResult, VideoRequest


class VideoAdapter(ABC):
    @abstractmethod
    def generate(self, request: VideoRequest) -> VideoClipResult:
        """Generate a single video clip from an image + prompt. Raises on hard failure."""
        ...


class NullVideoAdapter(VideoAdapter):
    """Deterministic stub for CI — returns a placeholder clip instantly."""

    MODEL_NAME: str = "null"

    def generate(self, request: VideoRequest) -> VideoClipResult:
        return VideoClipResult(
            shot_id=request.shot_id,
            video_url=f"null://clips/{request.shot_id}.mp4",
            duration_sec=request.duration_sec,
            model_used=self.MODEL_NAME,
            latency_ms=0,
        )
