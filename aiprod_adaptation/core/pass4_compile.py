from __future__ import annotations

import warnings
from typing import Any, cast

from pydantic import ValidationError

from aiprod_adaptation.models.intermediate import ShotDict, VisualScene
from aiprod_adaptation.models.schema import AIPRODOutput, Episode, Scene, Shot

_SCENE_KNOWN_KEYS: frozenset[str] = frozenset(
    {"scene_id", "characters", "location", "time_of_day", "visual_actions", "dialogues", "emotion"}
)


def compile_episode(
    scenes: list[VisualScene],
    shots: list[ShotDict],
    title: str,
    episode_id: str = "EP01",
) -> AIPRODOutput:
    """
    Assemble scenes and shots into a validated AIPRODOutput.

    Args:
        scenes: List of scene dictionaries from pass2_visual
        shots: List of shot dictionaries from pass3_shots
        title: Episode title

    Returns:
        AIPRODOutput: Fully validated output

    Raises:
        ValueError: If any Pydantic validation fails
    """
    if not title or not title.strip():
        raise ValueError("PASS 4: title must not be empty.")
    if not scenes:
        raise ValueError("PASS 4: scenes list must not be empty.")
    if not shots:
        raise ValueError("PASS 4: shots list must not be empty.")

    known_scene_ids = {s["scene_id"] for s in scenes}
    for shot in shots:
        if shot.get("scene_id") not in known_scene_ids:
            sid = shot.get('shot_id')
            scid = shot.get('scene_id')
            raise ValueError(
                f"PASS 4: shot '{sid}' references unknown scene_id '{scid}'"
            )

    try:
        pydantic_scenes = [
            Scene(**cast(Any, {k: v for k, v in s.items() if k in _SCENE_KNOWN_KEYS}))
            for s in scenes
        ]
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    validated_shots: list[Shot] = []
    for shot in shots:
        duration = shot.get("duration_sec")
        if not isinstance(duration, int) or not (3 <= duration <= 8):
            sid = shot.get('shot_id')
            raise ValueError(
                f"PASS 4: shot '{sid}' has invalid duration_sec={duration} (must be 3-8)"
            )
        try:
            validated_shots.append(Shot(**shot))
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    try:
        episode = Episode(episode_id=episode_id, scenes=pydantic_scenes, shots=validated_shots)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    try:
        return AIPRODOutput(title=title, episodes=[episode])
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


# Deprecated — use compile_episode. Kept for backward compatibility.
def compile_output(
    title: str,
    scenes: list[VisualScene],
    shots: list[ShotDict],
    episode_id: str = "EP01",
) -> AIPRODOutput:
    """Deprecated. Use compile_episode(scenes, shots, title).
    NOTE: argument order differs — compile_output takes (title, scenes, shots).
    """
    warnings.warn(
        "compile_output() is deprecated. Use compile_episode(scenes, shots, title). "
        "NOTE: argument order differs — compile_output takes (title, scenes, shots).",
        DeprecationWarning,
        stacklevel=2,
    )
    return compile_episode(scenes, shots, title, episode_id)
