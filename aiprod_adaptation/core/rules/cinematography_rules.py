"""
Cinematography rules — single source of truth for pass3_shots.py.

These rule tables drive the deterministic shot_type and camera_movement
calculation for each shot produced by Pass 3.

shot_type values   : "wide" | "medium" | "close_up" | "pov"
camera_movement values : "static" | "follow" | "pan"
"""

from __future__ import annotations

from aiprod_adaptation.core.rules.verb_categories import (
    CAMERA_INTERACTION_VERBS,
    CAMERA_MOTION_VERBS,
)

# ---------------------------------------------------------------------------
# shot_type rules
# Evaluated in order — first match wins.
# ---------------------------------------------------------------------------

SHOT_TYPE_RULES: list[tuple[str, list[str]]] = [
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

CAMERA_MOVEMENT_MOTION_KEYWORDS: list[str] = CAMERA_MOTION_VERBS
CAMERA_MOVEMENT_INTERACTION_KEYWORDS: list[str] = CAMERA_INTERACTION_VERBS
