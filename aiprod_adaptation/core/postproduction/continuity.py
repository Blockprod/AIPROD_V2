"""
ContinuityBuilder — detects continuity issues in a compiled shot list.

Checks performed
----------------
  ESTABLISHING : close-up present in scene without preceding wide/extreme_wide
  LIGHTING     : multiple distinct lighting_directives within one scene
  COLOR_GRADE  : mixed color_grade_hint values within one scene
"""

from __future__ import annotations

from aiprod_adaptation.core.postproduction.models import ContinuityNote
from aiprod_adaptation.models.schema import Scene, Shot

_ESTABLISHING_TYPES: frozenset[str] = frozenset({"wide", "extreme_wide"})
_CLOSE_TYPES: frozenset[str] = frozenset({"close_up", "extreme_close_up"})


class ContinuityBuilder:
    """Build a list of ContinuityNotes from a shot list and scene list."""

    def build(
        self,
        shots: list[Shot],
        scenes: list[Scene],
    ) -> list[ContinuityNote]:
        notes: list[ContinuityNote] = []
        counter = 0

        # Group shots by scene preserving insertion order
        scene_shots: dict[str, list[Shot]] = {}
        for shot in shots:
            scene_shots.setdefault(shot.scene_id, []).append(shot)

        for scene in scenes:
            sc_shots = scene_shots.get(scene.scene_id, [])
            if not sc_shots:
                continue

            # ---- ESTABLISHING check ----
            if len(sc_shots) > 1:
                has_establishing = sc_shots[0].shot_type in _ESTABLISHING_TYPES
                has_close_ups = any(s.shot_type in _CLOSE_TYPES for s in sc_shots)
                if has_close_ups and not has_establishing:
                    counter += 1
                    notes.append(
                        ContinuityNote(
                            note_id=f"CONT-{counter:03d}",
                            shot_id=sc_shots[0].shot_id,
                            scene_id=scene.scene_id,
                            continuity_type="establishing",
                            note=(
                                f"Scene {scene.scene_id}: close-up shots present "
                                "without a preceding establishing shot (wide/extreme_wide)."
                            ),
                            severity="warning",
                        )
                    )

            # ---- LIGHTING consistency ----
            lighting_dirs = [s.lighting_directives for s in sc_shots if s.lighting_directives]
            if len(set(lighting_dirs)) > 1:
                counter += 1
                notes.append(
                    ContinuityNote(
                        note_id=f"CONT-{counter:03d}",
                        shot_id=sc_shots[0].shot_id,
                        scene_id=scene.scene_id,
                        continuity_type="lighting",
                        note=(
                            f"Scene {scene.scene_id}: {len(set(lighting_dirs))} distinct "
                            "lighting directives detected. Verify key light consistency."
                        ),
                        severity="info",
                    )
                )

            # ---- COLOR GRADE consistency ----
            color_grades = [
                g for s in sc_shots if (g := s.metadata.get("color_grade_hint"))
            ]
            distinct_grades = set(color_grades)
            if len(distinct_grades) > 1:
                counter += 1
                notes.append(
                    ContinuityNote(
                        note_id=f"CONT-{counter:03d}",
                        shot_id=sc_shots[0].shot_id,
                        scene_id=scene.scene_id,
                        continuity_type="color",
                        note=(
                            f"Scene {scene.scene_id}: mixed color grades "
                            f"{sorted(distinct_grades)}. Normalise in DaVinci Resolve."
                        ),
                        severity="warning",
                    )
                )

        return notes
