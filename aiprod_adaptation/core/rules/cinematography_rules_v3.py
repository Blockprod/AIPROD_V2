"""
Cinematography Rules v3.0 — Cinematic grammar for AIPROD_Cinematic Pass 3.

Replaces the single-keyword SHOT_TYPE_RULES / CAMERA_MOVEMENT_RULES of v2 with
a layered, context-aware system that combines:

  (beat_type × action_intensity)  → base shot sequence + duration caps
  physical_action layer            → layer-specific shot overrides
  gaze_direction                   → POV/subjective override
  emotional_layer                  → tone-driven composition shift
  scene_type                       → scene-level camera grammar
  continuity_flags                 → shot injection rules (cliffhanger, first appearance)
  scene_tone × tod_visual          → lighting directives

All tables are pure data — no side effects, no randomness.
Every value is a plain Python literal (serialisable to JSON/YAML).
"""

from __future__ import annotations

# ===========================================================================
# 1. INTENSITY-AWARE SHOT SEQUENCES
#    Key: (beat_type, action_intensity) → (shot_types_list, duration_caps_list)
#    duration_caps: per-position ceiling in seconds; Pass 3 may lower further.
#    Sequence is cycled when the scene has more shots than sequence length.
# ===========================================================================

INTENSITY_SHOT_SEQUENCES: dict[tuple[str, str], tuple[list[str], list[int]]] = {
    # --- CLIMAX ---
    ("climax", "explosive"): (
        ["medium", "close_up", "extreme_close_up", "insert", "wide"],
        [4,        3,          3,                  3,        5],
    ),
    ("climax", "mid"): (
        ["medium", "close_up", "extreme_close_up", "medium"],
        [5,        4,          3,                  5],
    ),
    ("climax", "subtle"): (
        ["wide", "medium", "close_up"],
        [5,      5,        4],
    ),

    # --- ACTION ---
    ("action", "explosive"): (
        ["wide", "medium", "close_up", "insert"],
        [4,      4,        3,          3],
    ),
    ("action", "mid"): (
        ["wide", "medium", "close_up"],
        [5,      4,        4],
    ),
    ("action", "subtle"): (
        ["wide", "medium", "medium"],
        [5,      5,        4],
    ),

    # --- DIALOGUE SCENE ---
    ("dialogue_scene", "explosive"): (
        ["medium", "close_up", "extreme_close_up", "close_up"],
        [5,        4,          3,                  5],
    ),
    ("dialogue_scene", "mid"): (
        ["medium", "over_shoulder", "close_up", "close_up", "medium"],
        [5,        5,               4,          4,          5],
    ),
    ("dialogue_scene", "subtle"): (
        ["medium", "over_shoulder", "medium"],
        [5,        5,               5],
    ),

    # --- EXPOSITION ---
    ("exposition", "explosive"): (
        ["extreme_wide", "wide", "medium", "close_up"],
        [6,              5,      5,        4],
    ),
    ("exposition", "mid"): (
        ["extreme_wide", "wide", "medium", "medium"],
        [7,              6,      5,        5],
    ),
    ("exposition", "subtle"): (
        ["extreme_wide", "wide", "medium"],
        [8,              7,      6],
    ),

    # --- TRANSITION ---
    ("transition", "explosive"): (
        ["wide", "medium"],
        [4,      4],
    ),
    ("transition", "mid"): (
        ["wide", "medium"],
        [5,      4],
    ),
    ("transition", "subtle"): (
        ["wide", "medium"],
        [5,      5],
    ),

    # --- DENOUEMENT ---
    ("denouement", "explosive"): (
        ["wide", "medium", "close_up"],
        [6,      5,        4],
    ),
    ("denouement", "mid"): (
        ["wide", "medium", "close_up"],
        [7,      6,        5],
    ),
    ("denouement", "subtle"): (
        ["extreme_wide", "wide", "medium"],
        [8,              7,      7],
    ),
}

# Default when (beat_type, action_intensity) has no entry
SHOT_SEQUENCE_DEFAULT_V3: tuple[list[str], list[int]] = (
    ["wide", "medium", "medium", "close_up"],
    [6,      5,        5,        4],
)


