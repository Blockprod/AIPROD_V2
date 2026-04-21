"""
SmartVideoRouter — routes VideoRequests to Runway or Kling based on duration.

Runway Gen-3 Alpha Turbo: optimal for short shots (duration_sec <= threshold).
Kling v2: optimal for longer shots with camera movement (duration_sec > threshold).
"""

from __future__ import annotations

from aiprod_adaptation.video_gen.video_adapter import VideoAdapter
from aiprod_adaptation.video_gen.video_request import VideoClipResult, VideoRequest

DEFAULT_THRESHOLD_SEC = 5


class SmartVideoRouter(VideoAdapter):
    """
    Route short shots (≤ threshold_sec) to runway_adapter,
    longer shots to kling_adapter.
    """

    def __init__(
        self,
        runway_adapter: VideoAdapter,
        kling_adapter: VideoAdapter,
        threshold_sec: int = DEFAULT_THRESHOLD_SEC,
    ) -> None:
        self._runway = runway_adapter
        self._kling = kling_adapter
        self._threshold = threshold_sec

    def generate(self, request: VideoRequest) -> VideoClipResult:
        if request.duration_sec <= self._threshold:
            return self._runway.generate(request)
        return self._kling.generate(request)
