from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import structlog

from aiprod_adaptation.models.schema import AIPRODOutput

if TYPE_CHECKING:
    from aiprod_adaptation.core.adaptation.llm_adapter import LLMAdapter
    from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
    from aiprod_adaptation.image_gen.image_request import StoryboardOutput
    from aiprod_adaptation.post_prod.audio_adapter import AudioAdapter
    from aiprod_adaptation.post_prod.audio_request import ProductionOutput
    from aiprod_adaptation.video_gen.video_adapter import VideoAdapter
    from aiprod_adaptation.video_gen.video_request import VideoOutput

structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def run_pipeline(
    text: str,
    title: str,
    episode_id: str = "EP01",
    llm: "LLMAdapter | None" = None,
    character_descriptions: "dict[str, str] | None" = None,
) -> AIPRODOutput:
    from aiprod_adaptation.core.adaptation.classifier import InputClassifier
    from aiprod_adaptation.core.adaptation.llm_adapter import NullLLMAdapter
    from aiprod_adaptation.core.adaptation.normalizer import Normalizer
    from aiprod_adaptation.core.adaptation.novel_pipe import run_novel_pipe
    from aiprod_adaptation.core.adaptation.script_parser import ScriptParser
    from aiprod_adaptation.core.pass1_segment import segment
    from aiprod_adaptation.core.pass2_visual import visual_rewrite
    from aiprod_adaptation.core.pass3_shots import simplify_shots
    from aiprod_adaptation.core.pass4_compile import compile_episode

    logger.info("pipeline_start", input_length=len(text), title=title)

    effective_llm = llm if llm is not None else NullLLMAdapter()
    input_type = InputClassifier().classify(text)

    if input_type == "script":
        logger.debug("pass1_start", path="script")
        scenes_pass2 = ScriptParser().parse(text)
        logger.info("pass1_complete", scene_count=len(scenes_pass2), path="script")
    else:
        logger.debug("pass1_start", path="novel")
        raw_scenes = run_novel_pipe(effective_llm, text)
        if raw_scenes:
            scenes_pass2 = Normalizer().normalize(raw_scenes)
            logger.info("pass1_complete", scene_count=len(scenes_pass2), path="novel_llm")
        else:
            # Fallback: rule-based pipeline (NullLLMAdapter path / CI)
            scenes_pass1 = segment(text)
            logger.info("pass1_complete", scene_count=len(scenes_pass1), path="novel_rules")
            logger.debug("pass2_start")
            scenes_pass2 = visual_rewrite(scenes_pass1)
            logger.info("pass2_complete", scene_count=len(scenes_pass2))

    logger.debug("pass3_start")
    shots_pass3 = simplify_shots(scenes_pass2)
    logger.info("pass3_complete", shot_count=len(shots_pass3))

    logger.debug("pass4_start")
    output = compile_episode(scenes_pass2, shots_pass3, title, episode_id)
    logger.info("pipeline_complete", episode_count=len(output.episodes))

    if character_descriptions:
        from aiprod_adaptation.core.continuity.character_registry import CharacterRegistry
        from aiprod_adaptation.core.continuity.emotion_arc import EmotionArcTracker
        from aiprod_adaptation.core.continuity.prompt_enricher import PromptEnricher

        registry = CharacterRegistry().build(output)
        registry = CharacterRegistry().enrich_from_text(registry, character_descriptions)
        arc_states = EmotionArcTracker().track(output)
        output = PromptEnricher().enrich(output, registry, arc_states)
        logger.info("continuity_applied", characters=len(registry))

    return output


def run_pipeline_with_images(
    text: str,
    title: str,
    episode_id: str = "EP01",
    llm: "LLMAdapter | None" = None,
    character_descriptions: "dict[str, str] | None" = None,
    image_adapter: "ImageAdapter | None" = None,
    image_base_seed: "int | None" = None,
) -> "tuple[AIPRODOutput, StoryboardOutput | None]":
    output = run_pipeline(text, title, episode_id, llm, character_descriptions)
    storyboard: "StoryboardOutput | None" = None
    if image_adapter is not None:
        from aiprod_adaptation.image_gen.storyboard import StoryboardGenerator
        storyboard = StoryboardGenerator(
            adapter=image_adapter,
            base_seed=image_base_seed,
        ).generate(output)
        logger.info("storyboard_complete", generated=storyboard.generated, total=storyboard.total_shots)
    return output, storyboard


def run_pipeline_with_video(
    text: str,
    title: str,
    episode_id: str = "EP01",
    llm: "LLMAdapter | None" = None,
    character_descriptions: "dict[str, str] | None" = None,
    image_adapter: "ImageAdapter | None" = None,
    image_base_seed: "int | None" = None,
    video_adapter: "VideoAdapter | None" = None,
) -> "tuple[AIPRODOutput, StoryboardOutput | None, VideoOutput | None]":
    output, storyboard = run_pipeline_with_images(
        text, title, episode_id, llm, character_descriptions,
        image_adapter, image_base_seed,
    )
    video: "VideoOutput | None" = None
    if video_adapter is not None and storyboard is not None:
        from aiprod_adaptation.video_gen.video_sequencer import VideoSequencer
        video = VideoSequencer(adapter=video_adapter).generate(storyboard, output)
        logger.info("video_complete", generated=video.generated, total=video.total_shots)
    return output, storyboard, video


def run_pipeline_full(
    text: str,
    title: str,
    episode_id: str = "EP01",
    llm: "LLMAdapter | None" = None,
    character_descriptions: "dict[str, str] | None" = None,
    image_adapter: "ImageAdapter | None" = None,
    image_base_seed: "int | None" = None,
    video_adapter: "VideoAdapter | None" = None,
    audio_adapter: "AudioAdapter | None" = None,
) -> "tuple[AIPRODOutput, StoryboardOutput | None, VideoOutput | None, ProductionOutput | None]":
    output, storyboard, video = run_pipeline_with_video(
        text, title, episode_id, llm, character_descriptions,
        image_adapter, image_base_seed, video_adapter,
    )
    production: "ProductionOutput | None" = None
    if audio_adapter is not None and video is not None:
        from aiprod_adaptation.post_prod.audio_synchronizer import AudioSynchronizer
        _, production = AudioSynchronizer(adapter=audio_adapter).generate(video, output)
        logger.info("production_complete", total_duration_sec=production.total_duration_sec)
    return output, storyboard, video, production
