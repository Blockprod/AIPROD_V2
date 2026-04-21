"""
PASS 3 — SHOT ATOMIZATION
Input : List[dict]  (scene dicts from Pass 2, keys: visual_actions, dialogues, emotion)
Output: List[dict]  (shot dicts)

Shot dict keys: shot_id, scene_id, prompt, shot_type, camera_movement, duration_sec, emotion

shot_id format: "<scene_id>_SHOT_<NNN>" (e.g. "SCN_001_SHOT_001", per-scene counter)

Duration rules (deterministic, applied in order):
  Base = 3
  +1 if action contains a motion verb      (walk, run, move, approach)
  +1 if action contains an interaction verb (touch, grab, hold, open)
  +1 if action contains a perception verb   (look, watch, observe, notice)
  +1 if action description length > 10 words
  Clamp to [3, 8]

shot_type (structured field, not prompt prefix):
  close_up — facial expressions or small objects
  wide     — environment or movement
  medium   — character interactions (default)
  pov      — point-of-view shots

camera_movement:
  follow  — subject in motion
  pan     — interaction without locomotion
  static  — no dominant movement (default)
"""

from __future__ import annotations

import re
from typing import List

from aiprod_adaptation.models.intermediate import ShotDict, VisualScene

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

from .rules.duration_rules import _MOTION_VERBS, _INTERACTION_VERBS, _PERCEPTION_VERBS
from .rules.cinematography_rules import (
    SHOT_TYPE_RULES,
    SHOT_TYPE_DEFAULT,
    CAMERA_MOVEMENT_MOTION_KEYWORDS,
    CAMERA_MOVEMENT_INTERACTION_KEYWORDS,
)

_AMBIGUOUS_RE = re.compile(r"\b(seems?|appears?|perhaps|maybe)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_any(text_lower: str, verbs: List[str]) -> bool:
    return any(re.search(r"\b" + re.escape(v) + r"\b", text_lower) for v in verbs)


def _compute_shot_type(action: str) -> str:
    lower = action.lower()
    for shot_type, keywords in SHOT_TYPE_RULES:
        for kw in keywords:
            if kw in lower:
                return shot_type
    return SHOT_TYPE_DEFAULT


def _compute_camera_movement(action: str) -> str:
    lower = action.lower()
    if _has_any(lower, CAMERA_MOVEMENT_MOTION_KEYWORDS):
        return "follow"
    if _has_any(lower, CAMERA_MOVEMENT_INTERACTION_KEYWORDS):
        return "pan"
    return "static"


def _compute_duration(action: str) -> int:
    lower = action.lower()
    duration = 3
    if _has_any(lower, _MOTION_VERBS):
        duration += 1
    if _has_any(lower, _INTERACTION_VERBS):
        duration += 1
    if _has_any(lower, _PERCEPTION_VERBS):
        duration += 1
    if len(action.split()) > 10:
        duration += 1
    return max(3, min(8, duration))


def _build_prompt(action: str, location: str) -> str:
    clean = _AMBIGUOUS_RE.sub("", action).strip()
    clean = re.sub(r"\s{2,}", " ", clean)
    location_str = location if location else "unknown location"
    return f"{clean}, in {location_str}."


def _atomize_action(action: str) -> List[str]:
    """Split a visual_action string into atomic parts."""
    if action.rstrip().endswith(('.', '!', '?')):
        return [action]
    if ", " in action:
        parts = [p.strip() for p in action.split(", ") if p.strip()]
        if len(parts) > 1:
            return parts
    return [action]


def _make_shot_id(scene_id: str, shot_num: int) -> str:
    return f"{scene_id}_SHOT_{shot_num:03d}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def simplify_shots(scenes: List[VisualScene]) -> List[ShotDict]:
    """
    Decompose visual scenes into atomic shots.

    Args:
        scenes: List of scene dictionaries from pass2_visual

    Returns:
        List of shot dictionaries with shot_id, scene_id, prompt, duration_sec, emotion
    """
    if not scenes:
        raise ValueError("PASS 3: scenes list must not be empty.")

    shots: List[ShotDict] = []

    for scene in scenes:
        scene_id:       str       = scene["scene_id"]
        location:       str       = scene.get("location", "unknown location")
        emotion:        str       = scene.get("emotion", "neutral")
        visual_actions: List[str] = scene.get("visual_actions", [])

        if not visual_actions:
            raise ValueError(f"PASS 3: scene '{scene_id}' has empty visual_actions.")

        shot_num = 1
        for action in visual_actions:
            for part in _atomize_action(action):
                if not part.strip():
                    continue
                stype    = _compute_shot_type(part)
                movement = _compute_camera_movement(part)
                prompt   = _build_prompt(part, location)
                duration = _compute_duration(part)
                shots.append(
                    {
                        "shot_id":         _make_shot_id(scene_id, shot_num),
                        "scene_id":        scene_id,
                        "prompt":          prompt,
                        "duration_sec":    duration,
                        "emotion":         emotion,
                        "shot_type":       stype,
                        "camera_movement": movement,
                        "metadata":        {},
                    }
                )
                shot_num += 1

    if not shots:
        raise ValueError("PASS 3: atomization produced zero shots.")

    return shots


# Backward-compatibility alias (engine.py + test_pipeline.py import this name)
atomize_shots = simplify_shots