# ===========================================================================
# 2. CAMERA MOVEMENT SELECTION
#    Evaluated top-to-bottom, first match wins.
#    Entry: (shot_type, beat_type_or_None, action_intensity_or_None,
#             scene_tone_or_None, camera_movement)
#    None = wildcard.
# ===========================================================================

CAMERA_MOVEMENT_RULES_V3: list[tuple[str, str | None, str | None, str | None, str]] = [
    # Wide / establishing shots in motion-heavy scenes
    ("wide",           "action",        "explosive",  None,      "tracking"),
    ("wide",           "action",        "mid",        None,      "tracking"),
    ("wide",           "climax",        "explosive",  None,      "crane_up"),
    ("wide",           "climax",        "mid",        None,      "pan"),
    ("wide",           "denouement",    None,         None,      "dolly_out"),
    ("wide",           "transition",    None,         None,      "pan"),
    ("wide",           None,            None,         "epic",    "crane_up"),

    # Extreme wide — always static (geography anchor)
    ("extreme_wide",   None,            None,         None,      "static"),

    # Medium shots
    ("medium",         "dialogue_scene", None,        None,      "static"),
    ("medium",         "action",        "explosive",  None,      "handheld"),
    ("medium",         "climax",        "explosive",  None,      "handheld"),
    ("medium",         "exposition",    None,         None,      "pan"),
    ("medium",         None,            None,         None,      "static"),

    # Close-up shots
    ("close_up",       "action",        "explosive",  None,      "handheld"),
    ("close_up",       "action",        "mid",        None,      "handheld"),
    ("close_up",       "climax",        "explosive",  None,      "dolly_in"),
    ("close_up",       "climax",        "mid",        None,      "dolly_in"),
    ("close_up",       "dialogue_scene", "explosive", None,      "dolly_in"),
    ("close_up",       None,            None,         None,      "static"),

    # Extreme close-up — always static (kinetic energy is in the image itself)
    ("extreme_close_up", "climax",      "explosive",  None,      "static"),
    ("extreme_close_up", "dialogue_scene", "explosive", None,    "dolly_in"),
    ("extreme_close_up", None,          None,         None,      "static"),

    # Over-the-shoulder
    ("over_shoulder",  None,            None,         None,      "static"),

    # Insert (object/detail) — always static
    ("insert",         None,            None,         None,      "static"),

    # POV — always handheld (embodied subjectivity)
    ("pov",            None,            None,         None,      "handheld"),
]

# Default when no rule matches
CAMERA_MOVEMENT_DEFAULT_V3: str = "static"


# ===========================================================================
# 3. PHYSICAL LAYER SHOT OVERRIDES
#    When a PhysicalAction is available, the layer + intensity drive a
#    specific (shot_type, camera_movement) pair — overriding the sequence.
#    Key: (layer, intensity) → (shot_type, camera_movement)
# ===========================================================================

PHYSICAL_LAYER_SHOT_OVERRIDES: dict[tuple[str, str], tuple[str, str]] = {
    # micro_expression: always wants a tight shot
    ("micro_expression", "explosive"): ("extreme_close_up", "static"),
    ("micro_expression", "mid"):       ("close_up",         "static"),
    ("micro_expression", "subtle"):    ("close_up",         "static"),

    # posture: body language in space — medium shot
    ("posture", "explosive"):          ("medium",           "dolly_in"),
    ("posture", "mid"):                ("medium",           "static"),
    ("posture", "subtle"):             ("medium",           "static"),

    # gaze: POV or close-up depending on intensity
    ("gaze", "explosive"):             ("pov",              "handheld"),
    ("gaze", "mid"):                   ("pov",              "handheld"),
    ("gaze", "subtle"):                ("medium",           "static"),

    # gesture: hands and arms — close-up for expressive, medium for subtle
    ("gesture", "explosive"):          ("close_up",         "dolly_in"),
    ("gesture", "mid"):                ("close_up",         "static"),
    ("gesture", "subtle"):             ("medium",           "static"),

    # breath: visible breathing → extreme_close_up on chest/throat when explosive
    ("breath", "explosive"):           ("extreme_close_up", "static"),
    ("breath", "mid"):                 ("close_up",         "static"),
    ("breath", "subtle"):              ("medium",           "static"),
}


