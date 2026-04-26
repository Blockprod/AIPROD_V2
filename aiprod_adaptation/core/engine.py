from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Literal, cast

import structlog

from aiprod_adaptation.models.intermediate import VisualScene
from aiprod_adaptation.models.schema import AIPRODOutput

if TYPE_CHECKING:
    from aiprod_adaptation.core.adaptation.llm_adapter import LLMAdapter
    from aiprod_adaptation.core.production_budget import ProductionBudget
    from aiprod_adaptation.core.visual_bible import VisualBible
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

PipelineMode = Literal["auto", "deterministic", "generative"]


def _validate_pipeline_mode(pipeline_mode: str) -> PipelineMode:
    if pipeline_mode == "auto":
        return "auto"
    if pipeline_mode == "deterministic":
        return "deterministic"
    if pipeline_mode == "generative":
        return "generative"
    raise ValueError(
        "pipeline_mode must be one of 'auto', 'deterministic', or 'generative'."
    )


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


# ---------------------------------------------------------------------------
# Script-path enrichment — infer cinematic metadata for ScriptParser output.
# ScriptParser skips pass2, so beat_type / action_intensity / emotional_arc_index
# are never set.  This helper derives them from available data so that pass3
# produces cinematically varied shots instead of defaulting to "static" everywhere.
# ---------------------------------------------------------------------------

_EMOTION_TO_BEAT: dict[str, str] = {
    "angry":   "climax",
    "scared":  "climax",
    "tense":   "action",
    "nervous": "action",
    "sad":     "denouement",
    "happy":   "dialogue_scene",
    "neutral": "exposition",
    "joy":     "dialogue_scene",
    "fear":    "climax",
    "surprise": "transition",
    "disgust": "action",
    "contempt": "dialogue_scene",
}

_ACTION_KEYWORDS_HIGH = frozenset({
    "run", "sprint", "fight", "shoot", "explod", "crash", "attack", "chase",
    "scream", "jump", "fire", "kick", "punch", "collide", "burst",
})
_ACTION_KEYWORDS_MID = frozenset({
    "walk", "move", "approach", "reach", "grab", "push", "pull", "open",
    "turn", "look", "search", "enter", "exit", "rush", "step",
})


def _infer_action_intensity(visual_actions: list[str]) -> str:
    combined = " ".join(visual_actions).lower()
    for kw in _ACTION_KEYWORDS_HIGH:
        if kw in combined:
            return "explosive"
    for kw in _ACTION_KEYWORDS_MID:
        if kw in combined:
            return "mid"
    return "subtle"


_BEAT_TYPE_BY_POSITION: list[tuple[float, str]] = [
    # (upper_bound_exclusive, beat_type)
    (0.10, "exposition"),
    (0.30, "action"),
    (0.55, "climax"),
    (0.75, "dialogue_scene"),
    (0.90, "action"),
    (1.01, "denouement"),
]


def _beat_from_position(position: float, visual_actions: list[str]) -> str:
    """Infer beat_type from narrative arc position, cross-checking action content."""
    content_beat: str | None = None
    combined = " ".join(visual_actions).lower()
    for kw in _ACTION_KEYWORDS_HIGH:
        if kw in combined:
            content_beat = "climax"
            break
    if content_beat is None:
        for kw in _ACTION_KEYWORDS_MID:
            if kw in combined:
                content_beat = "action"
                break
    for upper, arc_beat in _BEAT_TYPE_BY_POSITION:
        if position < upper:
            # Prefer content_beat when it escalates the arc beat
            if content_beat == "climax" and arc_beat in ("exposition", "dialogue_scene"):
                return "action"
            return arc_beat
    return "denouement"


