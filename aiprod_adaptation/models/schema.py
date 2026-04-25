from typing import Any

from pydantic import BaseModel, Field, field_validator

_VALID_SHOT_TYPES: frozenset[str] = frozenset({
    "wide", "medium", "close_up", "pov",
    # v3.0 cinematic extensions
    "extreme_wide", "extreme_close_up", "two_shot", "over_shoulder", "insert",
    # v3.1 cinematic refinements
    "medium_wide", "medium_close",
})
_VALID_CAMERA_MOVEMENTS: frozenset[str] = frozenset({
    "static", "follow", "pan",
    # v3.0 cinematic extensions
    "dolly_in", "dolly_out", "tilt_up", "tilt_down", "crane_up", "crane_down",
    "tracking", "handheld",
    # v3.1 cinematic extensions
    "steadicam", "rack_focus", "whip_pan",
})
_VALID_TOD_VISUAL: frozenset[str] = frozenset({"dawn", "day", "dusk", "night", "interior"})
_VALID_DOMINANT_SOUND: frozenset[str] = frozenset({"dialogue", "ambient", "silence"})
_VALID_SCENE_TONES: frozenset[str] = frozenset({
    "neutral", "noir", "golden_hour", "clinical", "intimate", "epic", "surreal", "tense",
})
_VALID_BEAT_TYPES: frozenset[str] = frozenset({
    "exposition", "action", "dialogue_scene", "transition", "climax", "denouement",
})
_VALID_COLOR_GRADES: frozenset[str] = frozenset({
    "neutral", "warm", "cool", "desaturated", "high_contrast", "orange_teal",
    "monochrome", "bleach_bypass",
})
_VALID_SHOT_ROLES: frozenset[str] = frozenset({
    "establishing", "coverage", "reaction", "insert", "pov", "cutaway", "reveal",
})
_ALLOWED_METADATA_KEYS: frozenset[str] = frozenset({
    "time_of_day_visual", "dominant_sound",
    # v3.0 cinematic extensions
    "lens_mm", "depth_of_field", "color_grade_hint", "framing_note",
    "scene_tone", "beat_type", "emotional_beat_index", "ref_anchor_id",
    # v3.1 cinematic extensions
    "lighting_directives", "composition_description", "rhythm_purpose",
})


class Scene(BaseModel):
    scene_id: str
    characters: list[str]
    character_ids: list[str] = Field(default_factory=list)
    location: str
    location_id: str | None = None
    time_of_day: str | None = None
    visual_actions: list[str]
    dialogues: list[str]
    emotion: str
    action_units: list["ActionSpec"] = Field(default_factory=list)
    shot_ids: list[str] = Field(default_factory=list)
    # v3.0 cinematic fields
    beat_type: str | None = None          # exposition | action | dialogue_scene | transition | climax | denouement
    scene_tone: str | None = None         # noir | golden_hour | clinical | intimate | epic | surreal | tense | neutral
    emotional_beat_index: float | None = None  # cumulative dramatic intensity [0.0, 1.0]


class ActionSpec(BaseModel):
    subject_id: str
    action_type: str
    target: str | None = None
    modifiers: list[str] = Field(default_factory=list)
    location_id: str | None = None
    camera_intent: str = "static"
    source_text: str


