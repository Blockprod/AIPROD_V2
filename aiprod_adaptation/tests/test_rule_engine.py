"""
test_rule_engine.py — Sprint 7 test suite for the AIPROD_Cinematic Rule Engine.

Tests 7 functional areas:
  1. TestFieldResolution      — dot-path field resolver (None-safe)
  2. TestLeafConditions       — all FieldOperator variants
  3. TestCompoundConditions   — AND / OR / NOT nesting
  4. TestRuleEvaluator        — priority ordering, multi-rule evaluation
  5. TestConflictResolutionHard  — HARD conflict strategies
  6. TestConflictResolutionSoft  — SOFT conflict strategies
  7. TestFeasibilityEngine    — invariant-aware score computation
  8. TestBuiltinRules         — catalogue integrity + end-to-end scenario

All tests are deterministic / pure-Python.  No LLM, no network, no filesystem I/O.
"""

from __future__ import annotations

from typing import Any

import pytest

from aiprod_adaptation.core.feasibility.engine import (
    _ARCHITECTURE_MOVEMENT_PENALTY,
    _HEIGHT_MOVEMENT_PENALTY,
    _SHOT_DEPTH_PENALTY,
    FeasibilityEngine,
)
from aiprod_adaptation.core.rule_engine.builtin_rules import BUILTIN_RULES, make_default_evaluator
from aiprod_adaptation.core.rule_engine.conflict_resolver import ConflictResolutionEngine
from aiprod_adaptation.core.rule_engine.evaluator import RuleEvaluator, _get_field, _resolve_field
from aiprod_adaptation.core.rule_engine.models import (
    CompoundCondition,
    ConditionOperator,
    ConflictRecord,
    ConflictType,
    EvalContext,
    FieldOperator,
    LeafCondition,
    ResolutionStrategy,
    RuleAction,
    RuleEvalResult,
    RuleSpec,
)
from aiprod_adaptation.core.rules.cinematography_rules_v3 import (
    FEASIBILITY_BASE_SCORES,
    FEASIBILITY_DEFAULT_SCORE,
    FEASIBILITY_EXPLOSIVE_PENALTY,
    FEASIBILITY_STATIC_BONUS,
)
from aiprod_adaptation.models.schema import ActionSpec, Scene, Shot

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

try:
    from aiprod_adaptation.core.reference_image.models import (
        CameraHeightClass,
        ColorSwatch,
        DepthLayerEstimate,
        LightingAnalysis,
        LightingDirectionH,
        LightingDirectionV,
        VisualInvariants,
    )
    _HAS_REF_MODELS = True
except ImportError:
    _HAS_REF_MODELS = False

_ref_models_required = pytest.mark.skipif(
    not _HAS_REF_MODELS, reason="reference_image models unavailable"
)


def _make_color_swatch(rank: int = 1, hex_code: str = "#aabbcc") -> Any:
    return ColorSwatch(
        rank=rank,
        hex_code=hex_code,
        lab=[50.0, 0.0, 0.0],
        coverage_pct=100.0 / rank,
        variability="invariant",
    )


def _make_visual_invariants(
    camera_height_class: Any = None,
    dominant_layer: str = "midground",
    key_direction_h: Any = None,
    key_direction_v: Any = None,
) -> Any:
    if not _HAS_REF_MODELS:
        return None
    return VisualInvariants(
        source_path="/test/ref.jpg",
        width_px=1920,
        height_px=1080,
        aspect_ratio="16:9",
        subject_coverage_pct=25.0,
        luminance_fingerprint="deadbeef01234567",
        lighting=LightingAnalysis(
            key_direction_h=key_direction_h or LightingDirectionH.LEFT,
            key_direction_v=key_direction_v or LightingDirectionV.TOP,
            color_temperature_k=3200,
            intensity_l95=70.0,
            contrast_std_l=18.0,
            highlight_pct=4.0,
            shadow_pct=12.0,
        ),
        camera_height_class=camera_height_class or CameraHeightClass.EYE_LEVEL,
        depth_layers=DepthLayerEstimate(
            gradient_mean_foreground=50.0,
            gradient_mean_midground=80.0,
            gradient_mean_background=20.0,
            dominant_layer=dominant_layer,
        ),
        palette=[_make_color_swatch()],
    )


def _action(subject_id: str = "char_a") -> ActionSpec:
    return ActionSpec(
        subject_id=subject_id,
        action_type="moves",
        target=None,
        modifiers=[],
        location_id="loc_x",
        camera_intent="static",
        source_text="moves forward",
    )


def _shot(
    shot_id: str = "S01",
    scene_id: str = "SC01",
    shot_type: str = "medium",
    camera_movement: str = "static",
    duration_sec: int = 5,
    feasibility_score: int = 100,
    prompt: str = "A shot.",
    lighting_directives: str | None = None,
    visual_invariants_applied: list[str] | None = None,
) -> Shot:
    return Shot(
        shot_id=shot_id,
        scene_id=scene_id,
        prompt=prompt,
        duration_sec=duration_sec,
        emotion="neutral",
        shot_type=shot_type,
        camera_movement=camera_movement,
        action=_action(),
        metadata={},
        feasibility_score=feasibility_score,
        lighting_directives=lighting_directives,
        visual_invariants_applied=visual_invariants_applied or [],
    )


def _scene(
    scene_id: str = "SC01",
    beat_type: str | None = None,
    scene_tone: str | None = None,
) -> Scene:
    return Scene(
        scene_id=scene_id,
        characters=["Alice"],
        location="Office",
        visual_actions=["walks"],
        dialogues=["Hello"],
        emotion="neutral",
        beat_type=beat_type,
        scene_tone=scene_tone,
    )


