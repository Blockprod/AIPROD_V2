from __future__ import annotations

import structlog

from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry
from aiprod_adaptation.image_gen.character_sheet import CharacterSheetRegistry
from aiprod_adaptation.image_gen.checkpoint import CheckpointStore
from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import (
    ImageRequest,
    ImageResult,
    ShotStoryboardFrame,
    StoryboardOutput,
)
from aiprod_adaptation.image_gen.reference_pack import ReferencePack
from aiprod_adaptation.models.schema import AIPRODOutput, Scene, Shot

DEFAULT_STYLE_TOKEN = (
    "cinematic storyboard, 16:9 aspect ratio, film grain, anamorphic lens, color graded"
)

logger = structlog.get_logger(__name__)


def _all_shots(output: AIPRODOutput) -> list[Shot]:
    return [shot for ep in output.episodes for shot in ep.shots]


def _scene_map(output: AIPRODOutput) -> dict[str, Scene]:
    return {scene.scene_id: scene for ep in output.episodes for scene in ep.scenes}


class StoryboardGenerator:
    def __init__(
        self,
        adapter: ImageAdapter,
        base_seed: int | None = None,
        style_token: str = DEFAULT_STYLE_TOKEN,
        character_prompts: dict[str, str] | None = None,
        checkpoint: CheckpointStore | None = None,
        prepass_registry: CharacterImageRegistry | None = None,
        reference_pack: ReferencePack | None = None,
    ) -> None:
        self._adapter = adapter
        self._base_seed = base_seed
        self._style_token = style_token
        self._character_prompts: dict[str, str] = character_prompts or {}
        self._checkpoint = checkpoint
        self._prepass_registry = prepass_registry
        self._reference_pack = reference_pack

    def _location_key_for_shot(self, shot: Shot) -> str:
        if self._reference_pack is None:
            if shot.action is not None and shot.action.location_id:
                return shot.action.location_id
            return ""
        if (
            shot.action is not None
            and shot.action.location_id
            and shot.action.location_id in self._reference_pack.locations
        ):
            return shot.action.location_id
        return self._reference_pack.scene_locations.get(shot.scene_id, "")

    def build_requests(self, output: AIPRODOutput) -> list[ImageRequest]:
        """Build ImageRequests without generating — useful for inspection and tests."""
        return [
            ImageRequest(
                shot_id=shot.shot_id,
                scene_id=shot.scene_id,
                prompt=shot.prompt,
                action=shot.action,
                seed=self._base_seed + i if self._base_seed is not None else None,
            )
            for i, shot in enumerate(_all_shots(output))
        ]

    def prepass_character_sheets(
        self, registry: CharacterSheetRegistry
    ) -> CharacterSheetRegistry:
        """
        Generate one canonical image per character sheet. Idempotent.

        NOTE: This method is NOT called by the production pipeline (engine.py,
        EpisodeScheduler, cli.py). It is provided for advanced use cases where
        callers want to inject explicit character sheets before generate().
        """
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
                except Exception as exc:
                    logger.warning(
                        "character_sheet_prepass_failed",
                        character_name=sheet.name,
                        shot_id=req.shot_id,
                        error=str(exc),
                    )
        return registry

    def generate(self, output: AIPRODOutput) -> StoryboardOutput:
        shots = _all_shots(output)
        scenes = _scene_map(output)
        frames: list[ShotStoryboardFrame] = []
        char_registry = CharacterImageRegistry()

        # If a prepass registry was provided, seed char_registry with its data
        if self._prepass_registry is not None:
            for char in self._prepass_registry.known_characters():
                ref = self._prepass_registry.get_reference(char)
                prompt = self._prepass_registry.get_canonical_prompt(char)
                if ref:
                    char_registry.register(char, ref)
                if prompt:
                    char_registry.register_prompt(char, prompt)

        if self._reference_pack is not None:
            for name in self._reference_pack.characters:
                ref = self._reference_pack.character_reference_url(name)
                prompt = self._reference_pack.character_prompt(name)
                if ref:
                    char_registry.register(name, ref, overwrite=True)
                if prompt:
                    char_registry.register_prompt(name, prompt, overwrite=True)

        for name, prompt in self._character_prompts.items():
            char_registry.register_prompt(name, prompt, overwrite=True)

        for i, shot in enumerate(shots):
            seed = self._base_seed + i if self._base_seed is not None else None
            scene = scenes.get(shot.scene_id)
            shot_subject = shot.action.subject_id if shot.action is not None else ""
            primary_char = shot_subject or (
                scene.characters[0] if scene and scene.characters else ""
            )
            characters_in_frame: list[str] = list(scene.characters) if scene else []
            if shot_subject and shot_subject not in characters_in_frame:
                characters_in_frame.append(shot_subject)
            canonical = char_registry.get_canonical_prompt(primary_char) if primary_char else ""
            location_key = self._location_key_for_shot(shot)
            location_prompt = (
                self._reference_pack.location_prompt(location_key)
                if self._reference_pack is not None and location_key
                else ""
            )
            location_reference_url = (
                self._reference_pack.location_reference_url(location_key)
                if self._reference_pack is not None and location_key
                else ""
            )
            reference_url = char_registry.get_reference(primary_char) if primary_char else ""
            if not reference_url:
                reference_url = location_reference_url
            tod_visual: str = shot.metadata.get("time_of_day_visual", "day")
            dom_sound: str = shot.metadata.get("dominant_sound", "dialogue")

            prompt_parts = [shot.prompt, f"{tod_visual} lighting."]
            if location_prompt:
                prompt_parts.append(location_prompt)
            if canonical:
                prompt_parts.append(canonical)
            if self._style_token:
                prompt_parts.append(self._style_token)
            enriched_prompt = " ".join(prompt_parts)

            request = ImageRequest(
                shot_id=shot.shot_id,
                scene_id=shot.scene_id,
                prompt=enriched_prompt,
                action=shot.action,
                seed=seed,
                reference_image_url=reference_url,
            )
            if self._checkpoint is not None and self._checkpoint.has(shot.shot_id):
                cached = self._checkpoint.get(shot.shot_id)
                assert cached is not None
                frames.append(cached)
                if primary_char and cached.model_used != "error":
                    char_registry.register(primary_char, cached.image_url)
                continue
            try:
                result = self._adapter.generate(request)
            except Exception as exc:
                logger.warning(
                    "storyboard_frame_failed",
                    shot_id=shot.shot_id,
                    scene_id=shot.scene_id,
                    error=str(exc),
                )
                result = ImageResult(
                    shot_id=shot.shot_id,
                    image_url="error://generation-failed",
                    image_b64="",
                    model_used="error",
                    latency_ms=0,
                )
            if primary_char and result.model_used != "error":
                char_registry.register(primary_char, result.image_url)

            frame = ShotStoryboardFrame(
                    shot_id=result.shot_id,
                    scene_id=shot.scene_id,
                    image_url=result.image_url,
                    image_b64=result.image_b64,
                    model_used=result.model_used,
                    latency_ms=result.latency_ms,
                    cost_usd=result.cost_usd,
                    prompt_used=enriched_prompt,
                    seed_used=seed,
                    shot_type=shot.shot_type,
                    camera_movement=shot.camera_movement,
                    time_of_day_visual=tod_visual,
                    dominant_sound=dom_sound,
                    characters_in_frame=characters_in_frame,
                    reference_image_url=reference_url,
                )
            if self._checkpoint is not None:
                self._checkpoint.save(frame)
            frames.append(frame)

        return StoryboardOutput(
            title=output.title,
            frames=frames,
            style_token=self._style_token,
            total_shots=len(shots),
            generated=sum(1 for f in frames if f.model_used != "error"),
        )

