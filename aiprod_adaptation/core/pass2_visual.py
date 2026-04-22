"""
PASS 2 — VISUAL REWRITE
Input : scenes: List[dict]  (output from pass1_segment — each dict has
        scene_id, characters, location, time_of_day, raw_text)
Output: List[dict]  — each dict has:
        scene_id, characters, location, time_of_day,
        visual_actions, dialogues, emotion

Transformation rules (strict, deterministic):
  1. Remove internal thoughts: any sentence containing "thought",
     "wondered", "realized", "remembered", "imagined", "believed".
  2. Convert abstract concepts: replace sentences that contain an
     emotion keyword with the exact visual action from the mapping below.
  3. Preserve dialogues exactly (extracted via regex).
  4. Default: if no emotion keyword matches a sentence, keep it as-is.
  5. Pure function: no side effects, no randomness, no external APIs.

Emotion → trigger keywords → visual action mapping:
  angry   → angry/furious/enraged/mad/annoyed
            → "clenches fists, jaw tightens, steps forward aggressively"
  scared  → scared/afraid/terrified/fearful/panicked
            → "trembles, takes backward steps, eyes widen"
  sad     → sad/depressed/heartbroken/grieving/miserable
            → "lowers head, moves slowly, shoulders slumped"
  happy   → happy/joyful/delighted/pleased/cheerful
            → "smiles broadly, moves with energy, gestures openly"
  nervous → nervous/anxious/worried/uneasy/tense
            → "fidgets, paces, bites lip"
  neutral → (no match) → preserve original sentence
"""

from __future__ import annotations

import re

from aiprod_adaptation.models.intermediate import RawScene, VisualScene

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
from .rules.emotion_rules import _INTERNAL_THOUGHT_WORDS, EMOTION_RULES

# Regex to extract quoted dialogue (ASCII straight quotes and typographic curly quotes).
_DIALOGUE_RE: re.Pattern[str] = re.compile(r'["\u201C]([^"\u201C\u201D]*)["\u201D]')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    parts: list[str] = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _is_internal_thought(sentence: str) -> bool:
    lower = sentence.lower()
    for word in _INTERNAL_THOUGHT_WORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", lower):
            return True
    return False


def _detect_emotion_in_text(text_lower: str) -> str:
    """Return the first matching emotion name, or 'neutral'."""
    for emotion_name, keywords, _ in EMOTION_RULES:
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                return emotion_name
    return "neutral"


def _visual_action_for_emotion(emotion: str) -> str | None:
    """Return the visual action string for a named emotion, or None for neutral."""
    for emotion_name, _, visual_action in EMOTION_RULES:
        if emotion_name == emotion:
            return visual_action
    return None


def _transform_sentence(sentence: str) -> str | None:
    """
    Transform one sentence:
    - Internal thought  → None (discard)
    - Dialogue-only     → None (captured separately in dialogues list)
    - Contains dialogue → strip quoted content, keep surrounding action text
    - Contains emotion keyword → replace with corresponding visual action
    - Otherwise → return unchanged
    """
    if _is_internal_thought(sentence):
        return None
    # Strip inline quoted dialogue; keep surrounding action text.
    if _DIALOGUE_RE.search(sentence):
        sentence = _DIALOGUE_RE.sub("", sentence).strip(" ,")
        if not sentence:
            return None  # Pure dialogue — no surrounding action text
    lower = sentence.lower()
    for _, keywords, visual_action in EMOTION_RULES:
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", lower):
                return visual_action
    return sentence


def _extract_dialogues(raw_text: str) -> list[str]:
    """Extract all quoted strings from raw_text, preserving order."""
    return _DIALOGUE_RE.findall(raw_text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def visual_rewrite(scenes: list[RawScene]) -> list[VisualScene]:
    """
    Convert abstract narration into visual actions.

    Args:
        scenes: List of scene dictionaries from pass1_segment
                (each must contain: scene_id, characters, location,
                time_of_day, raw_text)

    Returns:
        List of scene dictionaries with visual_actions, dialogues,
        and emotion fields added.

    Raises ValueError if scenes is empty.
    """
    if not scenes:
        raise ValueError("PASS 2: scenes list must not be empty.")

    output: list[VisualScene] = []

    for scene in scenes:
        raw_text: str = scene.get("raw_text", "")
        if not raw_text.strip():
            raise ValueError(
                f"PASS 2: scene '{scene.get('scene_id', '?')}' has empty raw_text."
            )
        sentences = _split_sentences(raw_text)

        # Detect dominant scene emotion from the full raw_text.
        emotion = _detect_emotion_in_text(raw_text.lower())

        # Extract dialogues via regex.
        dialogues: list[str] = _extract_dialogues(raw_text)

        # Build visual_actions: transform each sentence, discard None.
        visual_actions: list[str] = []
        for sentence in sentences:
            result = _transform_sentence(sentence)
            if result is not None:
                visual_actions.append(result)

        output.append(
            {
                "scene_id":       scene["scene_id"],
                "characters":     list(scene.get("characters", [])),
                "location":       scene.get("location", "Unknown"),
                "time_of_day":    scene.get("time_of_day"),
                "visual_actions": visual_actions,
                "dialogues":      dialogues,
                "emotion":        emotion,
            }
        )

    return output


# Deprecated — use visual_rewrite. Kept for backward compatibility.
def transform_visuals(scenes: list[RawScene]) -> list[VisualScene]:
    """Deprecated. Use visual_rewrite()."""
    import warnings
    warnings.warn(
        "transform_visuals() is deprecated. Use visual_rewrite().",
        DeprecationWarning,
        stacklevel=2,
    )
    return visual_rewrite(scenes)
