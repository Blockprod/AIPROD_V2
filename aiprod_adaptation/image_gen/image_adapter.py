from __future__ import annotations

from abc import ABC, abstractmethod

from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult


class ImageAdapter(ABC):
    @abstractmethod
    def generate(self, request: ImageRequest) -> ImageResult:
        """Generate a single image from a request. Raises on hard failure."""
        ...


class NullImageAdapter(ImageAdapter):
    """Deterministic stub for CI — returns a placeholder result instantly."""

    MODEL_NAME: str = "null"

    def generate(self, request: ImageRequest) -> ImageResult:
        return ImageResult(
            shot_id=request.shot_id,
            image_url=f"null://storyboard/{request.shot_id}.png",
            image_b64="",
            model_used=self.MODEL_NAME,
            latency_ms=0,
        )
