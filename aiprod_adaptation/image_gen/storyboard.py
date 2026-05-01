from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    pass

from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry
from aiprod_adaptation.image_gen.character_sheet import CharacterSheetRegistry
from aiprod_adaptation.image_gen.checkpoint import CheckpointStore
from aiprod_adaptation.image_gen.flux_kontext_adapter import FluxKontextAdapter
from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import (
    ImageRequest,
    ImageResult,
    ShotStoryboardFrame,
    StoryboardOutput,
)
from aiprod_adaptation.image_gen.openai_image_adapter import OpenAIImageAdapter
from aiprod_adaptation.image_gen.reference_pack import ReferencePack
from aiprod_adaptation.models.schema import AIPRODOutput, Scene, Shot

DEFAULT_STYLE_TOKEN = (
    "photorealistic, hyperrealistic cinema, shot on ARRI Alexa 35 LF, "
    "anamorphic 2.39:1, Cooke S7i lenses, natural skin texture with visible pores, "
    "subsurface scattering, motivated practical lighting only, "
    "cinematic depth of field, color graded DI, film emulsion grain, tack sharp"
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt builder — dramatic archetype first, tech last (mirrors ChatGPT best practice)
# ---------------------------------------------------------------------------

_SHOT_TYPE_LABELS: dict[str, str] = {
    "extreme_close_up": "Extreme close-up portrait",
    "close_up": "Close-up portrait",
    "medium": "Medium shot",
    "wide": "Wide establishing shot",
    "extreme_wide": "Extreme wide establishing shot",
    "over_shoulder": "Over-shoulder shot",
    "insert": "Insert detail shot",
}

_TECH_FOOTER = (
    "4K hyperrealistic, cinematic quality, ARRI Alexa 35 LF, "
    "anamorphic 2.39:1, film emulsion grain, cinematic depth of field"
)

# For portrait close-ups: photography language, NOT cinema CGI language.
# FLUX.1 responds much better to analog photo cues for natural-looking skin.
_PORTRAIT_FOOTER = (
    "analog portrait photography, 35mm film, Kodak Portra 400, "
    "natural skin texture with visible pores, micro-imperfections, "
    "shallow depth of field f/2.0, soft bokeh background, film grain"
)

# Shot types that are tight portrait frames — location should NOT be injected
_PORTRAIT_SHOT_TYPES = frozenset({"extreme_close_up", "close_up"})

# Shot types where character-level framing directives ("Tight framing shoulders to crown")
# must be stripped so they don't override the wide/establishing composition.
_WIDE_SHOT_TYPES = frozenset({"wide", "extreme_wide", "insert", "over_shoulder"})

# Shot types where the character canonical prompt must be OMITTED entirely:
# - insert: object/detail close-up — character face would dominate and mislead the model
# - wide / extreme_wide: environment-first — character description causes portrait generation
_NO_CHAR_SHOT_TYPES = frozenset({"insert", "wide", "extreme_wide"})


def _strip_framing_directives(char_prompt: str) -> str:
    """Remove 'Tight framing ...' sentences from char prompts used in wide/
    establishing/insert shots where they would fight the composition direction."""
    sentences = char_prompt.split(". ")
    filtered = [s for s in sentences if not s.strip().lower().startswith("tight framing")]
    return ". ".join(filtered).strip()

# Boilerplate prefixes/suffixes in old-style character prompts (kept for
# backward compatibility with external prompts not yet migrated)
_CHAR_PROMPT_PREFIXES = (
    "photorealistic 35mm cinema still of a ",
    "photorealistic 35mm cinema still of ",
    "close-up portrait, ",
    "close-up portrait ",
    "photorealistic ",
    "35mm cinema still of a ",
    "35mm cinema still of ",
)

_CHAR_PROMPT_SUFFIXES = (
    ", ARRI Alexa 35 look",
    " ARRI Alexa 35 look",
    ", 4K hyperrealistic, cinematic quality, naturally contrasted chiaroscuro.",
    " 4K hyperrealistic, cinematic quality, naturally contrasted chiaroscuro.",
    ", 4K hyperrealistic, cinematic quality.",
    " 4K hyperrealistic, cinematic quality.",
    ", naturally contrasted chiaroscuro.",
    " naturally contrasted chiaroscuro.",
)

_LOC_TECH_STRIP = (
    "ARRI Alexa 35", "anamorphic", "film grain",
    "photorealistic cinematic interior,",
    "photorealistic cinematic interior",
    "photorealistic cinematic wide shot,",
    "photorealistic cinematic wide shot",
    "photorealistic cinematic",
    "photorealistic",
    "4K hyperrealistic, cinematic quality.",
    "4K hyperrealistic, cinematic quality",
)


def _condense_char_prompt(canonical: str) -> str:
    """Strip boilerplate preamble and trailing tech spec from character prompt."""
    if not canonical:
        return ""
    result = canonical
    for prefix in _CHAR_PROMPT_PREFIXES:
        if result.lower().startswith(prefix.lower()):
            result = result[len(prefix):]
            break
    for suffix in _CHAR_PROMPT_SUFFIXES:
        if result.endswith(suffix):
            result = result[: -len(suffix)]
    return result.strip().rstrip(",").strip()


def _condense_location(location_prompt: str) -> str:
    """Strip tech boilerplate from location prompt, keep visual descriptors."""
    if not location_prompt:
        return ""
    stripped = location_prompt
    for tech in _LOC_TECH_STRIP:
        stripped = stripped.replace(tech, " ").replace("  ", " ")
    parts = [p.strip() for p in stripped.split(",") if p.strip() and len(p.strip()) > 4]
    return ", ".join(parts[:5]).strip().strip(",").strip()


def _build_shot_prompt(
    shot: Shot,
    canonical_char: str,
    location_prompt: str,
    tod_visual: str,
) -> str:
    """
    Build a structured cinematic prompt optimised for gpt-image-1.

    Mirrors the prompt structure that produces best results on ChatGPT:
      1. Shot framing label
      2. Character canonical description (archetype + dramatic presence first)
      3. Location / environment atmosphere
      4. Lighting / tone
      5. Technical quality footer

    Character prompts in reference_pack.json should already start with the
    dramatic archetype ("protagonist of a dystopian thriller series...") so
    _condense_char_prompt only strips residual boilerplate.
    """
    framing = _SHOT_TYPE_LABELS.get(shot.shot_type or "", "Cinematic shot")
    char = _condense_char_prompt(canonical_char)
    is_portrait = (shot.shot_type or "") in _PORTRAIT_SHOT_TYPES
    shot_type_key = shot.shot_type or ""

    # Insert / wide / extreme_wide: drop char entirely so the model composes
    # the environment/object rather than defaulting to a portrait.
    if shot_type_key in _NO_CHAR_SHOT_TYPES:
        char = ""
    elif shot_type_key in _WIDE_SHOT_TYPES:
        # over_shoulder etc: keep char but strip tight-framing directives.
        char = _strip_framing_directives(char)

    segments: list[str] = [framing]
    if char:
        segments.append(char)

    if is_portrait and char:
        # Portrait close-up with a character: skip location (it confuses FLUX)
        # and use photography footer for natural skin/face rendering.
        segments.append(_PORTRAIT_FOOTER)
    else:
        # Wide / medium / over-shoulder / establishing shots: inject location + lighting.
        loc = _condense_location(location_prompt)
        if loc:
            segments.append(loc)
        # Only add tod_visual as a light qualifier; do NOT override location atmosphere
        # with a blanket colour — service spine has amber, black market has neon, etc.
        if tod_visual:
            segments.append(f"{tod_visual.capitalize()} lighting, naturally contrasted chiaroscuro")
        segments.append(_TECH_FOOTER)

    return " — ".join(s.strip().rstrip(" —").strip() for s in segments if s.strip())


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
        kontext_adapter: FluxKontextAdapter | None = None,
        adapter_overrides: dict[str, ImageAdapter] | None = None,
        budget_cap_usd: float | None = None,
    ) -> None:
        self._adapter = adapter
        self._base_seed = base_seed
        self._style_token = style_token
        self._character_prompts: dict[str, str] = character_prompts or {}
        self._checkpoint = checkpoint
        self._prepass_registry = prepass_registry
        self._reference_pack = reference_pack
        self._kontext_adapter = kontext_adapter
        self._adapter_overrides: dict[str, ImageAdapter] = adapter_overrides or {}
        self._budget_cap_usd: float | None = budget_cap_usd

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
                rgba = self._prepass_registry.get_rgba(char)
                if ref:
                    char_registry.register(char, ref)
                if prompt:
                    char_registry.register_prompt(char, prompt)
                if rgba is not None:
                    char_registry.register_rgba(char, rgba)

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

            # Use FluxKontextAdapter when available and a character reference exists
            if self._kontext_adapter is not None and reference_url:
                if isinstance(self._kontext_adapter, FluxKontextAdapter) and location_prompt:
                    kontext_prompt = FluxKontextAdapter.build_location_prompt(location_prompt)
                    kontext_request = ImageRequest(
                        shot_id=shot.shot_id,
                        scene_id=shot.scene_id,
                        prompt=kontext_prompt,
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
                        result = self._kontext_adapter.generate(kontext_request)
                    except Exception as exc:
                        logger.warning(
                            "kontext_frame_failed",
                            shot_id=shot.shot_id,
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
                        prompt_used=kontext_prompt,
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
                    continue

            prompt_parts = [shot.prompt, f"{tod_visual} lighting."]
            if location_prompt:
                prompt_parts.append(location_prompt)
            if canonical:
                prompt_parts.append(canonical)
            if self._style_token:
                prompt_parts.append(self._style_token)
            enriched_prompt = _build_shot_prompt(shot, canonical, location_prompt, tod_visual)

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
            _shot_adapter = self._adapter_overrides.get(shot.scene_id, self._adapter)
            try:
                # Use images.edit path when a reference image is available for the
                # primary character AND the adapter supports it.
                # gpt-image-1 images.edit uses the reference as a character consistency
                # guide (not pixel-level compositing), so it works for all shot types.
                rgba = char_registry.get_rgba(primary_char) if primary_char else None
                if rgba is not None and isinstance(_shot_adapter, OpenAIImageAdapter):
                    result = _shot_adapter.generate_edit(request, rgba)
                else:
                    result = _shot_adapter.generate(request)
            except Exception as exc:
                err_str = str(exc)
                # Fail-fast on auth/permission errors — abort immediately.
                if "403" in err_str or "must be verified" in err_str or (
                    "permission" in err_str.lower() and "organization" in err_str.lower()
                ):
                    raise RuntimeError(
                        f"Image adapter auth/permission error — aborting run to avoid "
                        f"wasting credits. Check API key and model access: {exc}"
                    ) from exc
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
            if self._budget_cap_usd is not None:
                running_cost = sum(f.cost_usd for f in frames)
                if running_cost >= self._budget_cap_usd:
                    logger.warning(
                        "budget_cap_reached",
                        cap_usd=self._budget_cap_usd,
                        cost_usd=running_cost,
                        shots_generated=len(frames),
                        shots_remaining=len(shots) - i - 1,
                    )
                    break

        return StoryboardOutput(
            title=output.title,
            frames=frames,
            style_token=self._style_token,
            total_shots=len(shots),
            generated=sum(1 for f in frames if f.model_used != "error"),
        )

