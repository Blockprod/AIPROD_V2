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

from aiprod_adaptation.models.intermediate import ActionSpec, ShotDict, VisualScene

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


def _slugify_identifier(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "unknown"


def _extract_subject_id(action: str, characters: list[str], fallback: str | None) -> str:
    lower = action.lower()
    for character in characters:
        if character.lower() in lower:
            return _slugify_identifier(character)
    if fallback:
        return fallback

    tokens = re.findall(r"[A-Za-z']+", action)
    if not tokens:
        return "unknown_subject"
    first = tokens[0].lower()
    if first in {"a", "an", "the"} and len(tokens) > 1:
        return _slugify_identifier(tokens[1])
    return _slugify_identifier(tokens[0])


def _extract_action_type_and_target(action: str) -> tuple[str, str | None, list[str]]:
    tokens = re.findall(r"[A-Za-z']+", action)
    lower_tokens = [token.lower() for token in tokens]
    if not lower_tokens:
        return "observe", None, []

    modifiers = [token for token in lower_tokens if token.endswith("ly")]
    index = 0
    while index < len(lower_tokens) and lower_tokens[index].endswith("ly"):
        index += 1

    if index < len(lower_tokens) and lower_tokens[index] in {"a", "an", "the"}:
        index += 2
    else:
        index += 1

    while index < len(lower_tokens) and lower_tokens[index] in {
        "am", "is", "are", "was", "were", "be", "been", "being",
        "has", "have", "had", "do", "does", "did",
    }:
        index += 1

    if index >= len(lower_tokens):
        action_type = lower_tokens[-1]
    else:
        action_type = lower_tokens[index]

    target: str | None = None
    target_markers = {
        "to", "toward", "towards", "into", "in",
        "at", "through", "inside", "onto", "on",
    }
    for target_index in range(index + 1, len(lower_tokens)):
        if lower_tokens[target_index] in target_markers:
            remainder = [
                token
                for token in lower_tokens[target_index + 1:]
                if token not in {"a", "an", "the"}
            ]
            if remainder:
                target = " ".join(remainder)
            break

    return action_type, target, modifiers


def _build_action_payload(
    action: str,
    characters: list[str],
    location: str,
    camera_movement: str,
    fallback: ActionSpec | None,
) -> ActionSpec:
    action_type, target, modifiers = _extract_action_type_and_target(action)
    fallback_location = fallback.get("location_id") if fallback is not None else None
    return {
        "subject_id": _extract_subject_id(
            action,
            characters,
            fallback.get("subject_id") if fallback is not None else None,
        ),
        "action_type": action_type,
        "target": target,
        "modifiers": modifiers,
        "location_id": (
            fallback_location
            if fallback_location is not None
            else None if location.lower() == "unknown location" else _slugify_identifier(location)
        ),
        "camera_intent": camera_movement,
        "source_text": action,
    }


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


_SPEECH_VERBS_SOUND: list[str] = [
    "said", "asked", "replied", "whispered", "shouted", "spoke", "speaks",
    "answered", "told", "says", "exclaimed",
    # NOTE: "called" excluded — too ambiguous ("seagulls called", "he called out")
]


def _compute_dominant_sound(action: str) -> str:
    """Infer dominant_sound from the action text."""
    if '"' in action or "\u201C" in action:
        return "dialogue"
    lower = action.lower()
    # Only flag as dialogue when the speech verb is in an attribution context:
    # at end-of-clause (followed by comma or end-of-string), NOT mid-sentence
    # idioms like "said nothing" or "said goodbye".
    for v in _SPEECH_VERBS_SOUND:
        if re.search(r"\b" + v + r"\b\s*[,.]?\s*$", lower):
            return "dialogue"
        if re.search(r"\b" + v + r"\b\s*,", lower):
            return "dialogue"
    return "ambient"


def _build_prompt(action: str, location: str) -> str:
    clean = _AMBIGUOUS_RE.sub("", action).strip().rstrip(".!?,;")
    clean = re.sub(r"\s{2,}", " ", clean).strip()
    if location and location.lower() != "unknown" and location.lower() not in clean.lower():
        return f"{clean}, in {location}."
    return f"{clean}."


def _atomize_action(action: str) -> list[str]:
    """Split a visual_action string into atomic parts.

    Contract for visual_actions entries:
      - preferred form: one declarative visual sentence per list item
      - backward-compatible compact form: multiple short action beats separated by `, `

    Example:
      - "John walks toward the door."
      - "John fidgets, paces, bites his lip"

    Pass 3 only atomizes on the compact `, ` form when the string does not already
    terminate as a sentence.
    """
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
        scenes: List of scene dictionaries from pass2_visual.
            Each scene must provide non-empty visual_actions.
            Expected visual_actions contract:
              - preferred: one declarative visual sentence per item
              - accepted for backward compatibility: a compact beat list separated by `, `
                such as "John fidgets, paces, bites his lip"
            Pass 3 atomizes the compact form into one shot per beat.

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
        action_units:   list[ActionSpec] = scene.get("action_units", [])
        dialogues:      list[str] = scene.get("dialogues", [])
        # NOTE: pacing/time_of_day_visual are only populated on the LLM path.
        # dominant_sound is computed per-shot on the rules path (NotRequired field).
        pacing:             str       = scene.get("pacing", "medium")
        tod_visual:         str       = scene.get("time_of_day_visual", "day")
        scene_dom_sound:    str | None = scene.get("dominant_sound")  # None on rules path

        if not visual_actions:
            raise ValueError(f"PASS 3: scene '{scene_id}' has empty visual_actions.")

        action_parts_with_specs: list[tuple[str, ActionSpec | None]] = []
        for index, action in enumerate(visual_actions):
            seed_action = action_units[index] if index < len(action_units) else None
            for part in _atomize_action(action):
                if part.strip():
                    action_parts_with_specs.append((part, seed_action))

        action_parts = [part for part, _ in action_parts_with_specs]
        single_shot_dialogue_scene = bool(dialogues) and len(action_parts) == 1

        shot_num = 1
        for part, seed_action in action_parts_with_specs:
                stype    = _compute_shot_type(part)
                movement = _compute_camera_movement(part)
                prompt   = _build_prompt(part, location)
                duration = _compute_duration(part)
                action_payload = _build_action_payload(
                    part,
                    list(scene.get("characters", [])),
                    location,
                    movement,
                    seed_action,
                )
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
                        "action":          action_payload,
                        "metadata": {
                            "time_of_day_visual": tod_visual,
                            "dominant_sound": (
                                scene_dom_sound
                                if scene_dom_sound is not None
                                else "dialogue"
                                if single_shot_dialogue_scene
                                else _compute_dominant_sound(part)
                            ),
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
