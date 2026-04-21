from __future__ import annotations

from typing import List, Optional

from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import (
    ImageRequest,
    ImageResult,
    StoryboardOutput,
)
from aiprod_adaptation.models.schema import AIPRODOutput, Shot


def _all_shots(output: AIPRODOutput) -> List[Shot]:
    return [shot for ep in output.episodes for shot in ep.shots]


class StoryboardGenerator:
    def __init__(
        self,
        adapter: ImageAdapter,
        base_seed: Optional[int] = None,
    ) -> None:
        self._adapter = adapter
        self._base_seed = base_seed

    def build_requests(self, output: AIPRODOutput) -> List[ImageRequest]:
        """Build ImageRequests without generating — useful for inspection and tests."""
        return [
            ImageRequest(
                shot_id=shot.shot_id,
                scene_id=shot.scene_id,
                prompt=shot.prompt,
                seed=self._base_seed + i if self._base_seed is not None else None,
            )
            for i, shot in enumerate(_all_shots(output))
        ]

    def generate(self, output: AIPRODOutput) -> StoryboardOutput:
        shots = _all_shots(output)
        results: List[ImageResult] = []

        for i, shot in enumerate(shots):
            seed = self._base_seed + i if self._base_seed is not None else None
            request = ImageRequest(
                shot_id=shot.shot_id,
                scene_id=shot.scene_id,
                prompt=shot.prompt,
                seed=seed,
            )
            try:
                result = self._adapter.generate(request)
            except Exception:
                result = ImageResult(
                    shot_id=shot.shot_id,
                    image_url="error://generation-failed",
                    image_b64="",
                    model_used="error",
                    latency_ms=0,
                )
            results.append(result)

        return StoryboardOutput(
            title=output.title,
            images=results,
            total_shots=len(shots),
            generated=sum(1 for r in results if r.model_used != "error"),
        )