# ===========================================================================
# 4. GAZE DIRECTION OVERRIDES
#    gaze_direction from BodyLanguageState → shot_type, camera_movement
#    Applied when a BodyLanguageState is available for the scene.
#    Priority: lower than PhysicalLayer overrides, higher than base sequence.
# ===========================================================================

GAZE_DIRECTION_RULES: dict[str, tuple[str, str]] = {
    "hunting":  ("pov",     "handheld"),   # R06
    "avoidant": ("medium",  "static"),     # character refuses to engage
    "inward":   ("close_up","static"),     # internal — extreme reaction shot
    "forward":  ("medium",  "static"),     # neutral engagement
    "scanning": ("wide",    "pan"),        # environmental awareness
}


# ===========================================================================
# 5. EMOTIONAL LAYER SHOT MODIFIERS
#    emotional_layer → (preferred_shot_cap, composition_modifier, force_dolly)
#    shot_cap:  max shot type allowed ("extreme_close_up" / "close_up" / "medium" / None)
#    comp_mod:  composition modification string to append
#    force_dolly: True → force dolly_in on the close shot of this scene
# ===========================================================================

EMOTIONAL_LAYER_MODIFIERS: dict[str, dict[str, object]] = {
    "erupting": {
        "final_shot_override":   "extreme_close_up",
        "final_movement_override": "static",
        "composition_note":      "expression fills frame, no headroom",
        "inject_final_cu":       True,
    },
    "disguised": {
        "insert_xcu_after_cu":   True,
        "xcu_movement":          "dolly_in",
        "composition_note":      "eyes in upper third, mouth excluded",
    },
    "displaced": {
        "composition_note":      "subject slightly off-axis, edge tension",
        "preferred_movement":    "dolly_in",
    },
    "surface_neutral": {
        "max_shot_type":         "medium",
        "preferred_movement":    "static",
        "block_extreme_cu":      True,
    },
    "surface": {
        # no extra constraint
    },
}


# ===========================================================================
# 6. SCENE TYPE CAMERA OVERRIDES
#    scene_type → overrides applied to ALL shots in the scene
# ===========================================================================

SCENE_TYPE_CAMERA_OVERRIDES: dict[str, dict[str, object]] = {
    "flashback": {
        "movement_override":       "dolly_out",   # except last shot
        "color_grade_override":    "desaturated",
        "min_lens_mm":             50,
        "composition_note":        "desaturated; vignette; grain overlay suggested",
    },
    "montage": {
        "duration_override":       3,
        "sequence_override":       ["insert", "close_up", "wide", "insert", "close_up"],
        "movement_override":       "static",
        "composition_note":        "rapid cuts, graphic match encouraged",
    },
    "dream": {
        "movement_override":       "steadicam",
        "color_grade_override":    "cool",
        "composition_note":        "floating camera, slightly off-speed, impossible angles allowed",
    },
    "cliffhanger": {
        "last_shot_type":          "extreme_close_up",
        "last_shot_movement":      "dolly_in",
        "last_duration_override":  4,
        "framing_note":            "freeze on apex expression",
    },
}


# ===========================================================================
# 7. CONTINUITY FLAG INJECTIONS
#    flag_prefix → injection spec
#    inject_before=True → add shot BEFORE first action shot
#    inject_after=True  → add shot AFTER last action shot
# ===========================================================================

CONTINUITY_FLAG_INJECTIONS: dict[str, dict[str, object]] = {
    "CLIFFHANGER": {
        "inject_after":    True,
        "shot_type":       "extreme_close_up",
        "camera_movement": "dolly_in",
        "duration":        4,
        "framing_note":    "freeze on apex expression",
        "shot_role":       "reveal",
    },
    "FIRST_APPEARANCE": {
        "inject_before":   True,
        "sequence":        ["wide", "medium"],
        "camera_movement": "static",
        "duration":        6,
        "shot_role":       "establishing",
        "framing_note":    "full body visible, environment readable",
    },
    "ACT_BREAK": {
        "inject_after":    True,
        "shot_type":       "extreme_wide",
        "camera_movement": "static",
        "duration":        6,
        "shot_role":       "establishing",
    },
}


