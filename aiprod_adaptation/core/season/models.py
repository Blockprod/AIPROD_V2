"""
season/models.py — Lightweight dataclasses for multi-episode state.

These are NOT Pydantic models to avoid heavy overhead during accumulation;
the Pydantic summary (SeasonCoherenceMetrics in schema.py) is only materialised
when SeasonCoherenceTracker.compute_metrics() is called.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EpisodeCoherenceSummary:
    """
    Per-episode summary extracted from an AIPRODOutput.

    Populated by SeasonCoherenceTracker.add_episode().

    Fields
    ------
    episode_id              : e.g. "EP01"
    shot_count              : number of shots in the episode
    mean_feasibility_score  : average feasibility_score across all shots
    consistency_score       : from Episode.consistency_report.consistency_score (or 1.0)
    hard_conflicts_resolved : from Episode.rule_engine_report.hard_conflicts_resolved (or 0)
    soft_conflicts_annotated: from Episode.rule_engine_report.soft_conflicts_annotated (or 0)
    dominant_palette_hex    : top hex code(s) from visual_bible_summary (may be empty)
    """
    episode_id: str
    shot_count: int
    mean_feasibility_score: float
    consistency_score: float
    hard_conflicts_resolved: int
    soft_conflicts_annotated: int
    dominant_palette_hex: list[str] = field(default_factory=list)


@dataclass
class SeasonState:
    """
    Accumulated state across all episodes added to a SeasonCoherenceTracker.

    summaries  : one EpisodeCoherenceSummary per episode (in add order)
    season_id  : set on first call to add_episode or via constructor
    series_title: set from visual_bible_summary["series_title"] when available
    """
    summaries: list[EpisodeCoherenceSummary] = field(default_factory=list)
    season_id: str = "S01"
    series_title: str = ""
