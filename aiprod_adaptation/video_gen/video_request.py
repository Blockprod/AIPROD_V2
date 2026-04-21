from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, field_validator


class VideoRequest(BaseModel):
    shot_id: str
    scene_id: str
    image_url: str
    prompt: str
    duration_sec: int
    motion_score: float = 5.0
    seed: Optional[int] = None
    last_frame_hint_url: str = ""   # last_frame of previous clip (intra-scene continuity)

    @field_validator("motion_score")
    @classmethod
    def validate_motion_score(cls, v: float) -> float:
        if not (1.0 <= v <= 10.0):
            raise ValueError(f"motion_score must be between 1.0 and 10.0, got {v}")
        return v


class VideoClipResult(BaseModel):
    shot_id: str
    video_url: str
    duration_sec: int
    model_used: str
    latency_ms: int
    last_frame_url: str = ""   # last frame of this clip (used as hint for next shot)


class VideoOutput(BaseModel):
    title: str
    clips: List[VideoClipResult]
    total_shots: int
    generated: int
