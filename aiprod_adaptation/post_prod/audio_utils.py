"""
audio_utils — utilities for measuring real audio duration from base64-encoded MP3.

Falls back gracefully to duration_hint_sec when mutagen is not installed.
"""

from __future__ import annotations


def audio_duration_from_b64(audio_b64: str, duration_hint_sec: int = 4) -> int:
    """
    Decode base64 MP3 and return the real duration in seconds (ceiling).

    Falls back to duration_hint_sec if:
    - audio_b64 is empty
    - mutagen is not installed
    - parsing fails for any reason
    """
    if not audio_b64:
        return duration_hint_sec
    try:
        import base64
        import importlib
        import math
        from io import BytesIO

        mutagen_mp3 = importlib.import_module("mutagen.mp3")
        raw = base64.b64decode(audio_b64)
        audio_obj = mutagen_mp3.MP3(BytesIO(raw))
        length = getattr(audio_obj.info, "length", None)
        if length is None:
            return duration_hint_sec
        return max(1, math.ceil(int(length)))
    except Exception:
        return duration_hint_sec
