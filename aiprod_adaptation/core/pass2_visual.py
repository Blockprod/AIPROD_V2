"""
PASS 2 — VISUAL TRANSFORMATION
Input : List[dict]  (intermediate scene dicts from Pass 1)
Output: List[dict]  (same structure, visual_actions rewritten)

Rules (applied strictly):
  1. Convert all internal thoughts and abstract concepts to observable
     physical actions using the emotion mapping below.
  2. Preserve dialogues unchanged.
  3. All lists preserve strict input order.
  4. No sets, no sorting, no randomness.

Emotion → observable physical action mapping (exact, non-negotiable):
  angry   → "clenches fists, jaw tightens, steps forward aggressively"
  scared  → "trembles, takes backward steps, eyes widen"
  sad     → "lowers head, moves slowly, shoulders slumped"
  happy   → "smiles broadly, moves with energy, gestures openly"
  nervous → "fidgets, paces, bites lip"
"""

from __future__ import annotations

import re
from typing import Dict, List

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMOTION_PHYSICAL: Dict[str, str] = {
    "angry":   "clenches fists, jaw tightens, steps forward aggressively",
    "scared":  "trembles, takes backward steps, eyes widen",
    "sad":     "lowers head, moves slowly, shoulders slumped",
    "happy":   "smiles broadly, moves with energy, gestures openly",
    "nervous": "fidgets, paces, bites lip",
}

# Patterns that signal internal-thought or abstract-concept sentences.
# Checked in order; first match wins.
_INTERNAL_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\bthought\b",        re.IGNORECASE),
    re.compile(r"\bthink(s|ing)?\b",  re.IGNORECASE),
    re.compile(r"\bfelt\b",           re.IGNORECASE),
    re.compile(r"\bfeel(s|ing)?\b",   re.IGNORECASE),
    re.compile(r"\bwonder(ed|s|ing)?\b", re.IGNORECASE),
    re.compile(r"\bknew\b",           re.IGNORECASE),
    re.compile(r"\bknow(s)?\b",       re.IGNORECASE),
    re.compile(r"\bbelieve(d|s)?\b",  re.IGNORECASE),
    re.compile(r"\bworr(ied|ies|y|ying)\b", re.IGNORECASE),
    re.compile(r"\bimagine(d|s)?\b",  re.IGNORECASE),
    re.compile(r"\bhoped?\b",         re.IGNORECASE),
    re.compile(r"\bfeared?\b",        re.IGNORECASE),
    re.compile(r"\bdreamed?\b",       re.IGNORECASE),
    re.compile(r"\bremember(ed|s)?\b",re.IGNORECASE),
    re.compile(r"\bwished?\b",        re.IGNORECASE),
    re.compile(r"\bdecide(d|s)?\b",   re.IGNORECASE),
    re.compile(r"\brealise(d|s)?\b",  re.IGNORECASE),
    re.compile(r"\brealize(d|s)?\b",  re.IGNORECASE),
    re.compile(r"\bunderst(ood|and|ands)\b", re.IGNORECASE),
    re.compile(r"\bconsidered?\b",    re.IGNORECASE),
]

# Abstract-concept nouns — sentences whose *subject* is one of these
# are treated as abstract even if they contain an action verb.
_ABSTRACT_NOUNS: List[re.Pattern[str]] = [
    re.compile(r"\bfear\b",       re.IGNORECASE),
    re.compile(r"\bdoubt\b",      re.IGNORECASE),
    re.compile(r"\bsorrow\b",     re.IGNORECASE),
    re.compile(r"\bgrief\b",      re.IGNORECASE),
    re.compile(r"\bhope\b",       re.IGNORECASE),
    re.compile(r"\bjoy\b",        re.IGNORECASE),
    re.compile(r"\banger\b",      re.IGNORECASE),
    re.compile(r"\banxiety\b",    re.IGNORECASE),
    re.compile(r"\bsadness\b",    re.IGNORECASE),
    re.compile(r"\bhappiness\b",  re.IGNORECASE),
    re.compile(r"\bnervousness\b",re.IGNORECASE),
    re.compile(r"\bemotion(s)?\b",re.IGNORECASE),
    re.compile(r"\bfeeling(s)?\b",re.IGNORECASE),
    re.compile(r"\bthought(s)?\b",re.IGNORECASE),
    re.compile(r"\bmemor(y|ies)\b",re.IGNORECASE),
    re.compile(r"\bpast\b",       re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_internal_or_abstract(sentence: str) -> bool:
    """Return True if the sentence expresses an internal thought or abstract concept."""
    for pattern in _INTERNAL_PATTERNS:
        if pattern.search(sentence):
            return True
    for pattern in _ABSTRACT_NOUNS:
        if pattern.search(sentence):
            return True
    return False


def _physical_action_for_emotion(emotion: str) -> str:
    """
    Return the canonical physical action string for the given emotion.
    Falls back to a neutral observable description when the emotion is
    not in the mapping (e.g. 'neutral').
    """
    return EMOTION_PHYSICAL.get(
        emotion,
        "stands still, expression unreadable, body composed",
    )


def _transform_sentence(sentence: str, emotion: str) -> str:
    """
    If the sentence is internal/abstract, replace it with the physical
    action corresponding to the scene emotion.
    Otherwise return the sentence unchanged.
    """
    if _is_internal_or_abstract(sentence):
        return _physical_action_for_emotion(emotion)
    return sentence


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transform_visuals(scenes: List[dict]) -> List[dict]:
    """
    PASS 2 — Rewrite visual_actions in each scene dict.

    - Internal-thought / abstract sentences → observable physical action.
    - Dialogues are left untouched.
    - Input list order is preserved exactly.

    Raises ValueError if scenes is empty.
    """
    if not scenes:
        raise ValueError("PASS 2: scenes list must not be empty.")

    output: List[dict] = []

    for scene in scenes:
        emotion: str = scene.get("emotion", "neutral")

        transformed_actions: List[str] = [
            _transform_sentence(action, emotion)
            for action in scene.get("visual_actions", [])
        ]

        # Build a new dict preserving all original keys; only visual_actions
        # is replaced.  We do NOT mutate the input dict.
        new_scene: dict = {
            "scene_id":      scene["scene_id"],
            "characters":    list(scene["characters"]),
            "location":      scene["location"],
            "time_of_day":   scene.get("time_of_day"),
            "visual_actions": transformed_actions,
            "dialogues":     list(scene["dialogues"]),
            "emotion":       emotion,
        }
        output.append(new_scene)

    return output
