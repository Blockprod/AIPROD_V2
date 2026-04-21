from __future__ import annotations

import sys

import structlog

from aiprod_adaptation.models.schema import AIPRODOutput

structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def run_pipeline(text: str, title: str, episode_id: str = "EP01") -> AIPRODOutput:
    """
    Execute the complete 4-pass transformation pipeline.

    Args:
        text: Raw narrative input text
        title: Episode title for the output

    Returns:
        AIPRODOutput: Fully validated structured output
    """
    logger.info("pipeline_start", input_length=len(text), title=title)

    from aiprod_adaptation.core.pass1_segment import segment
    logger.debug("pass1_start")
    scenes_pass1 = segment(text)
    logger.info("pass1_complete", scene_count=len(scenes_pass1))

    from aiprod_adaptation.core.pass2_visual import visual_rewrite
    logger.debug("pass2_start")
    scenes_pass2 = visual_rewrite(scenes_pass1)
    logger.info("pass2_complete", scene_count=len(scenes_pass2))

    from aiprod_adaptation.core.pass3_shots import simplify_shots
    logger.debug("pass3_start")
    shots_pass3 = simplify_shots(scenes_pass2)
    logger.info("pass3_complete", shot_count=len(shots_pass3))

    from aiprod_adaptation.core.pass4_compile import compile_episode
    logger.debug("pass4_start")
    output = compile_episode(scenes_pass2, shots_pass3, title, episode_id)
    logger.info("pipeline_complete", episode_count=len(output.episodes))

    return output
