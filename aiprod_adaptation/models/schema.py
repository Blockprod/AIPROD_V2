from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Scene(BaseModel):
    scene_id: str
    characters: List[str]
    location: str
    time_of_day: Optional[str] = None
    visual_actions: List[str]
    dialogues: List[str]
    emotion: str


class Shot(BaseModel):
    shot_id: str
    scene_id: str
    prompt: str
    duration_sec: int = Field(..., ge=3, le=8)
    emotion: str

    @field_validator("duration_sec")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if not (3 <= v <= 8):
            raise ValueError(
                f"duration_sec must be between 3 and 8 inclusive, got {v}"
            )
        return v


class Episode(BaseModel):
    episode_id: str
    scenes: List[Scene]
    shots: List[Shot]


class AIPRODOutput(BaseModel):
    title: str
    episodes: List[Episode]
