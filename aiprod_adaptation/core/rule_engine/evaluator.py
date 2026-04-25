"""
rule_engine/evaluator.py — Deterministic hierarchical rule evaluator.

Design guarantees
-----------------
- Rules are sorted once at construction time by (priority ASC, id ASC).
- `evaluate()` always returns results in that fixed order.
- Identical (rules, context) → identical result list.
- No mutations performed during evaluation.
- All conditions support arbitrary nesting (AND / OR / NOT).

Field resolution
----------------
Condition `field` values are dot-paths resolved against EvalContext:
  Root keys : shot, scene, visual_bible, ref_invariants, episode_index
  Examples  : "shot.feasibility_score"
              "ref_invariants.camera_height_class"
              "ref_invariants.depth_layers.dominant_layer"
              "ref_invariants.lighting.key_direction_h"
              "scene.scene_tone"

None-safety
-----------
If any path segment is None (e.g. ref_invariants is None), the resolved
value is None.  EXISTS → False, all comparison operators → False.
This ensures rules that reference ref_invariants silently skip when no
reference image is available.
"""

from __future__ import annotations

import re
from typing import Any

from .models import (
    CompoundCondition,
    ConditionOperator,
    ConflictRecord,
    ConflictType,
    EvalContext,
    FieldOperator,
    LeafCondition,
    RuleEvalResult,
    RuleSpec,
)

# ---------------------------------------------------------------------------
# Field resolution helpers
# ---------------------------------------------------------------------------


def _get_field(obj: Any, path: str) -> Any:
    """
    Resolve a dot-path against a nested object/dict.

    Supports Pydantic models (getattr), plain dicts, and combinations.
    Returns None for any missing segment (never raises).
    """
    if not path:
        return obj
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def _resolve_field(field_path: str, ctx: EvalContext) -> Any:
    """Resolve a rule field path from the EvalContext namespace."""
    ns: dict[str, Any] = {
        "shot":           ctx.shot,
        "scene":          ctx.scene,
        "visual_bible":   ctx.visual_bible,
        "ref_invariants": ctx.ref_invariants,
        "episode_index":  ctx.episode_index,
    }
    parts = field_path.split(".", 1)
    root_key = parts[0]
    sub_path  = parts[1] if len(parts) > 1 else ""
    root = ns.get(root_key)
    if not sub_path:
        return root
    return _get_field(root, sub_path)


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------


def _eval_leaf(cond: LeafCondition, ctx: EvalContext) -> bool:
    value = _resolve_field(cond.field, ctx)
    op    = cond.op
    ref   = cond.value

    if op == FieldOperator.EXISTS:
        return value is not None
    if op == FieldOperator.NOT_EXISTS:
        return value is None
    if op == FieldOperator.EQ:
        return bool(value == ref)
    if op == FieldOperator.NEQ:
        return bool(value != ref)
    if op == FieldOperator.LT:
        return value is not None and float(value) < float(ref)
    if op == FieldOperator.LTE:
        return value is not None and float(value) <= float(ref)
    if op == FieldOperator.GT:
        return value is not None and float(value) > float(ref)
    if op == FieldOperator.GTE:
        return value is not None and float(value) >= float(ref)
    if op == FieldOperator.IN:
        return value in cond.values
    if op == FieldOperator.NOT_IN:
        return value not in cond.values
    if op == FieldOperator.CONTAINS:
        return isinstance(value, str) and isinstance(ref, str) and ref in value
    if op == FieldOperator.CONTAINS_ANY:
        return isinstance(value, str) and any(v in value for v in cond.values)
    if op == FieldOperator.MATCHES_RE:
        return isinstance(value, str) and bool(
            re.search(str(ref), value, re.IGNORECASE)
        )
    return False


def _eval_condition(
    cond: LeafCondition | CompoundCondition,
    ctx: EvalContext,
) -> bool:
    """Recursively evaluate a (possibly nested) condition tree."""
    if isinstance(cond, LeafCondition):
        return _eval_leaf(cond, ctx)
    # CompoundCondition
    op = cond.operator
    if op == ConditionOperator.AND:
        return all(_eval_condition(c, ctx) for c in cond.operands)
    if op == ConditionOperator.OR:
        return any(_eval_condition(c, ctx) for c in cond.operands)
    if op == ConditionOperator.NOT:
        return not _eval_condition(cond.operands[0], ctx) if cond.operands else True
    return False


# ---------------------------------------------------------------------------
# RuleEvaluator
# ---------------------------------------------------------------------------


class RuleEvaluator:
    """
    Stateless, deterministic hierarchical rule evaluator.

    Construction
    ------------
    RuleEvaluator(rules)  — rules are sorted by (priority ASC, id ASC) once.

    Evaluation
    ----------
    evaluate(ctx) → list[RuleEvalResult]  — in sorted order, all rules evaluated.

    Unmatched rules return matched=False, conflict_type=NONE.
    Matched rules include a populated ConflictRecord.
    No mutations are performed — resolving conflicts is the job of
    ConflictResolutionEngine.
    """

    def __init__(self, rules: list[RuleSpec]) -> None:
        # Immutable tuple — insertion order cannot change after construction.
        self._rules: tuple[RuleSpec, ...] = tuple(
            sorted(rules, key=lambda r: (r.priority, r.id))
        )

    @property
    def rules(self) -> tuple[RuleSpec, ...]:
        """Read-only view of the sorted rule catalogue."""
        return self._rules

    def evaluate(self, ctx: EvalContext) -> list[RuleEvalResult]:
        """
        Evaluate all rules against *ctx* in (priority, id) order.

        Args:
            ctx: EvalContext — combined local + global context window.

        Returns:
            list[RuleEvalResult] in deterministic (priority, id) order.
            Every rule produces exactly one entry (matched or not).
        """
        results: list[RuleEvalResult] = []
        for rule in self._rules:
            matched = _eval_condition(rule.condition, ctx)
            if not matched:
                results.append(
                    RuleEvalResult(
                        rule_id=rule.id,
                        matched=False,
                        conflict_type=ConflictType.NONE,
                    )
                )
                continue

            # Build a ConflictRecord capturing the current field value
            current_value: Any = None
            if rule.action.target_field:
                current_value = _resolve_field(rule.action.target_field, ctx)

            conflict = ConflictRecord(
                rule_id=rule.id,
                conflict_type=rule.conflict_type,
                priority=rule.priority,
                shot_id=ctx.shot.shot_id if ctx.shot is not None else "",
                field_path=rule.action.target_field or "",
                current_value=current_value,
                invariant_value=None,  # populated by ConflictResolutionEngine
                description=rule.description,
            )
            results.append(
                RuleEvalResult(
                    rule_id=rule.id,
                    matched=True,
                    conflict_type=rule.conflict_type,
                    conflict=conflict,
                )
            )
        return results
