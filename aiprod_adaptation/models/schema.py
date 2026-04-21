from pydantic import BaseModel
from typing import Any, List, Optional


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
    duration_sec: int  # MUST be between 3 and 8 inclusive
    emotion: str
    shot_type: str = "medium"        # "wide" | "medium" | "close_up" | "pov"
    camera_movement: str = "static"  # "static" | "follow" | "pan"
    metadata: dict[str, Any] = {}


class Episode(BaseModel):
    episode_id: str
    scenes: List[Scene]
    shots: List[Shot]


class AIPRODOutput(BaseModel):
    title: str
    episodes: List[Episode]
