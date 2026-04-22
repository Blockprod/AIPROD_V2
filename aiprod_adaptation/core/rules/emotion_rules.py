"""
Emotion rules — single source of truth for pass2_visual.py.

EMOTION_RULES          : ordered list of (emotion_name, trigger_keywords, visual_action).
                         First matching emotion wins for both sentence-level and
                         scene-level detection.
_INTERNAL_THOUGHT_WORDS: verbs whose presence marks a sentence as an internal thought
                         (to be discarded from visual_actions).
"""

from __future__ import annotations

# Ordered list: (emotion_name, trigger_keywords, visual_action)
EMOTION_RULES: list[tuple[str, list[str], str]] = [
    (
        "angry",
        ["angry", "furious", "enraged", "mad", "annoyed"],
        "Clenches fists, jaw tightens, steps forward aggressively.",
    ),
    (
        "scared",
        ["scared", "afraid", "terrified", "fearful", "panicked"],
        "Trembles, takes backward steps, eyes widen.",
    ),
    (
        "sad",
        ["sad", "depressed", "heartbroken", "grieving", "miserable"],
        "Lowers head, moves slowly, shoulders slumped.",
    ),
    (
        "happy",
        ["happy", "joyful", "delighted", "pleased", "cheerful"],
        "Smiles broadly, moves with energy, gestures openly.",
    ),
    (
        "nervous",
        ["nervous", "anxious", "worried", "uneasy", "tense"],
        "Fidgets, paces, bites lip.",
    ),
]

# Internal-thought verbs — sentences containing these are removed from visual_actions.
_INTERNAL_THOUGHT_WORDS: list[str] = [
    "thought", "wondered", "realized", "remembered", "imagined", "believed",
    "knew", "hoped",
]
