"""
PASS 1 — SEGMENTATION
Input : raw_text: str
Output: List[dict]  — one dict per scene with keys:
    scene_id   : str           — format "SCN_001", "SCN_002", ...
    characters : List[str]     — explicit proper nouns only, input order
    location   : str           — detected noun phrase, default "Unknown"
    time_of_day: Optional[str] — detected time phrase, or None
    raw_text   : str           — original paragraph text of the scene

Segmentation rules (strict, deterministic):
  1. Split input by double newlines to identify paragraphs.
  2. Open a new scene when ANY of the following conditions is met:
       a. Explicit location change: "in the ", "inside the ", "at the ",
          "entered the ", "arrived at ", "moved to "
       b. Explicit time shift: "later", "meanwhile", "the next day",
          "hours later", "the following morning"
       c. Paragraph break combined with a major action category change
          (motion / speech / perception / interaction / state)
  3. Extract characters as capitalized proper nouns only. No inference.
  4. No emotional analysis. No creative interpretation.
  5. Pure function: fully deterministic, no side effects.
"""

from __future__ import annotations

import re

from aiprod_adaptation.models.intermediate import RawScene

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
from .rules.segmentation_rules import LOCATION_PHRASES, TIME_PHRASES

_MOTION_VERBS: list[str] = [
    "walk", "walked", "run", "ran", "move", "moved", "enter", "entered",
    "arrive", "arrived", "leave", "left", "step", "stepped", "rush", "rushed",
    "hurry", "hurried",
]
_SPEECH_VERBS: list[str] = [
    "said", "say", "told", "tell", "asked", "ask", "replied", "reply",
    "whispered", "whisper", "shouted", "shout", "spoke", "speak",
    "answered", "answer", "called", "call",
]
_PERCEPTION_VERBS: list[str] = [
    "saw", "see", "looked", "look", "heard", "hear", "felt", "feel",
    "noticed", "notice", "watched", "watch", "observed", "observe",
    "sensed", "sense",
]
_INTERACTION_VERBS: list[str] = [
    "gave", "give", "took", "take", "touched", "touch", "held", "hold",
    "grabbed", "grab", "handed", "hand", "pushed", "push", "pulled", "pull",
    "opened", "open", "closed", "close",
]
_STATE_VERBS: list[str] = [
    "was", "were", "is", "are", "became", "become", "seemed", "seem",
    "appeared", "appear", "remained", "remain", "stayed", "stay",
    "waited", "wait",
]

_CATEGORY_VERBS: list[tuple[str, list[str]]] = [
    ("motion",      _MOTION_VERBS),
    ("speech",      _SPEECH_VERBS),
    ("perception",  _PERCEPTION_VERBS),
    ("interaction", _INTERACTION_VERBS),
    ("state",       _STATE_VERBS),
]

_EXCLUDE_WORDS: frozenset[str] = frozenset({
    "The", "A", "An", "He", "She", "They", "We", "It", "His", "Her",
    "Their", "Its", "This", "That", "These", "Those", "Later", "Meanwhile",
    "Suddenly", "Then", "Now", "Here", "There",
})

# Single-word location names too generic to be useful in prompts.
# _detect_location returns "Unknown" for these, which suppresses the
# ", in room." / ", in door." suffix in shot prompts.
_GENERIC_LOCATIONS: frozenset[str] = frozenset({
    "room", "door", "table", "window", "wall", "floor",
    "stairs", "hall", "hallway", "corridor",
})




# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scene_id(index: int) -> str:
    return f"SCN_{index + 1:03d}"


def _split_sentences(text: str) -> list[str]:
    parts: list[str] = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _action_category(sentence_lower: str) -> str:
    for category, verbs in _CATEGORY_VERBS:
        for verb in verbs:
            if re.search(r"\b" + re.escape(verb) + r"\b", sentence_lower):
                return category
    return "state"


def _detect_location(sentence_lower: str) -> str | None:
    for phrase in LOCATION_PHRASES:
        if phrase in sentence_lower:
            idx = sentence_lower.index(phrase) + len(phrase)
            remainder = sentence_lower[idx:]
            match = re.match(r"[a-z0-9 '-]+", remainder)
            if match:
                raw = match.group(0).strip()
                for conj in (" and ", " but ", " or ", " then "):
                    if conj in raw:
                        raw = raw[: raw.index(conj)]
                raw = raw.strip()
                if not raw or raw in _GENERIC_LOCATIONS:
                    return "Unknown"
                return raw
            return "Unknown"
    return None


