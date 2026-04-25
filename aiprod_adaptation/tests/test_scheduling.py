"""
pytest test suite — EpisodeScheduler + RunMetrics (SO-04, SO-08)
"""

from __future__ import annotations

import pytest

from aiprod_adaptation.core.engine import run_pipeline
from aiprod_adaptation.core.run_metrics import RunMetrics
from aiprod_adaptation.core.scheduling.episode_scheduler import EpisodeScheduler, SchedulerResult
from aiprod_adaptation.image_gen.image_adapter import NullImageAdapter
from aiprod_adaptation.models.schema import AIPRODOutput
from aiprod_adaptation.post_prod.audio_adapter import NullAudioAdapter
from aiprod_adaptation.video_gen.video_adapter import NullVideoAdapter

_NOVEL = (
    "Alice walked into the old library and picked up a dusty book. "
    "Later, in the garden, she read quietly while birds sang above."
)


def _output() -> AIPRODOutput:
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


# ---------------------------------------------------------------------------
# PC-06 — Audio latency tracking
# ---------------------------------------------------------------------------

class TestAudioLatency:
    def test_timeline_clip_has_latency_ms_field(self) -> None:
        from aiprod_adaptation.post_prod.audio_request import TimelineClip
        clip = TimelineClip(
            shot_id="S1", scene_id="SC1", video_url="null://v.mp4",
            audio_url="null://a.mp3", duration_sec=3, start_sec=0,
        )
        assert clip.latency_ms == 0

    def test_audio_synchronizer_populates_latency_ms(self) -> None:
        from aiprod_adaptation.post_prod.audio_synchronizer import AudioSynchronizer
        output = _output()
        from aiprod_adaptation.image_gen.storyboard import StoryboardGenerator
        from aiprod_adaptation.video_gen.video_sequencer import VideoSequencer
        sb = StoryboardGenerator(adapter=NullImageAdapter(), base_seed=0).generate(output)
        video = VideoSequencer(adapter=NullVideoAdapter(), base_seed=0).generate(sb, output)
        _, production = AudioSynchronizer(adapter=NullAudioAdapter()).generate(video, output)
        for clip in production.timeline:
            assert isinstance(clip.latency_ms, int)

    def test_scheduler_metrics_audio_latency_zero_with_null_adapter(self) -> None:
        result = _scheduler().run(_output())
        assert result.metrics.audio_latency_ms == 0

    def test_scheduler_metrics_total_latency_includes_all_stages(self) -> None:
        result = _scheduler().run(_output())
        expected = (
            result.metrics.image_latency_ms
            + result.metrics.video_latency_ms
            + result.metrics.audio_latency_ms
        )
        assert result.metrics.total_latency_ms == expected


# ---------------------------------------------------------------------------
# PC-07 — CostReport observabilité
# ---------------------------------------------------------------------------

