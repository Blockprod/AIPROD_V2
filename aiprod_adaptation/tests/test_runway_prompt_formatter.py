"""
pytest test suite — RunwayPromptFormatter + R09 finalize_prompts

Covers:
  PF-01 — dolly_in camera movement produces correct motion prefix
  PF-02 — static camera movement produces still/minimal-motion text
  PF-03 — duration_sec >= 5 + non-transition → anti-cut clause appended
  PF-04 — beat_type="transition" → no anti-cut clause
  PF-05 — R09: reference_pack with reference_url → preservation clause injected
  PF-06 — R09: no reference_pack → no regression on existing R07/R08 behaviour
"""

from __future__ import annotations

from aiprod_adaptation.core.global_coherence.prompt_finalizer import finalize_prompts
from aiprod_adaptation.image_gen.reference_pack import ReferencePack, ReferenceSubject
from aiprod_adaptation.models.schema import ActionSpec, Shot
from aiprod_adaptation.video_gen.runway_prompt_formatter import format_runway_prompt

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_shot(
    camera_movement: str = "static",
    duration_sec: int = 5,
    beat_type: str = "",
    action: ActionSpec | None = None,
) -> Shot:
    return Shot(
        shot_id="SH0001",
        scene_id="SC001",
        prompt="a man walks through the corridor.",
        duration_sec=duration_sec,
        emotion="neutral",
        camera_movement=camera_movement,
        action=action,
        metadata={"beat_type": beat_type} if beat_type else {},
    )


def _make_action(
    subject_id: str = "john",
    modifiers: list[str] | None = None,
) -> ActionSpec:
    return ActionSpec(
        subject_id=subject_id,
        action_type="walks",
        target="",
        modifiers=modifiers or [],
        location_id="corridor",
        camera_intent="static",
        source_text="a man walks",
    )


# ---------------------------------------------------------------------------
# PF-01 — dolly_in prefix
# ---------------------------------------------------------------------------


class TestFormatRunwayPromptMotion:
    def test_dolly_in_prefix(self) -> None:
        shot = _make_shot(camera_movement="dolly_in", duration_sec=4)
        result = format_runway_prompt(shot)
        assert result.startswith("The camera slowly dollies in as the subject")

    def test_static_contains_perfectly_still(self) -> None:
        shot = _make_shot(camera_movement="static", duration_sec=4)
        result = format_runway_prompt(shot)
        assert "perfectly still" in result
        assert "Minimal subject motion only" in result


# ---------------------------------------------------------------------------
# PF-03 / PF-04 — Anti-cut clause
# ---------------------------------------------------------------------------


class TestAntiCutClause:
    def test_anti_cut_appended_for_long_non_transition(self) -> None:
        shot = _make_shot(camera_movement="tracking", duration_sec=6, beat_type="action")
        result = format_runway_prompt(shot)
        assert "Continuous, seamless shot." in result

    def test_anti_cut_duration_5_no_beat_type(self) -> None:
        shot = _make_shot(camera_movement="pan", duration_sec=5, beat_type="")
        result = format_runway_prompt(shot)
        assert "Continuous, seamless shot." in result

    def test_no_anti_cut_for_transition_beat(self) -> None:
        shot = _make_shot(camera_movement="whip_pan", duration_sec=6, beat_type="transition")
        result = format_runway_prompt(shot)
        assert "Continuous, seamless shot." not in result

    def test_no_anti_cut_for_short_shot(self) -> None:
        shot = _make_shot(camera_movement="dolly_in", duration_sec=4, beat_type="")
        result = format_runway_prompt(shot)
        assert "Continuous, seamless shot." not in result


# ---------------------------------------------------------------------------
# PF-05 — R09: preservation clause injected
# ---------------------------------------------------------------------------


class TestR09PreservationClause:
    def test_preservation_clause_injected_when_ref_url_present(self) -> None:
        shot = _make_shot(
            camera_movement="static",
            duration_sec=4,
            action=_make_action(subject_id="john"),
        )
        reference_pack = ReferencePack(
            characters={
                "john": ReferenceSubject(
                    prompt="John, a tall man with short dark hair and a grey jacket",
                    reference_image_urls=["http://example.com/john_ref.png"],
                )
            }
        )
        enriched_shots, count = finalize_prompts([shot], reference_pack=reference_pack)
        assert count == 1
        assert "while maintaining the same facial features" in enriched_shots[0].prompt
        assert "John, a tall man with short dark hair" in enriched_shots[0].prompt

    def test_no_clause_when_ref_url_empty(self) -> None:
        shot = _make_shot(
            camera_movement="static",
            duration_sec=4,
            action=_make_action(subject_id="john"),
        )
        reference_pack = ReferencePack(
            characters={
                "john": ReferenceSubject(
                    prompt="John, a tall man",
                    reference_image_urls=[],   # no image → R09 must not trigger
                )
            }
        )
        enriched_shots, count = finalize_prompts([shot], reference_pack=reference_pack)
        assert "while maintaining" not in enriched_shots[0].prompt


# ---------------------------------------------------------------------------
# PF-06 — R09 absent when reference_pack=None (no regression)
# ---------------------------------------------------------------------------


class TestR09NoRegressionWithoutReferencePack:
    def test_finalize_without_reference_pack_unchanged(self) -> None:
        shot = _make_shot(camera_movement="static", duration_sec=4)
        enriched_shots, count = finalize_prompts([shot])
        assert count == 0
        assert enriched_shots[0].prompt == shot.prompt
        assert "while maintaining" not in enriched_shots[0].prompt