def _detect_time(sentence_lower: str) -> str | None:
    for phrase in TIME_PHRASES:
        if phrase in sentence_lower:
            return phrase
    return None


def _collect_confirmed_nouns(all_paragraphs: list[str]) -> frozenset[str]:
    """Pre-scan all paragraphs; return words that appear at non-initial token
    position in at least one sentence (these are reliably proper nouns)."""
    confirmed: set[str] = set()
    for para in all_paragraphs:
        for sentence in _split_sentences(para):
            tokens = sentence.split()
            for i, token in enumerate(tokens):
                if i == 0:
                    continue
                clean = re.sub(r"'s?$", "", token).rstrip(".,!?;:\"'")
                if clean.isalpha() and clean[0].isupper() and clean not in _EXCLUDE_WORDS:
                    confirmed.add(clean)
    return frozenset(confirmed)


def _extract_proper_nouns(
    sentences: list[str], confirmed: frozenset[str]
) -> list[str]:
    seen: list[str] = []
    for sentence in sentences:
        tokens = sentence.split()
        for i, token in enumerate(tokens):
            clean = re.sub(r"'s?$", "", token).rstrip(".,!?;:\"'")
            if not clean.isalpha():
                continue
            if not clean[0].isupper():
                continue
            # Sentence-initial word: only keep if confirmed at non-initial
            # position elsewhere in the document (avoids "Together", "Hours",
            # "Seagulls" etc. while preserving "Marcus", "Clara", "Thomas").
            if i == 0 and clean not in confirmed:
                continue
            if clean in _EXCLUDE_WORDS:
                continue
            if clean not in seen:
                seen.append(clean)
    return seen


def _build_scene(
    index: int,
    paragraphs: list[str],
    location: str,
    time_of_day: str | None,
    confirmed: frozenset[str],
) -> RawScene:
    raw = " ".join(paragraphs)
    sentences = _split_sentences(raw)
    characters = _extract_proper_nouns(sentences, confirmed)
    return {
        "scene_id":    _make_scene_id(index),
        "characters":  characters,
        "location":    location,
        "time_of_day": time_of_day,
        "raw_text":    raw,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def segment(raw_text: str) -> list[RawScene]:
    """
    PASS 1 — Segment raw_text into a list of intermediate scene dicts.
    Raises ValueError on empty input or when segmentation produces zero scenes.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("PASS 1: raw_text must not be empty.")

    paragraphs: list[str] = [
        p.strip() for p in re.split(r"\n{2,}", raw_text) if p.strip()
    ]

    # Global pre-scan to find confirmed proper nouns (appear at non-initial
    # position at least once — ensures character names at sentence-start are kept).
    confirmed = _collect_confirmed_nouns(paragraphs)

    scenes:      list[RawScene] = []
    scene_index: int = 0

    current_paragraphs: list[str] = []
    current_location:   str = "Unknown"
    current_time:       str | None = None
    prev_category:      str | None = None

    for para_idx, paragraph in enumerate(paragraphs):
        sentences = _split_sentences(paragraph)
        if not sentences:
            continue

        # Detect triggers in this paragraph.
        loc:  str | None = None
        time: str | None = None
        for sentence in sentences:
            sl = sentence.lower()
            if loc is None:
                loc = _detect_location(sl)
            if time is None:
                time = _detect_time(sl)

        first_category = _action_category(sentences[0].lower())

        open_new_scene = False
        if loc is not None:
            open_new_scene = True
        elif time is not None:
            open_new_scene = True
        elif (
            para_idx > 0
            and prev_category is not None
            and first_category != prev_category
        ):
            open_new_scene = True

        if open_new_scene and current_paragraphs:
            scenes.append(
                _build_scene(
                    scene_index, current_paragraphs, current_location, current_time, confirmed
                )
            )
            scene_index += 1
            current_paragraphs = []
            current_location = "Unknown"
            current_time = None

        if loc is not None:
            current_location = loc
        if time is not None:
            current_time = time

        current_paragraphs.append(paragraph)
        prev_category = _action_category(sentences[-1].lower())

    if current_paragraphs:
        scenes.append(
            _build_scene(scene_index, current_paragraphs, current_location, current_time, confirmed)
        )

    if not scenes:
        raise ValueError("PASS 1: segmentation produced zero scenes.")

    return scenes
