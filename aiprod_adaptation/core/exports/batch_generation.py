"""
Batch Generation JSON export — ready-to-submit manifest for AI video generation APIs.

Compatible with
---------------
  - Runway Gen-3 Alpha / Gen-4 Turbo
  - Kling 1.6
  - Luma Dream Machine
  - Google Veo 2

Each shot includes the fully enriched prompt plus generation parameters derived
from shot metadata (aspect_ratio, motion_intensity, color_grade, duration).
Reference anchors (palette hex codes, camera height class) are embedded per-shot
for reference-aware generation APIs.
"""

from __future__ import annotations

import json
from typing import Any

from aiprod_adaptation.models.schema import AIPRODOutput

_MOVEMENT_TO_INTENSITY: dict[str, str] = {
    "static": "none",
    "rack_focus": "low",
    "tilt_up": "low",
    "tilt_down": "low",
    "pan": "low",
    "follow": "low",
    "steadicam": "moderate",
    "tracking": "moderate",
    "handheld": "moderate",
    "dolly_in": "moderate",
    "dolly_out": "moderate",
    "whip_pan": "high",
    "crane_up": "high",
    "crane_down": "high",
}


def export_batch_generation(
    output: AIPRODOutput,
    adapter_target: str = "runway",
    fps: float = 24.0,
    aspect_ratio: str = "16:9",
    ref_invariants: object | None = None,
) -> str:
    """
    Export AIPRODOutput as a batch generation manifest JSON.

    Args:
        output:         AIPRODOutput from the pipeline.
        adapter_target: Target adapter name ("runway" | "kling" | "luma" | "veo2").
        fps:            Target frame rate.
        aspect_ratio:   Output aspect ratio.
        ref_invariants: Optional VisualInvariants for reference anchor embedding.
    """
    ref_anchors: list[dict[str, Any]] = _extract_ref_anchors(ref_invariants)
    ref_camera_height: str | None = _extract_camera_height(ref_invariants)

    batch_shots: list[dict[str, Any]] = []
    for ep in output.episodes:
        for shot in ep.shots:
            motion_intensity = _MOVEMENT_TO_INTENSITY.get(shot.camera_movement, "moderate")

            generation_params: dict[str, Any] = {
                "aspect_ratio": aspect_ratio,
                "duration_sec": shot.duration_sec,
                "fps": fps,
                "motion_intensity": motion_intensity,
            }
            if shot.metadata.get("color_grade_hint"):
                generation_params["color_grade"] = shot.metadata["color_grade_hint"]
            if ref_camera_height:
                generation_params["camera_height_class"] = ref_camera_height

            shot_entry: dict[str, Any] = {
                "shot_id": shot.shot_id,
                "scene_id": shot.scene_id,
                "episode_id": ep.episode_id,
                "prompt": shot.prompt,
                "shot_type": shot.shot_type,
                "camera_movement": shot.camera_movement,
                "emotion": shot.emotion,
                "feasibility_score": shot.feasibility_score,
                "reference_anchor_strength": shot.reference_anchor_strength,
                "reference_anchors": ref_anchors,
                "generation_params": generation_params,
            }
            if shot.composition_description:
                shot_entry["composition_description"] = shot.composition_description
            if shot.lighting_directives:
                shot_entry["lighting_directives"] = shot.lighting_directives

            batch_shots.append(shot_entry)

    batch: dict[str, Any] = {
        "batch_schema": "aiprod_batch_generation",
        "schema_version": "1.0",
        "title": output.title,
        "adapter_target": adapter_target,
        "shot_count": len(batch_shots),
        "fps": fps,
        "aspect_ratio": aspect_ratio,
        "shots": batch_shots,
    }
    return json.dumps(batch, indent=2, ensure_ascii=False)


def _extract_ref_anchors(ref_invariants: object | None) -> list[dict[str, Any]]:
    if ref_invariants is None:
        return []
    palette = getattr(ref_invariants, "palette", None)
    if not palette:
        return []
    anchors = []
    for swatch in palette:
        variability = getattr(swatch, "variability", "variable")
        if variability in {"invariant", "semi_variable"}:
            anchors.append(
                {
                    "hex": getattr(swatch, "hex_code", None),
                    "variability": variability,
                    "coverage_pct": getattr(swatch, "coverage_pct", None),
                }
            )
    return anchors


def _extract_camera_height(ref_invariants: object | None) -> str | None:
    if ref_invariants is None:
        return None
    cam_h = getattr(ref_invariants, "camera_height_class", None)
    if cam_h is None:
        return None
    return cam_h.value if hasattr(cam_h, "value") else str(cam_h)
