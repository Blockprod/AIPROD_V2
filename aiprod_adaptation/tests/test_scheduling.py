"""
pytest test suite — EpisodeScheduler + RunMetrics (SO-04, SO-08)
"""

from __future__ import annotations

from aiprod_adaptation.core.engine import run_pipeline
from aiprod_adaptation.core.run_metrics import RunMetrics
from aiprod_adaptation.core.scheduling.episode_scheduler import EpisodeScheduler, SchedulerResult
from aiprod_adaptation.image_gen.image_adapter import NullImageAdapter
from aiprod_adaptation.post_prod.audio_adapter import NullAudioAdapter
from aiprod_adaptation.video_gen.video_adapter import NullVideoAdapter

_NOVEL = (
    "Alice walked into the old library and picked up a dusty book. "
    "Later, in the garden, she read quietly while birds sang above."
)


def _output():  # type: ignore[return]
    return run_pipeline(_NOVEL, "Scheduler Test")


def _scheduler() -> EpisodeScheduler:
    return EpisodeScheduler(
        image_adapter=NullImageAdapter(),
        video_adapter=NullVideoAdapter(),
        audio_adapter=NullAudioAdapter(),
        base_seed=0,
    )


class TestEpisodeScheduler:
    def test_scheduler_run_returns_scheduler_result(self) -> None:
        result = _scheduler().run(_output())
        assert isinstance(result, SchedulerResult)

    def test_scheduler_storyboard_frames_count_matches_shots(self) -> None:
        output = _output()
        result = _scheduler().run(output)
        total_shots = sum(len(ep.shots) for ep in output.episodes)
        assert len(result.storyboard.frames) == total_shots

    def test_scheduler_video_clips_count_matches_frames(self) -> None:
        result = _scheduler().run(_output())
        assert len(result.video.clips) == len(result.storyboard.frames)

    def test_scheduler_production_timeline_count_matches_clips(self) -> None:
        result = _scheduler().run(_output())
        assert len(result.production.timeline) == len(result.video.clips)

    def test_scheduler_result_image_urls_propagate_to_video(self) -> None:
        result = _scheduler().run(_output())
        for clip in result.video.clips:
            assert clip.video_url.startswith("null://")

    def test_scheduler_result_has_metrics(self) -> None:
        result = _scheduler().run(_output())
        assert isinstance(result.metrics, RunMetrics)


class TestRunMetrics:
    def test_run_metrics_success_rate_all_generated(self) -> None:
        m = RunMetrics(shots_requested=10, shots_generated=10)
        assert m.success_rate == 1.0

    def test_run_metrics_success_rate_partial_failure(self) -> None:
        m = RunMetrics(shots_requested=10, shots_generated=7)
        assert abs(m.success_rate - 0.7) < 1e-9

    def test_run_metrics_success_rate_zero_requested(self) -> None:
        m = RunMetrics()
        assert m.success_rate == 1.0

    def test_run_metrics_average_latency(self) -> None:
        m = RunMetrics(shots_generated=4, total_latency_ms=400)
        assert m.average_latency_ms == 100.0

    def test_run_metrics_average_latency_zero_generated(self) -> None:
        m = RunMetrics(total_latency_ms=100)
        assert m.average_latency_ms == 0.0

    def test_scheduler_metrics_shots_requested_matches_total(self) -> None:
        output = _output()
        total_shots = sum(len(ep.shots) for ep in output.episodes)
        result = _scheduler().run(output)
        assert result.metrics.shots_requested == total_shots

    def test_scheduler_metrics_shots_generated_matches_generated(self) -> None:
        result = _scheduler().run(_output())
        assert result.metrics.shots_generated == result.storyboard.generated