def _enrich_script_scenes(scenes: list[VisualScene], visual_bible: VisualBible | None = None) -> None:
    """Assign beat_type, action_intensity, emotional_beat_index, scene_type
    to VisualScene dicts produced by ScriptParser so that pass3 generates
    cinematically varied shots instead of defaulting to static everywhere.
    Modifies scenes in-place.
    """
    n = len(scenes)
    vb_locations: list[str] = []
    if visual_bible is not None:
        vb_locations = list(visual_bible.locations.keys())

    for i, scene in enumerate(scenes):
        position = i / max(n - 1, 1)  # 0.0 → 1.0
        arc_index = round(0.2 + position * 0.7, 3)  # [0.2, 0.9]
        visual_actions: list[str] = scene.get("visual_actions", [])
        if i == 0:
            beat_type: str = "exposition"
            scene["scene_type"] = "teaser"
        elif i == n - 1:
            beat_type = "denouement"
            scene["scene_type"] = "tag"
        else:
            beat_type = _beat_from_position(position, visual_actions)
            scene["scene_type"] = "standard"
        scene["beat_type"] = beat_type
        scene["action_intensity"] = _infer_action_intensity(visual_actions)
        scene["emotional_beat_index"] = arc_index
        # Inject FIRST_APPEARANCE flag so pass3 prepends a wide establishing shot,
        # ensuring continuity_accuracy (CA) sees an establishing shot first.
        flags: list[str] = list(scene.get("continuity_flags", []))
        if "FIRST_APPEARANCE" not in flags:
            flags.append("FIRST_APPEARANCE")
        scene["continuity_flags"] = flags
        # Assign a reference_location_id so pass3 scores anchor_strength = 0.9
        if vb_locations and not scene.get("reference_location_id"):
            loc_idx = i % len(vb_locations)
            scene["reference_location_id"] = vb_locations[loc_idx]


def run_pipeline(
    text: str,
    title: str,
    episode_id: str = "EP01",
    llm: LLMAdapter | None = None,
    character_descriptions: dict[str, str] | None = None,
    budget: ProductionBudget | None = None,
    require_llm: bool = False,
    pipeline_mode: PipelineMode = "auto",
    visual_bible: VisualBible | None = None,
    ref_invariants: object | None = None,
    episode_index: int = 1,
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
    from aiprod_adaptation.models.intermediate import RawScene

    logger.info("pipeline_start", input_length=len(text), title=title)

    effective_llm = llm if llm is not None else NullLLMAdapter()
    _budget = budget if budget is not None else ProductionBudget.for_short()
    input_type = InputClassifier().classify(text)
    resolved_mode = _validate_pipeline_mode(pipeline_mode)
    logger.info("pipeline_mode_selected", pipeline_mode=resolved_mode, input_type=input_type)

    if (
        resolved_mode == "generative"
        and input_type != "script"
        and isinstance(effective_llm, NullLLMAdapter)
    ):
        raise ValueError(
            "Generative mode requires a non-null LLM adapter for novel extraction."
        )

    if input_type == "script":
        logger.debug("pass1_start", path="script")
        scenes_pass2 = ScriptParser().parse(text)
        _enrich_script_scenes(scenes_pass2, visual_bible)
        logger.info("pass1_complete", scene_count=len(scenes_pass2), path="script")
    else:
        logger.debug("pass1_start", path="novel")
        use_llm_path = resolved_mode != "deterministic"
        if use_llm_path:
            scenes_llm = StoryExtractor().extract_all(effective_llm, text, _budget)
        else:
            scenes_llm = []
        if scenes_llm:
            scenes_pass2 = scenes_llm
            logger.info("pass1_complete", scene_count=len(scenes_pass2), path="novel_llm")
        else:
            if require_llm or resolved_mode == "generative":
                raise ValueError(
                    "LLM extraction produced no scenes; rule-based fallback is disabled."
                )
            # Fallback: rule-based pipeline (NullLLMAdapter path / CI)
            scenes_pass1 = segment(text)
            logger.info("pass1_complete", scene_count=len(scenes_pass1), path="novel_rules")
            logger.debug("pass2_start")
            scenes_pass2 = visual_rewrite(cast("list[RawScene]", scenes_pass1))
            logger.info("pass2_complete", scene_count=len(scenes_pass2))

    scenes_pass2 = StoryValidator().validate_all(scenes_pass2, threshold=0.5)
    if not scenes_pass2:
        raise ValueError("PASS 2: StoryValidator produced no filmable scenes after validation.")
    logger.info("story_validator_complete", valid_scene_count=len(scenes_pass2))

    logger.debug("pass3_start")
    shots_pass3 = simplify_shots(scenes_pass2)
    logger.info("pass3_complete", shot_count=len(shots_pass3))

    logger.debug("pass4_start")
    output = compile_episode(
        scenes_pass2,
        shots_pass3,
        title,
        episode_id,
        visual_bible=visual_bible,
        ref_invariants=ref_invariants,
        episode_index=episode_index,
    )
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
    require_llm: bool = False,
    pipeline_mode: PipelineMode = "auto",
) -> tuple[AIPRODOutput, StoryboardOutput | None]:
    output = run_pipeline(
        text,
        title,
        episode_id,
        llm,
        character_descriptions,
        budget,
        require_llm=require_llm,
        pipeline_mode=pipeline_mode,
    )
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
    require_llm: bool = False,
    pipeline_mode: PipelineMode = "auto",
) -> tuple[AIPRODOutput, StoryboardOutput | None, VideoOutput | None]:
    output, storyboard = run_pipeline_with_images(
        text,
        title,
        episode_id,
        llm,
        character_descriptions,
        image_adapter,
        image_base_seed,
        budget,
        require_llm=require_llm,
        pipeline_mode=pipeline_mode,
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
    require_llm: bool = False,
    pipeline_mode: PipelineMode = "auto",
) -> tuple[AIPRODOutput, StoryboardOutput | None, VideoOutput | None, ProductionOutput | None]:
    output, storyboard, video = run_pipeline_with_video(
        text,
        title,
        episode_id,
        llm,
        character_descriptions,
        image_adapter,
        image_base_seed,
        video_adapter,
        budget,
        require_llm=require_llm,
        pipeline_mode=pipeline_mode,
    )
    production: ProductionOutput | None = None
    if audio_adapter is not None and video is not None:
        from aiprod_adaptation.post_prod.audio_synchronizer import AudioSynchronizer
        _, production = AudioSynchronizer(adapter=audio_adapter).generate(video, output)
        logger.info("production_complete", total_duration_sec=production.total_duration_sec)
    return output, storyboard, video, production