# ===========================================================================
# 8. COMPOSITION DESCRIPTIONS
#    shot_type → canonical composition description
#    Provides storyboard-ready framing instructions.
# ===========================================================================

COMPOSITION_DESCRIPTIONS: dict[str, str] = {
    "extreme_wide":    "subject <10% frame height; environment dominant; horizon line at golden ratio",
    "wide":            "full figure visible; subject occupies 25–40% frame height; rule of thirds applied",
    "medium":          "waist-up framing; subject on vertical third; negative space on conversation side",
    "medium_close":    "chest-up framing; eyes at upper third; slight off-axis for tension",
    "close_up":        "shoulders-to-crown; eyes at upper third; mouth near center; ear off-frame",
    "extreme_close_up":"single facial feature or eyes fill frame; no headroom; texture dominant",
    "over_shoulder":   "foreground shoulder 30% frame; subject faces 2/3 frame; eyes visible and sharp",
    "two_shot":        "both subjects framed waist-up; 180° axis held; eyeline match critical",
    "insert":          "object fills 60–80% frame; surroundings soft; graphic isolation",
    "pov":             "camera at eye height of subject; handheld drift; 50–75mm FOV equivalent",
}

# Fallback for unknown shot types
COMPOSITION_DEFAULT: str = "subject centered; rule of thirds preferred"


# ===========================================================================
# 9. LIGHTING DIRECTIVES
#    (scene_tone, time_of_day_visual) → lighting directive prose
#    None = wildcard (matched last). First match wins.
# ===========================================================================

LIGHTING_DIRECTIVES: list[tuple[str | None, str | None, str]] = [
    # Noir
    ("noir",        "night",     "cold lateral left; hard rim shadow 45°; face 40% in darkness"),
    ("noir",        "interior",  "single practical source; strong shadow geometry; low key"),
    ("noir",        "dusk",      "last light filtered through venetian blind; high contrast"),
    ("noir",        None,        "hard side lighting; minimum fill; shadow as 2nd character"),

    # Tense
    ("tense",       "night",     "cold blue fill; under-light traces; pools of shadow between cuts"),
    ("tense",       "interior",  "flat institutional light above; no warmth; faces bleached"),
    ("tense",       None,        "mixed colour temperature; one cold source from background"),

    # Golden hour
    ("golden_hour", "dawn",      "warm horizontal rake from frame right; long shadows; lens flare acceptable"),
    ("golden_hour", "dusk",      "warm backlight rim; ambient fill from sky bounce; silhouette moments"),
    ("golden_hour", None,        "warm horizontal key; soft bounce fill; saturated shadow"),

    # Clinical
    ("clinical",    None,        "overhead fluorescent; even exposure; no practical warmth; flat shadows"),

    # Epic
    ("epic",        "day",       "hard overhead sun + sky bounce; god rays acceptable; high key"),
    ("epic",        "dawn",      "low sun grazing angle; volumetric atmosphere; silhouettes"),
    ("epic",        "dusk",      "backlit orange horizon; foreground in silhouette"),
    ("epic",        None,        "sweeping natural light; high dynamic range; no fill restraint"),

    # Intimate
    ("intimate",    "night",     "candlelight or practical lamp; warm pool; deep surrounding shadow"),
    ("intimate",    "interior",  "soft window bounce or lamplight; gentle falloff; no hard shadows"),
    ("intimate",    None,        "soft key; heavy fill ratio 1:2; warm colour temperature"),

    # Surreal
    ("surreal",     "night",     "cool monochrome; no motivated source; ambient bleeds"),
    ("surreal",     None,        "colour motivated by emotion not logic; mixed temps; dreamy halation"),

    # Default day/night
    (None,          "night",     "motivated practical sources only; cool ambient; silhouettes acceptable"),
    (None,          "dawn",      "soft diffused natural light; low saturation; horizon warm"),
    (None,          "dusk",      "warm directional fading; increasing shadow contrast"),
    (None,          "interior",  "motivated practical sources; mixed temperature acceptable"),
    (None,          None,        "natural motivated light; balanced exposure"),
]


