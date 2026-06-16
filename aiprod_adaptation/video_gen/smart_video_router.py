"""
SmartVideoRouter — routes VideoRequests to Runway, Kling 3.0, or Seedance 2.0.

Routing priority:
  1. character_reference_urls present → Seedance 2.0 (character consistency via reference_images)
  2. duration_sec <= threshold        → Runway (short atmospheric shots)
  3. duration_sec > threshold         → Kling 3.0 (long motion shots, professional camera control)
"""

from __future__ import annotations

from aiprod_adaptation.adapters.errors import AdapterError
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
        candidates: list[VideoAdapter]
        if request.character_reference_urls:
            candidates = [adapter for adapter in (self._seedance,) if adapter is not None]
        elif request.duration_sec <= self._threshold:
            candidates = [self._runway, self._kling]
        else:
            candidates = [self._kling, self._runway]
        if not candidates:
            raise RuntimeError("No compatible video provider is configured for this request.")

        failures: list[AdapterError] = []
        for index, adapter in enumerate(candidates):
            try:
                return adapter.generate(request)
            except AdapterError as exc:
                failures.append(exc)
                if not exc.retryable or index == len(candidates) - 1:
                    break
        detail = "; ".join(f"{failure.provider}:{failure.category}" for failure in failures)
        raise RuntimeError(f"All compatible video providers failed: {detail}") from failures[-1]
