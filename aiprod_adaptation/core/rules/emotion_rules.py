"""
Emotion rules — single source of truth for pass2_visual.py.

EMOTION_RULES          : ordered list of (emotion_name, trigger_keywords, visual_action).
                         First matching emotion wins for both sentence-level and
                         scene-level detection.
_INTERNAL_THOUGHT_WORDS: verbs whose presence marks a sentence as an internal thought
                         (to be discarded from visual_actions).

v3.0: taxonomy expanded from 5 to 15 emotions with layered body-language descriptors
(micro-expression + posture + proxemics). Existing entries preserved byte-identical.
"""

from __future__ import annotations

# Ordered list: (emotion_name, trigger_keywords, visual_action)
EMOTION_RULES: list[tuple[str, list[str], str]] = [
    # ---- Original 5 (byte-identical, order preserved) ----
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

    # ---- v3.0 extended emotions ----
    (
        "contempt",
        ["contempt", "disdain", "sneer", "scorn", "dismissive"],
        "Corner of mouth pulls back, weight shifts to one hip, maintains deliberate distance.",
    ),
    (
        "grief",
        ["grief", "mourning", "bereaved", "loss", "devastated"],
        "Chest heaves, hands cover face, body folds inward, movement ceases.",
    ),
    (
        "determined",
        ["determined", "resolve", "resolved", "purpose", "focused", "steeled"],
        "Jaw sets, eyes lock forward, spine straightens, pace becomes measured and deliberate.",
    ),
    (
        "shocked",
        ["shocked", "stunned", "disbelief", "startled", "frozen"],
        "Body goes rigid, breath caught, hands open at sides, eyes fixed unblinking.",
    ),
    (
        "relieved",
        ["relieved", "relief", "sigh", "tension releases", "exhales deeply"],
        "Shoulders drop, long exhale, head bows briefly, posture softens.",
    ),
    (
        "suspicious",
        ["suspicious", "wary", "distrustful", "guarded", "watchful"],
        "Eyes narrow, head tilts slightly, body turns at an oblique angle, weight back on heels.",
    ),
    (
        "desperate",
        ["desperate", "desperation", "frantic", "wild-eyed", "last resort"],
        "Rapid shallow breathing, erratic gestures, eyes dart, breaks into motion without direction.",
    ),
    (
        "disgusted",
        ["disgusted", "disgust", "revolted", "nauseated", "repulsed"],
        "Nose wrinkles, upper lip curls, head draws back, hand rises instinctively toward face.",
    ),
    (
        "resigned",
        ["resigned", "resignation", "gives up", "acceptance", "defeated"],
        "Arms drop, shoulders curve forward, gaze drops to middle distance, movement slows to a stop.",
    ),
    (
        "defiant",
        ["defiant", "defiance", "refuses", "unyielding", "stands ground"],
        "Chin raises, feet plant wide, arms cross or hang loose and ready, holds eye contact.",
    ),
]

# Internal-thought verbs — sentences containing these are removed from visual_actions.
_INTERNAL_THOUGHT_WORDS: list[str] = [
    "thought", "wondered", "realized", "remembered", "imagined", "believed",
    "knew", "hoped",
]

