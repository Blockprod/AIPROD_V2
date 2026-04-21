"""
AudioAdapter — abstract interface + NullAudioAdapter (deterministic CI stub).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from aiprod_adaptation.post_prod.audio_request import AudioRequest, AudioResult


class AudioAdapter(ABC):
    """Abstract interface for audio/TTS generation adapters."""

    @abstractmethod
    def generate(self, request: AudioRequest) -> AudioResult:
        ...


class NullAudioAdapter(AudioAdapter):
    """Deterministic stub for testing — produces no real audio."""

    MODEL_NAME = "null"

    def generate(self, request: AudioRequest) -> AudioResult:
        return AudioResult(
            shot_id=request.shot_id,
            audio_url=f"null://audio/{request.shot_id}.mp3",
            audio_b64="",
            duration_sec=request.duration_hint_sec,
            model_used=self.MODEL_NAME,
            latency_ms=0,
        )
