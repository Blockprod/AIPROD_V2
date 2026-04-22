"""
OpenAITTSAdapter — production TTS adapter using the OpenAI TTS API (tts-1-hd).

Requires:
    pip install openai
    OPENAI_API_KEY environment variable
"""

from __future__ import annotations

import base64
import os
import time

from aiprod_adaptation.post_prod.audio_adapter import AudioAdapter
from aiprod_adaptation.post_prod.audio_request import AudioRequest, AudioResult

DEFAULT_VOICE = "alloy"
DEFAULT_MODEL = "tts-1-hd"


class OpenAITTSAdapter(AudioAdapter):
    """Production adapter: OpenAI TTS — text → MP3 bytes."""

    MODEL_NAME = "openai-tts"

    def __init__(
        self,
        api_key: str | None = None,
        voice: str = DEFAULT_VOICE,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._voice = voice
        self._model = model

    def generate(self, request: AudioRequest) -> AudioResult:
        from openai import OpenAI

        client = OpenAI(api_key=self._api_key)
        voice = request.voice_id if request.voice_id != "default" else self._voice

        t0 = time.monotonic()
        response = client.audio.speech.create(
            model=self._model,
            voice=voice,
            input=request.text,
            response_format="mp3",
        )
        audio_bytes = response.content
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
