"""
MetricsEngine — deterministic computation of all quality metrics.

No external calls, no ML models, fully reproducible for any AIPRODOutput.

Usage
-----
    from aiprod_adaptation.core.metrics import MetricsEngine
    engine = MetricsEngine()
    ep_metrics = engine.compute_episode(output)
    season_metrics = engine.compute_season([output_ep01, output_ep02, ...])
"""

from __future__ import annotations

from aiprod_adaptation.core.metrics.models import (
    EpisodeMetrics,
    SeasonMetrics,
    ShotMetrics,
)
from aiprod_adaptation.models.schema import AIPRODOutput, Episode, Shot

# Diversity denominators — fixed by schema constants (schema.py v3.1)
_N_SHOT_TYPES: int = 11   # len(_VALID_SHOT_TYPES)
_N_MOVEMENTS: int = 16    # len(_VALID_CAMERA_MOVEMENTS)

_ESTABLISHING_TYPES: frozenset[str] = frozenset({"wide", "extreme_wide"})
_CLOSE_TYPES: frozenset[str] = frozenset({"close_up", "extreme_close_up"})


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


class MetricsEngine:
    """Stateless engine that computes all quality metrics deterministically."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_episode(self, output: AIPRODOutput) -> EpisodeMetrics:
        """Compute EpisodeMetrics from the first episode in *output*."""
        if not output.episodes:
            return self._empty_episode_metrics("UNKNOWN")
        return self._compute(output.episodes[0])

    def compute_season(
        self,
        outputs: list[AIPRODOutput],
        season_id: str = "S01",
    ) -> SeasonMetrics:
        """Compute SeasonMetrics by aggregating one AIPRODOutput per episode."""
        episode_metrics = [self.compute_episode(o) for o in outputs]
        return self._aggregate(season_id, episode_metrics)

    # ------------------------------------------------------------------
    # Per-episode computation
    # ------------------------------------------------------------------

    def _compute(self, ep: Episode) -> EpisodeMetrics:
        shots = ep.shots
        if not shots:
            return self._empty_episode_metrics(ep.episode_id)

        # Per-shot metrics
        shot_metrics_list: list[ShotMetrics] = []
        rqs_list: list[float] = []
        for shot in shots:
            rqs = _clamp(shot.reference_anchor_strength * (shot.feasibility_score / 100.0))
            shot_metrics_list.append(
                ShotMetrics(
                    shot_id=shot.shot_id,
                    reference_quality_score=round(rqs, 4),
                    feasibility_normalized=round(shot.feasibility_score / 100.0, 4),
                )
            )
            rqs_list.append(rqs)

        # RQS — duration-weighted mean
        total_duration = sum(s.duration_sec for s in shots)
        if total_duration > 0:
            rqs_ep = sum(r * s.duration_sec for r, s in zip(rqs_list, shots)) / total_duration
        else:
            rqs_ep = sum(rqs_list) / len(rqs_list)

        # VCS from ConsistencyReport
        vcs = float(ep.consistency_report.consistency_score) if ep.consistency_report else 0.5
        vcs = _clamp(vcs)

        # Feasibility — mean / 100
        fscore = _clamp(sum(s.feasibility_score for s in shots) / (len(shots) * 100.0))

        # Cinematic richness
        crs = self._cinematic_richness(shots)

        # Continuity accuracy
        ca = self._continuity_accuracy(ep)

        # Conflict resolution accuracy
        cra = self._conflict_resolution_accuracy(ep)

        # Overall episode quality
        oeq = _clamp(
            0.25 * vcs
            + 0.20 * fscore
            + 0.20 * crs
            + 0.15 * ca
            + 0.10 * cra
            + 0.10 * rqs_ep
        )

        return EpisodeMetrics(
            episode_id=ep.episode_id,
            shot_count=len(shots),
            total_duration_sec=total_duration,
            reference_quality_score=round(_clamp(rqs_ep), 4),
            visual_consistency_score=round(vcs, 4),
            feasibility_score=round(fscore, 4),
            cinematic_richness_score=round(crs, 4),
            continuity_accuracy=round(ca, 4),
            conflict_resolution_accuracy=round(cra, 4),
            overall_episode_quality=round(oeq, 4),
            shot_metrics=shot_metrics_list,
        )

    # ------------------------------------------------------------------
    # Individual metric computations
    # ------------------------------------------------------------------

    def _cinematic_richness(self, shots: list[Shot]) -> float:
        if not shots:
            return 0.0
        shot_type_div = len({s.shot_type for s in shots}) / _N_SHOT_TYPES
        movement_div = len({s.camera_movement for s in shots}) / _N_MOVEMENTS
        beat_indices: list[float] = [
            float(v)
            for s in shots
            if (v := s.metadata.get("emotional_beat_index")) is not None
        ]
        arc_range = (
            _clamp(max(beat_indices) - min(beat_indices))
            if len(beat_indices) >= 2
            else 0.0
        )
        return _clamp(0.40 * shot_type_div + 0.30 * movement_div + 0.30 * arc_range)

    def _continuity_accuracy(self, ep: Episode) -> float:
        shots = ep.shots
        scenes = ep.scenes
        if not scenes:
            return 1.0

        # Group shots by scene preserving insertion order
        scene_shots: dict[str, list[Shot]] = {}
        for shot in shots:
            scene_shots.setdefault(shot.scene_id, []).append(shot)

        violations = 0
        n_multi_scenes = 0
        for scene in scenes:
            sc_shots = scene_shots.get(scene.scene_id, [])
            if len(sc_shots) <= 1:
                continue
            n_multi_scenes += 1
            has_establishing = sc_shots[0].shot_type in _ESTABLISHING_TYPES
            has_close_ups = any(s.shot_type in _CLOSE_TYPES for s in sc_shots)
            if has_close_ups and not has_establishing:
                violations += 1

        if n_multi_scenes == 0:
            return 1.0
        return _clamp(1.0 - violations / n_multi_scenes)

    def _conflict_resolution_accuracy(self, ep: Episode) -> float:
        rer = ep.rule_engine_report
        if rer is None or rer.rules_evaluated == 0:
            return 1.0
        return _clamp(1.0 - rer.hard_conflicts_resolved / max(rer.rules_evaluated, 1))

    # ------------------------------------------------------------------
    # Season aggregation
    # ------------------------------------------------------------------

    def _aggregate(self, season_id: str, eps: list[EpisodeMetrics]) -> SeasonMetrics:
        if not eps:
            return SeasonMetrics(
                season_id=season_id,
                episode_count=0,
                reference_quality_score=0.0,
                visual_consistency_score=0.0,
                feasibility_score=0.0,
                cinematic_richness_score=0.0,
                continuity_accuracy=0.0,
                conflict_resolution_accuracy=0.0,
                overall_season_coherence_score=0.0,
            )

        n = len(eps)
        total_shots = sum(e.shot_count for e in eps)

        # Shot-count weighted
        if total_shots > 0:
            vcs_agg = sum(e.visual_consistency_score * e.shot_count for e in eps) / total_shots
            ca_agg = sum(e.continuity_accuracy * e.shot_count for e in eps) / total_shots
        else:
            vcs_agg = sum(e.visual_consistency_score for e in eps) / n
            ca_agg = sum(e.continuity_accuracy for e in eps) / n

        # Unweighted
        rqs_agg = sum(e.reference_quality_score for e in eps) / n
        fs_agg = sum(e.feasibility_score for e in eps) / n
        crs_agg = sum(e.cinematic_richness_score for e in eps) / n
        cra_agg = sum(e.conflict_resolution_accuracy for e in eps) / n

        oscs = _clamp(
            0.25 * vcs_agg
            + 0.20 * fs_agg
            + 0.20 * crs_agg
            + 0.15 * ca_agg
            + 0.10 * cra_agg
            + 0.10 * rqs_agg
        )

        return SeasonMetrics(
            season_id=season_id,
            episode_count=n,
            reference_quality_score=round(rqs_agg, 4),
            visual_consistency_score=round(vcs_agg, 4),
            feasibility_score=round(fs_agg, 4),
            cinematic_richness_score=round(crs_agg, 4),
            continuity_accuracy=round(ca_agg, 4),
            conflict_resolution_accuracy=round(cra_agg, 4),
            overall_season_coherence_score=round(oscs, 4),
            per_episode=eps,
        )

    @staticmethod
    def _empty_episode_metrics(episode_id: str) -> EpisodeMetrics:
        return EpisodeMetrics(
            episode_id=episode_id,
            shot_count=0,
            total_duration_sec=0,
            reference_quality_score=0.0,
            visual_consistency_score=0.0,
            feasibility_score=0.0,
            cinematic_richness_score=0.0,
            continuity_accuracy=1.0,
            conflict_resolution_accuracy=1.0,
            overall_episode_quality=0.0,
        )
