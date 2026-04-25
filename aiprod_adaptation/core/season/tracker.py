"""
season/tracker.py — SeasonCoherenceTracker accumulates episode results
and materialises SeasonCoherenceMetrics (Pydantic, JSON-serialisable).

Usage
-----
    tracker = SeasonCoherenceTracker(season_id="S01")
    tracker.add_episode(output_ep01)
    tracker.add_episode(output_ep02)
    metrics = tracker.compute_metrics()   # → SeasonCoherenceMetrics

Design
------
- Pure accumulation — no side effects on the AIPRODOutput objects.
- All arithmetic is deterministic: same inputs → same metrics.
- Palette drift is flagged when an episode's top palette hex deviates from
  the season-wide majority hex (simple majority vote, no LAB delta).
- `compute_metrics()` can be called multiple times; each call recomputes from
  the accumulated state (idempotent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiprod_adaptation.core.season.models import EpisodeCoherenceSummary, SeasonState

if TYPE_CHECKING:
    from aiprod_adaptation.models.schema import AIPRODOutput, SeasonCoherenceMetrics


class SeasonCoherenceTracker:
    """
    Accumulates AIPRODOutput objects for one season and derives coherence metrics.

    Parameters
    ----------
    season_id : str
        Identifier for the season, e.g. "S01".
    """

    def __init__(self, season_id: str = "S01") -> None:
        self._state = SeasonState(season_id=season_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_episode(self, output: AIPRODOutput) -> None:
        """Append one episode's output to the accumulated state."""
        ep = output.episodes[0] if output.episodes else None
        if ep is None:
            return

        shot_count = len(ep.shots)
        mean_feasibility = (
            sum(s.feasibility_score for s in ep.shots) / shot_count
            if shot_count > 0
            else 0.0
        )
        consistency_score = (
            ep.consistency_report.consistency_score
            if ep.consistency_report is not None
            else 1.0
        )
        hard = soft = 0
        if ep.rule_engine_report is not None:
            hard = ep.rule_engine_report.hard_conflicts_resolved
            soft = ep.rule_engine_report.soft_conflicts_annotated

        # Extract dominant palette hex from visual_bible_summary if present
        palette_hex: list[str] = []
        if output.visual_bible_summary:
            raw_palette = output.visual_bible_summary.get("palette", [])
            if isinstance(raw_palette, list):
                palette_hex = [str(h) for h in raw_palette if isinstance(h, str)]

        summary = EpisodeCoherenceSummary(
            episode_id=ep.episode_id,
            shot_count=shot_count,
            mean_feasibility_score=round(mean_feasibility, 2),
            consistency_score=consistency_score,
            hard_conflicts_resolved=hard,
            soft_conflicts_annotated=soft,
            dominant_palette_hex=palette_hex,
        )
        self._state.summaries.append(summary)

        # Update series_title from the first episode that provides it
        if not self._state.series_title and output.visual_bible_summary:
            self._state.series_title = str(
                output.visual_bible_summary.get("series_title", "")
            )

    def compute_metrics(self) -> SeasonCoherenceMetrics:
        """Return a SeasonCoherenceMetrics Pydantic object from accumulated state."""
        from aiprod_adaptation.models.schema import SeasonCoherenceMetrics

        summaries = self._state.summaries
        episode_count = len(summaries)

        if episode_count == 0:
            return SeasonCoherenceMetrics(
                season_id=self._state.season_id,
                episode_count=0,
                total_shots=0,
                mean_feasibility_score=0.0,
                consistency_score_mean=1.0,
            )

        total_shots = sum(s.shot_count for s in summaries)
        mean_feas = sum(s.mean_feasibility_score for s in summaries) / episode_count
        mean_consistency = sum(s.consistency_score for s in summaries) / episode_count

        # Palette drift: flag episodes whose top hex differs from the global majority
        palette_drift = _detect_palette_drift(summaries)

        rule_conflicts: dict[str, int] = {
            s.episode_id: s.hard_conflicts_resolved + s.soft_conflicts_annotated
            for s in summaries
        }

        return SeasonCoherenceMetrics(
            season_id=self._state.season_id,
            episode_count=episode_count,
            total_shots=total_shots,
            mean_feasibility_score=round(mean_feas, 2),
            consistency_score_mean=round(mean_consistency, 4),
            palette_drift_episodes=palette_drift,
            rule_conflicts_per_episode=rule_conflicts,
        )

    @property
    def state(self) -> SeasonState:
        """Read-only view of the accumulated state."""
        return self._state


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _detect_palette_drift(summaries: list[EpisodeCoherenceSummary]) -> list[str]:
    """
    Identify episodes whose first palette hex differs from the season majority.

    Algorithm
    ---------
    1. Collect all first-hex values across episodes that have palette data.
    2. Find the majority hex (most frequent).
    3. Return episode_ids where the first hex != majority hex.

    If fewer than 2 episodes have palette data, drift is undefined → return [].
    """
    hex_by_episode: dict[str, str] = {
        s.episode_id: s.dominant_palette_hex[0]
        for s in summaries
        if s.dominant_palette_hex
    }
    if len(hex_by_episode) < 2:
        return []

    # Majority vote
    counts: dict[str, int] = {}
    for h in hex_by_episode.values():
        counts[h] = counts.get(h, 0) + 1
    majority_hex = max(counts, key=lambda k: counts[k])

    return [eid for eid, h in sorted(hex_by_episode.items()) if h != majority_hex]