def _ctx(
    shot: Shot | None = None,
    scene: Scene | None = None,
    ref_invariants: Any = None,
    episode_index: int = 1,
) -> EvalContext:
    return EvalContext(
        shot=shot or _shot(),
        scene=scene or _scene(),
        visual_bible=None,
        ref_invariants=ref_invariants,
        episode_id="EP01",
        episode_index=episode_index,
    )


def _leaf(field: str, op: FieldOperator, value: Any = None, values: list[Any] | None = None) -> LeafCondition:
    return LeafCondition(field=field, op=op, value=value, values=values or [])


def _rule(
    rule_id: str,
    priority: int,
    condition: LeafCondition | CompoundCondition,
    target_field: str = "shot.camera_movement",
    conflict_type: ConflictType = ConflictType.SOFT,
) -> RuleSpec:
    return RuleSpec(
        id=rule_id,
        priority=priority,
        description="Test rule",
        condition=condition,
        action=RuleAction(type="DOWNGRADE", target_field=target_field),
        conflict_type=conflict_type,
    )


# ===========================================================================
# 1. TestFieldResolution
# ===========================================================================


class TestFieldResolution:
    """Tests for _get_field and _resolve_field helpers."""

    def test_get_field_single_attr(self):
        shot = _shot(feasibility_score=42)
        assert _get_field(shot, "feasibility_score") == 42

    def test_get_field_nested_attr(self):
        shot = _shot()
        # action.subject_id
        result = _get_field(shot, "action.subject_id")
        assert result == "char_a"

    def test_get_field_dict_key(self):
        d = {"a": {"b": 99}}
        assert _get_field(d, "a.b") == 99

    def test_get_field_missing_returns_none(self):
        shot = _shot()
        assert _get_field(shot, "nonexistent_field") is None

    def test_get_field_none_root_returns_none(self):
        assert _get_field(None, "any.path") is None

    def test_get_field_empty_path_returns_root(self):
        shot = _shot()
        assert _get_field(shot, "") is shot

    def test_resolve_field_shot_prefix(self):
        shot = _shot(feasibility_score=77)
        ctx = _ctx(shot=shot)
        result = _resolve_field("shot.feasibility_score", ctx)
        assert result == 77

    def test_resolve_field_scene_prefix(self):
        scene = _scene(beat_type="climax")
        ctx = _ctx(scene=scene)
        result = _resolve_field("scene.beat_type", ctx)
        assert result == "climax"

    def test_resolve_field_episode_index(self):
        ctx = _ctx(episode_index=7)
        assert _resolve_field("episode_index", ctx) == 7

    def test_resolve_field_ref_invariants_none(self):
        ctx = _ctx(ref_invariants=None)
        result = _resolve_field("ref_invariants.camera_height_class", ctx)
        assert result is None

    @_ref_models_required
    def test_resolve_field_ref_invariants_nested(self):
        inv = _make_visual_invariants(
            dominant_layer="background"
        )
        ctx = _ctx(ref_invariants=inv)
        result = _resolve_field("ref_invariants.depth_layers.dominant_layer", ctx)
        assert result == "background"


# ===========================================================================
# 2. TestLeafConditions
# ===========================================================================


class TestLeafConditions:
    """Tests for all FieldOperator variants."""

    def test_exists_true(self):
        shot = _shot(lighting_directives="hard light")
        ctx = _ctx(shot=shot)
        cond = _leaf("shot.lighting_directives", FieldOperator.EXISTS)
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        results = evaluator.evaluate(ctx)
        assert results[0].matched is True

    def test_exists_false_when_none(self):
        ctx = _ctx(shot=_shot(lighting_directives=None))
        cond = _leaf("shot.lighting_directives", FieldOperator.EXISTS)
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is False

    def test_not_exists(self):
        ctx = _ctx(shot=_shot(lighting_directives=None))
        cond = _leaf("shot.lighting_directives", FieldOperator.NOT_EXISTS)
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_eq_true(self):
        ctx = _ctx(shot=_shot(camera_movement="pan"))
        cond = _leaf("shot.camera_movement", FieldOperator.EQ, value="pan")
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_eq_false(self):
        ctx = _ctx(shot=_shot(camera_movement="pan"))
        cond = _leaf("shot.camera_movement", FieldOperator.EQ, value="static")
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is False

    def test_neq_true(self):
        ctx = _ctx(shot=_shot(camera_movement="pan"))
        cond = _leaf("shot.camera_movement", FieldOperator.NEQ, value="static")
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_lt_true(self):
        ctx = _ctx(shot=_shot(feasibility_score=30))
        cond = _leaf("shot.feasibility_score", FieldOperator.LT, value=40)
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_lt_false_equal(self):
        ctx = _ctx(shot=_shot(feasibility_score=40))
        cond = _leaf("shot.feasibility_score", FieldOperator.LT, value=40)
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is False

    def test_lte_true_equal(self):
        ctx = _ctx(shot=_shot(feasibility_score=40))
        cond = _leaf("shot.feasibility_score", FieldOperator.LTE, value=40)
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_gt_true(self):
        ctx = _ctx(shot=_shot(feasibility_score=80))
        cond = _leaf("shot.feasibility_score", FieldOperator.GT, value=70)
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_gte_true_equal(self):
        ctx = _ctx(shot=_shot(feasibility_score=70))
        cond = _leaf("shot.feasibility_score", FieldOperator.GTE, value=70)
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_in_true(self):
        ctx = _ctx(shot=_shot(camera_movement="pan"))
        cond = _leaf("shot.camera_movement", FieldOperator.IN, values=["pan", "static"])
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_not_in_true(self):
        ctx = _ctx(shot=_shot(camera_movement="tracking"))
        cond = _leaf("shot.camera_movement", FieldOperator.NOT_IN, values=["pan", "static"])
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_contains_true(self):
        ctx = _ctx(shot=_shot(prompt="lit from the right side"))
        cond = _leaf("shot.prompt", FieldOperator.CONTAINS, value="from the right")
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_contains_any_true(self):
        ctx = _ctx(shot=_shot(lighting_directives="right key light"))
        cond = _leaf("shot.lighting_directives", FieldOperator.CONTAINS_ANY,
                     values=["right key", "left key"])
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_matches_re_true(self):
        ctx = _ctx(shot=_shot(lighting_directives="hard light from the RIGHT"))
        cond = _leaf("shot.lighting_directives", FieldOperator.MATCHES_RE, value=r"\bright\b")
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_matches_re_false_no_word_boundary(self):
        ctx = _ctx(shot=_shot(lighting_directives="brightening effect"))
        cond = _leaf("shot.lighting_directives", FieldOperator.MATCHES_RE, value=r"\bright\b")
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is False

    def test_none_value_with_none_field_not_matches(self):
        """EXISTS on None field → matched=False; NEQ on None != 'static' → True."""
        ctx = _ctx(shot=_shot(lighting_directives=None))
        cond = _leaf("shot.lighting_directives", FieldOperator.EQ, value="hard light")
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is False


