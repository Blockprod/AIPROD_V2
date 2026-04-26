from __future__ import annotations

from pydantic import BaseModel, field_validator

from aiprod_adaptation.models.schema import ActionSpec


class VideoRequest(BaseModel):
    shot_id: str
    scene_id: str
    image_url: str
    prompt: str
    action: ActionSpec | None = None
    duration_sec: int
    motion_score: float = 5.0
    seed: int | None = None
    last_frame_hint_url: str = ""   # last_frame of previous clip (intra-scene continuity)
    character_reference_urls: list[str] = []   # used by Aleph (v2v) only

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
    cost_usd: float = 0.0
    last_frame_url: str = ""   # last frame of this clip (used as hint for next shot)


class VideoOutput(BaseModel):
    title: str
    clips: list[VideoClipResult]
    total_shots: int
    generated: int
