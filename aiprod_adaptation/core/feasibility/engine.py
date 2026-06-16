"""
feasibility/engine.py — Invariant-aware feasibility scoring for Pass 3 / Pass 4.

Extends the base `feasibility_score` from cinematography_rules_v3 with:
  P2  Lighting severity     — not penalised here (handled by conflict_resolver)
  P3  Camera height × movement incompatibility  — subtracted penalty
  P4  Shot type × depth layer mismatch          — subtracted penalty
  P3  Location architecture × movement          — subtracted penalty

Score formula
-------------
  base  = FEASIBILITY_BASE_SCORES.get((shot_type, movement), FEASIBILITY_DEFAULT_SCORE)
  base -= FEASIBILITY_EXPLOSIVE_PENALTY   if action_intensity == "explosive"
  base += FEASIBILITY_STATIC_BONUS        if movement == "static"
  final = clamp(base - inv_penalty - loc_penalty, 0, 100)

All operations are pure (no side effects, no randomness).
Identical inputs → identical integer output.

Integration
-----------
Call FeasibilityEngine.compute() in Pass 3 (after base score assignment) or
in Pass 4 (after visual_bible and ref_invariants become available).
The result replaces `shot.feasibility_score` via a revalidated model rebuild.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from aiprod_adaptation.core.rules.cinematography_catalog import CAMERA_MOVEMENTS, SHOT_TYPES
from aiprod_adaptation.core.rules.cinematography_rules_v3 import (
    FEASIBILITY_BASE_SCORES,
    FEASIBILITY_EXPLOSIVE_PENALTY,
    FEASIBILITY_STATIC_BONUS,
)

_SHOT_BASE: dict[str, int] = {
    "extreme_close_up": 90,
    "close_up": 94,
    "extreme_wide": 92,
    "wide": 95,
    "pov": 85,
    "two_shot": 92,
    "insert": 95,
    "over_shoulder": 92,
    "medium_wide": 94,
    "medium_close": 94,
    "medium": 95,
}
_MOVEMENT_COST: dict[str, int] = {
    "static": 0,
    "follow": 15,
    "pan": 5,
    "dolly_in": 13,
    "dolly_out": 13,
    "tilt_up": 8,
    "tilt_down": 8,
    "crane_up": 30,
    "crane_down": 30,
    "tracking": 20,
    "handheld": 17,
    "steadicam": 23,
    "rack_focus": 10,
    "whip_pan": 20,
    "zoom_in": 8,
    "zoom_out": 8,
}


@dataclass(frozen=True)
class FeasibilityBreakdown:
    base: int
    action_adjustment: int
    static_adjustment: int
    camera_height_penalty: int
    depth_penalty: int
    architecture_penalty: int
    final: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

# ---------------------------------------------------------------------------
# P3 — Camera height × movement incompatibility penalties
# (ref camera_height_class value, camera_movement) → penalty [0, 100]
# ---------------------------------------------------------------------------

_HEIGHT_MOVEMENT_PENALTY: dict[tuple[str, str], int] = {
    ("overhead",   "crane_up"):   40,
    ("overhead",   "tilt_up"):    30,
    ("overhead",   "dolly_in"):   20,
    ("overhead",   "dolly_out"):  20,
    ("high_angle", "crane_up"):   30,
    ("high_angle", "tilt_up"):    20,
    ("low_angle",  "crane_down"): 30,
    ("low_angle",  "tilt_down"):  20,
}

# ---------------------------------------------------------------------------
# P4 — Shot type × depth layer dominant mismatch penalties
# Soft penalty: the focal plane implied by the shot type mismatches the
# dominant depth layer in the reference.
# ---------------------------------------------------------------------------

_SHOT_DEPTH_PENALTY: dict[tuple[str, str], int] = {
    ("extreme_close_up", "background"):  15,
    ("close_up",         "background"):  10,
    ("wide",             "foreground"):   5,
    ("extreme_wide",     "foreground"):   5,
}

# ---------------------------------------------------------------------------
# P3 — Location architecture × movement constraint penalties
# Some camera movements are physically constrained by architectural style.
# ---------------------------------------------------------------------------

_ARCHITECTURE_MOVEMENT_PENALTY: dict[tuple[str, str], int] = {
    ("domestic",   "crane_up"):   25,
    ("domestic",   "crane_down"): 25,
    ("domestic",   "tracking"):   10,
    ("industrial", "rack_focus"):  10,
    ("natural",    "steadicam"):    5,  # rough terrain makes steadicam harder
}


class FeasibilityEngine:
    """
    Invariant-aware feasibility scorer.

    Stateless — all computation is pure.  Thread-safe.

    Usage
    -----
        engine = FeasibilityEngine()
        score  = engine.compute(shot, ref_invariants, location_invariant, action_intensity)
    """

    def compute(
        self,
        shot: Any,
        ref_invariants: Any | None,
        location_invariant: Any | None = None,
        action_intensity: str | None = None,
    ) -> int:
        """
        Compute the invariant-aware feasibility score for *shot*.

        Args:
            shot:               Shot Pydantic object (shot_type, camera_movement, …).
            ref_invariants:     VisualInvariants from reference image (optional).
                                When None, only base score and intensity modifiers apply.
            location_invariant: LocationInvariant TypedDict from VisualBible (optional).
                                When None, architecture constraint penalty is skipped.
            action_intensity:   "explosive" | "mid" | "subtle" | None.
                                "explosive" subtracts FEASIBILITY_EXPLOSIVE_PENALTY.

        Returns:
            int in [0, 100].
        """
        return self.compute_breakdown(
            shot, ref_invariants, location_invariant, action_intensity
        ).final

    def compute_breakdown(
        self,
        shot: Any,
        ref_invariants: Any | None,
        location_invariant: Any | None = None,
        action_intensity: str | None = None,
    ) -> FeasibilityBreakdown:
        shot_type = shot.shot_type
        movement = shot.camera_movement

        # 1. Base score (from cinematography_rules_v3 lookup table)
        if shot_type not in SHOT_TYPES or movement not in CAMERA_MOVEMENTS:
            raise ValueError(
                f"Unknown feasibility combination: shot_type={shot_type!r}, "
                f"camera_movement={movement!r}"
            )
        combination = (shot_type, movement)
        base = FEASIBILITY_BASE_SCORES.get(
            combination,
            max(0, _SHOT_BASE[shot_type] - _MOVEMENT_COST[movement]),
        )

        # 2. Explosive action intensity penalty
        action_adjustment = -FEASIBILITY_EXPLOSIVE_PENALTY if action_intensity == "explosive" else 0

        # 3. Static bonus (always achievable, regardless of scene complexity)
        static_adjustment = FEASIBILITY_STATIC_BONUS if movement == "static" else 0

        # 4. Reference invariant penalties (P3 + P4)
        height_penalty, depth_penalty = self._invariant_penalties(
            shot_type, movement, ref_invariants
        )

        # 5. Location architecture constraint penalty (P3)
        architecture_penalty = self._location_penalty(movement, location_invariant)

        final = max(
            0,
            min(
                100,
                base + action_adjustment + static_adjustment
                - height_penalty - depth_penalty - architecture_penalty,
            ),
        )
        return FeasibilityBreakdown(
            base=base,
            action_adjustment=action_adjustment,
            static_adjustment=static_adjustment,
            camera_height_penalty=height_penalty,
            depth_penalty=depth_penalty,
            architecture_penalty=architecture_penalty,
            final=final,
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _invariant_penalties(
        self,
        shot_type: str,
        movement: str,
        ref_invariants: Any | None,
    ) -> tuple[int, int]:
        if ref_invariants is None:
            return (0, 0)

        # P3: camera height × movement
        height = ref_invariants.camera_height_class
        height_val = height.value if hasattr(height, "value") else str(height)
        height_penalty = _HEIGHT_MOVEMENT_PENALTY.get((height_val, movement), 0)

        # P4: shot type × dominant depth layer
        dominant = ref_invariants.depth_layers.dominant_layer
        depth_penalty = _SHOT_DEPTH_PENALTY.get((shot_type, dominant), 0)

        return (height_penalty, depth_penalty)

    def _location_penalty(
        self,
        movement: str,
        location_invariant: Any | None,
    ) -> int:
        if location_invariant is None:
            return 0
        arch = location_invariant.get("architecture_style", "")
        return _ARCHITECTURE_MOVEMENT_PENALTY.get((arch, movement), 0)
