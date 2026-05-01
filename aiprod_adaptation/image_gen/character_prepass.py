"""
CharacterPrepass — generates one reference image per character before the main storyboard.
Populates CharacterImageRegistry so StoryboardGenerator can use consistent references.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field

import structlog

from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry
from aiprod_adaptation.image_gen.character_mask import (
    build_edit_mask,
)
from aiprod_adaptation.image_gen.character_mask import (
    remove_background as _remove_bg,
)
from aiprod_adaptation.image_gen.character_sheet import CharacterSheetRegistry
from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import ImageRequest
from aiprod_adaptation.models.schema import AIPRODOutput

_DEFAULT_STYLE_TOKEN = (
    "photorealistic, hyperrealistic cinema, shot on ARRI Alexa 35 LF, "
    "anamorphic 2.39:1, Cooke S7i lenses, natural skin texture with visible pores, "
    "subsurface scattering, motivated practical lighting only, "
    "cinematic depth of field, color graded DI, film emulsion grain, tack sharp"
)

logger = structlog.get_logger(__name__)

# Direction / camera keywords that ScriptParser may extract as character names.
# These are not characters and should be excluded from the prepass.
_DIRECTION_KEYWORDS: frozenset[str] = frozenset({
    "WORKER", "WORKERS", "CROWD", "GUARD", "GUARDS", "SOLDIER", "SOLDIERS",
    "OFFICER", "OFFICERS", "TECHNICIAN", "TECHNICIANS", "CIVILIAN", "CIVILIANS",
    "HANDHELD", "HANDHELD FAST", "HANDHELD SLOW", "STEADICAM", "DRONE",
    "AERIAL", "POV", "INSERT", "MONTAGE", "INTERCUT", "FLASHBACK", "FLASHFORWARD",
    "VOICE OVER", "V.O.", "O.S.", "O.C.", "NARRATOR",
})


def _unique_characters(output: AIPRODOutput) -> list[str]:
    """Return deduplicated list of characters that are primary subjects of shots.

    Scoped to shot.action.subject_id so that filtered runs (--shot-id) only
    prepass the characters actually needed, preventing wasted API credits.
    """
    seen: set[str] = set()
    result: list[str] = []
    for ep in output.episodes:
        for shot in ep.shots:
            if shot.action is None or not shot.action.subject_id:
                continue
            char = shot.action.subject_id
            if char.upper() in _DIRECTION_KEYWORDS:
                continue
            if char not in seen:
                seen.add(char)
                result.append(char)
    return result


@dataclass
class CharacterPrepassResult:
    generated: int
    failed: int
    cost_usd: float = 0.0
    registry: CharacterImageRegistry = field(default_factory=CharacterImageRegistry)


class CharacterPrepass:
    def __init__(
        self,
        adapter: ImageAdapter,
        sheet_registry: CharacterSheetRegistry | None = None,
        base_seed: int = 0,
        style_token: str = _DEFAULT_STYLE_TOKEN,
        remove_background: bool = False,
    ) -> None:
        self._adapter = adapter
        self._sheet_registry = sheet_registry or CharacterSheetRegistry()
        self._base_seed = base_seed
        self._style_token = style_token
        self._remove_background = remove_background

    def run(self, output: AIPRODOutput) -> CharacterPrepassResult:
        characters = _unique_characters(output)
        registry = CharacterImageRegistry()
        generated = 0
        failed = 0
        cost_usd = 0.0

        for idx, name in enumerate(characters):
            sheet = self._sheet_registry.get(name)
            if sheet is None:
                # No canonical defined for this character in the reference pack —
                # a prepass call would generate a meaningless image and waste credits.
                logger.debug("character_prepass_skipped_no_canonical", character_name=name)
                continue
            canonical = sheet.canonical_prompt
            seed = sheet.seed
            prompt = f"{canonical} {self._style_token}".strip()
            req = ImageRequest(
                shot_id=f"PREPASS_{name}",
                scene_id="CHARACTER_PREPASS",
                prompt=prompt,
                seed=seed,
            )
            try:
                result = self._adapter.generate(req)
                cost_usd += result.cost_usd
                # Prefer URL; fall back to data URI so storyboard can use it as reference
                ref_url = result.image_url
                if not ref_url and result.image_b64:
                    ref_url = f"data:image/png;base64,{result.image_b64}"
                registry.register(name, ref_url)
                registry.register_prompt(name, canonical)

                # Optionally remove background to produce RGBA edit-base for images.edit
                if self._remove_background and result.image_b64:
                    try:
                        raw_bytes = base64.b64decode(result.image_b64)
                        rgba_bytes = _remove_bg(raw_bytes)
                        edit_mask = build_edit_mask(rgba_bytes)
                        registry.register_rgba(name, edit_mask)
                        logger.debug(
                            "character_prepass_rgba_generated",
                            character_name=name,
                            rgba_bytes=len(edit_mask),
                        )
                    except Exception as mask_exc:
                        logger.warning(
                            "character_prepass_rgba_failed",
                            character_name=name,
                            error=str(mask_exc),
                        )

                generated += 1
            except Exception as exc:
                err_str = str(exc)
                # Fail-fast on auth/permission errors — do NOT silently continue
                # and waste credits on calls that will all fail for the same reason.
                if "403" in err_str or "must be verified" in err_str or (
                    "permission" in err_str.lower() and "organization" in err_str.lower()
                ):
                    raise RuntimeError(
                        f"Image adapter auth/permission error — aborting run to avoid "
                        f"wasting credits. Check API key and model access: {exc}"
                    ) from exc
                logger.warning(
                    "character_prepass_failed",
                    character_name=name,
                    shot_id=req.shot_id,
                    error=str(exc),
                )
                failed += 1

        return CharacterPrepassResult(
            generated=generated,
            failed=failed,
            cost_usd=cost_usd,
            registry=registry,
        )
