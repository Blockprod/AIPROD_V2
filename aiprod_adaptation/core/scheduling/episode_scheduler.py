from __future__ import annotations

from dataclasses import dataclass

from aiprod_adaptation.core.run_metrics import RunMetrics
from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass
from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import StoryboardOutput
from aiprod_adaptation.image_gen.storyboard import DEFAULT_STYLE_TOKEN, StoryboardGenerator
from aiprod_adaptation.models.schema import AIPRODOutput
from aiprod_adaptation.post_prod.audio_adapter import AudioAdapter
from aiprod_adaptation.post_prod.audio_request import ProductionOutput
from aiprod_adaptation.post_prod.audio_synchronizer import AudioSynchronizer
from aiprod_adaptation.video_gen.video_adapter import VideoAdapter
from aiprod_adaptation.video_gen.video_request import VideoOutput
from aiprod_adaptation.video_gen.video_sequencer import VideoSequencer


@dataclass
class SchedulerResult:
    storyboard: StoryboardOutput
    video: VideoOutput
    production: ProductionOutput
    metrics: RunMetrics


class EpisodeScheduler:
    def __init__(
        self,
        image_adapter: ImageAdapter,
        video_adapter: VideoAdapter,
        audio_adapter: AudioAdapter,
        base_seed: int = 42,
        style_token: str = DEFAULT_STYLE_TOKEN,
    ) -> None:
        self._image_adapter = image_adapter
        self._video_adapter = video_adapter
        self._audio_adapter = audio_adapter
        self._base_seed = base_seed
        self._style_token = style_token

    def run(self, output: AIPRODOutput) -> SchedulerResult:
        metrics = RunMetrics()

        prepass = CharacterPrepass(
            adapter=self._image_adapter,
            base_seed=self._base_seed,
            style_token=self._style_token,
        )
        prepass_result = prepass.run(output)

        storyboard = StoryboardGenerator(
            adapter=self._image_adapter,
            base_seed=self._base_seed,
            style_token=self._style_token,
            prepass_registry=prepass_result.registry,
        ).generate(output)
        metrics.shots_requested += storyboard.total_shots
        metrics.shots_generated += storyboard.generated
        metrics.shots_failed += storyboard.total_shots - storyboard.generated
        metrics.image_latency_ms += sum(f.latency_ms for f in storyboard.frames)
        metrics.total_latency_ms += metrics.image_latency_ms
        metrics.cost.image_api_calls += storyboard.generated

        video = VideoSequencer(
            adapter=self._video_adapter,
            base_seed=self._base_seed,
        ).generate(storyboard, output)
        metrics.video_latency_ms += sum(c.latency_ms for c in video.clips)
        metrics.total_latency_ms += metrics.video_latency_ms
        metrics.cost.video_api_calls += len(video.clips)

        _audio_results, production = AudioSynchronizer(
            adapter=self._audio_adapter,
        ).generate(video, output)
        metrics.audio_latency_ms += sum(c.latency_ms for c in production.timeline)
        metrics.total_latency_ms += metrics.audio_latency_ms
        metrics.cost.audio_api_calls += len(production.timeline)

        return SchedulerResult(
            storyboard=storyboard,
            video=video,
            production=production,
            metrics=metrics,
        )