class Shot(BaseModel):
    shot_id: str
    scene_id: str
    prompt: str
    duration_sec: int  # MUST be between 3 and 8 inclusive
    emotion: str
    shot_type: str = "medium"        # see _VALID_SHOT_TYPES
    camera_movement: str = "static"  # see _VALID_CAMERA_MOVEMENTS
    action: ActionSpec | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    # v3.1 cinematic fields (all Optional, backward compatible)
    shot_role: str | None = None
    composition_description: str | None = None
    lighting_directives: str | None = None
    framing_note: str | None = None
    rhythm_purpose: str | None = None
    visual_invariants_applied: list[str] = Field(default_factory=list)
    feasibility_score: int = 100
    reference_anchor_strength: float = 1.0

    @field_validator("duration_sec")
    @classmethod
    def validate_duration_sec(cls, v: int) -> int:
        if not (3 <= v <= 8):
            raise ValueError(
                f"Invalid duration_sec: {v}. Must be between 3 and 8 inclusive."
            )
        return v

    @field_validator("shot_type")
    @classmethod
    def validate_shot_type(cls, v: str) -> str:
        if v not in _VALID_SHOT_TYPES:
            raise ValueError(
                f"Invalid shot_type: {v!r}. Must be one of {sorted(_VALID_SHOT_TYPES)}"
            )
        return v

    @field_validator("camera_movement")
    @classmethod
    def validate_camera_movement(cls, v: str) -> str:
        if v not in _VALID_CAMERA_MOVEMENTS:
            raise ValueError(
                f"Invalid camera_movement: {v!r}. Must be one of {sorted(_VALID_CAMERA_MOVEMENTS)}"
            )
        return v

    @field_validator("action")
    @classmethod
    def validate_action_camera_intent(cls, value: ActionSpec | None) -> ActionSpec | None:
        if value is None:
            return None
        if value.camera_intent not in _VALID_CAMERA_MOVEMENTS:
            raise ValueError(
                "Invalid action.camera_intent: "
                f"{value.camera_intent!r}. Must be one of {sorted(_VALID_CAMERA_MOVEMENTS)}"
            )
        return value

    @field_validator("shot_role")
    @classmethod
    def validate_shot_role(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_SHOT_ROLES:
            raise ValueError(
                f"Invalid shot_role: {v!r}. Must be one of {sorted(_VALID_SHOT_ROLES)}"
            )
        return v

    @field_validator("feasibility_score")
    @classmethod
    def validate_feasibility_score(cls, v: int) -> int:
        if not (0 <= v <= 100):
            raise ValueError(
                f"Invalid feasibility_score: {v}. Must be between 0 and 100 inclusive."
            )
        return v

    @field_validator("reference_anchor_strength")
    @classmethod
    def validate_reference_anchor_strength(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(
                f"Invalid reference_anchor_strength: {v}. Must be in [0.0, 1.0]."
            )
        return v

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        invalid_keys = [key for key in value if key not in _ALLOWED_METADATA_KEYS]
        if invalid_keys:
            raise ValueError(
                "Invalid metadata keys: "
                f"{invalid_keys!r}. Allowed keys: {sorted(_ALLOWED_METADATA_KEYS)}"
            )

        time_of_day_visual = value.get("time_of_day_visual")
        if time_of_day_visual is not None and time_of_day_visual not in _VALID_TOD_VISUAL:
            raise ValueError(
                "Invalid metadata.time_of_day_visual: "
                f"{time_of_day_visual!r}. Must be one of {sorted(_VALID_TOD_VISUAL)}"
            )

        dominant_sound = value.get("dominant_sound")
        if dominant_sound is not None and dominant_sound not in _VALID_DOMINANT_SOUND:
            raise ValueError(
                "Invalid metadata.dominant_sound: "
                f"{dominant_sound!r}. Must be one of {sorted(_VALID_DOMINANT_SOUND)}"
            )

        # v3.0 cinematic field validators
        scene_tone = value.get("scene_tone")
        if scene_tone is not None and scene_tone not in _VALID_SCENE_TONES:
            raise ValueError(
                f"Invalid metadata.scene_tone: {scene_tone!r}. "
                f"Must be one of {sorted(_VALID_SCENE_TONES)}"
            )

        beat_type = value.get("beat_type")
        if beat_type is not None and beat_type not in _VALID_BEAT_TYPES:
            raise ValueError(
                f"Invalid metadata.beat_type: {beat_type!r}. "
                f"Must be one of {sorted(_VALID_BEAT_TYPES)}"
            )

        color_grade_hint = value.get("color_grade_hint")
        if color_grade_hint is not None and color_grade_hint not in _VALID_COLOR_GRADES:
            raise ValueError(
                f"Invalid metadata.color_grade_hint: {color_grade_hint!r}. "
                f"Must be one of {sorted(_VALID_COLOR_GRADES)}"
            )

        lens_mm = value.get("lens_mm")
        if lens_mm is not None and not isinstance(lens_mm, int):
            raise ValueError(
                f"Invalid metadata.lens_mm: {lens_mm!r}. Must be an integer (focal length in mm)."
            )

        emotional_beat_index = value.get("emotional_beat_index")
        if emotional_beat_index is not None:
            if not isinstance(emotional_beat_index, (int, float)):
                raise ValueError(
                    f"Invalid metadata.emotional_beat_index: {emotional_beat_index!r}. "
                    "Must be a float in [0.0, 1.0]."
                )
            if not (0.0 <= float(emotional_beat_index) <= 1.0):
                raise ValueError(
                    f"Invalid metadata.emotional_beat_index: {emotional_beat_index!r}. "
                    "Must be in [0.0, 1.0]."
                )

        return value


class PacingProfile(BaseModel):
    """Episode-level pacing metrics computed by Pass 4 pacing_analyzer."""
    total_duration_sec: int
    mean_shot_duration: float
    shot_count: int
    pacing_label: str  # "slow" | "medium" | "fast" | "montage"


class ConsistencyReport(BaseModel):
    """Coherence validation report produced by Pass 4 consistency_checker."""
    consistency_score: float = 1.0
    tone_conflicts: list[str] = Field(default_factory=list)            # scene_ids
    continuity_warnings: list[str] = Field(default_factory=list)       # string flags
    movement_simplifications: list[str] = Field(default_factory=list)  # shot_ids
    prompt_enrichments: int = 0


class RuleEngineReport(BaseModel):
    """
    Aggregated execution metrics from the Rule Engine loop in Pass 4.

    rules_evaluated        : total rule×shot evaluations performed
    hard_conflicts_resolved: HARD conflicts that resulted in a shot mutation
    soft_conflicts_annotated: SOFT conflicts that annotated visual_invariants_applied
    total_shots_modified   : number of distinct shots mutated by the resolver
    conflict_shot_ids      : shot_ids that had at least one resolved conflict
    rule_ids_fired         : unique rule IDs that matched at least one shot
    """
    rules_evaluated: int = 0
    hard_conflicts_resolved: int = 0
    soft_conflicts_annotated: int = 0
    total_shots_modified: int = 0
    conflict_shot_ids: list[str] = Field(default_factory=list)
    rule_ids_fired: list[str] = Field(default_factory=list)


class Episode(BaseModel):
    episode_id: str
    scenes: list[Scene]
    shots: list[Shot]
    # v4.0 cinematic fields (all Optional — backward compatible)
    pacing_profile: PacingProfile | None = None
    consistency_report: ConsistencyReport | None = None
    # v4.1 rule engine report
    rule_engine_report: RuleEngineReport | None = None


class AIPRODOutput(BaseModel):
    title: str
    episodes: list[Episode]
    # v4.0 cinematic fields (all Optional — backward compatible)
    visual_bible_summary: dict[str, Any] = Field(default_factory=dict)
    # v4.1 rule engine report (aggregated across all episodes in this output)
    rule_engine_report: RuleEngineReport | None = None


class SeasonCoherenceMetrics(BaseModel):
    """
    Visual coherence metrics computed across all episodes of a season.

    Produced by SeasonCoherenceTracker.compute_metrics().
    """
    season_id: str
    episode_count: int
    total_shots: int
    mean_feasibility_score: float
    consistency_score_mean: float
    palette_drift_episodes: list[str] = Field(default_factory=list)
    rule_conflicts_per_episode: dict[str, int] = Field(default_factory=dict)
    character_continuity_flags: list[str] = Field(default_factory=list)


class AIPRODSeason(BaseModel):
    """
    Multi-episode container for a full season of AIPROD_Cinematic output.

    Produced by running run_pipeline() (or process_narrative_with_reference())
    once per episode and aggregating via SeasonCoherenceTracker.
    """
    season_id: str
    series_title: str
    episodes: list[AIPRODOutput]
    coherence_metrics: SeasonCoherenceMetrics | None = None
    visual_bible_path: str | None = None