# ===========================================================================
# 10. SHOT ROLE MAPPING
#     shot_type → default shot_role label
# ===========================================================================

SHOT_ROLE_MAP: dict[str, str] = {
    "extreme_wide":    "establishing",
    "wide":            "establishing",
    "medium":          "coverage",
    "medium_close":    "coverage",
    "close_up":        "reaction",
    "extreme_close_up":"reaction",
    "over_shoulder":   "coverage",
    "two_shot":        "coverage",
    "insert":          "insert",
    "pov":             "pov",
}

SHOT_ROLE_DEFAULT: str = "coverage"


# ===========================================================================
# 11. FEASIBILITY SCORE MATRIX
#     (shot_type, camera_movement) → base feasibility score [0-100]
#     100 = trivially achievable; lower = requires specialist equipment.
#     Reduced by high action_intensity when movement is complex.
# ===========================================================================

FEASIBILITY_BASE_SCORES: dict[tuple[str, str], int] = {
    # Static shots — maximum feasibility
    ("extreme_wide",    "static"):   95,
    ("wide",            "static"):   95,
    ("medium",          "static"):   95,
    ("close_up",        "static"):   95,
    ("extreme_close_up","static"):   90,
    ("over_shoulder",   "static"):   92,
    ("two_shot",        "static"):   92,
    ("insert",          "static"):   95,
    ("pov",             "static"):   85,

    # Pan
    ("wide",            "pan"):      90,
    ("medium",          "pan"):      90,
    ("extreme_wide",    "pan"):      88,

    # Follow / tracking
    ("wide",            "follow"):   80,
    ("medium",          "follow"):   80,
    ("wide",            "tracking"): 75,
    ("medium",          "tracking"): 75,

    # Dolly
    ("medium",          "dolly_in"): 82,
    ("close_up",        "dolly_in"): 80,
    ("extreme_close_up","dolly_in"): 75,
    ("wide",            "dolly_out"):80,
    ("medium",          "dolly_out"):82,

    # Handheld
    ("close_up",        "handheld"): 78,
    ("medium",          "handheld"): 80,
    ("wide",            "handheld"): 78,
    ("pov",             "handheld"): 82,

    # Crane
    ("wide",            "crane_up"): 65,
    ("extreme_wide",    "crane_up"): 65,

    # Tilt
    ("medium",          "tilt_up"):  88,
    ("wide",            "tilt_up"):  85,

    # Steadicam
    ("medium",          "steadicam"):72,
    ("wide",            "steadicam"):72,
}

FEASIBILITY_DEFAULT_SCORE: int = 70

# Penalty applied to feasibility when action_intensity == "explosive"
FEASIBILITY_EXPLOSIVE_PENALTY: int = 10

# Reward applied when camera_movement == "static" (always achievable)
FEASIBILITY_STATIC_BONUS: int = 5


# ===========================================================================
# 12. DURATION TABLE
#     (beat_type, action_intensity, shot_type) → preferred duration in seconds
#     Clamp to [3, 8] in Pass 3.
#     This table takes precedence over both the verb-counting v2 logic
#     and the INTENSITY_SHOT_SEQUENCES duration_caps above.
#     Fallback: use the duration_cap from INTENSITY_SHOT_SEQUENCES.
# ===========================================================================

