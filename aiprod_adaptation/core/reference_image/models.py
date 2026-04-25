"""
Pydantic models for the reference_image analysis pipeline.

All models are JSON-serialisable (model.model_dump()) and produce
deterministic output given the same input image.

Priority hierarchy reflected in VisualInvariants:
  1. subject_* fields        — identity anchor (highest priority, never overridden)
  2. lighting                — key direction, temperature, intensity
  3. camera_height_class     — spatial coherence anchor
  4. depth_layers            — composition / depth anchor
  5. palette                 — colour anchor (can be modulated within constraints)
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class RejectionReason(StrEnum):
    RESOLUTION_TOO_LOW    = "RESOLUTION_TOO_LOW"
    TOO_BLURRY            = "TOO_BLURRY"
    OVEREXPOSED           = "OVEREXPOSED"
    UNDEREXPOSED          = "UNDEREXPOSED"
    LOW_INFORMATION       = "LOW_INFORMATION"
    MONOCHROMATIC_INPUT   = "MONOCHROMATIC_INPUT"
    LOAD_ERROR            = "LOAD_ERROR"


class CameraHeightClass(StrEnum):
    EYE_LEVEL  = "eye_level"
    LOW_ANGLE  = "low_angle"
    HIGH_ANGLE = "high_angle"
    OVERHEAD   = "overhead"


class LightingDirectionH(StrEnum):
    LEFT   = "left"
    CENTER = "center"
    RIGHT  = "right"


class LightingDirectionV(StrEnum):
    TOP    = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


# ---------------------------------------------------------------------------
# Color swatch
# ---------------------------------------------------------------------------

class ColorSwatch(BaseModel):
    """
    A dominant colour extracted from the image via LAB k-means clustering.

    rank          : 1 = most dominant (by pixel area), ascending.
    hex_code      : sRGB hex string, e.g. "#ff6b35".
    lab           : [L, a, b] in CIE LAB D65.
    coverage_pct  : percentage of total pixels in this cluster [0.0, 100.0].
    variability   : invariant classification.
                    "invariant"     — top-2 dominant colours (identity anchor).
                    "semi_variable" — rank 3–4 (accent, modulate within limits).
                    "variable"      — rank 5+ (background, freely adjustable).
    """
    rank: int
    hex_code: str
    lab: list[float] = Field(min_length=3, max_length=3)
    coverage_pct: float
    variability: str = "variable"

    @field_validator("hex_code")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        if not (v.startswith("#") and len(v) == 7):
            raise ValueError(f"hex_code must be '#RRGGBB', got: {v!r}")
        return v


# ---------------------------------------------------------------------------
# Lighting analysis
# ---------------------------------------------------------------------------

class LightingAnalysis(BaseModel):
    """
    Deterministic lighting characterisation extracted from luminance channel.

    key_direction_h     : dominant horizontal key-light origin (left/center/right).
    key_direction_v     : dominant vertical key-light origin (top/middle/bottom).
    color_temperature_k : approximate colour temperature in Kelvin
                          derived from R/B ratio in highlight zone.
                          Warm (tungsten) ≈ 2700–3200 K, Daylight ≈ 5500–6500 K, Cool (HMI) ≈ 5600–6500 K.
    intensity_l95       : 95th percentile of L* channel — peak brightness.
    contrast_std_l      : standard deviation of L* — scene contrast fingerprint.
    highlight_pct       : percentage of pixels with L* > 90 (specular / blown highlights).
    shadow_pct          : percentage of pixels with L* < 10 (crushed blacks / deep shadow).
    """
    key_direction_h: LightingDirectionH
    key_direction_v: LightingDirectionV
    color_temperature_k: int   # approximate, ±500 K tolerance
    intensity_l95: float       # [0.0, 100.0]
    contrast_std_l: float      # [0.0, ~50.0]
    highlight_pct: float       # [0.0, 100.0]
    shadow_pct: float          # [0.0, 100.0]


# ---------------------------------------------------------------------------
# Depth layer estimate
# ---------------------------------------------------------------------------

class DepthLayerEstimate(BaseModel):
    """
    Coarse depth-of-field layer analysis based on gradient magnitude bands.

    Each layer is a horizontal third of the image (foreground = bottom, background = top
    for standard eye-level framing).

    gradient_mean_* : mean Sobel magnitude in that horizontal band [0, 255].
                      Higher = more detail = closer to camera (more in focus).
    dominant_layer  : layer with highest gradient mean — likely focal plane.
    """
    gradient_mean_foreground: float   # bottom third
    gradient_mean_midground: float    # middle third
    gradient_mean_background: float   # top third
    dominant_layer: str               # "foreground" | "midground" | "background"


# ---------------------------------------------------------------------------
# Visual Invariants — main extraction output
# ---------------------------------------------------------------------------

class VisualInvariants(BaseModel):
    """
    Complete set of visual invariants extracted from a single reference image.
    Serialisable to JSON; used to enrich the VisualBible and shot prompts.

    Fields are ordered by constraint priority (highest → lowest):

    Priority 1 — Subject identity
      subject_coverage_pct  : how much of the frame the subject occupies.
      luminance_fingerprint  : MD5 of 32×32 luminance map — identity anchor.

    Priority 2 — Lighting
      lighting               : full lighting characterisation.

    Priority 3 — Camera / spatial coherence
      camera_height_class    : eye_level | low_angle | high_angle | overhead.
      aspect_ratio           : "16:9", "2.39:1", etc.

    Priority 4 — Depth / composition
      depth_layers           : foreground / midground / background gradient profile.

    Priority 5 — Colour palette
      palette                : up to 5 ColorSwatch objects, ranked by coverage.
    """
    # ---- source metadata ----
    source_path: str
    width_px: int
    height_px: int
    aspect_ratio: str

    # ---- priority 1: subject identity ----
    subject_coverage_pct: float    # otsu foreground ratio as percentage
    luminance_fingerprint: str     # MD5 hex of 32×32 L* map

    # ---- priority 2: lighting ----
    lighting: LightingAnalysis

    # ---- priority 3: camera / spatial coherence ----
    camera_height_class: CameraHeightClass

    # ---- priority 4: depth / composition ----
    depth_layers: DepthLayerEstimate

    # ---- priority 5: palette ----
    palette: list[ColorSwatch] = Field(min_length=1, max_length=5)

    def to_prompt_fragment(self) -> str:
        """
        Produce a concise, determistic prose fragment suitable for injection into
        a shot prompt. Encodes invariants ordered by priority.
        """
        top_colors = ", ".join(s.hex_code for s in self.palette[:2])
        lines = [
            f"Camera: {self.camera_height_class.value} shot, {self.aspect_ratio} frame.",
            (
                f"Lighting: key from {self.lighting.key_direction_h.value}-"
                f"{self.lighting.key_direction_v.value}, "
                f"~{self.lighting.color_temperature_k} K, "
                f"contrast std L*={self.lighting.contrast_std_l:.1f}."
            ),
            f"Dominant palette: {top_colors}.",
            f"Subject coverage: {self.subject_coverage_pct:.0f}% of frame.",
        ]
        return " ".join(lines)


# ---------------------------------------------------------------------------
# Reference Quality Report
# ---------------------------------------------------------------------------

class QualityComponentScores(BaseModel):
    clarity: float      # sharpness score [0.0, 1.0] — normalised Laplacian variance
    lighting: float     # usable-luminance ratio [0.0, 1.0]
    subject: float      # foreground coverage score [0.0, 1.0]
    depth: float        # gradient variation coefficient [0.0, 1.0]
    composition: float  # thirds-entropy score [0.0, 1.0]


class ReferenceQualityReport(BaseModel):
    """
    Output of ReferenceQualityGate.check().

    passed                : True iff no hard rejections AND composite_score >= threshold.
    composite_score       : weighted composite [0.0, 1.0].
    component_scores      : per-dimension breakdown.
    rejection_reasons     : list of hard-rejection codes (empty if passed).
    warnings              : soft issues (non-blocking).
    threshold_used        : the minimum score used for the pass/fail decision.
    recommendation        : human-readable action string.
    """
    source_path: str
    passed: bool
    composite_score: float
    component_scores: QualityComponentScores
    rejection_reasons: list[RejectionReason] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    threshold_used: float
    recommendation: str

    @property
    def is_warning_only(self) -> bool:
        return self.passed and len(self.warnings) > 0

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"[{status}] {self.source_path}  score={self.composite_score:.3f} "
            f"(threshold={self.threshold_used})",
            f"  clarity={self.component_scores.clarity:.3f}  "
            f"lighting={self.component_scores.lighting:.3f}  "
            f"subject={self.component_scores.subject:.3f}  "
            f"depth={self.component_scores.depth:.3f}  "
            f"composition={self.component_scores.composition:.3f}",
        ]
        for r in self.rejection_reasons:
            lines.append(f"  REJECT: {r.value}")
        for w in self.warnings:
            lines.append(f"  WARN:   {w}")
        lines.append(f"  → {self.recommendation}")
        return "\n".join(lines)
