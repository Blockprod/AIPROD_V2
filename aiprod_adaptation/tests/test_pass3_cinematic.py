"""
test_pass3_cinematic.py
=======================
Sprint 5 — Cinematic Pass 3 v3.1 tests.
Verifies: sequence selection, camera movement rules, physical layer overrides,
gaze overrides, emotional layer blocking, scene type overrides, continuity flag
injections, 180-degree guard, composition descriptions, lighting directives,
feasibility scoring, duration table, new Shot fields, and backward compat.
"""
from __future__ import annotations

import warnings
from typing import Any

import pytest

from aiprod_adaptation.core.pass3_shots import (
    _apply_180_degree_guard,
    _apply_emotional_layer_block,
    _apply_gaze_override,
    _apply_pacing,
    _apply_physical_layer_override,
    _compute_feasibility_score,
    _resolve_camera_movement,
    _resolve_composition,
    _resolve_duration,
    _resolve_framing_note,
    _resolve_lighting_directive,
    _resolve_rhythm_purpose,
    _resolve_shot_role,
    _resolve_shot_sequence,
    atomize_shots,
    simplify_shots,
)
from aiprod_adaptation.core.rules.cinematography_rules_v3 import (
    COMPOSITION_DESCRIPTIONS,
    CONTINUITY_FLAG_INJECTIONS,
    DURATION_TABLE,
    FEASIBILITY_BASE_SCORES,
    FEASIBILITY_DEFAULT_SCORE,
    FEASIBILITY_EXPLOSIVE_PENALTY,
    FEASIBILITY_STATIC_BONUS,
    FRAMING_NOTES,
    GAZE_DIRECTION_RULES,
    INTENSITY_SHOT_SEQUENCES,
    LIGHTING_DIRECTIVES,
    NEUTRAL_CUT_CAMERA_MOVEMENT,
    NEUTRAL_CUT_DURATION,
    NEUTRAL_CUT_SHOT_ROLE,
    NEUTRAL_CUT_SHOT_TYPE,
    OVER_SHOULDER_PAIR,
    PHYSICAL_LAYER_SHOT_OVERRIDES,
    SCENE_TYPE_CAMERA_OVERRIDES,
    SHOT_ROLE_DEFAULT,
    SHOT_ROLE_MAP,
    SHOT_SEQUENCE_DEFAULT_V3,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scene(**kwargs: Any) -> dict[str, Any]:
    """Build a minimal VisualScene dict for tests. Override any field with kwargs."""
    base: dict[str, Any] = {
        "scene_id":              kwargs.get("scene_id", "SCN_TEST"),
        "visual_actions":        kwargs.get("visual_actions", ["Character walks into the room and looks around."]),
        "action_units":          kwargs.get("action_units", []),
        "dialogues":             kwargs.get("dialogues", []),
        "characters":            kwargs.get("characters", ["Character"]),
        "location":              kwargs.get("location", "The Room"),
        "emotion":               kwargs.get("emotion", "neutral"),
        "pacing":                kwargs.get("pacing", "medium"),
        "time_of_day_visual":    kwargs.get("time_of_day_visual", "day"),
        "dominant_sound":        kwargs.get("dominant_sound", None),
        "beat_type":             kwargs.get("beat_type", None),
        "scene_tone":            kwargs.get("scene_tone", None),
        "emotional_beat_index":  kwargs.get("emotional_beat_index", None),
        "action_intensity":      kwargs.get("action_intensity", None),
        "emotional_layer":       kwargs.get("emotional_layer", None),
        "scene_type":            kwargs.get("scene_type", None),
        "continuity_flags":      kwargs.get("continuity_flags", []),
        "physical_actions":      kwargs.get("physical_actions", []),
        "body_language_states":  kwargs.get("body_language_states", []),
        "visual_invariants_applied": kwargs.get("visual_invariants_applied", []),
        "reference_location_id": kwargs.get("reference_location_id", None),
    }
    return base


def _multi_action_scene(**kwargs: Any) -> dict[str, Any]:
    """Scene with 4 visual actions to produce multiple shots."""
    actions = kwargs.pop("visual_actions", [
        "Kael steps into the corridor.",
        "He scans the empty hallway.",
        "His hand reaches for the door.",
        "He pushes through and disappears.",
    ])
    return _make_scene(visual_actions=actions, **kwargs)


# ===========================================================================
# 1. TestSequenceResolution
# ===========================================================================

class TestSequenceResolution:
    def test_climax_explosive_returns_expected_types(self) -> None:
        types, caps = _resolve_shot_sequence("climax", "explosive")
        assert types == ["medium", "close_up", "extreme_close_up", "insert", "wide"]
        assert caps  == [4, 3, 3, 3, 5]

    def test_dialogue_mid_starts_with_medium(self) -> None:
        types, _ = _resolve_shot_sequence("dialogue_scene", "mid")
        assert types[0] == "medium"

    def test_action_explosive_has_wide_first(self) -> None:
        types, _ = _resolve_shot_sequence("action", "explosive")
        assert types[0] == "wide"

    def test_exposition_subtle_has_long_caps(self) -> None:
        _, caps = _resolve_shot_sequence("exposition", "subtle")
        assert caps[0] >= 7

    def test_unknown_beat_type_returns_default(self) -> None:
        types, caps = _resolve_shot_sequence("unknown_beat", "explosive")
        assert types == SHOT_SEQUENCE_DEFAULT_V3[0]
        assert caps  == SHOT_SEQUENCE_DEFAULT_V3[1]

    def test_none_beat_type_returns_default(self) -> None:
        types, caps = _resolve_shot_sequence(None, None)
        assert types == SHOT_SEQUENCE_DEFAULT_V3[0]

    def test_none_intensity_falls_back_to_subtle(self) -> None:
        # beat_type known + None intensity → "subtle" fallback
        types_direct, _ = _resolve_shot_sequence("action", "subtle")
        types_none, _   = _resolve_shot_sequence("action", None)
        assert types_direct == types_none

    def test_transition_has_two_shots(self) -> None:
        types, _ = _resolve_shot_sequence("transition", "subtle")
        assert len(types) == 2

    def test_denouement_subtle_ends_with_medium(self) -> None:
        types, _ = _resolve_shot_sequence("denouement", "subtle")
        assert types[-1] == "medium"


# ===========================================================================
# 2. TestCameraMovementRules
# ===========================================================================

class TestCameraMovementRules:
    def test_wide_action_explosive_is_tracking(self) -> None:
        mv = _resolve_camera_movement("wide", "action", "explosive", None)
        assert mv == "tracking"

    def test_extreme_wide_always_static(self) -> None:
        for beat in ["action", "climax", "exposition", None]:
            mv = _resolve_camera_movement("extreme_wide", beat, "explosive", None)
            assert mv == "static", f"Expected static for extreme_wide/{beat}"

    def test_medium_dialogue_is_static(self) -> None:
        mv = _resolve_camera_movement("medium", "dialogue_scene", "mid", None)
        assert mv == "static"

    def test_close_up_climax_explosive_is_dolly_in(self) -> None:
        mv = _resolve_camera_movement("close_up", "climax", "explosive", None)
        assert mv == "dolly_in"

    def test_pov_always_handheld(self) -> None:
        mv = _resolve_camera_movement("pov", None, None, None)
        assert mv == "handheld"

    def test_insert_always_static(self) -> None:
        mv = _resolve_camera_movement("insert", "climax", "explosive", None)
        assert mv == "static"

    def test_over_shoulder_always_static(self) -> None:
        mv = _resolve_camera_movement("over_shoulder", "action", "explosive", None)
        assert mv == "static"

    def test_unknown_shot_type_returns_default(self) -> None:
        mv = _resolve_camera_movement("invisible_shot", None, None, None)
        assert mv == "static"

    def test_wide_epic_tone_is_crane_up(self) -> None:
        mv = _resolve_camera_movement("wide", None, None, "epic")
        assert mv == "crane_up"

    def test_medium_action_explosive_is_handheld(self) -> None:
        mv = _resolve_camera_movement("medium", "action", "explosive", None)
        assert mv == "handheld"


# ===========================================================================
# 3. TestPhysicalLayerOverrides
# ===========================================================================

class TestPhysicalLayerOverrides:
    def _make_pa(self, layer: str, intensity: str) -> dict[str, str]:
        return {"layer": layer, "intensity": intensity}

    def test_micro_expression_explosive_gives_xcu(self) -> None:
        stype, mv = _apply_physical_layer_override(
            self._make_pa("micro_expression", "explosive"), "medium", "static"
        )
        assert stype == "extreme_close_up"
        assert mv    == "static"

    def test_micro_expression_mid_gives_close_up(self) -> None:
        stype, mv = _apply_physical_layer_override(
            self._make_pa("micro_expression", "mid"), "wide", "pan"
        )
        assert stype == "close_up"

    def test_gaze_explosive_gives_pov_handheld(self) -> None:
        stype, mv = _apply_physical_layer_override(
            self._make_pa("gaze", "explosive"), "medium", "static"
        )
        assert stype == "pov"
        assert mv    == "handheld"

    def test_posture_mid_gives_medium_static(self) -> None:
        stype, mv = _apply_physical_layer_override(
            self._make_pa("posture", "mid"), "wide", "pan"
        )
        assert stype == "medium"
        assert mv    == "static"

    def test_breath_explosive_gives_xcu(self) -> None:
        stype, mv = _apply_physical_layer_override(
            self._make_pa("breath", "explosive"), "medium", "pan"
        )
        assert stype == "extreme_close_up"

    def test_gesture_mid_gives_close_up_static(self) -> None:
        stype, mv = _apply_physical_layer_override(
            self._make_pa("gesture", "mid"), "wide", "pan"
        )
        assert stype == "close_up"
        assert mv    == "static"

    def test_none_physical_action_returns_base(self) -> None:
        stype, mv = _apply_physical_layer_override(None, "medium", "static")
        assert stype == "medium"
        assert mv    == "static"

    def test_unknown_layer_returns_base(self) -> None:
        stype, mv = _apply_physical_layer_override(
            self._make_pa("unknown_layer", "mid"), "close_up", "dolly_in"
        )
        assert stype == "close_up"
        assert mv    == "dolly_in"


# ===========================================================================
# 4. TestGazeDirectionOverrides
# ===========================================================================

class TestGazeDirectionOverrides:
    def test_hunting_gives_pov_handheld(self) -> None:
        stype, mv = _apply_gaze_override("hunting", "medium", "static")
        assert stype == "pov"
        assert mv    == "handheld"

    def test_scanning_gives_wide_pan(self) -> None:
        stype, mv = _apply_gaze_override("scanning", "medium", "static")
        assert stype == "wide"
        assert mv    == "pan"

    def test_inward_gives_close_up_static(self) -> None:
        stype, mv = _apply_gaze_override("inward", "medium", "pan")
        assert stype == "close_up"
        assert mv    == "static"

    def test_avoidant_gives_medium_static(self) -> None:
        stype, mv = _apply_gaze_override("avoidant", "wide", "tracking")
        assert stype == "medium"
        assert mv    == "static"

    def test_forward_gives_medium_static(self) -> None:
        stype, mv = _apply_gaze_override("forward", "wide", "tracking")
        assert stype == "medium"
        assert mv    == "static"

    def test_unknown_gaze_returns_base(self) -> None:
        stype, mv = _apply_gaze_override("sideways", "close_up", "dolly_in")
        assert stype == "close_up"
        assert mv    == "dolly_in"

    def test_none_gaze_returns_base(self) -> None:
        stype, mv = _apply_gaze_override(None, "wide", "pan")
        assert stype == "wide"
        assert mv    == "pan"


# ===========================================================================
# 5. TestEmotionalLayerBlocking
# ===========================================================================

class TestEmotionalLayerBlocking:
    def test_surface_neutral_blocks_extreme_close_up(self) -> None:
        result = _apply_emotional_layer_block("surface_neutral", "extreme_close_up")
        assert result == "close_up"

    def test_surface_neutral_blocks_close_up_via_max(self) -> None:
        result = _apply_emotional_layer_block("surface_neutral", "close_up")
        # close_up is above max_shot_type="medium" in the order hierarchy
        assert result == "medium"

    def test_surface_neutral_keeps_medium(self) -> None:
        result = _apply_emotional_layer_block("surface_neutral", "medium")
        assert result == "medium"

    def test_erupting_does_not_block_xcu(self) -> None:
        result = _apply_emotional_layer_block("erupting", "extreme_close_up")
        assert result == "extreme_close_up"

    def test_none_layer_returns_unchanged(self) -> None:
        result = _apply_emotional_layer_block(None, "extreme_close_up")
        assert result == "extreme_close_up"

    def test_disguised_does_not_downgrade_close_up(self) -> None:
        result = _apply_emotional_layer_block("disguised", "close_up")
        assert result == "close_up"

    def test_surface_neutral_keeps_wide(self) -> None:
        result = _apply_emotional_layer_block("surface_neutral", "wide")
        assert result == "wide"


# ===========================================================================
# 6. TestSceneTypeOverrides
# ===========================================================================

class TestSceneTypeOverrides:
    def test_montage_duration_is_3(self) -> None:
        shots = simplify_shots([_make_scene(
            scene_type="montage",
            visual_actions=["Smoke rises.", "Rain falls.", "Clock ticks.", "Door slams.", "Silence."],
        )])
        assert all(s["duration_sec"] == 3 for s in shots)

    def test_montage_starts_with_insert_sequence(self) -> None:
        shots = simplify_shots([_make_scene(
            scene_type="montage",
            visual_actions=["Smoke rises.", "Rain falls.", "Clock ticks.", "Door slams.", "Silence."],
        )])
        # montage sequence: ["insert", "close_up", "wide", "insert", "close_up"]
        assert shots[0]["shot_type"] == "insert"

    def test_flashback_color_grade_hint(self) -> None:
        shots = simplify_shots([_make_scene(
            scene_type="flashback",
            visual_actions=["A child runs across a sunlit yard."],
        )])
        assert shots[0]["metadata"].get("color_grade_hint") == "desaturated"

    def test_cliffhanger_last_shot_is_xcu(self) -> None:
        shots = simplify_shots([_multi_action_scene(scene_type="cliffhanger")])
        last = shots[-1]
        assert last["shot_type"] == "extreme_close_up"

    def test_cliffhanger_last_shot_movement_dolly_in(self) -> None:
        shots = simplify_shots([_multi_action_scene(scene_type="cliffhanger")])
        assert shots[-1]["camera_movement"] == "dolly_in"

    def test_dream_color_grade_hint_cool(self) -> None:
        shots = simplify_shots([_make_scene(
            scene_type="dream",
            visual_actions=["She floats through corridors that bend like water."],
        )])
        assert shots[0]["metadata"].get("color_grade_hint") == "cool"


# ===========================================================================
# 7. TestContinuityFlagInjections
# ===========================================================================

class TestContinuityFlagInjections:
    def test_first_appearance_adds_shots_before(self) -> None:
        regular = simplify_shots([_make_scene(visual_actions=["Kael walks in."])])
        injected = simplify_shots([_make_scene(
            visual_actions=["Kael walks in."],
            continuity_flags=["FIRST_APPEARANCE"],
        )])
        assert len(injected) > len(regular)

    def test_first_appearance_first_shot_is_wide(self) -> None:
        shots = simplify_shots([_make_scene(
            visual_actions=["Kael walks in."],
            continuity_flags=["FIRST_APPEARANCE"],
        )])
        assert shots[0]["shot_type"] == "wide"

    def test_first_appearance_first_shot_role_establishing(self) -> None:
        shots = simplify_shots([_make_scene(
            visual_actions=["Kael walks in."],
            continuity_flags=["FIRST_APPEARANCE"],
        )])
        assert shots[0]["shot_role"] == "establishing"

    def test_cliffhanger_flag_adds_xcu_at_end(self) -> None:
        regular = simplify_shots([_make_scene(visual_actions=["He pauses."])])
        injected = simplify_shots([_make_scene(
            visual_actions=["He pauses."],
            continuity_flags=["CLIFFHANGER"],
        )])
        assert len(injected) > len(regular)
        assert injected[-1]["shot_type"] == "extreme_close_up"

    def test_act_break_adds_extreme_wide_at_end(self) -> None:
        shots = simplify_shots([_make_scene(
            visual_actions=["The last soldier falls."],
            continuity_flags=["ACT_BREAK"],
        )])
        assert shots[-1]["shot_type"] == "extreme_wide"

    def test_unknown_flag_does_not_crash(self) -> None:
        shots = simplify_shots([_make_scene(
            visual_actions=["She speaks."],
            continuity_flags=["NONEXISTENT_FLAG"],
        )])
        assert len(shots) >= 1


# ===========================================================================
# 8. Test180DegreeGuard
# ===========================================================================

class Test180DegreeGuard:
    def test_two_consecutive_over_shoulder_inserts_neutral(self) -> None:
        plan: list[dict[str, object]] = [
            {"_sequence_type": "over_shoulder", "_sequence_movement": "static",
             "_duration_cap": 5, "_shot_role": "coverage", "_framing_override": None},
            {"_sequence_type": "over_shoulder", "_sequence_movement": "static",
             "_duration_cap": 5, "_shot_role": "coverage", "_framing_override": None},
        ]
        result = _apply_180_degree_guard(plan)
        assert len(result) == 3
        neutral = result[1]
        assert neutral["_inject_type"] == NEUTRAL_CUT_SHOT_TYPE

    def test_neutral_cut_uses_medium_static(self) -> None:
        plan: list[dict[str, object]] = [
            {"_sequence_type": "over_shoulder", "_sequence_movement": "static",
             "_duration_cap": 5, "_shot_role": "coverage", "_framing_override": None},
            {"_sequence_type": "over_shoulder", "_sequence_movement": "static",
             "_duration_cap": 5, "_shot_role": "coverage", "_framing_override": None},
        ]
        result = _apply_180_degree_guard(plan)
        neutral = result[1]
        assert neutral["_inject_type"]     == "medium"
        assert neutral["_inject_movement"] == "static"
        assert neutral["_inject_duration"] == NEUTRAL_CUT_DURATION
        assert neutral["_inject_role"]     == NEUTRAL_CUT_SHOT_ROLE

    def test_non_over_shoulder_pair_not_affected(self) -> None:
        plan: list[dict[str, object]] = [
            {"_sequence_type": "medium", "_sequence_movement": "static",
             "_duration_cap": 5, "_shot_role": "coverage", "_framing_override": None},
            {"_sequence_type": "close_up", "_sequence_movement": "dolly_in",
             "_duration_cap": 4, "_shot_role": "reaction", "_framing_override": None},
        ]
        result = _apply_180_degree_guard(plan)
        assert len(result) == 2

    def test_single_over_shoulder_not_affected(self) -> None:
        plan: list[dict[str, object]] = [
            {"_sequence_type": "over_shoulder", "_sequence_movement": "static",
             "_duration_cap": 5, "_shot_role": "coverage", "_framing_override": None},
        ]
        result = _apply_180_degree_guard(plan)
        assert len(result) == 1


# ===========================================================================
# 9. TestCompositionDescriptions
# ===========================================================================

class TestCompositionDescriptions:
    def test_extreme_wide_mentions_environment(self) -> None:
        c = _resolve_composition("extreme_wide")
        assert "environment" in c.lower() or "horizon" in c.lower()

    def test_wide_mentions_full_figure(self) -> None:
        c = _resolve_composition("wide")
        assert "full" in c.lower() or "figure" in c.lower()

    def test_extreme_close_up_mentions_texture(self) -> None:
        c = _resolve_composition("extreme_close_up")
        assert "texture" in c.lower() or "frame" in c.lower()

    def test_over_shoulder_mentions_shoulder(self) -> None:
        c = _resolve_composition("over_shoulder")
        assert "shoulder" in c.lower()

    def test_insert_mentions_object(self) -> None:
        c = _resolve_composition("insert")
        assert "object" in c.lower() or "fill" in c.lower()

    def test_pov_mentions_eye_height(self) -> None:
        c = _resolve_composition("pov")
        assert "eye" in c.lower()

    def test_unknown_returns_default(self) -> None:
        c = _resolve_composition("magic_shot")
        from aiprod_adaptation.core.rules.cinematography_rules_v3 import COMPOSITION_DEFAULT
        assert c == COMPOSITION_DEFAULT

    def test_all_defined_keys_return_non_empty(self) -> None:
        for k in COMPOSITION_DESCRIPTIONS:
            c = _resolve_composition(k)
            assert c, f"Empty composition for {k}"


# ===========================================================================
# 10. TestLightingDirectives
# ===========================================================================

class TestLightingDirectives:
    def test_noir_night_has_cold_lateral(self) -> None:
        d = _resolve_lighting_directive("noir", "night")
        assert d is not None
        assert "cold" in d.lower() or "lateral" in d.lower()

    def test_golden_hour_dawn_has_warm(self) -> None:
        d = _resolve_lighting_directive("golden_hour", "dawn")
        assert d is not None
        assert "warm" in d.lower()

    def test_clinical_returns_overhead(self) -> None:
        d = _resolve_lighting_directive("clinical", "interior")
        assert d is not None
        assert "overhead" in d.lower() or "fluorescent" in d.lower()

    def test_default_day_fallback(self) -> None:
        d = _resolve_lighting_directive(None, None)
        assert d is not None
        assert len(d) > 5

    def test_none_tone_night_tod(self) -> None:
        d = _resolve_lighting_directive(None, "night")
        assert d is not None
        assert "night" in d.lower() or "practical" in d.lower() or "cool" in d.lower()

    def test_epic_day(self) -> None:
        d = _resolve_lighting_directive("epic", "day")
        assert d is not None
        assert "overhead" in d.lower() or "sun" in d.lower() or "high" in d.lower()


# ===========================================================================
# 11. TestFeasibilityScore
# ===========================================================================

class TestFeasibilityScore:
    def test_static_shot_gets_bonus(self) -> None:
        base = FEASIBILITY_BASE_SCORES.get(("medium", "static"), FEASIBILITY_DEFAULT_SCORE)
        score = _compute_feasibility_score("medium", "static", "mid")
        assert score >= base

    def test_explosive_intensity_reduces_score(self) -> None:
        normal  = _compute_feasibility_score("medium", "handheld", "mid")
        penalised = _compute_feasibility_score("medium", "handheld", "explosive")
        assert penalised == normal - FEASIBILITY_EXPLOSIVE_PENALTY

    def test_crane_up_has_low_base(self) -> None:
        score = _compute_feasibility_score("wide", "crane_up", "mid")
        assert score < 80

    def test_score_clamped_to_100(self) -> None:
        score = _compute_feasibility_score("medium", "static", None)
        assert score <= 100

    def test_score_clamped_to_zero_minimum(self) -> None:
        # Simulate extremely penalised score
        score = _compute_feasibility_score("extreme_wide", "crane_up", "explosive")
        assert score >= 0

    def test_unknown_combo_uses_default(self) -> None:
        score = _compute_feasibility_score("magic_shot", "flying", "mid")
        assert score == FEASIBILITY_DEFAULT_SCORE


# ===========================================================================
# 12. TestDurationTable
# ===========================================================================

class TestDurationTable:
    def test_climax_explosive_medium_is_4(self) -> None:
        d = _resolve_duration("climax", "explosive", "medium", 10, "medium")
        assert d == 4

    def test_exposition_subtle_extreme_wide_is_8(self) -> None:
        d = _resolve_duration("exposition", "subtle", "extreme_wide", 10, "medium")
        assert d == 8

    def test_fast_pacing_caps_to_5(self) -> None:
        # exposition subtle extreme_wide = 8, fast pacing → min(8, 5) = 5
        d = _resolve_duration("exposition", "subtle", "extreme_wide", 10, "fast")
        assert d == 5

    def test_slow_pacing_raises_floor_to_5(self) -> None:
        # climax explosive medium = 4, slow pacing → max(4, 5) = 5
        d = _resolve_duration("climax", "explosive", "medium", 10, "slow")
        assert d == 5

    def test_duration_capped_by_duration_cap(self) -> None:
        # exposition subtle extreme_wide = 8; cap=5 → 5
        d = _resolve_duration("exposition", "subtle", "extreme_wide", 5, "medium")
        assert d == 5

    def test_unknown_combo_uses_duration_cap(self) -> None:
        # No entry for (unknown_beat, mid, medium) → use duration_cap
        d = _resolve_duration("unknown_beat", "mid", "medium", 6, "medium")
        assert d == 6

    def test_duration_never_below_3(self) -> None:
        d = _resolve_duration("climax", "explosive", "insert", 1, "fast")
        assert d >= 3

    def test_duration_never_above_8(self) -> None:
        d = _resolve_duration("exposition", "subtle", "extreme_wide", 10, "slow")
        assert d <= 8

    def test_apply_pacing_fast(self) -> None:
        assert _apply_pacing(7, "fast") == 5

    def test_apply_pacing_slow(self) -> None:
        assert _apply_pacing(3, "slow") == 5

    def test_apply_pacing_medium_unchanged(self) -> None:
        assert _apply_pacing(6, "medium") == 6


# ===========================================================================
# 13. TestNewShotFields
# ===========================================================================

class TestNewShotFields:
    def _get_shot(self, **kwargs: Any) -> dict[str, Any]:
        return simplify_shots([_make_scene(**kwargs)])[0]

    def test_shot_role_present(self) -> None:
        shot = self._get_shot()
        assert "shot_role" in shot
        assert shot["shot_role"] is not None

    def test_composition_description_present(self) -> None:
        shot = self._get_shot()
        assert "composition_description" in shot
        assert isinstance(shot["composition_description"], str)
        assert len(shot["composition_description"]) > 5

    def test_lighting_directives_field_present(self) -> None:
        shot = self._get_shot()
        assert "lighting_directives" in shot
        # may be None if no lighting rule matches (unlikely with defaults)

    def test_framing_note_field_present(self) -> None:
        shot = self._get_shot()
        assert "framing_note" in shot

    def test_rhythm_purpose_present(self) -> None:
        shot = self._get_shot()
        assert "rhythm_purpose" in shot
        assert isinstance(shot["rhythm_purpose"], str)

    def test_visual_invariants_applied_is_list(self) -> None:
        shot = self._get_shot()
        assert isinstance(shot["visual_invariants_applied"], list)

    def test_feasibility_score_is_int(self) -> None:
        shot = self._get_shot()
        assert isinstance(shot["feasibility_score"], int)
        assert 0 <= shot["feasibility_score"] <= 100

    def test_reference_anchor_strength_is_float(self) -> None:
        shot = self._get_shot()
        assert isinstance(shot["reference_anchor_strength"], float)

    def test_reference_anchor_higher_with_ref_location(self) -> None:
        without_ref = self._get_shot()["reference_anchor_strength"]
        with_ref    = self._get_shot(reference_location_id="LOC_001")["reference_anchor_strength"]
        assert with_ref > without_ref

    def test_lighting_directives_with_scene_tone(self) -> None:
        shot = self._get_shot(scene_tone="noir", time_of_day_visual="night")
        assert shot["lighting_directives"] is not None
        assert "cold" in shot["lighting_directives"].lower() or "lateral" in shot["lighting_directives"].lower()


# ===========================================================================
# 14. TestBackwardCompat
# ===========================================================================

class TestBackwardCompat:
    def test_atomize_shots_emits_deprecation_warning(self) -> None:
        scene = _make_scene(visual_actions=["Marcus pauses."])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = atomize_shots([scene])
            assert any(issubclass(warn.category, DeprecationWarning) for warn in w)

    def test_atomize_shots_returns_same_as_simplify(self) -> None:
        scene = _make_scene(visual_actions=["Marcus pauses."])
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            via_old = atomize_shots([scene])
        via_new = simplify_shots([scene])
        assert len(via_old) == len(via_new)
        assert via_old[0]["shot_type"] == via_new[0]["shot_type"]

    def test_existing_scene_produces_valid_shots(self) -> None:
        shots = simplify_shots([_make_scene()])
        for s in shots:
            assert "shot_id"   in s
            assert "scene_id"  in s
            assert "prompt"    in s
            assert "shot_type" in s
            assert "duration_sec" in s
            assert s["duration_sec"] >= 3

    def test_metadata_has_required_keys(self) -> None:
        shots = simplify_shots([_make_scene()])
        for s in shots:
            assert "time_of_day_visual" in s["metadata"]
            assert "dominant_sound"     in s["metadata"]
            assert "depth_of_field"     in s["metadata"]

    def test_dominant_sound_dialogue_in_dialogue_scene(self) -> None:
        shot = simplify_shots([_make_scene(
            visual_actions=["Clara traces a line."],
            dialogues=["I found it."],
        )])[0]
        assert shot["metadata"]["dominant_sound"] == "dialogue"

    def test_empty_scenes_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            simplify_shots([])

    def test_empty_visual_actions_raises(self) -> None:
        with pytest.raises(ValueError, match="empty visual_actions"):
            simplify_shots([_make_scene(visual_actions=[])])

    def test_shot_id_format(self) -> None:
        shots = simplify_shots([_make_scene(scene_id="SCN_042")])
        assert shots[0]["shot_id"].startswith("SCN_042_SHOT_")

    def test_scene_id_propagated(self) -> None:
        shots = simplify_shots([_make_scene(scene_id="SCN_099")])
        assert all(s["scene_id"] == "SCN_099" for s in shots)