# ===========================================================================
# 3. TestCompoundConditions
# ===========================================================================


class TestCompoundConditions:
    """Tests for AND / OR / NOT compound conditions."""

    def test_and_both_true(self):
        ctx = _ctx(shot=_shot(feasibility_score=30, camera_movement="pan"))
        cond = CompoundCondition(
            operator=ConditionOperator.AND,
            operands=[
                _leaf("shot.feasibility_score", FieldOperator.LT, value=40),
                _leaf("shot.camera_movement", FieldOperator.NEQ, value="static"),
            ],
        )
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_and_one_false(self):
        ctx = _ctx(shot=_shot(feasibility_score=80, camera_movement="pan"))
        cond = CompoundCondition(
            operator=ConditionOperator.AND,
            operands=[
                _leaf("shot.feasibility_score", FieldOperator.LT, value=40),
                _leaf("shot.camera_movement", FieldOperator.NEQ, value="static"),
            ],
        )
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is False

    def test_or_one_true(self):
        ctx = _ctx(shot=_shot(feasibility_score=80, camera_movement="crane_up"))
        cond = CompoundCondition(
            operator=ConditionOperator.OR,
            operands=[
                _leaf("shot.feasibility_score", FieldOperator.LT, value=40),
                _leaf("shot.camera_movement", FieldOperator.EQ, value="crane_up"),
            ],
        )
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_or_both_false(self):
        ctx = _ctx(shot=_shot(feasibility_score=80, camera_movement="static"))
        cond = CompoundCondition(
            operator=ConditionOperator.OR,
            operands=[
                _leaf("shot.feasibility_score", FieldOperator.LT, value=40),
                _leaf("shot.camera_movement", FieldOperator.EQ, value="crane_up"),
            ],
        )
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is False

    def test_not_negates_true(self):
        ctx = _ctx(shot=_shot(camera_movement="static"))
        cond = CompoundCondition(
            operator=ConditionOperator.NOT,
            operands=[_leaf("shot.camera_movement", FieldOperator.EQ, value="static")],
        )
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is False

    def test_not_negates_false(self):
        ctx = _ctx(shot=_shot(camera_movement="pan"))
        cond = CompoundCondition(
            operator=ConditionOperator.NOT,
            operands=[_leaf("shot.camera_movement", FieldOperator.EQ, value="static")],
        )
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True

    def test_nested_and_or(self):
        # (feasibility < 40 AND movement != static) OR shot_type == wide
        ctx = _ctx(shot=_shot(feasibility_score=80, camera_movement="static", shot_type="wide"))
        cond = CompoundCondition(
            operator=ConditionOperator.OR,
            operands=[
                CompoundCondition(
                    operator=ConditionOperator.AND,
                    operands=[
                        _leaf("shot.feasibility_score", FieldOperator.LT, value=40),
                        _leaf("shot.camera_movement", FieldOperator.NEQ, value="static"),
                    ],
                ),
                _leaf("shot.shot_type", FieldOperator.EQ, value="wide"),
            ],
        )
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        assert evaluator.evaluate(ctx)[0].matched is True


# ===========================================================================
# 4. TestRuleEvaluator
# ===========================================================================


