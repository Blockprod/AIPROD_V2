"""
Season Coherence Report — structured JSON report for a full season.

Includes
--------
  - Season-level quality metrics (all 7 KPIs)
  - Per-episode breakdowns with broadcast gate evaluation
  - Comparison against Netflix targets
  - Actionable recommendations
"""

from __future__ import annotations

import json
from typing import Any

from aiprod_adaptation.core.metrics.models import (
    NETFLIX_TARGET_CINEMATIC_RICHNESS,
    NETFLIX_TARGET_CONFLICT_RESOLUTION,
    NETFLIX_TARGET_CONTINUITY,
    NETFLIX_TARGET_FEASIBILITY,
    NETFLIX_TARGET_OVERALL_COHERENCE,
    NETFLIX_TARGET_REFERENCE_QUALITY,
    NETFLIX_TARGET_VISUAL_CONSISTENCY,
    SeasonMetrics,
)
from aiprod_adaptation.models.schema import AIPRODOutput


def export_season_report(
    outputs: list[AIPRODOutput],
    season_id: str = "S01",
    series_title: str = "",
) -> str:
    """Generate a complete season coherence report as JSON."""
    from aiprod_adaptation.core.metrics.engine import MetricsEngine

    engine = MetricsEngine()
    season_metrics = engine.compute_season(outputs, season_id=season_id)

    ep_rows: list[dict[str, Any]] = []
    for ep_m in season_metrics.per_episode:
        ep_rows.append(
            {
                "episode_id": ep_m.episode_id,
                "shot_count": ep_m.shot_count,
                "total_duration_sec": ep_m.total_duration_sec,
                "metrics": {
                    "reference_quality_score": ep_m.reference_quality_score,
                    "visual_consistency_score": ep_m.visual_consistency_score,
                    "feasibility_score": ep_m.feasibility_score,
                    "cinematic_richness_score": ep_m.cinematic_richness_score,
                    "continuity_accuracy": ep_m.continuity_accuracy,
                    "conflict_resolution_accuracy": ep_m.conflict_resolution_accuracy,
                    "overall_episode_quality": ep_m.overall_episode_quality,
                },
                "broadcast_gate": "PASS" if ep_m.passes_broadcast_gate() else "FAIL",
            }
        )

    recommendations = _build_recommendations(season_metrics)

    report: dict[str, Any] = {
        "report_type": "season_coherence_report",
        "schema_version": "1.0",
        "season_id": season_id,
        "series_title": series_title,
        "episode_count": season_metrics.episode_count,
        "season_metrics": {
            "reference_quality_score": season_metrics.reference_quality_score,
            "visual_consistency_score": season_metrics.visual_consistency_score,
            "feasibility_score": season_metrics.feasibility_score,
            "cinematic_richness_score": season_metrics.cinematic_richness_score,
            "continuity_accuracy": season_metrics.continuity_accuracy,
            "conflict_resolution_accuracy": season_metrics.conflict_resolution_accuracy,
            "overall_season_coherence_score": season_metrics.overall_season_coherence_score,
        },
        "netflix_targets": {
            "reference_quality_score": NETFLIX_TARGET_REFERENCE_QUALITY,
            "visual_consistency_score": NETFLIX_TARGET_VISUAL_CONSISTENCY,
            "feasibility_score": NETFLIX_TARGET_FEASIBILITY,
            "cinematic_richness_score": NETFLIX_TARGET_CINEMATIC_RICHNESS,
            "continuity_accuracy": NETFLIX_TARGET_CONTINUITY,
            "conflict_resolution_accuracy": NETFLIX_TARGET_CONFLICT_RESOLUTION,
            "overall_season_coherence_score": NETFLIX_TARGET_OVERALL_COHERENCE,
        },
        "broadcast_gate": "PASS" if season_metrics.passes_broadcast_gate() else "FAIL",
        "per_episode": ep_rows,
        "recommendations": recommendations,
    }
    return json.dumps(report, indent=2, ensure_ascii=False)


def _build_recommendations(m: SeasonMetrics) -> list[str]:
    recs: list[str] = []
    if m.visual_consistency_score < NETFLIX_TARGET_VISUAL_CONSISTENCY:
        recs.append(
            f"Visual consistency ({m.visual_consistency_score:.2%}) below target "
            f"({NETFLIX_TARGET_VISUAL_CONSISTENCY:.0%}): review color grades and scene tones."
        )
    if m.feasibility_score < NETFLIX_TARGET_FEASIBILITY:
        recs.append(
            f"Feasibility ({m.feasibility_score:.2%}) below target "
            f"({NETFLIX_TARGET_FEASIBILITY:.0%}): reduce complex camera movements."
        )
    if m.cinematic_richness_score < NETFLIX_TARGET_CINEMATIC_RICHNESS:
        recs.append(
            f"Cinematic richness ({m.cinematic_richness_score:.2%}) below target "
            f"({NETFLIX_TARGET_CINEMATIC_RICHNESS:.0%}): increase shot type and movement diversity."
        )
    if m.continuity_accuracy < NETFLIX_TARGET_CONTINUITY:
        recs.append(
            f"Continuity accuracy ({m.continuity_accuracy:.2%}) below target "
            f"({NETFLIX_TARGET_CONTINUITY:.0%}): add establishing shots before close-ups."
        )
    if m.conflict_resolution_accuracy < NETFLIX_TARGET_CONFLICT_RESOLUTION:
        recs.append(
            f"Conflict resolution ({m.conflict_resolution_accuracy:.2%}) below target "
            f"({NETFLIX_TARGET_CONFLICT_RESOLUTION:.0%}): reduce rule violations before compilation."
        )
    if m.reference_quality_score < NETFLIX_TARGET_REFERENCE_QUALITY:
        recs.append(
            f"Reference quality ({m.reference_quality_score:.2%}) below target "
            f"({NETFLIX_TARGET_REFERENCE_QUALITY:.0%}): improve reference image anchoring."
        )
    if not recs:
        recs.append(
            "All metrics meet Netflix broadcast targets. Production is ready for delivery."
        )
    return recs
