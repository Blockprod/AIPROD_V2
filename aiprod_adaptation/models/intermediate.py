"""
Intermediate representations (IR) for the AIPROD pipeline.

These TypedDicts define the strict contracts between pipeline passes:

  Pass 1 → RawScene   → Pass 2
  Pass 2 → VisualScene → Pass 3
  Pass 3 → ShotDict   → Pass 4

Using TypedDict (not Pydantic) keeps zero runtime overhead while giving
mypy full static visibility into every key used between passes.
"""

from __future__ import annotations

from typing import Any, List, Optional

from typing_extensions import NotRequired, TypedDict


class RawScene(TypedDict):
    """Output of Pass 1 (segment). Input to Pass 2 (visual_rewrite)."""
    scene_id:    str
    characters:  List[str]
    location:    str
    time_of_day: Optional[str]
    raw_text:    str


class VisualScene(TypedDict):
    """Output of Pass 2 (visual_rewrite). Input to Pass 3 (simplify_shots)."""
    scene_id:       str
    characters:     List[str]
    location:       str
    time_of_day:    Optional[str]
    visual_actions: List[str]
    dialogues:      List[str]
    emotion:        str


class ShotDict(TypedDict):
    """Output of Pass 3 (simplify_shots). Input to Pass 4 (compile_episode)."""
    shot_id:          str
    scene_id:         str
    prompt:           str
    duration_sec:     int
    emotion:          str
    shot_type:        str   # "wide" | "medium" | "close_up" | "pov"
    camera_movement:  str   # "static" | "follow" | "pan"
    metadata:         NotRequired[dict[str, Any]]
