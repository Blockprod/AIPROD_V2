from __future__ import annotations

from typing import List, Optional

from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry
from aiprod_adaptation.image_gen.character_sheet import CharacterSheetRegistry
from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import (
    ImageRequest,
    ImageResult,
    ShotStoryboardFrame,
    StoryboardOutput,
)
from aiprod_adaptation.models.schema import AIPRODOutput, Scene, Shot

DEFAULT_STYLE_TOKEN = (
    "cinematic storyboard, 16:9 aspect ratio, film grain, anamorphic lens, color graded"
)


def _all_shots(output: AIPRODOutput) -> List[Shot]:
    return [shot for ep in output.episodes for shot in ep.shots]


def _scene_map(output: AIPRODOutput) -> dict[str, Scene]:
    return {scene.scene_id: scene for ep in output.episodes for scene in ep.scenes}


class StoryboardGenerator:
    def __init__(
        self,
        adapter: ImageAdapter,
        base_seed: Optional[int] = None,
        style_token: str = DEFAULT_STYLE_TOKEN,
        character_prompts: dict[str, str] | None = None,
    ) -> None:
        self._adapter = adapter
        self._base_seed = base_seed
        self._style_token = style_token
        self._character_prompts: dict[str, str] = character_prompts or {}

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

    def prepass_character_sheets(
        self, registry: CharacterSheetRegistry
    ) -> CharacterSheetRegistry:
        """Generate one canonical image per character sheet. Idempotent."""
        for sheet in registry.all_sheets():
            if not sheet.image_url:
                req = ImageRequest(
                    shot_id=f"CHAR_{sheet.name}",
                    scene_id="CHARACTER_SHEET",
                    prompt=f"{sheet.canonical_prompt} {self._style_token}".strip(),
                    seed=sheet.seed,
                )
                try:
                    result = self._adapter.generate(req)
                    sheet.image_url = result.image_url
                except Exception:
                    pass
        return registry

    def generate(self, output: AIPRODOutput) -> StoryboardOutput:
        shots = _all_shots(output)
        scenes = _scene_map(output)
        frames: List[ShotStoryboardFrame] = []
        char_registry = CharacterImageRegistry()

        for name, prompt in self._character_prompts.items():
            char_registry.register_prompt(name, prompt)

        for i, shot in enumerate(shots):
            seed = self._base_seed + i if self._base_seed is not None else None
            scene = scenes.get(shot.scene_id)
            primary_char = scene.characters[0] if scene and scene.characters else ""
            characters_in_frame: List[str] = list(scene.characters) if scene else []
            reference_url = char_registry.get_reference(primary_char) if primary_char else ""
            canonical = char_registry.get_canonical_prompt(primary_char) if primary_char else ""
            tod_visual: str = shot.metadata.get("time_of_day_visual", "day")
            dom_sound: str = shot.metadata.get("dominant_sound", "dialogue")

            prompt_parts = [shot.prompt, f"{tod_visual} lighting."]
            if canonical:
                prompt_parts.append(canonical)
            if self._style_token:
                prompt_parts.append(self._style_token)
            enriched_prompt = " ".join(prompt_parts)

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

            frames.append(
                ShotStoryboardFrame(
                    shot_id=result.shot_id,
                    scene_id=shot.scene_id,
                    image_url=result.image_url,
                    image_b64=result.image_b64,
                    model_used=result.model_used,
                    latency_ms=result.latency_ms,
                    prompt_used=enriched_prompt,
                    seed_used=seed,
                    shot_type=shot.shot_type,
                    camera_movement=shot.camera_movement,
                    time_of_day_visual=tod_visual,
                    dominant_sound=dom_sound,
                    characters_in_frame=characters_in_frame,
                    reference_image_url=reference_url,
                )
            )

        return StoryboardOutput(
            title=output.title,
            frames=frames,
            style_token=self._style_token,
            total_shots=len(shots),
            generated=sum(1 for f in frames if f.model_used != "error"),
        )

