"""
rule_engine/builtin_rules.py — Canonical AIPROD_Cinematic rule catalogue.

9 built-in rules spanning all 5 priority tiers.
All rules are expressed in the RuleSpec DSL — fully JSON-serialisable.

Rule IDs follow the naming convention:
  {DOMAIN}-{SEQ:02d}-{slug}
  CHR = Character identity (P1)
  LIT = Lighting (P2)
  SPC = Spatial coherence (P3)
  CMP = Composition (P4)
  NAR = Narrative intent (P5)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiprod_adaptation.core.rule_engine.evaluator import RuleEvaluator

from .models import (
    CompoundCondition,
    ConditionOperator,
    ConflictType,
    FieldOperator,
    LeafCondition,
    RuleAction,
    RuleSpec,
)

BUILTIN_RULES: list[RuleSpec] = [

    # ===========================================================================
    # P1 — Identity & anatomy
    # ===========================================================================

    RuleSpec(
        id="CHR-01-feasibility-gate",
        priority=1,
        description=(
            "P1: Shots with feasibility_score < 40 and non-static camera movement "
            "are physically infeasible given the reference constraints. "
            "Downgrade to static."
        ),
        condition=CompoundCondition(
            operator=ConditionOperator.AND,
            operands=[
                LeafCondition(
                    field="shot.feasibility_score",
                    op=FieldOperator.LT,
                    value=40,
                ),
                LeafCondition(
                    field="shot.camera_movement",
                    op=FieldOperator.NEQ,
                    value="static",
                ),
            ],
        ),
        action=RuleAction(
            type="DOWNGRADE",
            target_field="shot.camera_movement",
            downgrade_to="static",
        ),
        conflict_type=ConflictType.HARD,
    ),

    # ===========================================================================
    # P2 — Lighting
    # ===========================================================================

    RuleSpec(
        id="LIT-01-left-ref-right-directive",
        priority=2,
        description=(
            "P2: Reference image has key light from the LEFT but lighting_directives "
            "contains a reference to the RIGHT. Invariant wins — rewrite directive."
        ),
        condition=CompoundCondition(
            operator=ConditionOperator.AND,
            operands=[
                LeafCondition(
                    field="ref_invariants.lighting.key_direction_h",
                    op=FieldOperator.EQ,
                    value="left",
                ),
                LeafCondition(
                    field="shot.lighting_directives",
                    op=FieldOperator.MATCHES_RE,
                    value=r"\bright\b",
                ),
            ],
        ),
        action=RuleAction(
            type="REWRITE",
            target_field="shot.lighting_directives",
            rewrite_template="Replace contradicting right-side reference with left-key invariant.",
        ),
        conflict_type=ConflictType.HARD,
    ),

    RuleSpec(
        id="LIT-02-right-ref-left-directive",
        priority=2,
        description=(
            "P2: Reference image has key light from the RIGHT but lighting_directives "
            "contains a reference to the LEFT. Invariant wins — rewrite directive."
        ),
        condition=CompoundCondition(
            operator=ConditionOperator.AND,
            operands=[
                LeafCondition(
                    field="ref_invariants.lighting.key_direction_h",
                    op=FieldOperator.EQ,
                    value="right",
                ),
                LeafCondition(
                    field="shot.lighting_directives",
                    op=FieldOperator.MATCHES_RE,
                    value=r"\bleft\b",
                ),
            ],
        ),
        action=RuleAction(
            type="REWRITE",
            target_field="shot.lighting_directives",
            rewrite_template="Replace contradicting left-side reference with right-key invariant.",
        ),
        conflict_type=ConflictType.HARD,
    ),

    # ===========================================================================
    # P3 — Spatial coherence / camera angle
    # ===========================================================================

    RuleSpec(
        id="SPC-01-overhead-crane-up-incompatible",
        priority=3,
        description=(
            "P3: crane_up is physically impossible when the reference establishes "
            "an overhead camera position — the camera is already at maximum height."
        ),
        condition=CompoundCondition(
            operator=ConditionOperator.AND,
            operands=[
                LeafCondition(
                    field="ref_invariants.camera_height_class",
                    op=FieldOperator.EQ,
                    value="overhead",
                ),
                LeafCondition(
                    field="shot.camera_movement",
                    op=FieldOperator.EQ,
                    value="crane_up",
                ),
            ],
        ),
        action=RuleAction(
            type="DOWNGRADE",
            target_field="shot.camera_movement",
            downgrade_to="tilt_up",
        ),
        conflict_type=ConflictType.HARD,
    ),

    RuleSpec(
        id="SPC-02-high-angle-crane-up-incompatible",
        priority=3,
        description=(
            "P3: crane_up conflicts with a high_angle reference position — "
            "the camera cannot ascend further from an already elevated position."
        ),
        condition=CompoundCondition(
            operator=ConditionOperator.AND,
            operands=[
                LeafCondition(
                    field="ref_invariants.camera_height_class",
                    op=FieldOperator.EQ,
                    value="high_angle",
                ),
                LeafCondition(
                    field="shot.camera_movement",
                    op=FieldOperator.EQ,
                    value="crane_up",
                ),
            ],
        ),
        action=RuleAction(
            type="DOWNGRADE",
            target_field="shot.camera_movement",
            downgrade_to="tilt_up",
        ),
        conflict_type=ConflictType.HARD,
    ),

    RuleSpec(
        id="SPC-03-low-angle-crane-down-incompatible",
        priority=3,
        description=(
            "P3: crane_down conflicts with a low_angle reference position — "
            "the camera cannot descend further from an already low position."
        ),
        condition=CompoundCondition(
            operator=ConditionOperator.AND,
            operands=[
                LeafCondition(
                    field="ref_invariants.camera_height_class",
                    op=FieldOperator.EQ,
                    value="low_angle",
                ),
                LeafCondition(
                    field="shot.camera_movement",
                    op=FieldOperator.EQ,
                    value="crane_down",
                ),
            ],
        ),
        action=RuleAction(
            type="DOWNGRADE",
            target_field="shot.camera_movement",
            downgrade_to="tilt_down",
        ),
        conflict_type=ConflictType.HARD,
    ),

    RuleSpec(
        id="SPC-04-overhead-dolly-incompatible",
        priority=3,
        description=(
            "P3: dolly_in / dolly_out imply horizontal forward-backward axis movement "
            "which is inconsistent with an overhead (top-down) reference framing."
        ),
        condition=CompoundCondition(
            operator=ConditionOperator.AND,
            operands=[
                LeafCondition(
                    field="ref_invariants.camera_height_class",
                    op=FieldOperator.EQ,
                    value="overhead",
                ),
                LeafCondition(
                    field="shot.camera_movement",
                    op=FieldOperator.IN,
                    values=["dolly_in", "dolly_out"],
                ),
            ],
        ),
        action=RuleAction(
            type="DOWNGRADE",
            target_field="shot.camera_movement",
            downgrade_to="follow",
        ),
        conflict_type=ConflictType.HARD,
    ),

    # ===========================================================================
    # P4 — Composition / depth
    # ===========================================================================

    RuleSpec(
        id="CMP-01-close-up-background-depth-mismatch",
        priority=4,
        description=(
            "P4: extreme_close_up framing is suboptimal when the reference image's "
            "dominant depth layer is 'background'. The focal plane is likely misaligned. "
            "Flag for review — do not force-change shot_type."
        ),
        condition=CompoundCondition(
            operator=ConditionOperator.AND,
            operands=[
                LeafCondition(
                    field="shot.shot_type",
                    op=FieldOperator.EQ,
                    value="extreme_close_up",
                ),
                LeafCondition(
                    field="ref_invariants.depth_layers.dominant_layer",
                    op=FieldOperator.EQ,
                    value="background",
                ),
            ],
        ),
        action=RuleAction(
            type="ANNOTATE",
            target_field="shot.visual_invariants_applied",
            annotation_key="depth_conflict",
            annotation_value="extreme_close_up_on_background_dominant",
        ),
        conflict_type=ConflictType.SOFT,
    ),

    # ===========================================================================
    # P5 — Narrative intent
    # ===========================================================================

    RuleSpec(
        id="NAR-01-transition-shot-too-long",
        priority=5,
        description=(
            "P5: Transition/montage beat_type scenes should use short shot durations "
            "(≤ 4 s for effective montage rhythm). Shots > 5 s in transition scenes "
            "break the intended pacing. Flag for review."
        ),
        condition=CompoundCondition(
            operator=ConditionOperator.AND,
            operands=[
                LeafCondition(
                    field="scene.beat_type",
                    op=FieldOperator.EQ,
                    value="transition",
                ),
                LeafCondition(
                    field="shot.duration_sec",
                    op=FieldOperator.GT,
                    value=5,
                ),
            ],
        ),
        action=RuleAction(
            type="ANNOTATE",
            target_field="shot.visual_invariants_applied",
            annotation_key="pacing_conflict",
            annotation_value="transition_shot_duration_exceeds_montage_threshold",
        ),
        conflict_type=ConflictType.SOFT,
    ),
]

# ---------------------------------------------------------------------------
# Convenience: default evaluator with all built-in rules
# ---------------------------------------------------------------------------


def make_default_evaluator() -> RuleEvaluator:
    """Return a RuleEvaluator pre-loaded with all BUILTIN_RULES."""
    from aiprod_adaptation.core.rule_engine.evaluator import RuleEvaluator
    return RuleEvaluator(BUILTIN_RULES)
