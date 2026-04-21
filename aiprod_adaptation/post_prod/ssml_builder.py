"""
SSMLBuilder — wraps narration text in SSML prosody tags based on shot emotion.

Compatible with: ElevenLabs v3, Azure Neural TTS.
NOT compatible with: OpenAI TTS (ignores SSML silently).
"""

from __future__ import annotations

_EMOTION_PARAMS: dict[str, dict[str, str]] = {
    "fear":     {"rate": "slow",   "pitch": "low",    "break_ms": "500"},
    "joy":      {"rate": "medium", "pitch": "high",   "break_ms": "200"},
    "sadness":  {"rate": "slow",   "pitch": "low",    "break_ms": "400"},
    "anger":    {"rate": "fast",   "pitch": "medium", "break_ms": "100"},
    "neutral":  {"rate": "medium", "pitch": "medium", "break_ms": "300"},
    "suspense": {"rate": "slow",   "pitch": "low",    "break_ms": "700"},
}

_FALLBACK_EMOTION = "neutral"


class SSMLBuilder:
    """Builds SSML markup adapted to the emotion of a shot."""

    def build(self, text: str, emotion: str) -> str:
        """Return SSML-wrapped text for the given emotion."""
        params = _EMOTION_PARAMS.get(emotion, _EMOTION_PARAMS[_FALLBACK_EMOTION])
        return (
            f'<speak>'
            f'<prosody rate="{params["rate"]}" pitch="{params["pitch"]}">'
            f'{text}'
            f'<break time="{params["break_ms"]}ms"/>'
            f'</prosody>'
            f'</speak>'
        )
