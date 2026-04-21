"""
Verb categories — single source of truth for all verb lists used across rules modules.

duration_rules.py and cinematography_rules.py import from here.

Two sets of motion/interaction verbs exist intentionally:
  MOTION_VERBS        — used by duration_rules (base locomotion verbs only)
  CAMERA_MOTION_VERBS — used by cinematography_rules (broader set including entry/exit verbs)

Merging them would silently change duration calculations — kept separate by design.
"""

from __future__ import annotations

from typing import List

# ---------------------------------------------------------------------------
# Used by duration_rules.py — drives +1 second duration logic
# ---------------------------------------------------------------------------

MOTION_VERBS: List[str] = [
    "walk", "walks", "walked",
    "run", "runs", "ran",
    "move", "moves", "moved",
    "approach", "approaches", "approached",
]

INTERACTION_VERBS: List[str] = [
    "touch", "touches", "touched",
    "grab", "grabs", "grabbed",
    "hold", "holds", "held",
    "open", "opens", "opened",
]

PERCEPTION_VERBS: List[str] = [
    "look", "looks", "looked",
    "watch", "watches", "watched",
    "observe", "observes", "observed",
    "notice", "notices", "noticed",
]

# ---------------------------------------------------------------------------
# Used by cinematography_rules.py — drives camera_movement logic
# Broader than MOTION_VERBS: includes entry/exit/travel verbs
# ---------------------------------------------------------------------------

CAMERA_MOTION_VERBS: List[str] = [
    "walk", "walks", "walked",
    "run", "runs", "ran",
    "move", "moves", "moved",
    "approach", "approaches", "approached",
    "rush", "rushes", "rushed",
    "hurry", "hurries", "hurried",
    "stride", "strides", "strode",
    "march", "marches", "marched",
    "enter", "enters", "entered",
    "arrive", "arrives", "arrived",
    "leave", "leaves", "left",
    "step", "steps", "stepped",
]

CAMERA_INTERACTION_VERBS: List[str] = [
    "touch", "touches", "touched",
    "grab", "grabs", "grabbed",
    "hold", "holds", "held",
    "open", "opens", "opened",
    "reach", "reaches", "reached",
    "hand", "hands", "handed",
    "give", "gives", "gave",
    "take", "takes", "took",
    "push", "pushes", "pushed",
    "pull", "pulls", "pulled",
]
