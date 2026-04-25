"""
Quality metrics models for AIPROD_Cinematic.

All metrics are deterministic, normalised to [0.0–1.0], and JSON-serialisable.
Netflix broadcast targets are exposed as module-level constants.

Hierarchy
---------
  ShotMetrics    — per-shot reference_quality + feasibility
  EpisodeMetrics — per-episode aggregated metrics + broadcast gate
  SeasonMetrics  — season-level aggregation + overall_season_coherence_score

Formulas
--------
  RQS_i      = reference_anchor_strength_i × (feasibility_score_i / 100)
  RQS_ep     = Σ(RQS_i × dur_i) / Σ(dur_i)                  [duration-weighted]
  VCS        = ConsistencyReport.consistency_score             [from Pass 4]
  FS         = mean(feasibility_score) / 100
  CRS        = 0.40 × distinct_shot_types/11
               + 0.30 × distinct_camera_movements/16
               + 0.30 × (max_beat_index − min_beat_index)
  CA         = 1 − violations/max(multi_shot_scenes, 1)
  CRA        = 1 − hard_conflicts_resolved/max(rules_evaluated, 1)
  OEQ / OSCS = 0.25·VCS + 0.20·FS + 0.20·CRS + 0.15·CA + 0.10·CRA + 0.10·RQS
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Netflix broadcast targets
# ---------------------------------------------------------------------------
NETFLIX_TARGET_REFERENCE_QUALITY: float = 0.75
NETFLIX_TARGET_VISUAL_CONSISTENCY: float = 0.85
NETFLIX_TARGET_FEASIBILITY: float = 0.72
NETFLIX_TARGET_CINEMATIC_RICHNESS: float = 0.55
NETFLIX_TARGET_CONTINUITY: float = 0.80
NETFLIX_TARGET_CONFLICT_RESOLUTION: float = 0.92
NETFLIX_TARGET_OVERALL_COHERENCE: float = 0.78


class ShotMetrics(BaseModel):
    """Per-shot granular quality data."""

    shot_id: str
    reference_quality_score: float = Field(ge=0.0, le=1.0)
    feasibility_normalized: float = Field(ge=0.0, le=1.0)


class EpisodeMetrics(BaseModel):
    """Per-episode quality metrics — all values in [0.0, 1.0]."""

    episode_id: str
    shot_count: int
    total_duration_sec: int

    reference_quality_score: float = Field(ge=0.0, le=1.0)
    visual_consistency_score: float = Field(ge=0.0, le=1.0)
    feasibility_score: float = Field(ge=0.0, le=1.0)
    cinematic_richness_score: float = Field(ge=0.0, le=1.0)
    continuity_accuracy: float = Field(ge=0.0, le=1.0)
    conflict_resolution_accuracy: float = Field(ge=0.0, le=1.0)
    overall_episode_quality: float = Field(ge=0.0, le=1.0)

    shot_metrics: list[ShotMetrics] = Field(default_factory=list)

    def passes_broadcast_gate(self) -> bool:
        """Return True when all metrics meet Netflix broadcast targets."""
        return (
            self.reference_quality_score >= NETFLIX_TARGET_REFERENCE_QUALITY
            and self.visual_consistency_score >= NETFLIX_TARGET_VISUAL_CONSISTENCY
            and self.feasibility_score >= NETFLIX_TARGET_FEASIBILITY
            and self.cinematic_richness_score >= NETFLIX_TARGET_CINEMATIC_RICHNESS
            and self.continuity_accuracy >= NETFLIX_TARGET_CONTINUITY
            and self.conflict_resolution_accuracy >= NETFLIX_TARGET_CONFLICT_RESOLUTION
        )


class SeasonMetrics(BaseModel):
    """
    Aggregate quality metrics across all episodes of a season.

    Aggregation rules
    -----------------
    visual_consistency_score  — shot-count weighted mean
    continuity_accuracy       — shot-count weighted mean
    all other metrics         — unweighted mean

    overall_season_coherence_score (OSCS):
        = 0.25 × VCS + 0.20 × FS + 0.20 × CRS + 0.15 × CA + 0.10 × CRA + 0.10 × RQS
    Netflix target: OSCS ≥ 0.78
    """

    season_id: str
    episode_count: int

    reference_quality_score: float = Field(ge=0.0, le=1.0)
    visual_consistency_score: float = Field(ge=0.0, le=1.0)
    feasibility_score: float = Field(ge=0.0, le=1.0)
    cinematic_richness_score: float = Field(ge=0.0, le=1.0)
    continuity_accuracy: float = Field(ge=0.0, le=1.0)
    conflict_resolution_accuracy: float = Field(ge=0.0, le=1.0)
    overall_season_coherence_score: float = Field(ge=0.0, le=1.0)

    per_episode: list[EpisodeMetrics] = Field(default_factory=list)

    def passes_broadcast_gate(self) -> bool:
        """Return True when OSCS meets Netflix broadcast target."""
        return self.overall_season_coherence_score >= NETFLIX_TARGET_OVERALL_COHERENCE
