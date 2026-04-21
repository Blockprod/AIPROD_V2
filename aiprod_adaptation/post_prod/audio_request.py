"""
Post-production data models: AudioRequest, AudioResult, TimelineClip, ProductionOutput.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, field_validator


class AudioRequest(BaseModel):
    """Input for a single-shot audio generation request."""

    shot_id: str
    scene_id: str
    text: str
    voice_id: str = "default"
    language: str = "en"
    duration_hint_sec: int = 4

    @field_validator("duration_hint_sec")
    @classmethod
    def _duration_hint_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("duration_hint_sec must be >= 1")
        return v


class AudioResult(BaseModel):
    """Output from an audio generation adapter for a single shot."""

    shot_id: str
    audio_url: str
    audio_b64: str = ""
    duration_sec: int
    model_used: str
    latency_ms: int


class TimelineClip(BaseModel):
    """A fully assembled clip: video + audio + position in the timeline."""

    shot_id: str
    scene_id: str
    video_url: str
    audio_url: str
    duration_sec: int
    start_sec: int


class ProductionOutput(BaseModel):
    """Final production timeline ready for export."""

    title: str
    timeline: List[TimelineClip]
    total_duration_sec: int
    resolution: str = "3840x2160"
    fps: int = 24

    @field_validator("fps")
    @classmethod
    def _fps_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("fps must be >= 1")
        return v