class TestRuleEvaluator:
    """Tests for RuleEvaluator ordering, evaluation, and ConflictRecord population."""

    def test_rules_sorted_by_priority(self):
        r1 = _rule("Z-rule", 3, _leaf("shot.camera_movement", FieldOperator.EXISTS))
        r2 = _rule("A-rule", 1, _leaf("shot.camera_movement", FieldOperator.EXISTS))
        evaluator = RuleEvaluator([r1, r2])
        # First rule in the sorted tuple must be priority 1
        assert evaluator.rules[0].id == "A-rule"
        assert evaluator.rules[1].id == "Z-rule"

    def test_rules_sorted_by_id_within_same_priority(self):
        r1 = _rule("Z-first", 2, _leaf("shot.camera_movement", FieldOperator.EXISTS))
        r2 = _rule("A-first", 2, _leaf("shot.camera_movement", FieldOperator.EXISTS))
        evaluator = RuleEvaluator([r1, r2])
        assert evaluator.rules[0].id == "A-first"

    def test_unmatched_rule_has_matched_false(self):
        ctx = _ctx(shot=_shot(feasibility_score=90))
        cond = _leaf("shot.feasibility_score", FieldOperator.LT, value=40)
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        results = evaluator.evaluate(ctx)
        assert results[0].matched is False

    def test_matched_rule_populates_conflict(self):
        ctx = _ctx(shot=_shot(feasibility_score=30, camera_movement="pan"))
        cond = _leaf("shot.feasibility_score", FieldOperator.LT, value=40)
        evaluator = RuleEvaluator([_rule("R1", 1, cond, conflict_type=ConflictType.HARD)])
        results = evaluator.evaluate(ctx)
        assert results[0].matched is True
        assert results[0].conflict is not None
        assert results[0].conflict.rule_id == "R1"
        assert results[0].conflict.conflict_type == ConflictType.HARD

    def test_conflict_shot_id_populated(self):
        ctx = _ctx(shot=_shot(shot_id="MY_SHOT", feasibility_score=10))
        cond = _leaf("shot.feasibility_score", FieldOperator.LT, value=40)
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        results = evaluator.evaluate(ctx)
        assert results[0].conflict.shot_id == "MY_SHOT"  # type: ignore[union-attr]

    def test_all_rules_evaluated_even_when_early_match(self):
        ctx = _ctx(shot=_shot(feasibility_score=30, camera_movement="pan"))
        cond1 = _leaf("shot.feasibility_score", FieldOperator.LT, value=40)
        cond2 = _leaf("shot.camera_movement", FieldOperator.EQ, value="pan")
        evaluator = RuleEvaluator([_rule("R1", 1, cond1), _rule("R2", 2, cond2)])
        results = evaluator.evaluate(ctx)
        assert len(results) == 2

    def test_empty_rules_returns_empty(self):
        ctx = _ctx()
        evaluator = RuleEvaluator([])
        assert evaluator.evaluate(ctx) == []

    def test_results_order_matches_rule_order(self):
        r1 = _rule("A", 1, _leaf("shot.camera_movement", FieldOperator.EXISTS))
        r2 = _rule("B", 2, _leaf("shot.camera_movement", FieldOperator.EXISTS))
        evaluator = RuleEvaluator([r2, r1])  # intentionally reversed
        results = evaluator.evaluate(_ctx())
        assert results[0].rule_id == "A"
        assert results[1].rule_id == "B"

    def test_matched_conflict_has_current_value(self):
        ctx = _ctx(shot=_shot(camera_movement="crane_up"))
        cond = _leaf("shot.camera_movement", FieldOperator.EQ, value="crane_up")
        evaluator = RuleEvaluator([
            _rule("R1", 3, cond, target_field="shot.camera_movement")
        ])
        results = evaluator.evaluate(ctx)
        assert results[0].conflict.current_value == "crane_up"  # type: ignore[union-attr]

    def test_unmatched_has_none_conflict(self):
        ctx = _ctx(shot=_shot(camera_movement="static"))
        cond = _leaf("shot.camera_movement", FieldOperator.EQ, value="crane_up")
        evaluator = RuleEvaluator([_rule("R1", 1, cond)])
        results = evaluator.evaluate(ctx)
        assert results[0].conflict is None


# ===========================================================================
# 5. TestConflictResolutionHard
# ===========================================================================


