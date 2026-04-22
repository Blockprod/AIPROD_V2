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

from aiprod_adaptation.models.intermediate import ShotDict, VisualScene

from .rules.cinematography_rules import (
    CAMERA_MOVEMENT_INTERACTION_KEYWORDS,
    CAMERA_MOVEMENT_MOTION_KEYWORDS,
    SHOT_TYPE_DEFAULT,
    SHOT_TYPE_RULES,
)
from .rules.verb_categories import INTERACTION_VERBS as _INTERACTION_VERBS

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
from .rules.verb_categories import MOTION_VERBS as _MOTION_VERBS
from .rules.verb_categories import PERCEPTION_VERBS as _PERCEPTION_VERBS

_AMBIGUOUS_RE = re.compile(r"\b(seems?|appears?|perhaps|maybe)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_any(text_lower: str, verbs: list[str]) -> bool:
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


def _atomize_action(action: str) -> list[str]:
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

def simplify_shots(scenes: list[VisualScene]) -> list[ShotDict]:
    """
    Decompose visual scenes into atomic shots.

    Args:
        scenes: List of scene dictionaries from pass2_visual

    Returns:
        List of shot dictionaries with shot_id, scene_id, prompt, duration_sec, emotion
    """
    if not scenes:
        raise ValueError("PASS 3: scenes list must not be empty.")

    shots: list[ShotDict] = []

    for scene in scenes:
        scene_id:       str       = scene["scene_id"]
        location:       str       = scene.get("location", "unknown location")
        emotion:        str       = scene.get("emotion", "neutral")
        visual_actions: list[str] = scene.get("visual_actions", [])
        # NOTE: pacing/time_of_day_visual/dominant_sound are only populated on the LLM
        # path (StoryExtractor via Normalizer). On the rule-based path (Pass1→Pass2),
        # these fields always equal their defaults ("medium" / "day" / "dialogue").
        pacing:         str       = scene.get("pacing", "medium")
        tod_visual:     str       = scene.get("time_of_day_visual", "day")
        dom_sound:      str       = scene.get("dominant_sound", "dialogue")

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
                if pacing == "fast":
                    duration = min(duration, 5)
                elif pacing == "slow":
                    duration = max(duration, 5)
                shots.append(
                    {
                        "shot_id":         _make_shot_id(scene_id, shot_num),
                        "scene_id":        scene_id,
                        "prompt":          prompt,
                        "duration_sec":    duration,
                        "emotion":         emotion,
                        "shot_type":       stype,
                        "camera_movement": movement,
                        "metadata": {
                            "time_of_day_visual": tod_visual,
                            "dominant_sound":     dom_sound,
                        },
                    }
                )
                shot_num += 1

    if not shots:
        raise ValueError("PASS 3: atomization produced zero shots.")

    return shots


# Deprecated — use simplify_shots. Kept for backward compatibility.
def atomize_shots(scenes: list[VisualScene]) -> list[ShotDict]:
    """Deprecated. Use simplify_shots()."""
    import warnings
    warnings.warn(
        "atomize_shots() is deprecated. Use simplify_shots().",
        DeprecationWarning,
        stacklevel=2,
    )
    return simplify_shots(scenes)
