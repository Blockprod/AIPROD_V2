"""
DoP Style Rules — deterministic cinematographic grammar for AIPROD_Cinematic v3.0.

This module encodes the Director of Photography's visual language as pure data tables.
All functions are pure (no side effects, no randomness). Every decision is the product
of (beat_type × scene_tone × emotion × time_of_day) → cinematic parameter.

Tables
------
LENS_SELECTION_RULES
    (beat_type, scene_tone) → lens_mm
    Focal length chosen from the series lens kit. Nearest available focal length is
    resolved at runtime via VisualBible.nearest_focal_length().

DOF_RULES
    shot_type → depth_of_field string descriptor
    Used as a prose directive in the shot prompt (e.g. "shallow depth of field, f/1.8").

COLOR_GRADE_RULES
    (scene_tone, time_of_day_visual) → color_grade_hint
    Feeds metadata["color_grade_hint"] and the prompt enrichment layer.

SHOT_SEQUENCE_GRAMMAR
    beat_type → ordered list of shot_type roles
    Defines the canonical shot progression within a scene beat.
    Pass 3 uses this sequence to assign shot_type to consecutive shots.

BEAT_TYPE_KEYWORDS
    beat_type → trigger keyword list
    Used by Pass 1 to classify a scene's beat_type from the raw text.

SCENE_TONE_KEYWORDS
    scene_tone → trigger keyword list
    Used by Pass 2 to classify a scene's tone from the visual action list.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Lens selection rules
# Key: (beat_type, scene_tone) → target focal length in mm
# Fallback: scene_tone="neutral" and/or beat_type="exposition" use 35mm
# Evaluation: iterate LENS_SELECTION_RULES top-to-bottom, first match wins.
# ---------------------------------------------------------------------------

# Each entry: (beat_type_or_None, scene_tone_or_None, lens_mm)
# None means "any" — acts as a wildcard for that dimension.
LENS_SELECTION_RULES: list[tuple[str | None, str | None, int]] = [
    # Claustrophobic tension: wide-angle on climax/action in tense/noir
    ("climax",       "tense",        24),
    ("climax",       "noir",         24),
    ("action",       "tense",        24),
    ("action",       "noir",         24),

    # Intimate close dialogue: standard/short-tele for flattering compression
    ("dialogue_scene", "intimate",   50),
    ("dialogue_scene", "neutral",    50),
    ("dialogue_scene", "tense",      85),  # telephoto = surveillance, lack of privacy
    ("dialogue_scene", "noir",       85),

    # Epic vistas: wide
    ("exposition",   "epic",         24),
    ("action",       "epic",         24),

    # Clinical/surreal: standard lens emphasises flatness
    (None,           "clinical",     50),
    (None,           "surreal",      35),

    # Golden hour / intimate — warm, flattering standard
    (None,           "golden_hour",  50),
    (None,           "intimate",     50),

    # Denouement — reflective telephoto compression
    ("denouement",   None,           85),

    # Transition — wide to reestablish geography
    ("transition",   None,           24),

    # Default
    (None,           None,           35),
]


# ---------------------------------------------------------------------------
# Depth-of-field directives
# Keyed by shot_type.
# ---------------------------------------------------------------------------

DOF_RULES: dict[str, str] = {
    "extreme_close_up": "extremely shallow depth of field, f/1.4",
    "close_up":         "shallow depth of field, f/1.8–2.0",
    "medium_close":     "shallow-to-moderate depth of field, f/2.8",
    "over_shoulder":    "shallow depth of field, f/2.0–2.8, subject in focus, background soft",
    "two_shot":         "moderate depth of field, f/4.0",
    "medium":           "moderate depth of field, f/4.0–5.6",
    "medium_wide":      "moderate-to-deep depth of field, f/5.6–8.0",
    "insert":           "macro depth of field, f/2.8, detail sharp, surroundings diffused",
    "wide":             "deep depth of field, f/8.0",
    "extreme_wide":     "deep depth of field, f/11\u201316",
    "pov":              "sharp focus at subject distance, shallow foreground",
}


# ---------------------------------------------------------------------------
# Color grade rules
# Key: (scene_tone, time_of_day_visual) → color_grade_hint
# None values act as wildcards (checked last).
# ---------------------------------------------------------------------------

COLOR_GRADE_RULES: list[tuple[str | None, str | None, str]] = [
    # Noir at night/dusk → high contrast monochrome-leaning
    ("noir",        "night",     "high_contrast"),
    ("noir",        "dusk",      "high_contrast"),
    ("noir",        "interior",  "high_contrast"),
    ("noir",        None,        "high_contrast"),

    # Tense scenes → desaturated / bleach bypass
    ("tense",       "night",     "bleach_bypass"),
    ("tense",       "interior",  "desaturated"),
    ("tense",       None,        "desaturated"),

    # Golden hour → warm
    ("golden_hour", "dawn",      "warm"),
    ("golden_hour", "dusk",      "warm"),
    ("golden_hour", None,        "warm"),

    # Clinical → desaturated
    ("clinical",    None,        "desaturated"),

    # Epic outdoor → orange-teal
    ("epic",        "day",       "orange_teal"),
    ("epic",        "dawn",      "warm"),
    ("epic",        "dusk",      "warm"),
    ("epic",        None,        "orange_teal"),

    # Intimate → warm
    ("intimate",    "night",     "warm"),
    ("intimate",    "interior",  "warm"),
    ("intimate",    None,        "warm"),

    # Surreal → cool or monochrome
    ("surreal",     "night",     "monochrome"),
    ("surreal",     None,        "cool"),

    # Default cool at night, neutral otherwise
    (None,          "night",     "cool"),
    (None,          "dusk",      "cool"),
    (None,          None,        "neutral"),
]


# ---------------------------------------------------------------------------
# Shot sequence grammar
# beat_type → ordered list of canonical shot roles for a scene
# Pass 3 cycles through this list as it produces shots for a scene.
# ---------------------------------------------------------------------------

SHOT_SEQUENCE_GRAMMAR: dict[str, list[str]] = {
    "exposition":     ["extreme_wide", "wide", "medium", "medium"],
    "action":         ["wide", "wide", "medium", "close_up", "insert"],
    "dialogue_scene": ["medium", "over_shoulder", "close_up", "close_up", "medium"],
    "transition":     ["wide", "medium"],
    "climax":         ["medium", "close_up", "extreme_close_up", "wide", "close_up"],
    "denouement":     ["wide", "medium", "close_up"],
}

# Fallback when beat_type is unknown
SHOT_SEQUENCE_DEFAULT: list[str] = ["wide", "medium", "medium", "close_up"]


# ---------------------------------------------------------------------------
# Beat type detection keywords
# Used by Pass 1 to tag scene beat_type from raw_text.
# Evaluation: first list with any keyword match wins.
# ---------------------------------------------------------------------------

BEAT_TYPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("climax", [
        "finally", "screamed", "explosion", "gunshot", "last chance",
        "everything changed", "crashed", "collapsed", "fought", "detonated",
        "in flames", "broke through",
    ]),
    ("action", [
        "ran", "chased", "fired", "escaped", "dodged", "tackled", "leapt",
        "sprinted", "burst through", "ambushed", "attacked", "struggled",
    ]),
    ("dialogue_scene", [
        "said", "replied", "asked", "whispered", "shouted", "told",
        "answered", "argued", "confessed", "admitted", "explained",
        "\"", "\u201C",
    ]),
    ("transition", [
        "meanwhile", "later", "the next day", "the following morning",
        "hours later", "weeks later", "elsewhere", "at the same time",
        "across town", "back at",
    ]),
    ("denouement", [
        "finally at peace", "it was over", "for the last time", "looked back",
        "walked away", "closed the door", "silence fell", "end of",
    ]),
]

BEAT_TYPE_DEFAULT: str = "exposition"


# ---------------------------------------------------------------------------
# Scene tone detection keywords
# Used by Pass 2 to classify scene_tone from visual actions and raw text.
# Evaluation: first list with any keyword match wins.
# ---------------------------------------------------------------------------

SCENE_TONE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("tense", [
        "threat", "weapon", "cornered", "trapped", "interrogation",
        "surveillance", "stalked", "pursued", "ticking", "countdown",
        "can't escape", "shadows", "watching",
    ]),
    ("noir", [
        "rain", "neon", "alley", "detective", "cigarette", "whiskey",
        "crime", "murder", "corrupt", "double-cross", "femme fatale",
        "shadows lengthen", "grimy",
    ]),
    ("epic", [
        "horizon", "army", "battle", "thousands", "legendary", "skyline",
        "cathedral", "mountain", "vast", "sprawling", "monumental",
    ]),
    ("golden_hour", [
        "sunset", "sunrise", "golden light", "warm glow", "long shadows",
        "amber", "honey-coloured", "dawn breaks",
    ]),
    ("clinical", [
        "laboratory", "hospital", "white walls", "sterile", "fluorescent",
        "procedure", "diagnosis", "autopsy", "antiseptic",
    ]),
    ("intimate", [
        "whispers", "holds hands", "close together", "tears", "embrace",
        "confession", "forgiveness", "alone together", "quiet room",
    ]),
    ("surreal", [
        "impossible", "distorted", "dreamlike", "vision", "hallucination",
        "mirror", "endless", "disappeared", "shifted reality",
    ]),
]

SCENE_TONE_DEFAULT: str = "neutral"


# ---------------------------------------------------------------------------
# Helpers — pure functions operating on the tables above
# ---------------------------------------------------------------------------

def resolve_lens_mm(beat_type: str | None, scene_tone: str | None) -> int:
    """
    Return the target focal length (mm) for a shot given its beat type and scene tone.
    First matching rule wins. Falls back to 35mm.
    """
    for rule_beat, rule_tone, lens in LENS_SELECTION_RULES:
        beat_match = (rule_beat is None) or (rule_beat == beat_type)
        tone_match = (rule_tone is None) or (rule_tone == scene_tone)
        if beat_match and tone_match:
            return lens
    return 35


def resolve_color_grade(scene_tone: str | None, time_of_day_visual: str | None) -> str:
    """
    Return the color_grade_hint string for a shot.
    First matching rule wins. Falls back to "neutral".
    """
    for rule_tone, rule_tod, grade in COLOR_GRADE_RULES:
        tone_match = (rule_tone is None) or (rule_tone == scene_tone)
        tod_match = (rule_tod is None) or (rule_tod == time_of_day_visual)
        if tone_match and tod_match:
            return grade
    return "neutral"


def resolve_dof(shot_type: str) -> str:
    """Return the depth-of-field directive for a shot type."""
    return DOF_RULES.get(shot_type, "moderate depth of field, f/4.0–5.6")


def resolve_beat_type(raw_text: str) -> str:
    """
    Classify a scene's beat_type from its raw text.
    First list with any keyword match wins. Case-insensitive.
    Returns BEAT_TYPE_DEFAULT ("exposition") if no match.
    """
    lower = raw_text.lower()
    for beat, keywords in BEAT_TYPE_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return beat
    return BEAT_TYPE_DEFAULT


def resolve_scene_tone(text: str) -> str:
    """
    Classify a scene's tone from combined visual actions / raw text.
    First list with any keyword match wins. Case-insensitive.
    Returns SCENE_TONE_DEFAULT ("neutral") if no match.
    """
    lower = text.lower()
    for tone, keywords in SCENE_TONE_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return tone
    return SCENE_TONE_DEFAULT


def get_shot_sequence(beat_type: str) -> list[str]:
    """
    Return the canonical shot-type sequence for a scene beat.
    Cycles if the scene has more shots than the sequence length.
    """
    return SHOT_SEQUENCE_GRAMMAR.get(beat_type, SHOT_SEQUENCE_DEFAULT)