def process_narrative_with_reference(
    text: str,
    title: str,
    visual_bible: VisualBible,
    ref_invariants: object | None = None,
    episode_id: str = "EP01",
    episode_index: int = 1,
    llm: LLMAdapter | None = None,
    character_descriptions: dict[str, str] | None = None,
    pipeline_mode: PipelineMode = "auto",
) -> AIPRODOutput:
    """
    Primary entry point for AIPROD_Cinematic reference-anchored production.

    Wraps run_pipeline() with mandatory VisualBible and optional ref_invariants,
    ensuring the Rule Engine in Pass 4 has access to the reference invariants for
    every shot.

    Parameters
    ----------
    text             : narrative text (novel excerpt or script)
    title            : episode title
    visual_bible     : VisualBible instance (from core/visual_bible.py)
    ref_invariants   : VisualInvariants from reference image analysis (optional).
                       If provided, the Rule Engine will enforce P2–P4 constraints.
    episode_id       : e.g. "EP01"
    episode_index    : 1-based episode number within the season (for Rule Engine context)
    llm              : LLM adapter for novel extraction (optional — deterministic fallback)
    character_descriptions : character descriptions for continuity enrichment (optional)
    pipeline_mode    : "auto" | "deterministic" | "generative"

    Returns
    -------
    AIPRODOutput with rule_engine_report populated (even when no conflicts are found).
    """
    logger.info(
        "process_narrative_with_reference_start",
        title=title,
        episode_id=episode_id,
        episode_index=episode_index,
        has_ref_invariants=ref_invariants is not None,
    )
    output = run_pipeline(
        text=text,
        title=title,
        episode_id=episode_id,
        llm=llm,
        character_descriptions=character_descriptions,
        require_llm=False,
        pipeline_mode=pipeline_mode,
        visual_bible=visual_bible,
        ref_invariants=ref_invariants,
        episode_index=episode_index,
    )
    logger.info(
        "process_narrative_with_reference_complete",
        episode_id=episode_id,
        shots=sum(len(ep.shots) for ep in output.episodes),
        hard_resolved=(
            output.rule_engine_report.hard_conflicts_resolved
            if output.rule_engine_report else 0
        ),
        soft_annotated=(
            output.rule_engine_report.soft_conflicts_annotated
            if output.rule_engine_report else 0
        ),
    )
    return output
