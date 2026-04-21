"""
Duration rules — single source of truth for pass3_shots.py.

These verb lists drive the deterministic duration calculation:
  +1 second if the action contains a motion verb
  +1 second if the action contains an interaction verb
  +1 second if the action contains a perception verb
"""

from __future__ import annotations

from typing import List

_MOTION_VERBS: List[str] = [
    "walk", "walks", "walked",
    "run", "runs", "ran",
    "move", "moves", "moved",
    "approach", "approaches", "approached",
]

_INTERACTION_VERBS: List[str] = [
    "touch", "touches", "touched",
    "grab", "grabs", "grabbed",
    "hold", "holds", "held",
    "open", "opens", "opened",
]

_PERCEPTION_VERBS: List[str] = [
    "look", "looks", "looked",
    "watch", "watches", "watched",
    "observe", "observes", "observed",
    "notice", "notices", "noticed",
]
