"""
Pass 4 Coherence Rules — deterministic validation and enrichment tables.

These tables drive the global coherence layer applied during Pass 4 compilation.
All entries are pure Python literals (JSON-serialisable, no side effects).

Rule categories
---------------
FEASIBILITY_MOVEMENT_MINIMUM
    Shots below this feasibility_score have camera_movement downgraded to "static".

PACING_LABEL_RULES
    (max_mean_duration_sec, pacing_label) — evaluated top-to-bottom, first match wins.

TONE_COLOR_GRADE_DEFAULTS
    scene_tone → expected default color_grade_hint for consistency normalisation.

ARC_LENS_PROFILE
    episode_position (1-based, 1-10) → lens compression multiplier.
    Applied when series-level visual arc enrichment is active.

WIDE_SHOT_TYPES / CLOSE_SHOT_TYPES / REACTION_SHOT_TYPES
    Frozen sets used for shot-ratio calculations.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. Feasibility gate
# ---------------------------------------------------------------------------

#: Shots with feasibility_score strictly below this value AND camera_movement
#: not already "static" → downgrade movement to "static".
FEASIBILITY_MOVEMENT_MINIMUM: int = 40

# ---------------------------------------------------------------------------
# 2. Consistency score penalties (applied once per occurrence)
# ---------------------------------------------------------------------------

#: Deducted per scene with a colour-grade conflict (tone_conflicts list)
CONSISTENCY_PENALTY_TONE_CONFLICT: float = 0.10

#: Deducted per shot that required movement simplification
CONSISTENCY_PENALTY_MOVEMENT_SIMPLIFICATION: float = 0.05

#: Deducted when the dramatic arc across the episode is flat
CONSISTENCY_PENALTY_ARC_FLAT: float = 0.05

#: Episode consistency_score below this threshold → "WARN" level in the report
CONSISTENCY_WARN_THRESHOLD: float = 0.70

# ---------------------------------------------------------------------------
# 3. Dramatic arc detection
# ---------------------------------------------------------------------------

#: If the range (max - min) of emotional_beat_index values across all shots
#: in an episode is narrower than this value, the arc is flagged as flat.
ARC_FLAT_THRESHOLD: float = 0.10

# ---------------------------------------------------------------------------
# 4. Establishing shot ratio
# ---------------------------------------------------------------------------

#: Minimum ratio of wide / extreme_wide shots expected in the FIRST scene of
#: an episode to ensure geographic establishment for the viewer.
ESTABLISHING_SHOT_MIN_RATIO: float = 0.10

# ---------------------------------------------------------------------------
# 5. Colour grade homogeneity
# ---------------------------------------------------------------------------

#: Maximum number of distinct color_grade_hint values allowed within a single
#: scene before the dominant / tone-default grade is enforced.
COLOR_GRADE_MAX_DISTINCT: int = 2

# ---------------------------------------------------------------------------
# 6. Pacing label rules
#    Evaluated top-to-bottom, first match wins.
#    Entry: (max_mean_duration_sec, pacing_label)
# ---------------------------------------------------------------------------

PACING_LABEL_RULES: list[tuple[float, str]] = [
    (3.5,          "montage"),   # mean_shot_duration <= 3.5 s
    (4.5,          "fast"),      # mean_shot_duration <= 4.5 s
    (6.0,          "medium"),    # mean_shot_duration <= 6.0 s
    (float("inf"), "slow"),      # mean_shot_duration  > 6.0 s
]

# ---------------------------------------------------------------------------
# 7. Tone → default colour grade
#    Used to normalise conflicting colour grades within a scene.
# ---------------------------------------------------------------------------

TONE_COLOR_GRADE_DEFAULTS: dict[str, str] = {
    "noir":        "high_contrast",
    "golden_hour": "warm",
    "clinical":    "neutral",
    "intimate":    "warm",
    "epic":        "orange_teal",
    "surreal":     "cool",
    "tense":       "high_contrast",
    "neutral":     "neutral",
}

# ---------------------------------------------------------------------------
# 8. Visual arc profile (episode position → lens compression multiplier)
#    Tighter lenses as the season builds pressure (episodes 1-10).
#    Applied to the series-wide lens_mm when arc enrichment is active.
#    Episodes beyond position 10 use the position-10 value.
# ---------------------------------------------------------------------------

ARC_LENS_PROFILE: dict[int, float] = {
    1:  1.00,
    2:  1.00,
    3:  1.05,
    4:  1.05,
    5:  1.10,
    6:  1.10,
    7:  1.15,
    8:  1.15,
    9:  1.20,
    10: 1.25,
}

# ---------------------------------------------------------------------------
# 9. Shot type classification sets (for ratio calculations)
# ---------------------------------------------------------------------------

WIDE_SHOT_TYPES: frozenset[str] = frozenset({"wide", "extreme_wide"})
CLOSE_SHOT_TYPES: frozenset[str] = frozenset({"close_up", "extreme_close_up"})
REACTION_SHOT_TYPES: frozenset[str] = frozenset({
    "close_up", "extreme_close_up", "insert", "pov",
})

# ---------------------------------------------------------------------------
# 10. Prompt enrichment
# ---------------------------------------------------------------------------

#: Separator inserted between original prompt content and appended cinematic
#: directives during the finalisation pass.
PROMPT_ENRICHMENT_SEPARATOR: str = " |cinematic| "

#: Sub-labels for enrichment sections appended to the prompt
PROMPT_LABEL_COMPOSITION: str = "Composition"
PROMPT_LABEL_LIGHTING: str = "Lighting"
PROMPT_LABEL_CHARACTER: str = "Character"
PROMPT_LABEL_LOCATION: str = "Location"
