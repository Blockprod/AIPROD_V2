"""
PASS 1 — SEGMENTATION
Input : str raw_text
Output: List[dict]  (intermediate scene dicts, not yet validated Pydantic models)

Rules (applied strictly, in order):
  1. Split by double newlines to obtain paragraphs.
  2. Within each paragraph, further split into sentences (on ". " / "! " / "? ").
  3. Open a new scene when ANY of the following triggers fire:
       a. Location phrase detected in a sentence
          ("in the ", "inside the ", "at the ", "entered the ",
           "arrived at ", "moved to ")
       b. Time phrase detected
          ("later", "meanwhile", "the next day", "hours later",
           "the following morning")
       c. Paragraph boundary + action-category change
          (motion → speech → perception → interaction → state change)
  4. Characters: extract only explicit proper nouns (Title-case words that are
     NOT sentence-initial and NOT inside the known trigger vocab).
     Proper-noun detection is purely lexical — no inference.
  5. All lists preserve strict input order.
  6. No sets, no sorting, no randomness.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOCATION_PHRASES: List[str] = [
    "in the ",
    "inside the ",
    "at the ",
    "entered the ",
    "arrived at ",
    "moved to ",
]

TIME_PHRASES: List[str] = [
    "the following morning",
    "the next day",
    "hours later",
    "meanwhile",
    "later",
]

# Verb keywords that characterise each action category.
# Order within each list is irrelevant for detection but preserved for clarity.
_MOTION_VERBS: List[str] = [
    "walk", "walked", "run", "ran", "move", "moved", "enter", "entered",
    "arrive", "arrived", "leave", "left", "step", "stepped", "rush", "rushed",
    "hurry", "hurried",
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
    "opened", "open", "closed", "close",
]
_STATE_VERBS: List[str] = [
    "was", "were", "is", "are", "became", "become", "seemed", "seem",
    "appeared", "appear", "remained", "remain", "stayed", "stay",
    "waited", "wait",
]

_CATEGORY_MAP: Dict[str, List[str]] = {
    "motion": _MOTION_VERBS,
    "speech": _SPEECH_VERBS,
    "perception": _PERCEPTION_VERBS,
    "interaction": _INTERACTION_VERBS,
    "state": _STATE_VERBS,
}

# Default emotion when none can be inferred from trigger vocabulary.
_DEFAULT_EMOTION: str = "neutral"

# Emotion keywords for simple lexical detection (longest match, first wins).
_EMOTION_KEYWORDS: List[tuple[str, str]] = [
    ("excit", "happy"),
    ("happy", "happy"),
    ("joyful", "happy"),
    ("smile", "happy"),
    ("warm", "happy"),
    ("angry", "angry"),
    ("anger", "angry"),
    ("furious", "angry"),
    ("rage", "angry"),
    ("scared", "scared"),
    ("fear", "scared"),
    ("terrif", "scared"),
    ("sad", "sad"),
    ("grief", "sad"),
    ("cry", "sad"),
    ("sobbing", "sad"),
    ("nervous", "nervous"),
    ("nervously", "nervous"),
    ("anxious", "nervous"),
    ("worried", "nervous"),
    ("fidget", "nervous"),
]

# Words that are grammatically capitalised but are NOT proper nouns:
# sentence-initial words, first-person "I", and trigger vocabulary are
# excluded dynamically; this set covers residual false-positives.
_EXCLUDE_WORDS: frozenset[str] = frozenset({
    "The", "A", "An", "He", "She", "They", "We", "It", "His", "Her",
    "Their", "Its", "This", "That", "These", "Those", "Later", "Meanwhile",
    "Suddenly", "Then", "Now", "Here", "There",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> List[str]:
    """Split a block of text into individual sentences."""
    # Split on sentence-ending punctuation followed by whitespace or end.
    parts: List[str] = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _detect_location(sentence_lower: str) -> Optional[str]:
    """Return the first matching location phrase, or None."""
    for phrase in LOCATION_PHRASES:
        if phrase in sentence_lower:
            # Extract the location noun phrase that follows the trigger.
            idx = sentence_lower.index(phrase) + len(phrase)
            remainder = sentence_lower[idx:]
            # Take up to the first punctuation or end of sentence.
            loc_match = re.match(r"[a-z0-9 '-]+", remainder)
            if loc_match:
                raw = loc_match.group(0).strip()
                # Stop at coordinating conjunctions to avoid over-extraction.
                for conj in (" and ", " but ", " or ", " then "):
                    if conj in raw:
                        raw = raw[: raw.index(conj)]
                return raw.strip()
            return "unknown location"
    return None


def _detect_time(sentence_lower: str) -> Optional[str]:
    """Return the first matching time phrase, or None."""
    for phrase in TIME_PHRASES:
        if phrase in sentence_lower:
            return phrase
    return None


def _action_category(sentence_lower: str) -> str:
    """Return the action category of a sentence based on verb keywords."""
    for category, verbs in _CATEGORY_MAP.items():
        for verb in verbs:
            if re.search(r"\b" + re.escape(verb) + r"\b", sentence_lower):
                return category
    return "state"  # default fallback


def _extract_emotion(text_lower: str) -> str:
    """Return the first detected emotion keyword, or the default."""
    for keyword, emotion in _EMOTION_KEYWORDS:
        if keyword in text_lower:
            return emotion
    return _DEFAULT_EMOTION


def _extract_proper_nouns(sentences: List[str]) -> List[str]:
    """
    Extract explicit proper nouns from a list of sentences.

    Rules:
    - A token is a proper noun candidate if it is Title-Case and:
        1. It is NOT the very first token of a sentence.
        2. It is NOT in _EXCLUDE_WORDS.
        3. It is a purely alphabetic string (no digits, no punctuation).
    - Preserve first-occurrence order; no duplicates; no sets.
    """
    seen: List[str] = []
    for sentence in sentences:
        tokens = sentence.split()
        for i, token in enumerate(tokens):
            # Strip trailing punctuation for analysis.
            clean = token.rstrip(".,!?;:\"'")
            if not clean.isalpha():
                continue
            if not clean[0].isupper():
                continue
            if i == 0:
                # Sentence-initial capitalisation — skip.
                continue
            if clean in _EXCLUDE_WORDS:
                continue
            if clean not in seen:
                seen.append(clean)
    return seen


def _make_scene_id(index: int) -> str:
    return f"SC{index + 1:03d}"


def _build_scene(
    scene_index: int,
    sentences: List[str],
    location: str,
    time_of_day: Optional[str],
) -> dict:
    """Assemble a raw intermediate scene dict from collected sentences."""
    full_text = " ".join(sentences)
    full_lower = full_text.lower()

    characters = _extract_proper_nouns(sentences)
    emotion = _extract_emotion(full_lower)

    # Dialogues: sentences containing quoted speech.
    dialogues: List[str] = [
        s for s in sentences if '"' in s or "'" in s
    ]

    # Visual actions: all non-dialogue sentences (internal thoughts kept
    # verbatim at this stage; Pass 2 will convert them to observable actions).
    visual_actions: List[str] = [
        s for s in sentences if s not in dialogues
    ]

    return {
        "scene_id": _make_scene_id(scene_index),
        "characters": characters,
        "location": location,
        "time_of_day": time_of_day,
        "visual_actions": visual_actions,
        "dialogues": dialogues,
        "emotion": emotion,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def segment(raw_text: str) -> List[dict]:
    """
    PASS 1 — Segment raw_text into a list of intermediate scene dicts.

    Raises ValueError on empty input.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("PASS 1: raw_text must not be empty.")

    # Step 1: Split into paragraphs on double newlines.
    paragraphs: List[str] = [
        p.strip() for p in re.split(r"\n{2,}", raw_text) if p.strip()
    ]

    scenes: List[dict] = []
    scene_index: int = 0

    for para_idx, paragraph in enumerate(paragraphs):
        sentences = _split_sentences(paragraph)
        if not sentences:
            continue

        # Track action category of the previous sentence within this paragraph
        # for intra-paragraph category-change detection.
        prev_category: Optional[str] = None
        # Accumulator for the current scene's sentences.
        current_sentences: List[str] = []
        current_location: str = "unknown location"
        current_time: Optional[str] = None

        # When crossing a paragraph boundary we must check for category change
        # vs the last sentence of the previous scene.
        if scenes:
            last_scene = scenes[-1]
            last_visual = last_scene.get("visual_actions", [])
            if last_visual:
                prev_category = _action_category(last_visual[-1].lower())

        for sent_idx, sentence in enumerate(sentences):
            sent_lower = sentence.lower()

            loc = _detect_location(sent_lower)
            time = _detect_time(sent_lower)
            category = _action_category(sent_lower)

            # Determine whether to open a new scene.
            open_new_scene: bool = False

            if loc is not None:
                open_new_scene = True
            elif time is not None:
                open_new_scene = True
            elif (
                sent_idx == 0
                and para_idx > 0
                and prev_category is not None
                and category != prev_category
            ):
                # Paragraph boundary + category change.
                open_new_scene = True

            if open_new_scene and current_sentences:
                # Flush the current accumulator as a complete scene.
                scenes.append(
                    _build_scene(
                        scene_index,
                        current_sentences,
                        current_location,
                        current_time,
                    )
                )
                scene_index += 1
                current_sentences = []
                current_location = "unknown location"
                current_time = None

            # Update location / time for the new (or continuing) scene.
            if loc is not None:
                current_location = loc
            if time is not None:
                current_time = time

            current_sentences.append(sentence)
            prev_category = category

        # Flush remaining sentences as the final scene of this paragraph.
        if current_sentences:
            scenes.append(
                _build_scene(
                    scene_index,
                    current_sentences,
                    current_location,
                    current_time,
                )
            )
            scene_index += 1

    if not scenes:
        raise ValueError("PASS 1: segmentation produced zero scenes.")

    return scenes
