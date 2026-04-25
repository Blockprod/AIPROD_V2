"""
reference_image — deterministic reference image analysis for AIPROD_Cinematic v3.0.

Public API
----------
from aiprod_adaptation.core.reference_image import (
    ReferenceQualityGate,
    VisualInvariantsExtractor,
    ReferenceQualityReport,
    VisualInvariants,
)

gate = ReferenceQualityGate()
report = gate.check(path)               # → ReferenceQualityReport
if report.passed:
    extractor = VisualInvariantsExtractor()
    invariants = extractor.extract(path)  # → VisualInvariants

All operations are deterministic, pixel-level, and produce JSON-serialisable output.
No neural models, no randomness, no external API calls.
"""

from aiprod_adaptation.core.reference_image.extractor import VisualInvariantsExtractor
from aiprod_adaptation.core.reference_image.models import (
    ColorSwatch,
    DepthLayerEstimate,
    LightingAnalysis,
    ReferenceQualityReport,
    RejectionReason,
    VisualInvariants,
)
from aiprod_adaptation.core.reference_image.quality_gate import ReferenceQualityGate

__all__ = [
    "ColorSwatch",
    "DepthLayerEstimate",
    "LightingAnalysis",
    "ReferenceQualityReport",
    "RejectionReason",
    "VisualInvariants",
    "ReferenceQualityGate",
    "VisualInvariantsExtractor",
]
