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

from aiprod_adaptation.models.intermediate import ActionSpec, RawScene, VisualScene

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
from .rules.cinematography_rules import (
    CAMERA_MOVEMENT_INTERACTION_KEYWORDS,
    CAMERA_MOVEMENT_MOTION_KEYWORDS,
)
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


_SPEECH_TAG_RE: re.Pattern[str] = re.compile(
    r"^(?P<subject>[A-Za-z]+) "
    r"(?P<verb>said|asked|replied|whispered|shouted|exclaimed|told|called|answered)"
    r"[.,]?$",
    re.IGNORECASE,
)

# Strips speech-attribution prefix left after dialogue-quote removal:
# "Clara said quietly, tracing..." → "tracing..."
# "Thomas asked, his voice low." → "his voice low."
# Requires a comma — bare "she said." is caught by _SPEECH_TAG_RE instead.
_SPEECH_ATTR_PREFIX_RE: re.Pattern[str] = re.compile(
    r"^(?P<subject>[A-Za-z]+) "
    r"(?P<verb>said|asked|replied|whispered|shouted|exclaimed|told|answered)"
    r"\b[^,]*,\s*(?P<detail>.+)$",
    re.IGNORECASE,
)


def _normalize_subject(subject: str) -> str:
    return subject[:1].upper() + subject[1:]


def _speaker_visual_label(subject: str) -> str:
    normalized = _normalize_subject(subject)
    generic_by_pronoun = {
        "She": "A woman",
        "He": "A man",
        "They": "People",
        "We": "People",
        "I": "A person",
        "You": "Someone",
    }
    return generic_by_pronoun.get(normalized, normalized)


def _extract_speech_subject(sentence: str) -> str | None:
    stripped = _DIALOGUE_RE.sub("", sentence).strip(" ,")
    stripped = re.sub(r"\s{2,}", " ", stripped).strip(" ,")
    match = _SPEECH_TAG_RE.match(stripped.rstrip(".!?,;"))
    if match is None:
        return None
    return _normalize_subject(match.group("subject"))


def _transform_sentence(sentence: str) -> str | None:
    """
    Transform one sentence:
    - Internal thought  → None (discard)
    - Dialogue-only     → None (captured separately in dialogues list)
    - Contains dialogue → strip quoted content, keep surrounding action text
    - Speech-tag only   → None (e.g. 'she said.', 'Marcus asked.')
    - Contains emotion keyword → replace with corresponding visual action
    - Otherwise → return unchanged
    """
    if _is_internal_thought(sentence):
        return None
    # Strip inline quoted dialogue; keep surrounding action text.
    if _DIALOGUE_RE.search(sentence):
        sentence = _DIALOGUE_RE.sub("", sentence).strip(" ,")
        # Collapse multiple spaces left by adjacent quote removals
        sentence = re.sub(r"\s{2,}", " ", sentence).strip(" ,")
        if not sentence:
            return None  # Pure dialogue — no surrounding action text
        # Discard pure speech tags: "she said.", "Marcus asked.", etc.
        if _SPEECH_TAG_RE.match(sentence.rstrip(".!?,;")):
            return None
        attr_match = _SPEECH_ATTR_PREFIX_RE.match(sentence)
        if attr_match is not None:
            detail = attr_match.group("detail").strip(" ,")
            if not detail:
                return None
            # "his voice low", "her eyes wide" — fragment only, not a visual action.
            if len(detail.split()) < 4:
                return None
            subject = _normalize_subject(attr_match.group("subject"))
            if re.match(r"^[A-Za-z]+ing\b", detail):
                sentence = f"{subject} was {detail}"
            else:
                sentence = detail[0].upper() + detail[1:]
    lower = sentence.lower()
    for _, keywords, visual_action in EMOTION_RULES:
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", lower):
                return visual_action
    return sentence


def _extract_dialogues(raw_text: str) -> list[str]:
    """Extract all quoted strings from raw_text, preserving order."""
    return _DIALOGUE_RE.findall(raw_text)


def _slugify_identifier(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "unknown"


def _has_any(text_lower: str, keywords: list[str]) -> bool:
    return any(re.search(r"\b" + re.escape(keyword) + r"\b", text_lower) for keyword in keywords)


def _infer_camera_intent(action: str) -> str:
    lower = action.lower()
    if _has_any(lower, CAMERA_MOVEMENT_MOTION_KEYWORDS):
        return "follow"
    if _has_any(lower, CAMERA_MOVEMENT_INTERACTION_KEYWORDS):
        return "pan"
    return "static"


def _extract_subject_id(action: str, characters: list[str]) -> str:
    lower = action.lower()
    for character in characters:
        if character.lower() in lower:
            return _slugify_identifier(character)

    tokens = re.findall(r"[A-Za-z']+", action)
    if not tokens:
        return "unknown_subject"

    pronoun_subjects = {
        "he": "male_subject",
        "she": "female_subject",
        "they": "group_subject",
        "we": "group_subject",
        "i": "speaker_subject",
        "you": "listener_subject",
    }
    first = tokens[0].lower()
    if first in pronoun_subjects:
        return pronoun_subjects[first]
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


def _build_action_unit(action: str, characters: list[str], location: str) -> ActionSpec:
    action_type, target, modifiers = _extract_action_type_and_target(action)
    return {
        "subject_id": _extract_subject_id(action, characters),
        "action_type": action_type,
        "target": target,
        "modifiers": modifiers,
        "location_id": None if location.lower() == "unknown" else _slugify_identifier(location),
        "camera_intent": _infer_camera_intent(action),
        "source_text": action,
    }


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

        # Build visual_actions: transform each sentence.
        visual_actions: list[str] = []
        for sentence in sentences:
            result = _transform_sentence(sentence)
            if result is not None:
                visual_actions.append(result)

        # Fallback: if all sentences were discarded (pure-dialogue scene),
        # produce a minimal visual placeholder rather than an empty list.
        if not visual_actions:
            chars: list[str] = list(scene.get("characters", []))
            speaker = next(
                (
                    extracted for extracted in (
                        _extract_speech_subject(sentence) for sentence in sentences
                    )
                    if extracted is not None
                ),
                None,
            )
            if speaker is None and chars:
                speaker = chars[0]
            if speaker is not None:
                visual_actions = [f"{_speaker_visual_label(speaker)} speaks."]
            else:
                visual_actions = ["Dialogue scene."]

        output.append(
            {
                "scene_id":       scene["scene_id"],
                "characters":     list(scene.get("characters", [])),
                "location":       scene.get("location", "Unknown"),
                "time_of_day":    scene.get("time_of_day"),
                "visual_actions": visual_actions,
                "dialogues":      dialogues,
                "emotion":        emotion,
                "action_units":   [
                    _build_action_unit(
                        action,
                        list(scene.get("characters", [])),
                        scene.get("location", "Unknown"),
                    )
                    for action in visual_actions
                ],
            }
        )
        time_of_day = scene.get("time_of_day")
        if time_of_day in {"dawn", "day", "dusk", "night", "interior"}:
            output[-1]["time_of_day_visual"] = time_of_day

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
