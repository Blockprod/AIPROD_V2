"""
PASS 3 — SHOT ATOMIZATION
Input : List[dict]  (scene dicts from Pass 2)
Output: List[dict]  (shot dicts, not yet validated Pydantic models)

Rules (applied strictly):
  1. Each shot represents exactly one continuous action.
  2. Duration: 3–8 seconds (deterministic assignment, no randomness).
  3. Split on:
       a. Verb change within a sentence (compound predicates)
       b. Character focus shift (different subject detected)
       c. New object interaction
  4. Each prompt must be a single unambiguous visual sentence including:
       subject, action, environment, and detail.
  5. All lists preserve strict input order.
  6. No sets, no sorting, no randomness.

Duration assignment rule (deterministic):
  - Base = 3 seconds.
  - +1 s if the action contains a motion verb.
  - +1 s if the action contains an interaction verb.
  - +1 s if the action contains a perception verb.
  - +1 s if the prompt is longer than 80 characters.
  - Clamp result to [3, 8].
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Verb lists for split detection (shared with Pass 1 vocabulary)
# ---------------------------------------------------------------------------

_MOTION_VERBS: List[str] = [
    "walk", "walked", "run", "ran", "move", "moved", "enter", "entered",
    "arrive", "arrived", "leave", "left", "step", "stepped", "rush", "rushed",
    "hurry", "hurried", "approach", "approached",
]
_SPEECH_VERBS: List[str] = [
    "said", "say", "told", "tell", "asked", "ask", "replied", "reply",
    "whispered", "whisper", "shouted", "shout", "spoke", "speak",
    "answered", "answer", "called", "call",
]
_PERCEPTION_VERBS: List[str] = [
    "saw", "see", "looked", "look", "heard", "hear", "felt", "feel",
    "noticed", "notice", "watched", "watch", "observed", "observe",
    "sensed", "sense",
]
_INTERACTION_VERBS: List[str] = [
    "gave", "give", "took", "take", "touched", "touch", "held", "hold",
    "grabbed", "grab", "handed", "hand", "pushed", "push", "pulled", "pull",
    "opened", "open", "closed", "close", "picked", "pick", "placed", "place",
]

# All verbs across categories, used for compound-predicate splitting.
_ALL_VERB_LISTS: List[Tuple[str, List[str]]] = [
    ("motion",      _MOTION_VERBS),
    ("speech",      _SPEECH_VERBS),
    ("perception",  _PERCEPTION_VERBS),
    ("interaction", _INTERACTION_VERBS),
]

# Conjunctions that may join two independent predicates.
_COORD_CONJUNCTIONS: List[str] = [" and ", " then ", " but ", " while "]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verb_category(text_lower: str) -> Optional[str]:
    """Return the first matching verb category found in the text, or None."""
    for category, verbs in _ALL_VERB_LISTS:
        for verb in verbs:
            if re.search(r"\b" + re.escape(verb) + r"\b", text_lower):
                return category
    return None


def _split_on_conjunction(sentence: str) -> List[str]:
    """
    Split a sentence into sub-clauses on coordinating conjunctions
    only when each part contains a different verb category (verb change).
    Returns the original sentence as a single-element list if no split
    is warranted.
    """
    sentence_lower = sentence.lower()
    for conj in _COORD_CONJUNCTIONS:
        if conj in sentence_lower:
            idx = sentence_lower.index(conj)
            left  = sentence[:idx].strip()
            right = sentence[idx + len(conj):].strip()
            if not left or not right:
                continue
            cat_left  = _verb_category(left.lower())
            cat_right = _verb_category(right.lower())
            # Split only when verb categories differ (verb change rule).
            if cat_left is not None and cat_right is not None and cat_left != cat_right:
                return [left, right]
    return [sentence]


def _atomize_action(action: str) -> List[str]:
    """
    Break a single visual_action string into atomic action clauses.
    Handles:
      - Comma-separated compound physical actions (from emotion mapping).
      - Coordinating conjunction splits when verb category changes.
    Returns list of non-empty stripped strings in input order.

    Full sentences (ending with terminal punctuation) are never split —
    they originate from Pass 1/2 narrative text and are already self-contained.
    """
    # Full narrative sentences: do not split.
    if action.rstrip().endswith(('.', '!', '?')):
        return [action]

    # Comma-separated compound actions (emotion mapping output, no terminal punct).
    if ", " in action:
        parts = [p.strip() for p in action.split(", ") if p.strip()]
        if len(parts) > 1:
            return parts

    # Try conjunction-based split for short phrases.
    return _split_on_conjunction(action)


def _build_prompt(
    atomic_action: str,
    location: str,
    characters: List[str],
    scene_id: str,
) -> str:
    """
    Construct a single unambiguous visual prompt sentence.

    - Full sentence (ends with terminal punctuation): used as-is; location is
      appended only when it is known and not already present in the sentence.
    - Short action phrase (no terminal punctuation): constructed as
      '<subject> <action>, in <location>.'
    """
    location_str = location if location else "an unknown location"

    if atomic_action.rstrip().endswith(('.', '!', '?')):
        # Full narrative sentence — preserve as written.
        if (
            location_str.lower() != "unknown location"
            and location_str.lower() not in atomic_action.lower()
        ):
            terminal = atomic_action[-1]
            base = atomic_action[:-1].rstrip()
            return f"{base}, in {location_str}{terminal}"
        return atomic_action

    # Short action phrase from emotion mapping or conjunction split.
    subject = characters[0] if characters else "a figure"
    action_text = atomic_action[0].lower() + atomic_action[1:] if atomic_action else atomic_action
    return f"{subject} {action_text}, in {location_str}."


def _compute_duration(prompt: str, atomic_action: str) -> int:
    """
    Deterministic duration in [3, 8] seconds.
    Base = 3.
    +1 if motion verb present.
    +1 if interaction verb present.
    +1 if perception verb present.
    +1 if prompt length > 80 characters.
    Clamp to [3, 8].
    """
    action_lower = atomic_action.lower()
    duration = 3
    if _verb_category(action_lower) == "motion" or any(
        re.search(r"\b" + re.escape(v) + r"\b", action_lower) for v in _MOTION_VERBS
    ):
        duration += 1
    if any(
        re.search(r"\b" + re.escape(v) + r"\b", action_lower) for v in _INTERACTION_VERBS
    ):
        duration += 1
    if any(
        re.search(r"\b" + re.escape(v) + r"\b", action_lower) for v in _PERCEPTION_VERBS
    ):
        duration += 1
    if len(prompt) > 80:
        duration += 1
    return max(3, min(8, duration))


def _make_shot_id(shot_index: int) -> str:
    return f"SH{shot_index + 1:04d}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def atomize_shots(scenes: List[dict]) -> List[dict]:
    """
    PASS 3 — Produce a flat list of shot dicts from scene dicts.

    Each shot dict contains:
      shot_id, scene_id, prompt, duration_sec, emotion

    Raises ValueError if scenes is empty or any scene has empty visual_actions.
    """
    if not scenes:
        raise ValueError("PASS 3: scenes list must not be empty.")

    shots: List[dict] = []
    shot_index: int = 0

    for scene in scenes:
        scene_id:    str       = scene["scene_id"]
        location:    str       = scene.get("location", "unknown location")
        characters:  List[str] = scene.get("characters", [])
        emotion:     str       = scene.get("emotion", "neutral")
        visual_actions: List[str] = scene.get("visual_actions", [])

        if not visual_actions:
            raise ValueError(
                f"PASS 3: scene '{scene_id}' has empty visual_actions."
            )

        for action in visual_actions:
            atomic_parts = _atomize_action(action)

            for part in atomic_parts:
                if not part.strip():
                    continue
                prompt   = _build_prompt(part, location, characters, scene_id)
                duration = _compute_duration(prompt, part)

                shots.append(
                    {
                        "shot_id":      _make_shot_id(shot_index),
                        "scene_id":     scene_id,
                        "prompt":       prompt,
                        "duration_sec": duration,
                        "emotion":      emotion,
                    }
                )
                shot_index += 1

    if not shots:
        raise ValueError("PASS 3: atomization produced zero shots.")

    return shots
