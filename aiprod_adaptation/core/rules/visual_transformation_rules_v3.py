"""
Visual Transformation Rules v3 — AIPROD_Cinematic Pass 2.

Supplementary rule tables that govern HOW body language is modified
contextually (intensity shifting, scene-type adaptation, environmental
interaction, emotional layering).

All tables are pure data — JSON-serialisable, fully deterministic.

Tables
------
CONTEXT_INTENSITY_MODIFIERS
    Words detected in ±2-sentence context window that shift arc_index
    before intensity-tier lookup.  Negative = suppress/cool.  Positive = amplify.

INTENSITY_TIER_THRESHOLDS
    arc_index breakpoints → tier name.

SCENE_TYPE_ACTION_MODIFIERS
    scene_type → per-layer suffix/override strings applied after body-language lookup.

ENVIRONMENT_INTERACTION_RULES
    (architecture_style, emotion) → environmental_interaction prose string.

EMOTIONAL_LAYER_RULES
    Ordered list: (context_marker_list, emotion_wildcard, layer_name).
    First match wins.  Assigns the emotional_layer field on VisualScene.

BEAT_TYPE_INTENSITY_FLOOR
    beat_type → minimum intensity tier string (never produce below this floor).

SILENT_SCENE_THRESHOLD
    Word count below which a scene is treated as a silent scene
    (R15: micro-expression and environmental focus only).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Intensity tier thresholds
# arc_index breakpoints. Evaluated top-to-bottom; first match wins.
# ---------------------------------------------------------------------------

#: (min_arc_index, tier_name)  — sorted ascending by min_arc_index.
INTENSITY_TIER_THRESHOLDS: list[tuple[float, str]] = [
    (0.70, "explosive"),
    (0.35, "mid"),
    (0.00, "subtle"),
]


# ---------------------------------------------------------------------------
# Context intensity modifiers
# Keys present in ±2-sentence window → delta applied to arc_index before tiering.
# Negative delta = colder / more controlled.  Positive = amplified.
# ---------------------------------------------------------------------------

CONTEXT_INTENSITY_MODIFIERS: dict[str, float] = {
    # --- suppress / cool ---
    "cold":        -0.30,
    "icy":         -0.30,
    "impassive":   -0.28,
    "impassible":  -0.28,
    "mask":        -0.25,
    "blank":       -0.25,
    "stone-faced": -0.25,
    "controlled":  -0.22,
    "contained":   -0.22,
    "suppressed":  -0.22,
    "barely":      -0.20,
    "swallowed":   -0.18,
    "hidden":      -0.18,
    "forced":      -0.15,
    "measured":    -0.15,
    "deliberate":  -0.12,
    "still":       -0.10,
    # --- amplify ---
    "suddenly":    +0.25,
    "violently":   +0.35,
    "erupted":     +0.40,
    "burst":       +0.32,
    "flooded":     +0.22,
    "overwhelmed": +0.28,
    "unbearable":  +0.28,
    "shaking":     +0.25,
    "trembling":   +0.22,
    "blind":       +0.32,   # "blind with rage"
    "white-hot":   +0.38,
    "uncontrolled":+0.35,
    "wave":        +0.18,
    "broke":       +0.25,
}


# ---------------------------------------------------------------------------
# Scene-type action modifiers
# Applied to the composed layers after emotion lookup.
# None = no modification for that layer component.
# ---------------------------------------------------------------------------

SCENE_TYPE_ACTION_MODIFIERS: dict[str, dict[str, str | None]] = {
    "flashback": {
        "motion_suffix":   "motion carries the weight of memory — each movement deliberate, as if underwater",
        "gaze_override":   "gaze directed inward, unfocused on present space; eyes see what isn't here",
        "gesture_suffix":  "hands reach but do not quite complete the action",
        "breath_override": "breath held, suspended in the recalled moment",
    },
    "dream": {
        "motion_suffix":   "movement detached from gravity; no impact registering in the body",
        "gaze_override":   "pupils dilated; seeing what isn't there; turned wholly inward",
        "gesture_suffix":  "reaching motion — object never grasped",
        "breath_override": "shallow, irregular, as if still sleeping",
    },
    "montage": {
        "motion_suffix":   "staccato — single kinetic instant, freeze-frame quality",
        "gaze_override":   "direct, present-tense; the instant the camera finds them",
        "gesture_suffix":  "arrested mid-motion, held",
        "breath_override": None,  # breath layer omitted in montage
    },
    "cliffhanger": {
        "motion_suffix":   "motion arrests mid-action — suspended in the moment before knowledge",
        "gaze_override":   "wide, shock-dilated, locked on the revelation; time has stopped",
        "gesture_suffix":  "held position, not yet resolved",
        "breath_override": "sharp intake; then held silence",
    },
    "teaser": {
        "motion_suffix":   "controlled, purposeful; every move world-establishing",
        "gaze_override":   "scanning, reading the environment — cataloguing",
        "gesture_suffix":  None,
        "breath_override": None,
    },
    "tag": {
        "motion_suffix":   "quieter version of the scene's primary action; aftermath quality",
        "gaze_override":   "softer, reflective; the worst is over",
        "gesture_suffix":  None,
        "breath_override": "slower, settling",
    },
    "transition": {
        "motion_suffix":   "body already in motion toward the next place",
        "gaze_override":   "forward and outward; destination-oriented",
        "gesture_suffix":  None,
        "breath_override": None,
    },
    "standard": {
        "motion_suffix":   None,
        "gaze_override":   None,
        "gesture_suffix":  None,
        "breath_override": None,
    },
}


# ---------------------------------------------------------------------------
# Environment interaction rules
# (architecture_style, emotion) → environmental_interaction prose string.
# Evaluated top-to-bottom; first match on both dimensions wins.
# "any" acts as wildcard for architecture_style.
# ---------------------------------------------------------------------------

#: Each entry: (architecture_style, emotion, environmental_action_string)
ENVIRONMENT_INTERACTION_RULES: list[tuple[str, str, str]] = [
    # Brutalist
    ("brutalist", "angry",     "slams palm against concrete wall; the surface absorbs nothing — the impact returns"),
    ("brutalist", "scared",    "back presses to cold concrete; the texture registers through fabric as the room closes in"),
    ("brutalist", "nervous",   "fingertip traces a crack in the concrete wall; repetitive, orienting"),
    ("brutalist", "trapped",   "eyes measure the slab geometry; no give anywhere in this architecture"),
    ("brutalist", "defiant",   "plants against the concrete; the building's mass behind the stand"),
    # Industrial
    ("industrial", "nervous",  "fingers trace conduit pipe along wall; metal is cold and indifferent under the hand"),
    ("industrial", "determined","steps carry precise weight across steel grating; the sound announces arrival"),
    ("industrial", "scared",   "grips overhead gantry strut; cold steel, solid — the only certainty in the space"),
    ("industrial", "angry",    "fist meets industrial shelving; metal rings; objects settle into new positions"),
    # Office / modern
    ("office", "angry",        "hand descends flat on desk surface; papers register the force; objects shift position"),
    ("office", "nervous",      "pen clicked in a held rhythm; cap turned, replaced; hands need occupation"),
    ("office", "suspicious",   "body angles to include doorway in peripheral vision; always faces the room, never the wall"),
    ("office", "determined",   "closes the file deliberately; the click of it is the decision made"),
    ("office", "resigned",     "gaze goes to the window; the city outside continues without acknowledgement"),
    # Domestic
    ("domestic", "grief",      "hands close around a common object — a cup, a photograph, a piece of fabric — as if warmth might transfer"),
    ("domestic", "relieved",   "collapses into the nearest chair or surface; the body finally releases its held shape"),
    ("domestic", "nervous",    "adjusts objects that don't need adjusting; the room rearranged by anxiety"),
    ("domestic", "sad",        "sits at the table but doesn't use it; hands on the surface; the room too familiar"),
    # Clinical / medical
    ("clinical", "scared",     "backs against equipment; cold metal handle gripped for orientation in the sterile space"),
    ("clinical", "determined", "moves through the space without touching anything; hygienic distance as control"),
    ("clinical", "disgusted",  "cannot touch the surfaces; gloves or jacket sleeve used as barrier"),
    ("clinical", "nervous",    "reads labels that have already been read; the chart reviewed again without need"),
    # Natural / outdoor
    ("natural", "relieved",    "turns face to the light source; shoulders drop; fingers open and uncurl"),
    ("natural", "grief",       "gaze goes to the horizon; soft-focuses to middle distance; the scale of it"),
    ("natural", "determined",  "faces into wind or light; the element met directly"),
    ("natural", "scared",      "instinctively seeks cover; edges toward tree line or structure"),
    # Fallback — any architecture
    ("any", "cliffhanger",     "freezes mid-step in the space; body suspended between one world and the next"),
]


# ---------------------------------------------------------------------------
# Emotional layer rules
# Ordered: first matching context-marker cluster wins.
# Assigns the emotional_layer field on VisualScene.
# Format: (context_markers: list[str], emotion_wildcard: str, layer_name: str)
# emotion_wildcard: "*" matches any emotion; otherwise must match exactly.
# ---------------------------------------------------------------------------

#: (context_markers, emotion_wildcard, layer_name)
EMOTIONAL_LAYER_RULES: list[tuple[list[str], str, str]] = [
    # surface_neutral: emotion fully suppressed; face holds a blank shape
    (["impassible", "impassive", "blank", "mask", "stone-faced",
      "gave nothing away", "no expression", "face still", "face held"],
     "*", "surface_neutral"),

    # disguised: emotion active but deliberately controlled; micro-expression leaks
    (["cold", "icy", "controlled", "contained", "barely", "forced calm",
      "jaw set", "measured", "swallowed", "suppressed"],
     "*", "disguised"),

    # erupting: emotion breaking through active containment
    (["couldn't hold back", "burst", "erupted", "broke through",
      "no longer", "finally", "unable to contain", "gave way"],
     "*", "erupting"),

    # displaced: emotion channelled into physical action rather than expression
    (["threw", "swept", "slammed", "kicked", "drove", "hurled",
      "smashed", "gripped until"],
     "*", "displaced"),
]

#: Default emotional layer when no rule matches
EMOTIONAL_LAYER_DEFAULT: str = "surface"


# ---------------------------------------------------------------------------
# Beat-type intensity floor
# Certain beat types mandate a minimum intensity tier regardless of arc_index.
# ---------------------------------------------------------------------------

#: beat_type → minimum intensity tier string
BEAT_TYPE_INTENSITY_FLOOR: dict[str, str] = {
    "climax":    "mid",      # R14: climax never produces subtle body language
    "action":    "mid",
    "denouement":"subtle",   # denouement can be very quiet
    "transition":"subtle",
    "exposition":"subtle",
    "dialogue_scene":"subtle",
}

#: Default floor when beat_type is unrecognised
BEAT_TYPE_INTENSITY_FLOOR_DEFAULT: str = "subtle"


# ---------------------------------------------------------------------------
# Silent scene threshold (R15)
# ---------------------------------------------------------------------------

#: Word count below which a scene is treated as a silent scene.
SILENT_SCENE_WORD_THRESHOLD: int = 30


# ---------------------------------------------------------------------------
# Dialogue beat gaze override (R13)
# Applied to the gaze layer when beat_type == "dialogue_scene"
# ---------------------------------------------------------------------------

DIALOGUE_BEAT_GAZE_OVERRIDE: str = (
    "gaze alternates between interlocutor and middle distance; "
    "speaker-aligned; yields and reclaims eye contact with conversational rhythm"
)
DIALOGUE_BEAT_GESTURE_NOTE: str = (
    "gesture subdued, economical; hands speaker-aligned; "
    "no large displacement activity during speech"
)
