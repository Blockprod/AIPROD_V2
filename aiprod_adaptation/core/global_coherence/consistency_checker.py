"""
consistency_checker.py — Pass 4 global coherence validation.

Receives the Pydantic Shot and Scene objects produced by compile_episode and
applies the deterministic rule set from pass4_coherence_rules:

  R01 Feasibility gate        : downgrade camera_movement when score < threshold
  R02 Colour grade homogeneity: normalise conflicting grades within a scene
  R03 Establishing shot check : warn when first scene lacks wide/extreme_wide shots
  R04 Dramatic arc flatness   : detect flat emotional_beat_index trajectory

Returns:
    (enriched_shots: list[Shot], report: ConsistencyReport)

All Shot mutations use model_copy(update=...) — no in-place mutation of
Pydantic objects.  The ConsistencyReport is a new Pydantic instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiprod_adaptation.core.visual_bible import VisualBible

from aiprod_adaptation.core.rules.pass4_coherence_rules import (
    ARC_FLAT_THRESHOLD,
    COLOR_GRADE_MAX_DISTINCT,
    CONSISTENCY_PENALTY_ARC_FLAT,
    CONSISTENCY_PENALTY_MOVEMENT_SIMPLIFICATION,
    CONSISTENCY_PENALTY_TONE_CONFLICT,
    ESTABLISHING_SHOT_MIN_RATIO,
    FEASIBILITY_MOVEMENT_MINIMUM,
    TONE_COLOR_GRADE_DEFAULTS,
    WIDE_SHOT_TYPES,
)
from aiprod_adaptation.models.schema import ConsistencyReport, Scene, Shot


def check_and_enrich(
    scenes: list[Scene],
    shots: list[Shot],
    visual_bible: VisualBible | None = None,
) -> tuple[list[Shot], ConsistencyReport]:
    """
    Validate and (where required) mutate the compiled shot list.

    Args:
        scenes: Compiled Scene objects (Pydantic) from compile_episode.
        shots:  Compiled Shot objects (Pydantic) from compile_episode.
        visual_bible: Optional VisualBible instance. Not used directly here;
                      reserved for future location-lighting override (R08).

    Returns:
        (enriched_shots, ConsistencyReport)
    """
    tone_conflicts: list[str] = []
    continuity_warnings: list[str] = []
    movement_simplifications: list[str] = []

    scene_by_id: dict[str, Scene] = {s.scene_id: s for s in scenes}

    # ------------------------------------------------------------------
    # R01 — Feasibility gate
    # ------------------------------------------------------------------
    working_shots: list[Shot] = []
    for shot in shots:
        if (
            shot.feasibility_score < FEASIBILITY_MOVEMENT_MINIMUM
            and shot.camera_movement != "static"
        ):
            shot = shot.model_copy(update={"camera_movement": "static"})
            movement_simplifications.append(shot.shot_id)
        working_shots.append(shot)

    # ------------------------------------------------------------------
    # R02 — Colour grade homogeneity per scene
    # ------------------------------------------------------------------
    # Build scene → shot index map so we can replace shots by index
    scene_shot_indices: dict[str, list[int]] = {}
    for idx, shot in enumerate(working_shots):
        scene_shot_indices.setdefault(shot.scene_id, []).append(idx)

    for scene_id, indices in scene_shot_indices.items():
        scene = scene_by_id.get(scene_id)
        if scene is None:
            continue
        # Collect distinct colour grades
        grades: set[str] = set()
        for i in indices:
            cg = working_shots[i].metadata.get("color_grade_hint")
            if cg:
                grades.add(str(cg))
        if len(grades) > COLOR_GRADE_MAX_DISTINCT:
            # Normalise all shots in this scene to the tone default
            tone = scene.scene_tone or "neutral"
            default_grade = TONE_COLOR_GRADE_DEFAULTS.get(tone, "neutral")
            for i in indices:
                shot = working_shots[i]
                cg = shot.metadata.get("color_grade_hint")
                if cg and cg != default_grade:
                    new_meta = {**shot.metadata, "color_grade_hint": default_grade}
                    working_shots[i] = shot.model_copy(update={"metadata": new_meta})
            tone_conflicts.append(scene_id)

    # ------------------------------------------------------------------
    # R03 — Establishing shot in first scene
    # ------------------------------------------------------------------
    if scenes:
        first_scene_id = scenes[0].scene_id
        first_indices = scene_shot_indices.get(first_scene_id, [])
        if first_indices:
            wide_count = sum(
                1 for i in first_indices
                if working_shots[i].shot_type in WIDE_SHOT_TYPES
            )
            wide_ratio = wide_count / len(first_indices)
            if wide_ratio < ESTABLISHING_SHOT_MIN_RATIO:
                continuity_warnings.append(
                    f"no_establishing_shot:scene={first_scene_id}"
                )

    # ------------------------------------------------------------------
    # R04 — Dramatic arc flatness
    # ------------------------------------------------------------------
    beat_indices_values: list[float] = []
    for shot in working_shots:
        ebi = shot.metadata.get("emotional_beat_index")
        if ebi is not None:
            try:
                beat_indices_values.append(float(ebi))
            except (TypeError, ValueError):
                pass

    arc_flat = False
    if len(beat_indices_values) >= 2:
        arc_range = max(beat_indices_values) - min(beat_indices_values)
        if arc_range < ARC_FLAT_THRESHOLD:
            arc_flat = True
            continuity_warnings.append("dramatic_arc_flat")

    # ------------------------------------------------------------------
    # Compute consistency_score
    # ------------------------------------------------------------------
    score = 1.0
    score -= CONSISTENCY_PENALTY_TONE_CONFLICT * len(tone_conflicts)
    score -= CONSISTENCY_PENALTY_MOVEMENT_SIMPLIFICATION * len(movement_simplifications)
    if arc_flat:
        score -= CONSISTENCY_PENALTY_ARC_FLAT
    score = max(0.0, min(1.0, score))

    report = ConsistencyReport(
        consistency_score=round(score, 4),
        tone_conflicts=tone_conflicts,
        continuity_warnings=continuity_warnings,
        movement_simplifications=movement_simplifications,
        prompt_enrichments=0,  # will be updated by prompt_finalizer
    )

    return working_shots, report
