"""
Cinematography rules — single source of truth for pass3_shots.py.

These rule tables drive the deterministic shot_type and camera_movement
calculation for each shot produced by Pass 3.

shot_type values   : "wide" | "medium" | "close_up" | "pov"
camera_movement values : "static" | "follow" | "pan"
"""

from __future__ import annotations

from typing import List, Tuple

# ---------------------------------------------------------------------------
# shot_type rules
# Evaluated in order — first match wins.
# ---------------------------------------------------------------------------

SHOT_TYPE_RULES: List[Tuple[str, List[str]]] = [
    ("pov", [
        "pov",
        "point of view",
    ]),
    ("close_up", [
        "smile", "smiles", "smiling",
        "frown", "frowns", "frowning",
        "jaw", "eyes", "lip", "lips", "brow",
        "clench", "clenches", "clenched",
        "stare", "stares", "staring",
        "glare", "glares", "glaring",
        "widen", "widens", "widened",
    ]),
    ("wide", [
        "walk", "walks", "walked",
        "run", "runs", "ran",
        "move", "moves", "moved",
        "approach", "approaches", "approached",
        "rush", "rushes", "rushed",
        "hurry", "hurries", "hurried",
        "stride", "strides", "strode",
        "march", "marches", "marched",
    ]),
]
# Fallback when no rule matches:
SHOT_TYPE_DEFAULT: str = "medium"

# ---------------------------------------------------------------------------
# camera_movement rules
# Motion verbs → "follow"
# Interaction verbs (no motion) → "pan"
# Default → "static"
# ---------------------------------------------------------------------------

CAMERA_MOVEMENT_MOTION_KEYWORDS: List[str] = [
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

CAMERA_MOVEMENT_INTERACTION_KEYWORDS: List[str] = [
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
