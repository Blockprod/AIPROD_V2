"""
SmartVideoRouter — routes VideoRequests to Runway, Kling 3.0, or Seedance 2.0.

Routing priority:
  1. character_reference_urls present → Seedance 2.0 (character consistency via reference_images)
  2. duration_sec <= threshold        → Runway (short atmospheric shots)
  3. duration_sec > threshold         → Kling 3.0 (long motion shots, professional camera control)
"""

from __future__ import annotations

from aiprod_adaptation.video_gen.video_adapter import VideoAdapter
from aiprod_adaptation.video_gen.video_request import VideoClipResult, VideoRequest

DEFAULT_THRESHOLD_SEC = 5


class SmartVideoRouter(VideoAdapter):
    """
    Route requests to Runway, Kling 3.0, or Seedance 2.0 based on content and duration.

    - character_reference_urls present → Seedance 2.0
    - short shots (≤ threshold_sec), no characters → Runway
    - long shots (> threshold_sec), no characters  → Kling 3.0
    """

    def __init__(
        self,
        runway_adapter: VideoAdapter,
        kling_adapter: VideoAdapter,
        seedance_adapter: VideoAdapter | None = None,
        threshold_sec: int = DEFAULT_THRESHOLD_SEC,
    ) -> None:
        self._runway = runway_adapter
        self._kling = kling_adapter
        self._seedance = seedance_adapter
        self._threshold = threshold_sec

    def generate(self, request: VideoRequest) -> VideoClipResult:
        if self._seedance is not None and request.character_reference_urls:
            return self._seedance.generate(request)
        if request.duration_sec <= self._threshold:
            return self._runway.generate(request)
        return self._kling.generate(request)
