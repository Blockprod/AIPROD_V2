"""
rule_engine/conflict_resolver.py — Deterministic conflict resolution engine.

Resolution algorithm
--------------------
1. Filter eval_results to matched conflicts (HARD or SOFT).
2. Sort by (priority ASC, HARD before SOFT at equal priority).
3. For each conflict:
   a. HARD → apply mandatory strategy via _resolve_hard().
   b. SOFT → attempt compromise; fall back to NARRATIVE_YIELDS.
4. Record every action in a ResolutionRecord.
5. Return (resolved_shot, list[ResolutionRecord]).

Shot mutations
--------------
All mutations use model_copy(update=...) — Pydantic immutability preserved.
The input `shot` is never modified in place.

HARD strategies by field
------------------------
  shot.camera_movement     → DOWNGRADE_MOVEMENT (deterministic chain)
  shot.lighting_directives → STRIP_AND_REPLACE with ref invariant
  shot.prompt (any other)  → FLAG_AND_PASS (annotate visual_invariants_applied)

SOFT strategies
---------------
  shot.camera_movement → COMPROMISE (downgrade one step)
  other fields         → NARRATIVE_YIELDS (annotate visual_invariants_applied)

Camera movement downgrade chain (deterministic, no randomness)
--------------------------------------------------------------
  crane_up   → tilt_up   → static
  crane_down → tilt_down → static
  whip_pan   → pan       → static
  tracking   → follow    → static
  steadicam  → follow    → static
  dolly_in   → follow    → static
  dolly_out  → follow    → static
  handheld   → static
  follow     → static
  pan        → static
  tilt_up    → static
  tilt_down  → static
"""

from __future__ import annotations

from typing import Any

from aiprod_adaptation.models.schema import Shot

from .models import (
    ConflictRecord,
    ConflictType,
    EvalContext,
    ResolutionRecord,
    ResolutionStrategy,
    RuleEvalResult,
)

# ---------------------------------------------------------------------------
# Camera movement downgrade chain
# ---------------------------------------------------------------------------

_MOVEMENT_DOWNGRADE_CHAIN: dict[str, str] = {
    "crane_up":   "tilt_up",
    "crane_down": "tilt_down",
    "whip_pan":   "pan",
    "tracking":   "follow",
    "steadicam":  "follow",
    "dolly_in":   "follow",
    "dolly_out":  "follow",
    "handheld":   "static",
    "follow":     "static",
    "pan":        "static",
    "tilt_up":    "static",
    "tilt_down":  "static",
    "rack_focus": "static",
}

# Movements that are physically incompatible with each camera height class.
# Used by _hard_downgrade_movement to validate the downgrade target.
_HEIGHT_INCOMPATIBLE_MOVEMENTS: dict[str, frozenset[str]] = {
    "overhead":   frozenset({"crane_up", "tilt_up", "dolly_in", "dolly_out"}),
    "high_angle": frozenset({"crane_up", "tilt_up"}),
    "low_angle":  frozenset({"crane_down", "tilt_down"}),
    "eye_level":  frozenset(),
}


def _downgrade_once(movement: str) -> str:
    """Follow the downgrade chain exactly one step."""
    return _MOVEMENT_DOWNGRADE_CHAIN.get(movement, "static")


# ---------------------------------------------------------------------------
# ConflictResolutionEngine
# ---------------------------------------------------------------------------