class TestConflictResolutionHard:
    """Tests for HARD conflict resolution strategies."""

    def _conflict(
        self,
        rule_id: str,
        priority: int,
        field_path: str,
        shot_id: str = "S01",
    ) -> ConflictRecord:
        return ConflictRecord(
            rule_id=rule_id,
            conflict_type=ConflictType.HARD,
            priority=priority,
            shot_id=shot_id,
            field_path=field_path,
        )

    def _result(
        self,
        rule_id: str,
        priority: int,
        field_path: str,
    ) -> RuleEvalResult:
        return RuleEvalResult(
            rule_id=rule_id,
            matched=True,
            conflict_type=ConflictType.HARD,
            conflict=self._conflict(rule_id, priority, field_path),
        )

    def test_hard_downgrade_crane_up_to_tilt_up(self):
        """crane_up → tilt_up (overhead context → crane_up is incompatible)."""
        if not _HAS_REF_MODELS:
            pytest.skip("reference_image models unavailable")
        shot = _shot(camera_movement="crane_up")
        inv = _make_visual_invariants(camera_height_class=CameraHeightClass.OVERHEAD)
        ctx = _ctx(shot=shot, ref_invariants=inv)
        engine = ConflictResolutionEngine()
        result = self._result("SPC-01", 3, "shot.camera_movement")
        resolved, records = engine.resolve(shot, ctx, [result])
        assert resolved.camera_movement == "tilt_up"
        assert records[0].was_modified is True
        assert records[0].strategy == ResolutionStrategy.DOWNGRADE_MOVEMENT

    def test_hard_downgrade_crane_up_no_invariants_uses_chain(self):
        """Without ref_invariants, crane_up → tilt_up via chain."""
        shot = _shot(camera_movement="crane_up")
        ctx = _ctx(shot=shot, ref_invariants=None)
        engine = ConflictResolutionEngine()
        result = self._result("SPC-01", 3, "shot.camera_movement")
        resolved, records = engine.resolve(shot, ctx, [result])
        assert resolved.camera_movement == "tilt_up"

    def test_hard_downgrade_crane_down_to_tilt_down(self):
        shot = _shot(camera_movement="crane_down")
        ctx = _ctx(shot=shot)
        engine = ConflictResolutionEngine()
        result = self._result("SPC-03", 3, "shot.camera_movement")
        resolved, _ = engine.resolve(shot, ctx, [result])
        assert resolved.camera_movement == "tilt_down"

    def test_hard_downgrade_tracking_to_follow(self):
        shot = _shot(camera_movement="tracking")
        ctx = _ctx(shot=shot)
        engine = ConflictResolutionEngine()
        result = self._result("R1", 3, "shot.camera_movement")
        resolved, _ = engine.resolve(shot, ctx, [result])
        assert resolved.camera_movement == "follow"

    def test_hard_downgrade_whip_pan_to_pan(self):
        shot = _shot(camera_movement="whip_pan")
        ctx = _ctx(shot=shot)
        engine = ConflictResolutionEngine()
        result = self._result("R1", 3, "shot.camera_movement")
        resolved, _ = engine.resolve(shot, ctx, [result])
        assert resolved.camera_movement == "pan"

    def test_hard_downgrade_static_no_change(self):
        """static is already the minimum — no modification."""
        shot = _shot(camera_movement="static")
        ctx = _ctx(shot=shot)
        engine = ConflictResolutionEngine()
        result = self._result("R1", 3, "shot.camera_movement")
        resolved, records = engine.resolve(shot, ctx, [result])
        assert resolved.camera_movement == "static"
        assert records[0].was_modified is False

    def test_hard_fix_lighting_directive_from_ref(self):
        """lighting_directives conflicting with ref key direction → replaced."""
        if not _HAS_REF_MODELS:
            pytest.skip("reference_image models unavailable")
        shot = _shot(lighting_directives="Motivated from the right, hard sidelight.")
        inv = _make_visual_invariants(
            key_direction_h=LightingDirectionH.LEFT,
            key_direction_v=LightingDirectionV.TOP,
        )
        ctx = _ctx(shot=shot, ref_invariants=inv)
        engine = ConflictResolutionEngine()
        result = self._result("LIT-01", 2, "shot.lighting_directives")
        resolved, records = engine.resolve(shot, ctx, [result])
        assert resolved.lighting_directives == "Key light: top-left"
        assert records[0].strategy == ResolutionStrategy.STRIP_AND_REPLACE
        assert records[0].was_modified is True

    def test_hard_fix_lighting_no_ref_no_change(self):
        """Without ref_invariants, lighting fix falls back to no-action."""
        shot = _shot(lighting_directives="Hard light from the right.")
        ctx = _ctx(shot=shot, ref_invariants=None)
        engine = ConflictResolutionEngine()
        result = self._result("LIT-01", 2, "shot.lighting_directives")
        resolved, records = engine.resolve(shot, ctx, [result])
        assert records[0].was_modified is False

    def test_hard_flag_and_annotate_unknown_field(self):
        """HARD conflict on unknown field → annotate visual_invariants_applied."""
        shot = _shot()
        ctx = _ctx(shot=shot)
        engine = ConflictResolutionEngine()
        result = self._result("CHR-02", 1, "shot.prompt")
        resolved, records = engine.resolve(shot, ctx, [result])
        assert "HARD-CONFLICT:CHR-02" in resolved.visual_invariants_applied
        assert records[0].strategy == ResolutionStrategy.FLAG_AND_PASS

    def test_hard_flag_idempotent(self):
        """Second HARD flag on the same shot doesn't duplicate the entry."""
        shot = _shot(visual_invariants_applied=["HARD-CONFLICT:CHR-02"])
        ctx = _ctx(shot=shot)
        engine = ConflictResolutionEngine()
        result = self._result("CHR-02", 1, "shot.prompt")
        resolved, records = engine.resolve(shot, ctx, [result])
        assert resolved.visual_invariants_applied.count("HARD-CONFLICT:CHR-02") == 1
        assert records[0].was_modified is False

    def test_hard_before_soft_at_same_priority(self):
        """HARD conflicts resolved before SOFT at the same priority level."""
        shot = _shot(camera_movement="tracking")
        ctx = _ctx(shot=shot)
        engine = ConflictResolutionEngine()
        hard_result = RuleEvalResult(
            rule_id="R_HARD",
            matched=True,
            conflict_type=ConflictType.HARD,
            conflict=ConflictRecord(
                rule_id="R_HARD",
                conflict_type=ConflictType.HARD,
                priority=3,
                shot_id="S01",
                field_path="shot.camera_movement",
            ),
        )
        soft_result = RuleEvalResult(
            rule_id="R_SOFT",
            matched=True,
            conflict_type=ConflictType.SOFT,
            conflict=ConflictRecord(
                rule_id="R_SOFT",
                conflict_type=ConflictType.SOFT,
                priority=3,
                shot_id="S01",
                field_path="shot.camera_movement",
            ),
        )
        # Pass soft first to verify sorting
        _, records = engine.resolve(shot, ctx, [soft_result, hard_result])
        # HARD record should appear first
        assert records[0].conflict.rule_id == "R_HARD"

    def test_original_shot_not_mutated(self):
        """Input shot must remain unchanged after resolve()."""
        shot = _shot(camera_movement="crane_up")
        ctx = _ctx(shot=shot)
        engine = ConflictResolutionEngine()
        hard_result = RuleEvalResult(
            rule_id="R1",
            matched=True,
            conflict_type=ConflictType.HARD,
            conflict=ConflictRecord(
                rule_id="R1",
                conflict_type=ConflictType.HARD,
                priority=3,
                shot_id=shot.shot_id,
                field_path="shot.camera_movement",
            ),
        )
        resolved, _ = engine.resolve(shot, ctx, [hard_result])
        assert shot.camera_movement == "crane_up"  # original unchanged
        assert resolved.camera_movement != "crane_up"


