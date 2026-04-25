from __future__ import annotations

import os
import time

from aiprod_adaptation.post_prod.audio_adapter import AudioAdapter
from aiprod_adaptation.post_prod.audio_request import AudioRequest, AudioResult

DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_VOICE = "Rachel"


class RunwayTTSAdapter(AudioAdapter):
    """Production adapter: Runway text-to-speech."""

    MODEL_NAME = "runway-tts"

    def __init__(
        self,
        api_token: str | None = None,
        model: str | None = None,
        voice: str | None = None,
    ) -> None:
        self._token = api_token or os.environ.get("RUNWAY_API_TOKEN", "")
        self._model = model or os.environ.get("RUNWAY_AUDIO_MODEL", DEFAULT_MODEL)
        self._voice = voice or os.environ.get("RUNWAY_TTS_VOICE", DEFAULT_VOICE)

    def generate(self, request: AudioRequest) -> AudioResult:
        if not self._token:
            raise ValueError("RUNWAY_API_TOKEN is required for Runway text-to-speech.")

        import runwayml

        client = runwayml.RunwayML(api_key=self._token)
        voice = request.voice_id if request.voice_id != "default" else self._voice

        t0 = time.monotonic()
        task = client.text_to_speech.create(
            model=self._model,
            prompt_text=request.text,
            voice={"type": "runway-preset", "preset_id": voice},
        )
        result = task.wait_for_task_output()
        latency_ms = int((time.monotonic() - t0) * 1000)

        return AudioResult(
            shot_id=request.shot_id,
            audio_url=result.output[0],
            audio_b64="",
            duration_sec=request.duration_hint_sec,
            model_used=self._model,
            latency_ms=latency_ms,
        )