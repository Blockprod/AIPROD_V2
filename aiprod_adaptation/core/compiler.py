"""Pure deterministic four-pass compiler boundary.

This module owns only Pass 1 -> Pass 2 -> Pass 3 -> Pass 4. It performs no
adapter calls, scheduling, post-production, environment reads, or logging.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from aiprod_adaptation.core.adaptation.story_validator import StoryValidator
from aiprod_adaptation.core.pass1_segment import segment
from aiprod_adaptation.core.pass2_visual import visual_rewrite
from aiprod_adaptation.core.pass3_shots import simplify_shots
from aiprod_adaptation.core.pass4_compile import compile_episode
from aiprod_adaptation.models.intermediate import CinematicScene, RawScene
from aiprod_adaptation.models.schema import AIPRODOutput, IRVersion

if TYPE_CHECKING:
    from aiprod_adaptation.core.visual_bible import VisualBible


def compile_text(
    text: str,
    title: str,
    *,
    ir_version: IRVersion,
    episode_id: str = "EP01",
    visual_bible: VisualBible | None = None,
    ref_invariants: object | None = None,
    episode_index: int = 1,
) -> AIPRODOutput:
    return compile_pass1(
        segment(text),
        title,
        ir_version=ir_version,
        episode_id=episode_id,
        visual_bible=visual_bible,
        ref_invariants=ref_invariants,
        episode_index=episode_index,
    )


def compile_pass1(
    scenes: Sequence[RawScene | CinematicScene],
    title: str,
    *,
    ir_version: IRVersion,
    episode_id: str = "EP01",
    visual_bible: VisualBible | None = None,
    ref_invariants: object | None = None,
    episode_index: int = 1,
) -> AIPRODOutput:
    if not scenes:
        raise ValueError("PASS 1: scene contract must not be empty.")
    pass2 = visual_rewrite(list(scenes), visual_bible)
    validated = StoryValidator().validate_all(pass2, threshold=0.5)
    if not validated:
        raise ValueError("StoryValidator produced no filmable scenes after validation.")
    if visual_bible is not None:
        missing_slugs = visual_bible.validate_slugs(pass2)
        if missing_slugs:
            raise ValueError(f"VisualBible missing scene slugs: {missing_slugs}")
    pass3 = simplify_shots(pass2)
    return compile_episode(
        pass2,
        pass3,
        title,
        episode_id,
        visual_bible=visual_bible,
        ref_invariants=ref_invariants,
        episode_index=episode_index,
        ir_version=ir_version,
    )
