"""
PASS 2 — CINEMATIC VISUAL REWRITE  (AIPROD_Cinematic v3.0)
===========================================================
Input : scenes: list[RawScene | CinematicScene]
        visual_bible: VisualBible | None = None
Output: list[VisualScene]

Transformation pipeline (deterministic, rule-based — no LLM):
--------------------------------------------------------------
1.  Parse sentences; strip internal thoughts; extract dialogues.
2.  Detect dominant emotion from full raw_text (EMOTION_RULES, first-match).
3.  Determine intensity tier (subtle/mid/explosive) from emotional_arc_index
    (Pass 1 field). Apply CONTEXT_INTENSITY_MODIFIERS from ±2-sentence window.
    Apply BEAT_TYPE_INTENSITY_FLOOR (climax/action → minimum "mid").
4.  Look up EMOTION_BODY_LANGUAGE[emotion][tier] → 5-layer dict.
5.  Apply SCENE_TYPE_ACTION_MODIFIERS for flashback/dream/montage/cliffhanger.
    Apply DIALOGUE_BEAT_GAZE_OVERRIDE when beat_type == "dialogue_scene".
6.  Compose enriched visual_actions strings from layers + character invariants
    (VisualBible wardrobe_fingerprint, physical_signature, lighting_affinity).
7.  Apply ENVIRONMENT_INTERACTION_RULES for location architecture × emotion.
8.  Detect emotional_layer (EMOTIONAL_LAYER_RULES: disguised/erupting/etc.).
9.  Build PhysicalAction list (one per layer per character).
10. Build BodyLanguageState per character (BODY_LANGUAGE_STATE_AFTER).
11. Propagate Pass-1 cinematic fields unchanged (scene_type, act_position,
    reference_location_id, continuity_flags).

Backward compatibility
----------------------
Signature: visual_rewrite(scenes, visual_bible=None).
RawScene-only callers work without modification — cinematic fields accessed
via .get() with safe defaults. All mandatory VisualScene keys are unchanged.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from aiprod_adaptation.models.intermediate import (
    ActionSpec,
    BodyLanguageState,
    PhysicalAction,
    RawScene,
    VisualScene,
)

if TYPE_CHECKING:
    from aiprod_adaptation.core.visual_bible import VisualBible

# ---------------------------------------------------------------------------
# Rule tables
# ---------------------------------------------------------------------------
from .rules.cinematography_rules import (
    CAMERA_MOVEMENT_INTERACTION_KEYWORDS,
    CAMERA_MOVEMENT_MOTION_KEYWORDS,
)
from .rules.dop_style_rules import SCENE_TONE_KEYWORDS, SCENE_TONE_DEFAULT
from .rules.emotion_rules import _INTERNAL_THOUGHT_WORDS, EMOTION_RULES
from .rules.body_language_rules import (
    BODY_LANGUAGE_STATE_AFTER,
    EMOTION_BODY_LANGUAGE,
    PHYSICAL_ACTION_LAYERS,
)
from .rules.visual_transformation_rules_v3 import (
    BEAT_TYPE_INTENSITY_FLOOR,
    BEAT_TYPE_INTENSITY_FLOOR_DEFAULT,
    CONTEXT_INTENSITY_MODIFIERS,
    DIALOGUE_BEAT_GAZE_OVERRIDE,
    DIALOGUE_BEAT_GESTURE_NOTE,
    EMOTIONAL_LAYER_DEFAULT,
    EMOTIONAL_LAYER_RULES,
    ENVIRONMENT_INTERACTION_RULES,
    INTENSITY_TIER_THRESHOLDS,
    SCENE_TYPE_ACTION_MODIFIERS,
    SILENT_SCENE_WORD_THRESHOLD,
)

# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------

_DIALOGUE_RE: re.Pattern[str] = re.compile(r'["\u201C]([^"\u201C\u201D]*)["\u201D]')

_SPEECH_TAG_RE: re.Pattern[str] = re.compile(
    r"^(?P<subject>[A-Za-z]+) "
    r"(?P<verb>said|asked|replied|whispered|shouted|exclaimed|told|called|answered)"
    r"[.,]?$",
    re.IGNORECASE,
)
_SPEECH_ATTR_PREFIX_RE: re.Pattern[str] = re.compile(
    r"^(?P<subject>[A-Za-z]+) "
    r"(?P<verb>said|asked|replied|whispered|shouted|exclaimed|told|answered)"
    r"\b[^,]*,\s*(?P<detail>.+)$",
    re.IGNORECASE,
)


# ===========================================================================
# --- Section 1: Unchanged v2 helpers (backward compat) ---
# ===========================================================================

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
    for emotion_name, keywords, _ in EMOTION_RULES:
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                return emotion_name
    return "neutral"


def _visual_action_for_emotion(emotion: str) -> str | None:
    for emotion_name, _, visual_action in EMOTION_RULES:
        if emotion_name == emotion:
            return visual_action
    return None


def _normalize_subject(subject: str) -> str:
    return subject[:1].upper() + subject[1:]


def _speaker_visual_label(subject: str) -> str:
    normalized = _normalize_subject(subject)
    generic_by_pronoun = {
        "She": "A woman", "He": "A man", "They": "People",
        "We": "People", "I": "A person", "You": "Someone",
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
    if _is_internal_thought(sentence):
        return None
    if _DIALOGUE_RE.search(sentence):
        sentence = _DIALOGUE_RE.sub("", sentence).strip(" ,")
        sentence = re.sub(r"\s{2,}", " ", sentence).strip(" ,")
        if not sentence:
            return None
        if _SPEECH_TAG_RE.match(sentence.rstrip(".!?,;")):
            return None
        attr_match = _SPEECH_ATTR_PREFIX_RE.match(sentence)
        if attr_match is not None:
            detail = attr_match.group("detail").strip(" ,")
            if not detail:
                return None
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
    return _DIALOGUE_RE.findall(raw_text)


def _slugify_identifier(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "unknown"


def _has_any(text_lower: str, keywords: list[str]) -> bool:
    return any(
        re.search(r"\b" + re.escape(keyword) + r"\b", text_lower)
        for keyword in keywords
    )


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
        "he": "male_subject", "she": "female_subject",
        "they": "group_subject", "we": "group_subject",
        "i": "speaker_subject", "you": "listener_subject",
    }
    first = tokens[0].lower()
    if first in pronoun_subjects:
        return pronoun_subjects[first]
    if first in {"a", "an", "the"} and len(tokens) > 1:
        return _slugify_identifier(tokens[1])
    return _slugify_identifier(tokens[0])


def _extract_action_type_and_target(action: str) -> tuple[str, str | None, list[str]]:
    tokens = re.findall(r"[A-Za-z']+", action)
    lower_tokens = [t.lower() for t in tokens]
    if not lower_tokens:
        return "observe", None, []
    modifiers = [t for t in lower_tokens if t.endswith("ly")]
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
    action_type = lower_tokens[-1] if index >= len(lower_tokens) else lower_tokens[index]
    target: str | None = None
    target_markers = {"to", "toward", "towards", "into", "in", "at", "through", "inside", "onto", "on"}
    for ti in range(index + 1, len(lower_tokens)):
        if lower_tokens[ti] in target_markers:
            remainder = [t for t in lower_tokens[ti + 1:] if t not in {"a", "an", "the"}]
            if remainder:
                target = " ".join(remainder)
            break
    return action_type, target, modifiers


def _build_action_unit(action: str, characters: list[str], location: str) -> ActionSpec:
    action_type, target, modifiers = _extract_action_type_and_target(action)
    return {
        "subject_id":   _extract_subject_id(action, characters),
        "action_type":  action_type,
        "target":       target,
        "modifiers":    modifiers,
        "location_id":  None if location.lower() == "unknown" else _slugify_identifier(location),
        "camera_intent":_infer_camera_intent(action),
        "source_text":  action,
    }


# ===========================================================================
# --- Section 2: Cinematic v3.0 helpers ---
# ===========================================================================

def _arc_index_to_tier(arc_index: float) -> str:
    """Convert emotional_arc_index [0.0, 1.0] to intensity tier string."""
    for threshold, tier in INTENSITY_TIER_THRESHOLDS:
        if arc_index >= threshold:
            return tier
    return "subtle"


def _apply_context_modifiers(arc_index: float, context_text: str) -> float:
    """
    Scan context_text for CONTEXT_INTENSITY_MODIFIERS and apply delta to arc_index.
    Uses whole-word matching to avoid false positives (e.g. "broken" ≠ "broke").
    Clamps result to [0.0, 1.0].
    """
    lower = context_text.lower()
    delta = 0.0
    for marker, mod in CONTEXT_INTENSITY_MODIFIERS.items():
        if re.search(r"\b" + re.escape(marker) + r"\b", lower):
            delta += mod
    return max(0.0, min(1.0, arc_index + delta))


def _apply_intensity_floor(tier: str, beat_type: str) -> str:
    """
    Enforce minimum intensity tier from BEAT_TYPE_INTENSITY_FLOOR.
    Tier ordering: subtle < mid < explosive.
    """
    floor = BEAT_TYPE_INTENSITY_FLOOR.get(beat_type, BEAT_TYPE_INTENSITY_FLOOR_DEFAULT)
    order = ["subtle", "mid", "explosive"]
    tier_idx  = order.index(tier)  if tier  in order else 0
    floor_idx = order.index(floor) if floor in order else 0
    return order[max(tier_idx, floor_idx)]


def _detect_emotional_layer(raw_text: str, emotion: str) -> str:  # noqa: ARG001
    """
    Return the emotional layer name based on context markers in raw_text.
    Evaluated top-to-bottom; first matching rule wins.
    """
    lower = raw_text.lower()
    for markers, emo_wildcard, layer_name in EMOTIONAL_LAYER_RULES:
        if emo_wildcard != "*" and emo_wildcard != emotion:
            continue
        if any(marker in lower for marker in markers):
            return layer_name
    return EMOTIONAL_LAYER_DEFAULT


def _resolve_scene_type_modifiers(scene_type: str) -> dict[str, str | None]:
    """Return the modifier dict for a scene type, defaulting to 'standard'."""
    return SCENE_TYPE_ACTION_MODIFIERS.get(
        scene_type,
        SCENE_TYPE_ACTION_MODIFIERS["standard"],
    )


def _build_layers(
    emotion: str,
    tier: str,
    scene_type: str,
    beat_type: str,
) -> dict[str, str]:
    """
    Look up EMOTION_BODY_LANGUAGE[emotion][tier] and apply scene-type and
    beat-type overrides.  Returns a dict of layer → description string.
    """
    base = EMOTION_BODY_LANGUAGE.get(emotion, EMOTION_BODY_LANGUAGE["neutral"])
    layers: dict[str, str] = dict(base.get(tier, base.get("subtle", {})))

    mods = _resolve_scene_type_modifiers(scene_type)

    # Apply scene-type overrides
    motion_suffix = mods.get("motion_suffix")
    if motion_suffix and "posture" in layers:
        layers["posture"] = f"{layers['posture']}; {motion_suffix}"

    gaze_override = mods.get("gaze_override")
    if gaze_override:
        layers["gaze"] = gaze_override

    gesture_suffix = mods.get("gesture_suffix")
    if gesture_suffix and "gesture" in layers:
        layers["gesture"] = f"{layers['gesture']}; {gesture_suffix}"

    breath_override = mods.get("breath_override")
    if breath_override is None and scene_type == "montage":
        # R08: suppress breath layer entirely in montage
        layers.pop("breath", None)
    elif breath_override is not None:
        layers["breath"] = breath_override

    # R13: dialogue beat gaze override
    if beat_type == "dialogue_scene":
        layers["gaze"]    = DIALOGUE_BEAT_GAZE_OVERRIDE
        layers["gesture"] = f"{layers.get('gesture', '')}; {DIALOGUE_BEAT_GESTURE_NOTE}".lstrip("; ")

    return layers


def _compose_visual_actions_from_layers(
    character_label: str,
    layers: dict[str, str],
    wardrobe_suffix: str,
    location_light: str,
) -> list[str]:
    """
    Compose the list of visual_action strings from the five body-language layers.
    Injects wardrobe and lighting invariants where cinematically relevant.
    """
    actions: list[str] = []

    # Lighting-aware establishing line (only if location_light is non-empty)
    if location_light:
        actions.append(f"{character_label} — {location_light}.")

    # Posture
    if posture := layers.get("posture"):
        actions.append(f"{character_label}: {posture}.")

    # Gesture (inject wardrobe if available)
    if gesture := layers.get("gesture"):
        if wardrobe_suffix:
            actions.append(f"{character_label}: {gesture} — {wardrobe_suffix}.")
        else:
            actions.append(f"{character_label}: {gesture}.")

    # Gaze + micro_expression (combined for concision)
    gaze = layers.get("gaze", "")
    mexpr = layers.get("micro_expression", "")
    if gaze and mexpr:
        actions.append(f"{character_label}: {gaze}; {mexpr}.")
    elif gaze:
        actions.append(f"{character_label}: {gaze}.")
    elif mexpr:
        actions.append(f"{character_label}: {mexpr}.")

    # Breath
    if breath := layers.get("breath"):
        actions.append(f"{character_label} — {breath}.")

    return actions


def _get_location_invariants(
    reference_location_id: str | None,
    visual_bible: "VisualBible | None",
) -> tuple[str, str]:
    """
    Return (lighting_condition, architecture_style) from VisualBible.
    Falls back to empty strings when not available.
    """
    if visual_bible is None or not reference_location_id:
        return "", ""
    loc_data = visual_bible._data.get("locations", {}).get(reference_location_id, {})
    lighting    = loc_data.get("lighting_condition", "")
    arch_style  = loc_data.get("architecture_style",  "")
    return lighting, arch_style


def _get_character_invariant(
    character: str,
    visual_bible: "VisualBible | None",
) -> tuple[str, str]:
    """Return (wardrobe_fingerprint, lighting_affinity) for a character."""
    if visual_bible is None:
        return "", ""
    char_data = visual_bible._data.get("characters", {}).get(character, {})
    wardrobe = char_data.get("wardrobe_fingerprint", "")
    lighting = char_data.get("lighting_affinity", "")
    return wardrobe, lighting


def _get_environmental_interaction(
    arch_style: str,
    emotion: str,
) -> str | None:
    """
    Look up ENVIRONMENT_INTERACTION_RULES for (arch_style, emotion).
    Returns prose string or None.  Falls back to "any" wildcard.
    """
    if not arch_style:
        return None
    # Exact match first
    for rule_arch, rule_emotion, env_action in ENVIRONMENT_INTERACTION_RULES:
        if rule_arch == arch_style and rule_emotion == emotion:
            return env_action
    # Wildcard match
    for rule_arch, rule_emotion, env_action in ENVIRONMENT_INTERACTION_RULES:
        if rule_arch == "any" and rule_emotion == emotion:
            return env_action
    return None


def _build_physical_actions(
    character_id: str,
    layers: dict[str, str],
    tier: str,
) -> list[PhysicalAction]:
    """Build the structured PhysicalAction list from the layers dict."""
    actions: list[PhysicalAction] = []
    for layer in PHYSICAL_ACTION_LAYERS:
        if desc := layers.get(layer):
            actions.append({
                "character_id": character_id,
                "layer":        layer,
                "description":  desc,
                "intensity":    tier,
            })
    return actions


def _build_body_language_state(
    character_id: str,
    emotion: str,
    tier: str,
    posture_desc: str,
) -> BodyLanguageState:
    """Build the BodyLanguageState carried forward from this scene."""
    after = (
        BODY_LANGUAGE_STATE_AFTER
        .get(emotion, BODY_LANGUAGE_STATE_AFTER["neutral"])
        .get(tier, {"energy_level": "still", "gaze_direction": "forward"})
    )
    return {
        "character_id":    character_id,
        "posture":         posture_desc[:80] if posture_desc else "neutral",
        "energy_level":    after["energy_level"],
        "gaze_direction":  after["gaze_direction"],
        "dominant_emotion":emotion,
    }


def _detect_scene_tone(visual_actions: list[str]) -> str:
    """Classify scene_tone from the assembled visual_actions list."""
    combined = " ".join(visual_actions).lower()
    for tone_name, keywords in SCENE_TONE_KEYWORDS:
        for kw in keywords:
            if kw.lower() in combined:
                return tone_name
    return SCENE_TONE_DEFAULT


def _is_silent_scene(raw_text: str, dialogues: list[str]) -> bool:
    """R15: silent scene detection."""
    return len(raw_text.split()) < SILENT_SCENE_WORD_THRESHOLD and not dialogues


# Words that look capitalized but are not character names.
_NOT_CHARACTER_WORDS: frozenset[str] = frozenset({
    "the", "a", "an", "this", "that", "these", "those",
    "he", "she", "they", "we", "i", "you", "it", "one",
    "his", "her", "their", "our", "my", "your", "its",
    "in", "on", "at", "to", "of", "and", "but", "or",
    "with", "for", "from", "by", "as", "then", "also", "nor",
    "inside", "outside", "across", "through", "behind", "beside",
    "suddenly", "slowly", "quickly", "finally", "later", "then",
})


def _extract_primary_character_from_text(raw_text: str) -> str | None:
    """
    Fallback: when Pass 1 returns no characters, extract the first proper-noun-like
    capitalized token from raw_text that is not a common word or sentence-initial word.
    Returns None if no candidate is found.
    """
    tokens = raw_text.split()
    for idx, word in enumerate(tokens):
        clean = re.sub(r"[^A-Za-z']", "", word)
        if not clean:
            continue
        # Skip sentence-initial capitals unless they're mid-sentence
        if idx == 0:
            continue
        if clean[0].isupper() and clean.lower() not in _NOT_CHARACTER_WORDS:
            return clean
    # Re-scan allowing position 0 if no mid-sentence candidate found
    for word in tokens:
        clean = re.sub(r"[^A-Za-z']", "", word)
        if not clean:
            continue
        if clean[0].isupper() and clean.lower() not in _NOT_CHARACTER_WORDS:
            return clean
    return None


# ===========================================================================
# --- Public API ---
# ===========================================================================

def visual_rewrite(
    scenes: list[RawScene],
    visual_bible: "VisualBible | None" = None,
) -> list[VisualScene]:
    """
    PASS 2 — Convert abstract narration into cinematic visual actions.

    Parameters
    ----------
    scenes       : list[RawScene | CinematicScene]
        Output of Pass 1.  CinematicScene fields (scene_type, beat_type,
        emotional_arc_index, etc.) are accessed via .get() — backward
        compatible with plain RawScene dicts.
    visual_bible : VisualBible | None
        Optional series visual bible.  When provided, character wardrobe /
        physical signature and location lighting / architecture are injected
        into the generated action descriptions.

    Returns
    -------
    list[VisualScene]
        All mandatory v2 keys present.  v3.0 cinematic fields populated
        when CinematicScene input or visual_bible is available.

    Raises
    ------
    ValueError if scenes is empty or any scene has empty raw_text.
    """
    if not scenes:
        raise ValueError("PASS 2: scenes list must not be empty.")

    output: list[VisualScene] = []

    for scene in scenes:
        raw_text: str = scene.get("raw_text", "")  # type: ignore[attr-defined]
        if not raw_text.strip():
            raise ValueError(
                f"PASS 2: scene '{scene.get('scene_id', '?')}' has empty raw_text."
            )

        # ----- Basic parsing (v2 compat path) -----
        sentences  = _split_sentences(raw_text)
        dialogues  = _extract_dialogues(raw_text)
        emotion    = _detect_emotion_in_text(raw_text.lower())
        characters = list(scene.get("characters", []))  # type: ignore[attr-defined]
        location   = scene.get("location", "Unknown")   # type: ignore[attr-defined]

        # Fallback: if Pass 1 returned no characters, try to extract from raw_text.
        # This handles very short inputs where Pass 1's regex-based extractor may miss names.
        if not characters:
            guess = _extract_primary_character_from_text(raw_text)
            if guess:
                characters = [guess]

        # ----- Cinematic fields from Pass 1 (NotRequired, safe .get()) -----
        scene_type: str   = scene.get("scene_type", "standard")          # type: ignore[attr-defined]
        beat_type:  str   = scene.get("beat_type",  "exposition")         # type: ignore[attr-defined]
        arc_index:  float = scene.get("emotional_arc_index", 0.5)         # type: ignore[attr-defined]
        ref_loc_id: str | None = scene.get("reference_location_id")       # type: ignore[attr-defined]
        act_pos:    str | None = scene.get("act_position")                 # type: ignore[attr-defined]
        cont_flags: list[str]  = list(scene.get("continuity_flags", []))  # type: ignore[attr-defined]

        # ----- Context window for intensity modifiers (±2-sentence window) -----
        context_text = " ".join(sentences[:4]) if len(sentences) >= 4 else raw_text

        # ----- Intensity tier computation -----
        adjusted_arc = _apply_context_modifiers(arc_index, context_text)
        tier         = _arc_index_to_tier(adjusted_arc)
        tier         = _apply_intensity_floor(tier, beat_type)

        # ----- Emotional layer -----
        emotional_layer = _detect_emotional_layer(raw_text, emotion)

        # ----- Location invariants -----
        lighting_condition, arch_style = _get_location_invariants(ref_loc_id, visual_bible)

        # ----- Body-language layers for primary emotion -----
        layers = _build_layers(emotion, tier, scene_type, beat_type)

        # ----- Per-character processing -----
        physical_actions:    list[PhysicalAction]    = []
        body_language_states: list[BodyLanguageState] = []
        visual_invariants_applied: list[str]          = []

        primary_char = characters[0] if characters else None
        char_label   = primary_char or "Figure"

        if primary_char and visual_bible is not None:
            wardrobe, lighting_affinity = _get_character_invariant(primary_char, visual_bible)
            if wardrobe:
                visual_invariants_applied.append(f"wardrobe:{primary_char}:{wardrobe[:60]}")
            if lighting_affinity:
                visual_invariants_applied.append(f"lighting_affinity:{primary_char}:{lighting_affinity[:60]}")
            wardrobe_suffix = wardrobe[:50] if wardrobe else ""
        else:
            wardrobe_suffix = ""

        if lighting_condition:
            visual_invariants_applied.append(f"location_lighting:{lighting_condition[:60]}")

        char_id = _slugify_identifier(primary_char) if primary_char else "unknown"
        physical_actions.extend(_build_physical_actions(char_id, layers, tier))

        posture_desc = layers.get("posture", "")
        body_language_states.append(
            _build_body_language_state(char_id, emotion, tier, posture_desc)
        )

        # ----- Environmental interactions -----
        environmental_interactions: list[str] = []
        env_action = _get_environmental_interaction(arch_style, emotion)
        if env_action:
            environmental_interactions.append(env_action)
        if lighting_condition:
            environmental_interactions.append(f"light: {lighting_condition}")

        # ----- Compose enriched visual_actions list -----
        is_silent = _is_silent_scene(raw_text, dialogues)

        if is_silent:
            # R15: micro-expression + environmental focus only
            visual_actions: list[str] = []
            if mexpr := layers.get("micro_expression"):
                visual_actions.append(f"{char_label}: {mexpr}.")
            for ei in environmental_interactions[:1]:
                visual_actions.append(f"{ei}.")
            if not visual_actions:
                visual_actions = ["Silence."]
        else:
            # Standard path: compose from layers + v2 sentence fallback
            visual_actions = _compose_visual_actions_from_layers(
                char_label, layers, wardrobe_suffix, lighting_condition
            )

            # Append any non-emotion, non-thought sentences not yet captured
            for sentence in sentences:
                result = _transform_sentence(sentence)
                if result is None:
                    continue
                # Skip if it duplicates the flat v2 action string
                skip = False
                for _, keywords, flat_action in EMOTION_RULES:
                    if any(re.search(r"\b" + re.escape(kw) + r"\b", sentence.lower()) for kw in keywords):
                        skip = True
                        break
                if not skip:
                    visual_actions.append(result)

        # Fallback for pure-dialogue scenes
        if not visual_actions:
            speaker = next(
                (
                    _extract_speech_subject(s) for s in sentences
                    if _extract_speech_subject(s) is not None
                ),
                primary_char,
            )
            visual_actions = [
                f"{_speaker_visual_label(speaker)} speaks."
                if speaker else "Dialogue scene."
            ]

        # ----- Detect scene tone -----
        scene_tone = _detect_scene_tone(visual_actions)

        # ----- Assemble VisualScene -----
        vs: VisualScene = {
            "scene_id":       scene["scene_id"],
            "characters":     characters,
            "location":       location,  # type: ignore[arg-type]
            "time_of_day":    scene.get("time_of_day"),  # type: ignore[attr-defined]
            "visual_actions": visual_actions,
            "dialogues":      dialogues,
            "emotion":        emotion,
            "action_units": [
                _build_action_unit(a, characters, location)  # type: ignore[arg-type]
                for a in visual_actions
            ],
            # v3.0 cinematic fields
            "physical_actions":           physical_actions,
            "environmental_interactions": environmental_interactions,
            "visual_invariants_applied":  visual_invariants_applied,
            "emotional_layer":            emotional_layer,
            "action_intensity":           tier,
            "body_language_states":       body_language_states,
            "scene_tone":                 scene_tone,
            "beat_type":                  beat_type,
            "emotional_beat_index":       adjusted_arc,
        }

        # Propagate Pass-1 provenance fields
        if scene_type != "standard":
            vs["scene_type"] = scene_type
        if act_pos is not None:
            vs["act_position"] = act_pos
        if ref_loc_id is not None:
            vs["reference_location_id"] = ref_loc_id
        if cont_flags:
            vs["continuity_flags"] = cont_flags

        # dominant_sound: set at scene level so pass3_shots.py propagates it
        # to all shots from this scene (no per-shot re-inference needed).
        if dialogues:
            vs["dominant_sound"] = "dialogue"

        time_of_day = scene.get("time_of_day")  # type: ignore[attr-defined]
        if time_of_day in {"dawn", "day", "dusk", "night", "interior"}:
            vs["time_of_day_visual"] = time_of_day

        output.append(vs)

    return output


# ---------------------------------------------------------------------------
# Deprecated alias
# ---------------------------------------------------------------------------

def transform_visuals(scenes: list[RawScene]) -> list[VisualScene]:
    """Deprecated. Use visual_rewrite()."""
    import warnings
    warnings.warn(
        "transform_visuals() is deprecated. Use visual_rewrite().",
        DeprecationWarning,
        stacklevel=2,
    )
    return visual_rewrite(scenes)


