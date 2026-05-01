from __future__ import annotations

from dataclasses import dataclass

from aiprod_adaptation.core.run_metrics import RunMetrics
from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass
from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import StoryboardOutput
from aiprod_adaptation.image_gen.reference_pack import ReferencePack
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
        reference_pack: ReferencePack | None = None,
        adapter_overrides: dict[str, ImageAdapter] | None = None,
        budget_cap_usd: float | None = None,
        remove_background: bool = False,
    ) -> None:
        self._image_adapter = image_adapter
        self._video_adapter = video_adapter
        self._audio_adapter = audio_adapter
        self._base_seed = base_seed
        self._style_token = style_token
        self._reference_pack = reference_pack
        self._adapter_overrides: dict[str, ImageAdapter] = adapter_overrides or {}
        self._budget_cap_usd: float | None = budget_cap_usd
        self._remove_background = remove_background

    def run(self, output: AIPRODOutput) -> SchedulerResult:
        metrics = RunMetrics()

        prepass = CharacterPrepass(
            adapter=self._image_adapter,
            sheet_registry=(
                self._reference_pack.to_character_sheet_registry(base_seed=self._base_seed)
                if self._reference_pack is not None
                else None
            ),
            base_seed=self._base_seed,
            style_token=self._style_token,
            remove_background=self._remove_background,
        )
        prepass_result = prepass.run(output)
        metrics.cost.image_api_calls += prepass_result.generated
        metrics.cost.image_cost_usd += prepass_result.cost_usd

        storyboard = StoryboardGenerator(
            adapter=self._image_adapter,
            base_seed=self._base_seed,
            style_token=self._style_token,
            prepass_registry=prepass_result.registry,
            reference_pack=self._reference_pack,
            adapter_overrides=self._adapter_overrides or None,
            budget_cap_usd=self._budget_cap_usd,
        ).generate(output)
        metrics.shots_requested += storyboard.total_shots
        metrics.shots_generated += storyboard.generated
        metrics.shots_failed += storyboard.total_shots - storyboard.generated
        metrics.image_latency_ms += sum(f.latency_ms for f in storyboard.frames)
        metrics.total_latency_ms += metrics.image_latency_ms
        metrics.cost.image_api_calls += storyboard.generated
        metrics.cost.image_cost_usd += sum(frame.cost_usd for frame in storyboard.frames)

        video = VideoSequencer(
            adapter=self._video_adapter,
            base_seed=self._base_seed,
        ).generate(storyboard, output)
        metrics.video_latency_ms += sum(c.latency_ms for c in video.clips)
        metrics.total_latency_ms += metrics.video_latency_ms
        metrics.cost.video_api_calls += len(video.clips)
        metrics.cost.video_cost_usd += sum(clip.cost_usd for clip in video.clips)

        audio_results, production = AudioSynchronizer(
            adapter=self._audio_adapter,
        ).generate(video, output)
        metrics.audio_latency_ms += sum(c.latency_ms for c in production.timeline)
        metrics.total_latency_ms += metrics.audio_latency_ms
        metrics.cost.audio_api_calls += len(production.timeline)
        metrics.cost.audio_cost_usd += sum(result.cost_usd for result in audio_results)

        return SchedulerResult(
            storyboard=storyboard,
            video=video,
            production=production,
            metrics=metrics,
        )
