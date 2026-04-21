from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, field_validator


class ImageRequest(BaseModel):
    shot_id: str
    scene_id: str
    prompt: str
    negative_prompt: str = "blurry, low quality, watermark, text, oversaturated"
    width: int = 1024
    height: int = 576
    num_steps: int = 28
    guidance_scale: float = 7.5
    seed: Optional[int] = None
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


class StoryboardOutput(BaseModel):
    title: str
    images: List[ImageResult]
    total_shots: int
    generated: int