# ===========================================================================
# 6. TestConflictResolutionSoft
# ===========================================================================


class TestConflictResolutionSoft:
    """Tests for SOFT conflict strategies."""

    def _soft_result(self, rule_id: str, field_path: str, priority: int = 4) -> RuleEvalResult:
        return RuleEvalResult(
            rule_id=rule_id,
            matched=True,
            conflict_type=ConflictType.SOFT,
            conflict=ConflictRecord(
                rule_id=rule_id,
                conflict_type=ConflictType.SOFT,
                priority=priority,
                shot_id="S01",
                field_path=field_path,
            ),
        )

    def test_soft_compromise_movement_downgrade(self):
        shot = _shot(camera_movement="dolly_in")
        ctx = _ctx(shot=shot)
        engine = ConflictResolutionEngine()
        result = self._soft_result("CMP-01", "shot.camera_movement")
        resolved, records = engine.resolve(shot, ctx, [result])
        assert resolved.camera_movement == "follow"  # dolly_in → follow
        assert records[0].strategy == ResolutionStrategy.COMPROMISE
        assert records[0].was_modified is True

    def test_soft_static_no_compromise(self):
        """static is already lowest — FLAG_AND_PASS."""
        shot = _shot(camera_movement="static")
        ctx = _ctx(shot=shot)
        engine = ConflictResolutionEngine()
        result = self._soft_result("CMP-01", "shot.camera_movement")
        resolved, records = engine.resolve(shot, ctx, [result])
        assert resolved.camera_movement == "static"
        assert records[0].strategy == ResolutionStrategy.FLAG_AND_PASS

    def test_soft_narrative_yields_annotates(self):
        shot = _shot()
        ctx = _ctx(shot=shot)
        engine = ConflictResolutionEngine()
        result = self._soft_result("NAR-01", "shot.visual_invariants_applied")
        resolved, records = engine.resolve(shot, ctx, [result])
        assert "SOFT-CONFLICT:NAR-01" in resolved.visual_invariants_applied
        assert records[0].strategy == ResolutionStrategy.NARRATIVE_YIELDS

    def test_soft_narrative_yields_idempotent(self):
        shot = _shot(visual_invariants_applied=["SOFT-CONFLICT:NAR-01"])
        ctx = _ctx(shot=shot)
        engine = ConflictResolutionEngine()
        result = self._soft_result("NAR-01", "shot.visual_invariants_applied")
        resolved, records = engine.resolve(shot, ctx, [result])
        assert resolved.visual_invariants_applied.count("SOFT-CONFLICT:NAR-01") == 1
        assert records[0].was_modified is False

    def test_no_conflicts_returns_original_shot(self):
        shot = _shot()
        ctx = _ctx(shot=shot)
        engine = ConflictResolutionEngine()
        resolved, records = engine.resolve(shot, ctx, [])
        assert resolved is shot
        assert records == []

    def test_unmatched_results_ignored(self):
        """Unmatched RuleEvalResults (matched=False) are ignored by the resolver."""
        shot = _shot(camera_movement="crane_up")
        ctx = _ctx(shot=shot)
        engine = ConflictResolutionEngine()
        unmatched = RuleEvalResult(rule_id="R1", matched=False, conflict_type=ConflictType.NONE)
        resolved, records = engine.resolve(shot, ctx, [unmatched])
        assert resolved is shot
        assert records == []


# ===========================================================================
# 7. TestFeasibilityEngine
# ===========================================================================


