from typing import Any

from pydantic import BaseModel, Field, field_validator

_VALID_SHOT_TYPES: frozenset[str] = frozenset({"wide", "medium", "close_up", "pov"})
_VALID_CAMERA_MOVEMENTS: frozenset[str] = frozenset({"static", "follow", "pan"})
_VALID_TOD_VISUAL: frozenset[str] = frozenset({"dawn", "day", "dusk", "night", "interior"})
_VALID_DOMINANT_SOUND: frozenset[str] = frozenset({"dialogue", "ambient", "silence"})
_ALLOWED_METADATA_KEYS: frozenset[str] = frozenset({"time_of_day_visual", "dominant_sound"})


class Scene(BaseModel):
    scene_id: str
    characters: list[str]
    character_ids: list[str] = Field(default_factory=list)
    location: str
    location_id: str | None = None
    time_of_day: str | None = None
    visual_actions: list[str]
    dialogues: list[str]
    emotion: str
    action_units: list["ActionSpec"] = Field(default_factory=list)
    shot_ids: list[str] = Field(default_factory=list)


class ActionSpec(BaseModel):
    subject_id: str
    action_type: str
    target: str | None = None
    modifiers: list[str] = Field(default_factory=list)
    location_id: str | None = None
    camera_intent: str = "static"
    source_text: str


class Shot(BaseModel):
    shot_id: str
    scene_id: str
    prompt: str
    duration_sec: int  # MUST be between 3 and 8 inclusive
    emotion: str
    shot_type: str = "medium"        # "wide" | "medium" | "close_up" | "pov"
    camera_movement: str = "static"  # "static" | "follow" | "pan"
    action: ActionSpec | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

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

    @field_validator("action")
    @classmethod
    def validate_action_camera_intent(cls, value: ActionSpec | None) -> ActionSpec | None:
        if value is None:
            return None
        if value.camera_intent not in _VALID_CAMERA_MOVEMENTS:
            raise ValueError(
                "Invalid action.camera_intent: "
                f"{value.camera_intent!r}. Must be one of {sorted(_VALID_CAMERA_MOVEMENTS)}"
            )
        return value

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        invalid_keys = [key for key in value if key not in _ALLOWED_METADATA_KEYS]
        if invalid_keys:
            raise ValueError(
                "Invalid metadata keys: "
                f"{invalid_keys!r}. Allowed keys: {sorted(_ALLOWED_METADATA_KEYS)}"
            )

        time_of_day_visual = value.get("time_of_day_visual")
        if time_of_day_visual is not None and time_of_day_visual not in _VALID_TOD_VISUAL:
            raise ValueError(
                "Invalid metadata.time_of_day_visual: "
                f"{time_of_day_visual!r}. Must be one of {sorted(_VALID_TOD_VISUAL)}"
            )

        dominant_sound = value.get("dominant_sound")
        if dominant_sound is not None and dominant_sound not in _VALID_DOMINANT_SOUND:
            raise ValueError(
                "Invalid metadata.dominant_sound: "
                f"{dominant_sound!r}. Must be one of {sorted(_VALID_DOMINANT_SOUND)}"
            )

        return value


class Episode(BaseModel):
    episode_id: str
    scenes: list[Scene]
    shots: list[Shot]


class AIPRODOutput(BaseModel):
    title: str
    episodes: list[Episode]
