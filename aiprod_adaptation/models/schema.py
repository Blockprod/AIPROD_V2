from typing import Any

from pydantic import BaseModel, field_validator

_VALID_SHOT_TYPES: frozenset[str] = frozenset({"wide", "medium", "close_up", "pov"})
_VALID_CAMERA_MOVEMENTS: frozenset[str] = frozenset({"static", "follow", "pan"})


class Scene(BaseModel):
    scene_id: str
    characters: list[str]
    location: str
    time_of_day: str | None = None
    visual_actions: list[str]
    dialogues: list[str]
    emotion: str


class Shot(BaseModel):
    shot_id: str
    scene_id: str
    prompt: str
    duration_sec: int  # MUST be between 3 and 8 inclusive
    emotion: str
    shot_type: str = "medium"        # "wide" | "medium" | "close_up" | "pov"
    camera_movement: str = "static"  # "static" | "follow" | "pan"
    metadata: dict[str, Any] = {}

    @field_validator("duration_sec")
    @classmethod
    def validate_duration_sec(cls, v: int) -> int:
        if not (3 <= v <= 8):
            raise ValueError(
                f"Invalid duration_sec: {v}. Must be between 3 and 8 inclusive."
            )
        return v

    @field_validator("shot_type")
    @classmethod
    def validate_shot_type(cls, v: str) -> str:
        if v not in _VALID_SHOT_TYPES:
            raise ValueError(
                f"Invalid shot_type: {v!r}. Must be one of {sorted(_VALID_SHOT_TYPES)}"
            )
        return v

    @field_validator("camera_movement")
    @classmethod
    def validate_camera_movement(cls, v: str) -> str:
        if v not in _VALID_CAMERA_MOVEMENTS:
            raise ValueError(
                f"Invalid camera_movement: {v!r}. Must be one of {sorted(_VALID_CAMERA_MOVEMENTS)}"
            )
        return v


class Episode(BaseModel):
    episode_id: str
    scenes: list[Scene]
    shots: list[Shot]


class AIPRODOutput(BaseModel):
    title: str
    episodes: list[Episode]