class ConflictResolutionEngine:
    """
    Deterministic conflict resolution for AIPROD_Cinematic shots.

    Usage
    -----
        engine  = ConflictResolutionEngine()
        shot_out, records = engine.resolve(shot, ctx, eval_results)

    The engine is stateless — it can be shared and reused safely.
    """

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def resolve(
        self,
        shot: Shot,
        ctx: EvalContext,
        eval_results: list[RuleEvalResult],
    ) -> tuple[Shot, list[ResolutionRecord]]:
        """
        Apply all matched conflicts to *shot* in priority order.

        Args:
            shot:         Original Shot (never mutated in-place).
            ctx:          EvalContext used to produce *eval_results*.
            eval_results: Output of RuleEvaluator.evaluate().

        Returns:
            (resolved_shot, resolution_records)
            resolved_shot == shot when no conflicts were resolved (was_modified=False).
        """
        # --- filter: matched conflicts (HARD or SOFT) ----------------------
        active: list[RuleEvalResult] = [
            r
            for r in eval_results
            if r.matched
            and r.conflict_type != ConflictType.NONE
            and r.conflict is not None
        ]

        # --- sort: priority ASC, HARD before SOFT at equal priority --------
        active.sort(
            key=lambda r: (
                r.conflict.priority,                       # type: ignore[union-attr]
                0 if r.conflict_type == ConflictType.HARD else 1,
            )
        )

        records: list[ResolutionRecord] = []
        working_shot = shot

        for result in active:
            assert result.conflict is not None  # guaranteed by filter above
            if result.conflict_type == ConflictType.HARD:
                working_shot, record = self._resolve_hard(
                    working_shot, result.conflict, ctx
                )
            else:  # SOFT
                working_shot, record = self._resolve_soft(
                    working_shot, result.conflict, ctx
                )
            records.append(record)

        return working_shot, records

    # -----------------------------------------------------------------------
    # HARD strategies
    # -----------------------------------------------------------------------

    def _resolve_hard(
        self,
        shot: Shot,
        conflict: ConflictRecord,
        ctx: EvalContext,
    ) -> tuple[Shot, ResolutionRecord]:
        """Dispatch to the correct HARD strategy based on field_path."""
        fp = conflict.field_path
        if fp == "shot.camera_movement":
            return self._hard_downgrade_movement(shot, conflict, ctx)
        if fp == "shot.lighting_directives":
            return self._hard_fix_lighting_directive(shot, conflict, ctx)
        # Default: flag the conflict, annotate visual_invariants_applied
        return self._hard_flag_and_annotate(shot, conflict, ctx)

    def _hard_downgrade_movement(
        self,
        shot: Shot,
        conflict: ConflictRecord,
        ctx: EvalContext,
    ) -> tuple[Shot, ResolutionRecord]:
        """
        Downgrade camera_movement using the deterministic chain.

        If a `downgrade_to` target was encoded in the conflict's rule, use it.
        Otherwise, derive the target from the camera height incompatibility map,
        falling back to one step down the chain.
        """
        orig = shot.camera_movement

        # Check if the height class tells us what the incompatibility is;
        # then follow the chain exactly one step.
        target: str | None = None
        if ctx.ref_invariants is not None:
            height = ctx.ref_invariants.camera_height_class
            height_val = height.value if hasattr(height, "value") else str(height)
            incompatible = _HEIGHT_INCOMPATIBLE_MOVEMENTS.get(height_val, frozenset())
            if orig in incompatible:
                target = _downgrade_once(orig)

        target = target or _downgrade_once(orig)

        if target == orig:
            return shot, ResolutionRecord(
                conflict=conflict,
                strategy=ResolutionStrategy.NO_ACTION,
                original_value=orig,
                resolved_value=orig,
                was_modified=False,
            )

        new_shot = shot.model_copy(update={"camera_movement": target})
        return new_shot, ResolutionRecord(
            conflict=conflict,
            strategy=ResolutionStrategy.DOWNGRADE_MOVEMENT,
            original_value=orig,
            resolved_value=target,
            was_modified=True,
        )

    def _hard_fix_lighting_directive(
        self,
        shot: Shot,
        conflict: ConflictRecord,
        ctx: EvalContext,
    ) -> tuple[Shot, ResolutionRecord]:
        """
        Replace lighting_directives with the invariant derived from ref_invariants.
        """
        orig = shot.lighting_directives or ""

        # Build invariant lighting directive from reference image analysis
        invariant: str = ""
        if ctx.ref_invariants is not None:
            kh = ctx.ref_invariants.lighting.key_direction_h
            kv = ctx.ref_invariants.lighting.key_direction_v
            kh_val = kh.value if hasattr(kh, "value") else str(kh)
            kv_val = kv.value if hasattr(kv, "value") else str(kv)
            invariant = f"Key light: {kv_val}-{kh_val}"
        elif conflict.invariant_value:
            invariant = str(conflict.invariant_value)

        if not invariant or orig == invariant:
            return shot, ResolutionRecord(
                conflict=conflict,
                strategy=ResolutionStrategy.NO_ACTION,
                original_value=orig,
                resolved_value=orig,
                was_modified=False,
            )

        new_shot = shot.model_copy(update={"lighting_directives": invariant})
        return new_shot, ResolutionRecord(
            conflict=conflict,
            strategy=ResolutionStrategy.STRIP_AND_REPLACE,
            original_value=orig,
            resolved_value=invariant,
            was_modified=True,
        )

    def _hard_flag_and_annotate(
        self,
        shot: Shot,
        conflict: ConflictRecord,
        ctx: EvalContext,
    ) -> tuple[Shot, ResolutionRecord]:
        """
        For HARD conflicts on fields we cannot safely rewrite (e.g. shot.prompt):
        annotate visual_invariants_applied and pass the shot through.
        """
        flag = f"HARD-CONFLICT:{conflict.rule_id}"
        if flag in shot.visual_invariants_applied:
            return shot, ResolutionRecord(
                conflict=conflict,
                strategy=ResolutionStrategy.FLAG_AND_PASS,
                original_value=None,
                resolved_value=flag,
                was_modified=False,
            )
        new_applied = list(shot.visual_invariants_applied) + [flag]
        new_shot = shot.model_copy(
            update={"visual_invariants_applied": new_applied}
        )
        return new_shot, ResolutionRecord(
            conflict=conflict,
            strategy=ResolutionStrategy.FLAG_AND_PASS,
            original_value=None,
            resolved_value=flag,
            was_modified=True,
        )

    # -----------------------------------------------------------------------
    # SOFT strategies
    # -----------------------------------------------------------------------

    def _resolve_soft(
        self,
        shot: Shot,
        conflict: ConflictRecord,
        ctx: EvalContext,
    ) -> tuple[Shot, ResolutionRecord]:
        """Dispatch SOFT conflict to the most appropriate strategy."""
        fp = conflict.field_path
        if fp == "shot.camera_movement":
            return self._soft_compromise_movement(shot, conflict, ctx)
        return self._soft_narrative_yields(shot, conflict, ctx)

    def _soft_compromise_movement(
        self,
        shot: Shot,
        conflict: ConflictRecord,
        ctx: EvalContext,
    ) -> tuple[Shot, ResolutionRecord]:
        """Downgrade camera movement one step as a compromise."""
        orig = shot.camera_movement
        compromise = _downgrade_once(orig)
        if compromise != orig:
            new_shot = shot.model_copy(update={"camera_movement": compromise})
            return new_shot, ResolutionRecord(
                conflict=conflict,
                strategy=ResolutionStrategy.COMPROMISE,
                original_value=orig,
                resolved_value=compromise,
                was_modified=True,
            )
        return shot, ResolutionRecord(
            conflict=conflict,
            strategy=ResolutionStrategy.FLAG_AND_PASS,
            original_value=orig,
            resolved_value=orig,
            was_modified=False,
        )

    def _soft_narrative_yields(
        self,
        shot: Shot,
        conflict: ConflictRecord,
        ctx: EvalContext,
    ) -> tuple[Shot, ResolutionRecord]:
        """Narrative intent yields: annotate visual_invariants_applied, shot unchanged."""
        flag = f"SOFT-CONFLICT:{conflict.rule_id}"
        if flag in shot.visual_invariants_applied:
            return shot, ResolutionRecord(
                conflict=conflict,
                strategy=ResolutionStrategy.NARRATIVE_YIELDS,
                original_value=None,
                resolved_value=flag,
                was_modified=False,
            )
        new_applied = list(shot.visual_invariants_applied) + [flag]
        new_shot = shot.model_copy(update={"visual_invariants_applied": new_applied})
        return new_shot, ResolutionRecord(
            conflict=conflict,
            strategy=ResolutionStrategy.NARRATIVE_YIELDS,
            original_value=None,
            resolved_value=flag,
            was_modified=True,
        )