class TestCostReport:
    def test_cost_report_default_values_are_zero(self) -> None:
        from aiprod_adaptation.core.cost_report import CostReport
        report = CostReport()
        assert report.total_cost_usd == 0.0
        assert report.llm_tokens_input == 0
        assert report.image_api_calls == 0

    def test_cost_report_total_cost_sums_all_categories(self) -> None:
        from aiprod_adaptation.core.cost_report import CostReport
        report = CostReport(
            llm_cost_usd=0.01,
            image_cost_usd=0.05,
            video_cost_usd=0.10,
            audio_cost_usd=0.02,
        )
        assert abs(report.total_cost_usd - 0.18) < 1e-9

    def test_cost_report_merge_sums_fields(self) -> None:
        from aiprod_adaptation.core.cost_report import CostReport
        a = CostReport(llm_tokens_input=100, image_api_calls=3, llm_cost_usd=0.01)
        b = CostReport(llm_tokens_input=200, image_api_calls=1, llm_cost_usd=0.02)
        merged = a.merge(b)
        assert merged.llm_tokens_input == 300
        assert merged.image_api_calls == 4
        assert abs(merged.llm_cost_usd - 0.03) < 1e-9

    def test_run_metrics_has_cost_field(self) -> None:
        from aiprod_adaptation.core.cost_report import CostReport
        result = _scheduler().run(_output())
        assert hasattr(result.metrics, "cost")
        assert isinstance(result.metrics.cost, CostReport)

    def test_cost_report_to_summary_str_format(self) -> None:
        from aiprod_adaptation.core.cost_report import CostReport
        c = CostReport(
            image_api_calls=3, video_api_calls=2, audio_api_calls=5,
            llm_tokens_input=100, llm_tokens_output=50,
        )
        s = c.to_summary_str()
        assert "Image: 3 calls" in s
        assert "Video: 2 calls" in s
        assert "Audio: 5 calls" in s
        assert "Total: $0.0000" in s

    def test_cost_report_merge_with_empty_is_identity(self) -> None:
        from aiprod_adaptation.core.cost_report import CostReport
        c = CostReport(image_api_calls=3, video_api_calls=2, llm_cost_usd=1.5)
        merged = c.merge(CostReport())
        assert merged.image_api_calls == 3
        assert merged.video_api_calls == 2
        assert abs(merged.llm_cost_usd - 1.5) < 1e-9

    def test_cost_report_notes_document_runtime_gaps(self) -> None:
        from aiprod_adaptation.core.cost_report import CostReport

        report = CostReport()

        assert (
            (
                "llm_tokens_input, llm_tokens_output, and llm_cost_usd are not populated "
                "by scheduler runtime."
            )
            in report.notes
        )

    def test_scheduler_metrics_aggregate_adapter_costs(self) -> None:
        from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
        from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult
        from aiprod_adaptation.post_prod.audio_adapter import AudioAdapter
        from aiprod_adaptation.post_prod.audio_request import AudioRequest, AudioResult
        from aiprod_adaptation.video_gen.video_adapter import VideoAdapter
        from aiprod_adaptation.video_gen.video_request import VideoClipResult, VideoRequest

        class CostedImageAdapter(ImageAdapter):
            def generate(self, request: ImageRequest) -> ImageResult:
                return ImageResult(
                    shot_id=request.shot_id,
                    image_url=f"null://storyboard/{request.shot_id}.png",
                    model_used="costed-image",
                    latency_ms=1,
                    cost_usd=0.11,
                )

        class CostedVideoAdapter(VideoAdapter):
            def generate(self, request: VideoRequest) -> VideoClipResult:
                return VideoClipResult(
                    shot_id=request.shot_id,
                    video_url=f"null://video/{request.shot_id}.mp4",
                    duration_sec=request.duration_sec,
                    model_used="costed-video",
                    latency_ms=2,
                    cost_usd=0.22,
                )

        class CostedAudioAdapter(AudioAdapter):
            def generate(self, request: AudioRequest) -> AudioResult:
                return AudioResult(
                    shot_id=request.shot_id,
                    audio_url=f"null://audio/{request.shot_id}.mp3",
                    duration_sec=request.duration_hint_sec,
                    model_used="costed-audio",
                    latency_ms=3,
                    cost_usd=0.33,
                )

        output = _output()
        total_shots = sum(len(ep.shots) for ep in output.episodes)
        scheduler = EpisodeScheduler(
            image_adapter=CostedImageAdapter(),
            video_adapter=CostedVideoAdapter(),
            audio_adapter=CostedAudioAdapter(),
            base_seed=0,
        )

        result = scheduler.run(output)

        assert result.metrics.cost.image_cost_usd == pytest.approx(total_shots * 0.11)
        assert result.metrics.cost.video_cost_usd == pytest.approx(total_shots * 0.22)
        assert result.metrics.cost.audio_cost_usd == pytest.approx(total_shots * 0.33)
        assert result.metrics.cost.total_cost_usd == pytest.approx(total_shots * 0.66)
