"""
Intermediate representations (IR) for the AIPROD pipeline.

These TypedDicts define the strict contracts between pipeline passes:

  Pass 1 → RawScene / CinematicScene → Pass 2
  Pass 2 → VisualScene               → Pass 3
  Pass 3 → ShotDict                  → Pass 4

Using TypedDict (not Pydantic) keeps zero runtime overhead while giving
mypy full static visibility into every key used between passes.

v3.0 additions
--------------
CinematicScene  — enriched output of Pass 1 with scene_type, beat_type,
                  emotional_arc_index, act_position, reference_location_id,
                  sublocation, characters_entering, continuity_flags.
VisualScene     — extended with scene_type, act_position,
                  reference_location_id, continuity_flags (propagated
                  unchanged from Pass 1).

v3.0 Pass 2 additions
---------------------
PhysicalAction      — one layer of a multi-layer body-language action unit.
BodyLanguageState   — character's carried body-language state exiting a scene.
VisualScene         — extended with physical_actions, body_language_states,
                      environmental_interactions, visual_invariants_applied,
                      emotional_layer, action_intensity.
"""

from __future__ import annotations

from typing import Any, NotRequired

from typing_extensions import TypedDict


class ActionSpec(TypedDict):
    """Structured action payload propagated alongside textual compatibility fields."""
    subject_id: str
    action_type: str
    target: str | None
    modifiers: list[str]
    location_id: str | None
    camera_intent: str
    source_text: str


class PhysicalAction(TypedDict):
    """
    One layer of a multi-layer body-language action unit (Pass 2 v3.0).

    layer
        One of: "posture" | "gesture" | "gaze" | "micro_expression" | "breath"
    description
        English present-tense directive suitable for shot prompt / storyboard.
    intensity
        "subtle" | "mid" | "explosive"
    character_id
        Identifier of the character performing this action (slugified name or pronoun).
    """
    character_id: str
    layer:        str    # "posture"|"gesture"|"gaze"|"micro_expression"|"breath"
    description:  str
    intensity:    str    # "subtle"|"mid"|"explosive"


class BodyLanguageState(TypedDict):
    """
    Character-level body language state carried OUT of a scene.

    Used to propagate continuity across scenes and episodes.
    The ContinuityTracker (future sprint) consumes this to maintain
    consistent physical characterisation across a 10-episode season.

    energy_level
        "still"    — no energy expenditure; waiting or empty
        "coiled"   — energy held back, ready to act
        "released" — energy expressed and now spent
        "exhausted"— energy depleted; body at low register
        "charged"  — energy actively building; positive or negative

    gaze_direction
        "inward"   — looking at memory / thought, not present space
        "forward"  — engaged with what is in front
        "avoidant" — actively avoiding eye contact or subject
        "hunting"  — scanning for threat or target
        "scanning" — neutral alert scan of environment
    """
    character_id:     str
    posture:          str   # brief prose descriptor of final posture
    energy_level:     str   # "still"|"coiled"|"released"|"exhausted"|"charged"
    gaze_direction:   str   # "inward"|"forward"|"avoidant"|"hunting"|"scanning"
    dominant_emotion: str   # emotion name from EMOTION_RULES


class RawScene(TypedDict):
    """
    Output of Pass 1 (segment) — base contract, backward compatible with v2.
    Use CinematicScene for the full v3.0 enriched output.
    """
    scene_id:    str
    characters:  list[str]
    location:    str
    time_of_day: str | None
    raw_text:    str


