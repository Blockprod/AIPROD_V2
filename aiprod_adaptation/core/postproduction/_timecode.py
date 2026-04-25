"""
Shared timecode utility — SMPTE HH:MM:SS:FF notation.

Used by audio_directives, continuity, and timeline modules.
"""

from __future__ import annotations


def frames_to_timecode(frames: int, fps: float) -> str:
    """Convert absolute frame count to HH:MM:SS:FF timecode string."""
    fps_int = max(1, int(fps))
    ff = frames % fps_int
    total_sec = frames // fps_int
    ss = total_sec % 60
    mm = (total_sec // 60) % 60
    hh = total_sec // 3600
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def timecode_to_frames(tc: str, fps: float) -> int:
    """Parse HH:MM:SS:FF timecode string to absolute frame count."""
    parts = tc.split(":")
    if len(parts) != 4:
        raise ValueError(f"Invalid timecode: {tc!r}. Expected HH:MM:SS:FF.")
    hh, mm, ss, ff = (int(p) for p in parts)
    fps_int = max(1, int(fps))
    return ((hh * 3600 + mm * 60 + ss) * fps_int) + ff