class TestFeasibilityEngine:
    """Tests for FeasibilityEngine invariant-aware scoring."""

    def test_base_score_no_invariants(self):
        """Without ref_invariants, score = base + static_bonus (for static movement)."""
        engine = FeasibilityEngine()
        shot = _shot(shot_type="medium", camera_movement="static")
        expected_base = FEASIBILITY_BASE_SCORES.get(("medium", "static"), FEASIBILITY_DEFAULT_SCORE)
        expected = min(100, expected_base + FEASIBILITY_STATIC_BONUS)
        assert engine.compute(shot, None) == expected

    def test_score_in_range(self):
        """Score is always [0, 100]."""
        engine = FeasibilityEngine()
        for st, mv in [("wide", "crane_up"), ("medium", "static"), ("extreme_close_up", "handheld")]:
            if not _HAS_REF_MODELS:
                score = engine.compute(_shot(shot_type=st, camera_movement=mv), None)
            else:
                inv = _make_visual_invariants(camera_height_class=CameraHeightClass.OVERHEAD)
                score = engine.compute(_shot(shot_type=st, camera_movement=mv), inv)
            assert 0 <= score <= 100, f"out-of-range for ({st}, {mv}): {score}"

    @_ref_models_required
    def test_overhead_crane_up_penalised(self):
        """crane_up with overhead reference → lower score than without reference."""
        engine = FeasibilityEngine()
        shot = _shot(shot_type="wide", camera_movement="crane_up")
        score_no_inv = engine.compute(shot, None)
        inv = _make_visual_invariants(camera_height_class=CameraHeightClass.OVERHEAD)
        score_with_inv = engine.compute(shot, inv)
        assert score_with_inv < score_no_inv

    @_ref_models_required
    def test_overhead_crane_up_penalty_amount(self):
        """Verify the exact overhead × crane_up penalty = 40."""
        engine = FeasibilityEngine()
        shot = _shot(shot_type="wide", camera_movement="crane_up")
        score_no_inv = engine.compute(shot, None)
        inv = _make_visual_invariants(camera_height_class=CameraHeightClass.OVERHEAD)
        score_with_inv = engine.compute(shot, inv)
        expected_penalty = _HEIGHT_MOVEMENT_PENALTY.get(("overhead", "crane_up"), 0)
        assert score_no_inv - score_with_inv == expected_penalty

    @_ref_models_required
    def test_eye_level_no_penalty(self):
        """eye_level reference adds no penalty for standard movements."""
        engine = FeasibilityEngine()
        shot = _shot(shot_type="medium", camera_movement="pan")
        inv = _make_visual_invariants(camera_height_class=CameraHeightClass.EYE_LEVEL)
        score_no_inv = engine.compute(shot, None)
        score_with_inv = engine.compute(shot, inv)
        assert score_no_inv == score_with_inv

    @_ref_models_required
    def test_depth_layer_penalty_extreme_close_up_background(self):
        """extreme_close_up on background dominant depth → 15-point penalty."""
        engine = FeasibilityEngine()
        shot = _shot(shot_type="extreme_close_up", camera_movement="static")
        expected_penalty = _SHOT_DEPTH_PENALTY.get(("extreme_close_up", "background"), 0)
        assert expected_penalty == 15  # contract test
        inv_bg = _make_visual_invariants(dominant_layer="background")
        inv_mid = _make_visual_invariants(dominant_layer="midground")
        score_bg  = engine.compute(shot, inv_bg)
        score_mid = engine.compute(shot, inv_mid)
        assert score_mid - score_bg == expected_penalty

    def test_location_domestic_crane_penalised(self):
        """crane_up in a domestic architecture → 25-point location penalty."""
        engine = FeasibilityEngine()
        shot = _shot(shot_type="wide", camera_movement="crane_up")
        loc = {"architecture_style": "domestic"}
        expected_penalty = _ARCHITECTURE_MOVEMENT_PENALTY.get(("domestic", "crane_up"), 0)
        assert expected_penalty == 25
        score_no_loc = engine.compute(shot, None, location_invariant=None)
        score_with_loc = engine.compute(shot, None, location_invariant=loc)
        assert score_no_loc - score_with_loc == expected_penalty

    def test_location_none_no_penalty(self):
        """None location_invariant contributes 0 penalty."""
        engine = FeasibilityEngine()
        shot = _shot(shot_type="medium", camera_movement="tracking")
        s1 = engine.compute(shot, None, location_invariant=None)
        s2 = engine.compute(shot, None, location_invariant={"architecture_style": "unknown"})
        assert s1 == s2

    def test_explosive_action_penalty_applied(self):
        """explosive action_intensity subtracts FEASIBILITY_EXPLOSIVE_PENALTY."""
        engine = FeasibilityEngine()
        shot = _shot(shot_type="medium", camera_movement="pan")
        s_normal    = engine.compute(shot, None, action_intensity=None)
        s_explosive = engine.compute(shot, None, action_intensity="explosive")
        # The static bonus does not apply (movement = pan), so:
        #   s_normal = base (95? depends on lookup)
        #   s_explosive = base - FEASIBILITY_EXPLOSIVE_PENALTY
        assert s_normal - s_explosive == FEASIBILITY_EXPLOSIVE_PENALTY

    def test_static_bonus_applied(self):
        """Static movement bonus is added on top of base score."""
        engine = FeasibilityEngine()
        shot_static = _shot(shot_type="medium", camera_movement="static")
        shot_pan    = _shot(shot_type="medium", camera_movement="pan")
        base_static = FEASIBILITY_BASE_SCORES.get(("medium", "static"), FEASIBILITY_DEFAULT_SCORE)
        base_pan    = FEASIBILITY_BASE_SCORES.get(("medium", "pan"),    FEASIBILITY_DEFAULT_SCORE)
        expected_static = min(100, base_static + FEASIBILITY_STATIC_BONUS)
        expected_pan    = base_pan  # no bonus
        assert engine.compute(shot_static, None) == expected_static
        assert engine.compute(shot_pan, None)    == expected_pan

    def test_score_clamped_at_zero(self):
        """Combined penalties cannot push the score below 0."""
        engine = FeasibilityEngine()
        if not _HAS_REF_MODELS:
            pytest.skip("reference_image models unavailable")
        # extreme_close_up + overhead + background + crane_up + domestic architecture
        shot = _shot(shot_type="extreme_close_up", camera_movement="crane_up")
        inv = _make_visual_invariants(
            camera_height_class=CameraHeightClass.OVERHEAD,
            dominant_layer="background",
        )
        loc = {"architecture_style": "domestic"}
        score = engine.compute(shot, inv, location_invariant=loc, action_intensity="explosive")
        assert score >= 0

    def test_score_clamped_at_100(self):
        """Score cannot exceed 100."""
        engine = FeasibilityEngine()
        shot = _shot(shot_type="medium", camera_movement="static")
        score = engine.compute(shot, None, action_intensity=None)
        assert score <= 100


# ===========================================================================
# 8. TestBuiltinRules
# ===========================================================================


