"""
ColorManager — Valide la cohérence des LUTs et color grades (v5.0).

Responsabilités:
    - Vérifier que chaque shot avec location_id a une lut_id assignée dans color_luts
    - Bloquer les color_grade_hint orange_teal (interdit District Zero S1)
    - Vérifier que desaturated/monochrome est réservé à denouement/flashback
"""
from __future__ import annotations

from dataclasses import dataclass, field

from aiprod_adaptation.models.schema import AIPRODOutput, Shot

_FORBIDDEN_GRADES: frozenset[str] = frozenset({"orange_teal"})
_RESTRICTED_GRADES: frozenset[str] = frozenset({"desaturated", "monochrome"})
_ALLOWED_RESTRICTED_BEATS: frozenset[str] = frozenset({"denouement"})
_ALLOWED_RESTRICTED_SCENES: frozenset[str] = frozenset({"flashback"})


@dataclass
class ColorValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ColorManager:
    """Validates LUT assignments and color grade consistency."""

    def validate(
        self,
        output: AIPRODOutput,
    ) -> ColorValidationResult:
        """
        Validates color grading across all shots:
          - Forbidden grades (orange_teal) → error
          - Restricted grades only on denouement/flashback → error otherwise
          - Location without lut_id in color_luts → warning
        """
        errors: list[str] = []
        warnings: list[str] = []
        color_luts = output.color_luts

        # Build scene_type index from scenes
        scene_type_index: dict[str, str] = {}
        for episode in output.episodes:
            for scene in episode.scenes:
                scene_type_index[scene.scene_id] = getattr(scene, "scene_type", "") or ""

        for episode in output.episodes:
            for shot in episode.shots:
                grade = (shot.metadata or {}).get("color_grade_hint", "")
                beat = (shot.metadata or {}).get("beat_type", "")
                scene_type = scene_type_index.get(shot.scene_id, "")

                # Forbidden check
                if grade in _FORBIDDEN_GRADES:
                    errors.append(
                        f"{shot.shot_id}: forbidden color_grade_hint '{grade}' "
                        f"(district zero s1 — use cool/warm/high_contrast)"
                    )

                # Restricted grades check
                if grade in _RESTRICTED_GRADES:
                    allowed = (
                        beat in _ALLOWED_RESTRICTED_BEATS
                        or scene_type in _ALLOWED_RESTRICTED_SCENES
                    )
                    if not allowed:
                        errors.append(
                            f"{shot.shot_id}: '{grade}' is restricted to "
                            f"denouement/flashback only (beat='{beat}', scene_type='{scene_type}')"
                        )

                # LUT coverage warning
                loc_id = self._resolve_location_id(shot, episode.scenes if hasattr(episode, "scenes") else [])
                if loc_id and loc_id not in color_luts:
                    warnings.append(
                        f"{shot.shot_id}: location '{loc_id}' has no lut_id in color_luts"
                    )

        return ColorValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def _resolve_location_id(self, shot: Shot, scenes: list) -> str | None:
        for scene in scenes:
            if scene.scene_id == shot.scene_id:
                return scene.location_id or None
        return None
