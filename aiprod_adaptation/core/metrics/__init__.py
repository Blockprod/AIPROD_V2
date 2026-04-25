"""core/metrics — deterministic quality metrics for AIPROD_Cinematic."""

from aiprod_adaptation.core.metrics.engine import MetricsEngine
from aiprod_adaptation.core.metrics.models import (
    NETFLIX_TARGET_CINEMATIC_RICHNESS,
    NETFLIX_TARGET_CONFLICT_RESOLUTION,
    NETFLIX_TARGET_CONTINUITY,
    NETFLIX_TARGET_FEASIBILITY,
    NETFLIX_TARGET_OVERALL_COHERENCE,
    NETFLIX_TARGET_REFERENCE_QUALITY,
    NETFLIX_TARGET_VISUAL_CONSISTENCY,
    EpisodeMetrics,
    SeasonMetrics,
    ShotMetrics,
)

__all__ = [
    "MetricsEngine",
    "EpisodeMetrics",
    "SeasonMetrics",
    "ShotMetrics",
    "NETFLIX_TARGET_CINEMATIC_RICHNESS",
    "NETFLIX_TARGET_CONFLICT_RESOLUTION",
    "NETFLIX_TARGET_CONTINUITY",
    "NETFLIX_TARGET_FEASIBILITY",
    "NETFLIX_TARGET_OVERALL_COHERENCE",
    "NETFLIX_TARGET_REFERENCE_QUALITY",
    "NETFLIX_TARGET_VISUAL_CONSISTENCY",
]
