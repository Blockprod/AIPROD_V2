"""
ElevenLabsAdapter — production TTS adapter using the ElevenLabs v1 API.

Requires:
    pip install elevenlabs
    ELEVENLABS_API_KEY environment variable
"""

from __future__ import annotations

import os
import time

from aiprod_adaptation.post_prod.audio_adapter import AudioAdapter
from aiprod_adaptation.post_prod.audio_request import AudioRequest, AudioResult

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel (ElevenLabs)
DEFAULT_MODEL_ID = "eleven_multilingual_v2"


class ElevenLabsAdapter(AudioAdapter):
    """Production adapter: ElevenLabs TTS — text → MP3 bytes."""

    MODEL_NAME = "elevenlabs"

    def __init__(
        self,
        api_key: str | None = None,
        voice_id: str = DEFAULT_VOICE_ID,
        model_id: str = DEFAULT_MODEL_ID,
    ) -> None:
        self._api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self._voice_id = voice_id
        self._model_id = model_id

    def generate(self, request: AudioRequest) -> AudioResult:
        import base64

        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=self._api_key)
        voice_id = request.voice_id if request.voice_id != "default" else self._voice_id

        t0 = time.monotonic()
        audio_bytes = b"".join(
            client.text_to_speech.convert(
                text=request.text,
                voice_id=voice_id,
                model_id=self._model_id,
                output_format="mp3_44100_128",
            )
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        return AudioResult(
            shot_id=request.shot_id,
            audio_url="",
            audio_b64=audio_b64,
            duration_sec=request.duration_hint_sec,
            model_used=self.MODEL_NAME,
            latency_ms=latency_ms,
        )