DURATION_TABLE: dict[tuple[str, str, str], int] = {
    # CLIMAX explosive
    ("climax", "explosive", "medium"):           4,
    ("climax", "explosive", "close_up"):         3,
    ("climax", "explosive", "extreme_close_up"): 3,
    ("climax", "explosive", "insert"):           3,
    ("climax", "explosive", "wide"):             5,
    # CLIMAX mid
    ("climax", "mid", "medium"):                 5,
    ("climax", "mid", "close_up"):               4,
    ("climax", "mid", "extreme_close_up"):       3,
    # CLIMAX subtle
    ("climax", "subtle", "wide"):                5,
    ("climax", "subtle", "medium"):              5,
    ("climax", "subtle", "close_up"):            4,

    # ACTION explosive
    ("action", "explosive", "wide"):             4,
    ("action", "explosive", "medium"):           4,
    ("action", "explosive", "close_up"):         3,
    ("action", "explosive", "insert"):           3,
    # ACTION mid
    ("action", "mid", "wide"):                   5,
    ("action", "mid", "medium"):                 4,
    ("action", "mid", "close_up"):               4,
    # ACTION subtle
    ("action", "subtle", "wide"):                5,
    ("action", "subtle", "medium"):              5,

    # DIALOGUE explosive
    ("dialogue_scene", "explosive", "medium"):           5,
    ("dialogue_scene", "explosive", "close_up"):         4,
    ("dialogue_scene", "explosive", "extreme_close_up"): 3,
    # DIALOGUE mid
    ("dialogue_scene", "mid", "medium"):                 5,
    ("dialogue_scene", "mid", "over_shoulder"):          5,
    ("dialogue_scene", "mid", "close_up"):               4,
    # DIALOGUE subtle
    ("dialogue_scene", "subtle", "medium"):              5,
    ("dialogue_scene", "subtle", "over_shoulder"):       5,

    # EXPOSITION
    ("exposition", "explosive", "extreme_wide"):         6,
    ("exposition", "explosive", "wide"):                 5,
    ("exposition", "mid", "extreme_wide"):               7,
    ("exposition", "mid", "wide"):                       6,
    ("exposition", "mid", "medium"):                     5,
    ("exposition", "subtle", "extreme_wide"):            8,
    ("exposition", "subtle", "wide"):                    7,
    ("exposition", "subtle", "medium"):                  6,

    # DENOUEMENT
    ("denouement", "subtle", "extreme_wide"):            8,
    ("denouement", "subtle", "wide"):                    7,
    ("denouement", "mid", "wide"):                       7,
    ("denouement", "mid", "medium"):                     6,
    ("denouement", "mid", "close_up"):                   5,
    ("denouement", "explosive", "close_up"):             4,

    # TRANSITION
    ("transition", "subtle", "wide"):                    5,
    ("transition", "subtle", "medium"):                  5,
    ("transition", "mid", "wide"):                       5,
    ("transition", "mid", "medium"):                     4,
    ("transition", "explosive", "wide"):                 4,
    ("transition", "explosive", "medium"):               4,
}

DURATION_DEFAULT: int = 5


# ===========================================================================
# 13. 180° RULE GUARD
#     Pairs of shot_types that trigger the 180° continuity check.
#     If shot N is type A and shot N+1 is type B (both from this set)
#     and they share characters, a neutral cut shot_type is inserted.
# ===========================================================================

OVER_SHOULDER_PAIR: frozenset[str] = frozenset({"over_shoulder"})

# Shot type to insert as neutral cut when 180° rule is violated
NEUTRAL_CUT_SHOT_TYPE: str = "medium"
NEUTRAL_CUT_CAMERA_MOVEMENT: str = "static"
NEUTRAL_CUT_DURATION: int = 4
NEUTRAL_CUT_SHOT_ROLE: str = "cutaway"


# ===========================================================================
# 14. FRAMING NOTES
#     (shot_type, emotional_layer) → framing note override
#     Applied when emotional context demands a specific frame adjustment.
# ===========================================================================

FRAMING_NOTES: dict[tuple[str, str], str] = {
    ("extreme_close_up", "erupting"):    "expression fills frame, no headroom",
    ("extreme_close_up", "disguised"):   "eyes in upper third, mouth excluded",
    ("extreme_close_up", "displaced"):   "asymmetric; subject placed off-center hard",
    ("close_up",         "disguised"):   "controlled expression; eyes carry subtext",
    ("close_up",         "erupting"):    "micro-tear or jaw-set visible",
    ("pov",              "hunting"):     "target visible at center; handheld drift amplifies threat",
    ("medium",           "coiled"):      "subject left-third; door or exit right-third",
    ("wide",             "released"):    "subject small in frame; environment overwhelms",
    ("over_shoulder",    "avoidant"):    "subject looks away; negative space used deliberately",
}

FRAMING_NOTE_DEFAULT: str | None = None