class TestBuiltinRules:
    """Catalogue integrity and end-to-end scenario tests for BUILTIN_RULES."""

    def test_all_ids_unique(self):
        ids = [r.id for r in BUILTIN_RULES]
        assert len(ids) == len(set(ids)), "Duplicate rule IDs in BUILTIN_RULES"

    def test_all_priorities_in_range(self):
        for rule in BUILTIN_RULES:
            assert 1 <= rule.priority <= 5, f"Rule {rule.id} has invalid priority {rule.priority}"

    def test_json_serialisable(self):
        """All BUILTIN_RULES must round-trip through model_dump() / model_validate()."""
        for rule in BUILTIN_RULES:
            data = rule.model_dump()
            round_tripped = RuleSpec.model_validate(data)
            assert round_tripped.id == rule.id

    def test_make_default_evaluator_returns_evaluator(self):
        evaluator = make_default_evaluator()
        assert isinstance(evaluator, RuleEvaluator)
        assert len(evaluator.rules) == len(BUILTIN_RULES)

    def test_chr01_fires_on_low_feasibility_non_static(self):
        """CHR-01: feasibility < 40 + non-static → HARD match."""
        shot = _shot(feasibility_score=30, camera_movement="pan")
        ctx = _ctx(shot=shot)
        evaluator = make_default_evaluator()
        results = evaluator.evaluate(ctx)
        chr01 = next(r for r in results if r.rule_id == "CHR-01-feasibility-gate")
        assert chr01.matched is True
        assert chr01.conflict_type == ConflictType.HARD

    def test_chr01_does_not_fire_on_static(self):
        """CHR-01: static movement is always feasible regardless of score."""
        shot = _shot(feasibility_score=10, camera_movement="static")
        ctx = _ctx(shot=shot)
        evaluator = make_default_evaluator()
        results = evaluator.evaluate(ctx)
        chr01 = next(r for r in results if r.rule_id == "CHR-01-feasibility-gate")
        assert chr01.matched is False

    @_ref_models_required
    def test_spc01_fires_overhead_crane_up(self):
        """SPC-01: overhead reference + crane_up → HARD match."""
        shot = _shot(camera_movement="crane_up")
        inv = _make_visual_invariants(camera_height_class=CameraHeightClass.OVERHEAD)
        ctx = _ctx(shot=shot, ref_invariants=inv)
        evaluator = make_default_evaluator()
        results = evaluator.evaluate(ctx)
        spc01 = next(r for r in results if r.rule_id == "SPC-01-overhead-crane-up-incompatible")
        assert spc01.matched is True

    @_ref_models_required
    def test_spc01_does_not_fire_eye_level(self):
        """SPC-01: eye_level reference + crane_up → no match."""
        shot = _shot(camera_movement="crane_up")
        inv = _make_visual_invariants(camera_height_class=CameraHeightClass.EYE_LEVEL)
        ctx = _ctx(shot=shot, ref_invariants=inv)
        evaluator = make_default_evaluator()
        results = evaluator.evaluate(ctx)
        spc01 = next(r for r in results if r.rule_id == "SPC-01-overhead-crane-up-incompatible")
        assert spc01.matched is False

    @_ref_models_required
    def test_lit01_fires_left_ref_right_directive(self):
        """LIT-01: ref key_direction_h=left + 'right' in lighting_directives → HARD match."""
        shot = _shot(lighting_directives="Motivated hard light from the right.")
        inv = _make_visual_invariants(key_direction_h=LightingDirectionH.LEFT)
        ctx = _ctx(shot=shot, ref_invariants=inv)
        evaluator = make_default_evaluator()
        results = evaluator.evaluate(ctx)
        lit01 = next(r for r in results if r.rule_id == "LIT-01-left-ref-right-directive")
        assert lit01.matched is True

    @_ref_models_required
    def test_nar01_fires_transition_long_shot(self):
        """NAR-01: transition beat + duration > 5 → SOFT match."""
        shot = _shot(duration_sec=7)
        scene = _scene(beat_type="transition")
        ctx = _ctx(shot=shot, scene=scene)
        evaluator = make_default_evaluator()
        results = evaluator.evaluate(ctx)
        nar01 = next(r for r in results if r.rule_id == "NAR-01-transition-shot-too-long")
        assert nar01.matched is True
        assert nar01.conflict_type == ConflictType.SOFT

    @_ref_models_required
    def test_end_to_end_detective_dark_room(self):
        """
        End-to-end scenario: detective in a dark room.

        Setup:
          ref image  → camera_height_class = OVERHEAD, key_direction_h = LEFT
          shot       → camera_movement = crane_up, lighting_directives = '...from the right...'

        Expected resolutions (in order):
          1. LIT-01 (P2 HARD) → lighting_directives replaced with 'Key light: top-left'
          2. SPC-01 (P3 HARD) → camera_movement downgraded crane_up → tilt_up
        """
        shot = _shot(
            camera_movement="crane_up",
            lighting_directives="Motivated from the right, hard sidelight.",
        )
        inv = _make_visual_invariants(
            camera_height_class=CameraHeightClass.OVERHEAD,
            key_direction_h=LightingDirectionH.LEFT,
            key_direction_v=LightingDirectionV.TOP,
        )
        ctx = _ctx(shot=shot, ref_invariants=inv)

        evaluator = make_default_evaluator()
        eval_results = evaluator.evaluate(ctx)

        engine = ConflictResolutionEngine()
        resolved, records = engine.resolve(shot, ctx, eval_results)

        # Lighting must be corrected (P2 HARD takes priority)
        assert resolved.lighting_directives == "Key light: top-left"
        # Camera movement must be downgraded (P3 HARD)
        assert resolved.camera_movement == "tilt_up"
        # Both modifications recorded
        assert any(r.was_modified and r.strategy == ResolutionStrategy.STRIP_AND_REPLACE for r in records)
        assert any(r.was_modified and r.strategy == ResolutionStrategy.DOWNGRADE_MOVEMENT for r in records)
        # Original shot is unchanged
        assert shot.camera_movement == "crane_up"
        assert shot.lighting_directives == "Motivated from the right, hard sidelight."
