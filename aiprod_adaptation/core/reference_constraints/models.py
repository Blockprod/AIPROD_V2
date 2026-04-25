"""
reference_constraints/models.py — Actionable constraint set derived from VisualInvariants.

ReferenceConstraints is the normalised, pipeline-ready form of the raw analysis
data produced by VisualInvariantsExtractor.  It is produced once per reference image
(or per location) and injected into:

  - Pass 3 (FeasibilityEngine.compute)
  - Pass 4 Rule Engine (EvalContext.ref_invariants is a VisualInvariants;
    ReferenceConstraints is the derived, human-readable companion)

Design
------
- All fields are optional so the model is valid even from a partial reference.
- `forbidden_movements` and `suggested_movements` are derived from `camera_height`
  using deterministic lookup tables (no heuristics, no randomness).
- JSON round-trip via model.model_dump() / ReferenceConstraints.model_validate().
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReferenceConstraints(BaseModel):
    """
    Actionable constraints extracted from a reference image + optional location data.

    camera_height       : "eye_level" | "low_angle" | "high_angle" | "overhead" | None
    lighting_direction_h: "left" | "center" | "right" | None
    lighting_direction_v: "top" | "middle" | "bottom" | None
    dominant_depth_layer: "foreground" | "midground" | "background" | None
    forbidden_movements : camera movements physically incompatible with camera_height
    suggested_movements : camera movements compatible and visually coherent
    palette_anchor_hex  : hex codes of invariant (rank 1-2) and semi-variable (rank 3-4)
                          colours — to be preserved in shot prompt colour directives
    location_id         : optional location identifier from VisualBible
    architecture_style  : e.g. "brutalist" | "domestic" | "industrial" | "natural" | None
                          — feeds FeasibilityEngine location penalty
    """

    camera_height: str | None = None
    lighting_direction_h: str | None = None
    lighting_direction_v: str | None = None
    dominant_depth_layer: str | None = None
    forbidden_movements: list[str] = Field(default_factory=list)
    suggested_movements: list[str] = Field(default_factory=list)
    palette_anchor_hex: list[str] = Field(default_factory=list)
    location_id: str | None = None
    architecture_style: str | None = None
