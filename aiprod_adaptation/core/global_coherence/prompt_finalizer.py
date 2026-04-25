"""
prompt_finalizer.py — Last-pass prompt enrichment for Pass 4.

Appends cinematic directives to each shot's prompt when they are set on the
Shot object but not yet present in the prompt text.  Optionally injects
character and location invariant fragments from a VisualBible.

Rules applied (from pass4_coherence_rules):
    R05  composition_description set + absent from prompt → append
    R06  lighting_directives set + absent from prompt → append
    R07  VisualBible provided + subject_id matches known character → append fragment
    R08  VisualBible provided + location_id matches known location → append fragment

All Shot mutations use model_copy(update=...) — no in-place mutation.

Returns:
    (enriched_shots: list[Shot], enrichment_count: int)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiprod_adaptation.core.visual_bible import VisualBible

from aiprod_adaptation.core.rules.pass4_coherence_rules import (
    PROMPT_ENRICHMENT_SEPARATOR,
    PROMPT_LABEL_CHARACTER,
    PROMPT_LABEL_COMPOSITION,
    PROMPT_LABEL_LIGHTING,
    PROMPT_LABEL_LOCATION,
)
from aiprod_adaptation.models.schema import Shot


def finalize_prompts(
    shots: list[Shot],
    visual_bible: VisualBible | None = None,
) -> tuple[list[Shot], int]:
    """
    Enrich shot prompts with cinematic directives.

    Args:
        shots:        Validated Shot objects after consistency checking.
        visual_bible: Optional VisualBible instance for character/location
                      invariant injection.  If None, R07/R08 are skipped.

    Returns:
        (enriched_shots, total_enrichment_count) where enrichment_count is
        the number of shots that received at least one addition.
    """
    enriched: list[Shot] = []
    total_enriched = 0

    for shot in shots:
        additions: list[str] = []
        prompt = shot.prompt

        # ------------------------------------------------------------------
        # R05 — composition_description
        # ------------------------------------------------------------------
        if shot.composition_description and shot.composition_description not in prompt:
            additions.append(
                f"{PROMPT_LABEL_COMPOSITION}: {shot.composition_description}"
            )

        # ------------------------------------------------------------------
        # R06 — lighting_directives
        # ------------------------------------------------------------------
        if shot.lighting_directives and shot.lighting_directives not in prompt:
            additions.append(
                f"{PROMPT_LABEL_LIGHTING}: {shot.lighting_directives}"
            )

        # ------------------------------------------------------------------
        # R07 — Character invariant from VisualBible
        # ------------------------------------------------------------------
        if visual_bible is not None and shot.action is not None:
            subject_id = shot.action.subject_id
            if subject_id:
                for char_name in visual_bible.characters:
                    if (
                        char_name.lower() in subject_id.lower()
                        or subject_id.lower() in char_name.lower()
                    ):
                        fragment = visual_bible.get_character_prompt_fragment(char_name)
                        if fragment and fragment not in prompt:
                            additions.append(
                                f"{PROMPT_LABEL_CHARACTER}: {fragment}"
                            )
                        break

        # ------------------------------------------------------------------
        # R08 — Location invariant from VisualBible
        # ------------------------------------------------------------------
        if visual_bible is not None and shot.action is not None:
            loc_id = shot.action.location_id
            if loc_id:
                fragment = visual_bible.get_location_prompt_fragment(loc_id)
                if fragment and fragment not in prompt:
                    additions.append(
                        f"{PROMPT_LABEL_LOCATION}: {fragment}"
                    )

        # ------------------------------------------------------------------
        # Build enriched prompt
        # ------------------------------------------------------------------
        if additions:
            new_prompt = (
                prompt.rstrip(".")
                + PROMPT_ENRICHMENT_SEPARATOR
                + ". ".join(additions)
                + "."
            )
            shot = shot.model_copy(update={"prompt": new_prompt})
            total_enriched += 1

        enriched.append(shot)

    return enriched, total_enriched