class CinematicScene(TypedDict):
    """
    Enriched output of Pass 1 (pass1_segment.py v3.0).
    Superset of RawScene — all mandatory fields are identical; cinematic
    fields are NotRequired so consumers can test with plain RawScene dicts.

    scene_type
        "standard"   — ordinary narrative scene
        "flashback"  — memory / past-tense cluster
        "dream"      — surreal / oneiric sequence
        "montage"    — rapid-cut series (≥3 ultra-short paragraphs)
        "teaser"     — pre-title cold open
        "tag"        — post-climax coda
        "cliffhanger"— episode-ending tension beat
        "transition" — structural act-break passage

    act_position
        "teaser" | "act1" | "act2" | "act3" | "act4" | "tag" | "act_end"

    emotional_arc_index
        Continuous float [0.0, 1.0].  Computed as:
        (scene_position / estimated_total_scenes) × beat_weight × scene_type_weight
        where weights come from segmentation_rules_v3.BEAT_TYPE_WEIGHTS
        and SCENE_TYPE_WEIGHTS.

    reference_location_id
        VisualBible slug (e.g. "the_archive") when the detected location
        matches a known location in the injected VisualBible.

    continuity_flags
        List of string tokens used by the Quality Gate and continuity tracker:
          "FIRST_APPEARANCE:{name}"   — character debut in this scene
          "CLIFFHANGER"               — end-of-episode tension marker detected
          "FLASHBACK_TRIGGER"         — scene classified as flashback
          "LOCATION_RECURRENCE:{slug}"— location seen for the second time
          "ACT_BREAK"                 — structural act boundary
    """
    # ---- Mandatory (RawScene compat) ----
    scene_id:    str
    characters:  list[str]
    location:    str
    time_of_day: str | None
    raw_text:    str
    # ---- Cinematic enrichment (NotRequired for compat) ----
    scene_type:            NotRequired[str]        # standard|flashback|dream|montage|teaser|tag|cliffhanger|transition
    sublocation:           NotRequired[str]        # e.g. "back room", "window seat"
    beat_type:             NotRequired[str]        # exposition|action|dialogue_scene|transition|climax|denouement
    emotional_arc_index:   NotRequired[float]      # [0.0, 1.0]
    act_position:          NotRequired[str]        # teaser|act1|act2|act3|act4|tag|act_end
    reference_location_id: NotRequired[str]        # VisualBible slug
    characters_entering:   NotRequired[list[str]]  # new in this scene vs previous
    continuity_flags:      NotRequired[list[str]]  # ["FIRST_APPEARANCE:Kael", "CLIFFHANGER"]


class VisualScene(TypedDict):
    """Output of Pass 2 (visual_rewrite). Input to Pass 3 (simplify_shots)."""
    scene_id:       str
    characters:     list[str]
    location:       str
    time_of_day:    str | None
    visual_actions: list[str]
    # Each entry: one declarative sentence in English, subject + verb + object.
    # Example: "John walks toward the door."
    # No dialogue, no stage directions, no internal thoughts.
    dialogues:      list[str]
    emotion:        str
    # Optional enrichment fields (SE-04) — set by StoryExtractor when LLM provides them
    pacing:             NotRequired[str]   # "fast" | "medium" | "slow"
    time_of_day_visual: NotRequired[str]   # "dawn" | "day" | "dusk" | "night" | "interior"
    dominant_sound:     NotRequired[str]   # "dialogue" | "ambient" | "silence"
    action_units:       NotRequired[list[ActionSpec]]
    # v3.0 cinematic fields — set by Pass 1 (beat_type) and Pass 2 (scene_tone)
    beat_type:          NotRequired[str]   # exposition | action | dialogue_scene | transition | climax | denouement
    scene_tone:         NotRequired[str]   # noir | golden_hour | clinical | intimate | epic | surreal | tense | neutral
    emotional_beat_index: NotRequired[float]  # cumulative dramatic intensity [0.0, 1.0]
    # v3.0 Pass-1 provenance fields — propagated unchanged from CinematicScene
    scene_type:            NotRequired[str]        # see CinematicScene.scene_type
    act_position:          NotRequired[str]        # see CinematicScene.act_position
    reference_location_id: NotRequired[str]        # VisualBible slug
    continuity_flags:      NotRequired[list[str]]  # ["FIRST_APPEARANCE:Kael", ...]
    # v3.0 Pass-2 cinematic body-language fields (all NotRequired for compat)
    physical_actions:            NotRequired[list[PhysicalAction]]
    # Structured multi-layer body language actions — 5 layers per emotion.
    environmental_interactions:  NotRequired[list[str]]
    # Prose strings describing character↔environment contact (architecture-driven).
    visual_invariants_applied:   NotRequired[list[str]]
    # Which VisualBible invariants were injected (wardrobe, lighting, etc.).
    emotional_layer:             NotRequired[str]
    # "surface" | "surface_neutral" | "disguised" | "erupting" | "displaced"
    action_intensity:            NotRequired[str]
    # "subtle" | "mid" | "explosive"
    body_language_states:        NotRequired[list[BodyLanguageState]]
    # One BodyLanguageState per character — carries forward to next scene.


class ShotDict(TypedDict):
    """Output of Pass 3 (simplify_shots). Input to Pass 4 (compile_episode)."""
    shot_id:          str
    scene_id:         str
    prompt:           str
    duration_sec:     int
    emotion:          str
    shot_type:        str   # "wide" | "medium" | "close_up" | "pov"
    camera_movement:  str   # "static" | "follow" | "pan"
    metadata:         NotRequired[dict[str, Any]]
    action:           NotRequired[ActionSpec]
