from __future__ import annotations

from pydantic import BaseModel, field_validator

from aiprod_adaptation.models.schema import ActionSpec


class ImageRequest(BaseModel):
    shot_id: str
    scene_id: str
    prompt: str
    action: ActionSpec | None = None
    negative_prompt: str = (
        "cartoon, anime, illustration, painting, 3D render, CGI, digital art, "
        "plastic skin, uncanny valley, wax figure, deformed hands, asymmetric face, "
        "bad anatomy, blurry, low resolution, watermark, text, logo, "
        "oversaturated, flat lighting, stock photography, AI artifacts, "
        "stylised, painted look, smooth skin, airbrushed"
    )
    width: int = 1024
    height: int = 576
    num_steps: int = 28
    guidance_scale: float = 7.5
    seed: int | None = None
    reference_image_url: str = ""

    @field_validator("num_steps")
    @classmethod
    def validate_steps(cls, v: int) -> int:
        if not (1 <= v <= 150):
            raise ValueError(f"num_steps must be between 1 and 150, got {v}")
        return v

    @field_validator("guidance_scale")
    @classmethod
    def validate_guidance(cls, v: float) -> float:
        if not (1.0 <= v <= 30.0):
            raise ValueError(f"guidance_scale must be between 1.0 and 30.0, got {v}")
        return v


class ImageResult(BaseModel):
    shot_id: str
    image_url: str
    image_b64: str = ""
    model_used: str
    latency_ms: int
    cost_usd: float = 0.0


class ShotStoryboardFrame(BaseModel):
    shot_id: str
    scene_id: str
    image_url: str
    image_b64: str = ""
    model_used: str
    latency_ms: int
    cost_usd: float = 0.0
    prompt_used: str
    seed_used: int | None = None
    shot_type: str = ""
    camera_movement: str = ""
    time_of_day_visual: str = "day"
    dominant_sound: str = "dialogue"
    characters_in_frame: list[str] = []
    reference_image_url: str = ""


class StoryboardOutput(BaseModel):
    title: str
    frames: list[ShotStoryboardFrame]
    style_token: str = ""
    total_shots: int
    generated: int
