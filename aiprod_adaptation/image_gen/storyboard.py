from __future__ import annotations

from typing import List, Optional

from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry
from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import (
    ImageRequest,
    ImageResult,
    StoryboardOutput,
)
from aiprod_adaptation.models.schema import AIPRODOutput, Scene, Shot


def _all_shots(output: AIPRODOutput) -> List[Shot]:
    return [shot for ep in output.episodes for shot in ep.shots]


def _scene_map(output: AIPRODOutput) -> dict[str, Scene]:
    return {scene.scene_id: scene for ep in output.episodes for scene in ep.scenes}


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
        scenes = _scene_map(output)
        results: List[ImageResult] = []
        char_registry = CharacterImageRegistry()

        for i, shot in enumerate(shots):
            seed = self._base_seed + i if self._base_seed is not None else None
            scene = scenes.get(shot.scene_id)
            primary_char = scene.characters[0] if scene and scene.characters else ""
            reference_url = char_registry.get_reference(primary_char) if primary_char else ""
            tod_visual = shot.metadata.get("time_of_day_visual", "day")
            enriched_prompt = f"{shot.prompt} {tod_visual} lighting."
            request = ImageRequest(
                shot_id=shot.shot_id,
                scene_id=shot.scene_id,
                prompt=enriched_prompt,
                seed=seed,
                reference_image_url=reference_url,
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
            if primary_char and result.model_used != "error":
                char_registry.register(primary_char, result.image_url)
            results.append(result)

        return StoryboardOutput(
            title=output.title,
            images=results,
            total_shots=len(shots),
            generated=sum(1 for r in results if r.model_used != "error"),
        )
