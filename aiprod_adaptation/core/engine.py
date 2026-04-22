from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import structlog

from aiprod_adaptation.models.schema import AIPRODOutput

if TYPE_CHECKING:
    from aiprod_adaptation.core.adaptation.llm_adapter import LLMAdapter
    from aiprod_adaptation.core.production_budget import ProductionBudget
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


def _apply_continuity_enrichment(
    output: AIPRODOutput,
    character_descriptions: dict[str, str],
) -> AIPRODOutput:
    from aiprod_adaptation.core.continuity.character_registry import CharacterRegistry
    from aiprod_adaptation.core.continuity.emotion_arc import EmotionArcTracker
    from aiprod_adaptation.core.continuity.prompt_enricher import PromptEnricher

    _cr = CharacterRegistry()
    registry = _cr.build(output)
    registry = _cr.enrich_from_text(registry, character_descriptions)
    arc_states = EmotionArcTracker().track(output)
    return PromptEnricher().enrich(output, registry, arc_states)


def run_pipeline(
    text: str,
    title: str,
    episode_id: str = "EP01",
    llm: LLMAdapter | None = None,
    character_descriptions: dict[str, str] | None = None,
    budget: ProductionBudget | None = None,
) -> AIPRODOutput:
    from aiprod_adaptation.core.adaptation.classifier import InputClassifier
    from aiprod_adaptation.core.adaptation.llm_adapter import NullLLMAdapter
    from aiprod_adaptation.core.adaptation.script_parser import ScriptParser
    from aiprod_adaptation.core.adaptation.story_extractor import StoryExtractor
    from aiprod_adaptation.core.adaptation.story_validator import StoryValidator
    from aiprod_adaptation.core.pass1_segment import segment
    from aiprod_adaptation.core.pass2_visual import visual_rewrite
    from aiprod_adaptation.core.pass3_shots import simplify_shots
    from aiprod_adaptation.core.pass4_compile import compile_episode
    from aiprod_adaptation.core.production_budget import ProductionBudget

    logger.info("pipeline_start", input_length=len(text), title=title)

    effective_llm = llm if llm is not None else NullLLMAdapter()
    _budget = budget if budget is not None else ProductionBudget.for_short()
    input_type = InputClassifier().classify(text)

    if input_type == "script":
        logger.debug("pass1_start", path="script")
        scenes_pass2 = ScriptParser().parse(text)
        logger.info("pass1_complete", scene_count=len(scenes_pass2), path="script")
    else:
        logger.debug("pass1_start", path="novel")
        scenes_llm = StoryExtractor().extract_all(effective_llm, text, _budget)
        if scenes_llm:
            scenes_pass2 = scenes_llm
            logger.info("pass1_complete", scene_count=len(scenes_pass2), path="novel_llm")
        else:
            # Fallback: rule-based pipeline (NullLLMAdapter path / CI)
            scenes_pass1 = segment(text)
            logger.info("pass1_complete", scene_count=len(scenes_pass1), path="novel_rules")
            logger.debug("pass2_start")
            scenes_pass2 = visual_rewrite(scenes_pass1)
            logger.info("pass2_complete", scene_count=len(scenes_pass2))

    scenes_pass2 = StoryValidator().validate_all(scenes_pass2, threshold=0.5)
    if not scenes_pass2:
        raise ValueError("PASS 2: StoryValidator produced no filmable scenes after validation.")
    logger.info("story_validator_complete", valid_scene_count=len(scenes_pass2))

    logger.debug("pass3_start")
    shots_pass3 = simplify_shots(scenes_pass2)
    logger.info("pass3_complete", shot_count=len(shots_pass3))

    logger.debug("pass4_start")
    output = compile_episode(scenes_pass2, shots_pass3, title, episode_id)
    logger.info("pipeline_complete", episode_count=len(output.episodes))

    if character_descriptions:
        output = _apply_continuity_enrichment(output, character_descriptions)
        logger.info("continuity_applied", characters=len(character_descriptions))

    return output


def run_pipeline_with_images(
    text: str,
    title: str,
    episode_id: str = "EP01",
    llm: LLMAdapter | None = None,
    character_descriptions: dict[str, str] | None = None,
    image_adapter: ImageAdapter | None = None,
    image_base_seed: int | None = None,
    budget: ProductionBudget | None = None,
) -> tuple[AIPRODOutput, StoryboardOutput | None]:
    output = run_pipeline(text, title, episode_id, llm, character_descriptions, budget)
    storyboard: StoryboardOutput | None = None
    if image_adapter is not None:
        from aiprod_adaptation.image_gen.storyboard import StoryboardGenerator
        storyboard = StoryboardGenerator(
            adapter=image_adapter,
            base_seed=image_base_seed,
        ).generate(output)
        logger.info(
            "storyboard_complete", generated=storyboard.generated, total=storyboard.total_shots
        )
        for frame in storyboard.frames:
            if frame.image_url.startswith("error://"):
                logger.warning(
                    "storyboard_frame_failed", shot_id=frame.shot_id, url=frame.image_url
                )
    return output, storyboard


def run_pipeline_with_video(
    text: str,
    title: str,
    episode_id: str = "EP01",
    llm: LLMAdapter | None = None,
    character_descriptions: dict[str, str] | None = None,
    image_adapter: ImageAdapter | None = None,
    image_base_seed: int | None = None,
    video_adapter: VideoAdapter | None = None,
    budget: ProductionBudget | None = None,
) -> tuple[AIPRODOutput, StoryboardOutput | None, VideoOutput | None]:
    output, storyboard = run_pipeline_with_images(
        text, title, episode_id, llm, character_descriptions,
        image_adapter, image_base_seed, budget,
    )
    video: VideoOutput | None = None
    if video_adapter is not None and storyboard is not None:
        from aiprod_adaptation.video_gen.video_sequencer import VideoSequencer
        video = VideoSequencer(adapter=video_adapter).generate(storyboard, output)
        logger.info("video_complete", generated=video.generated, total=video.total_shots)
    return output, storyboard, video


def run_pipeline_full(
    text: str,
    title: str,
    episode_id: str = "EP01",
    llm: LLMAdapter | None = None,
    character_descriptions: dict[str, str] | None = None,
    image_adapter: ImageAdapter | None = None,
    image_base_seed: int | None = None,
    video_adapter: VideoAdapter | None = None,
    audio_adapter: AudioAdapter | None = None,
    budget: ProductionBudget | None = None,
) -> tuple[AIPRODOutput, StoryboardOutput | None, VideoOutput | None, ProductionOutput | None]:
    output, storyboard, video = run_pipeline_with_video(
        text, title, episode_id, llm, character_descriptions,
        image_adapter, image_base_seed, video_adapter, budget,
    )
    production: ProductionOutput | None = None
    if audio_adapter is not None and video is not None:
        from aiprod_adaptation.post_prod.audio_synchronizer import AudioSynchronizer
        _, production = AudioSynchronizer(adapter=audio_adapter).generate(video, output)
        logger.info("production_complete", total_duration_sec=production.total_duration_sec)
    return output, storyboard, video, production
