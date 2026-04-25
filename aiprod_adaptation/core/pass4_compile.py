from __future__ import annotations

import warnings
from typing import Any, cast

from pydantic import ValidationError

from aiprod_adaptation.models.intermediate import ShotDict, VisualScene
from aiprod_adaptation.models.schema import AIPRODOutput, Episode, Scene, Shot

_SCENE_KNOWN_KEYS: frozenset[str] = frozenset(
    {
        "scene_id",
        "characters",
        "character_ids",
        "location",
        "location_id",
        "time_of_day",
        "visual_actions",
        "dialogues",
        "emotion",
        "action_units",
        "shot_ids",
    }
)


def _slugify_identifier(text: str) -> str:
    slug = "".join(character.lower() if character.isalnum() else "_" for character in text)
    slug = "_".join(part for part in slug.split("_") if part)
    return slug or "unknown"


def _character_ids_for_scene(scene: VisualScene) -> list[str]:
    explicit = [_slugify_identifier(character) for character in scene.get("characters", [])]
    if explicit:
        return explicit

    derived: list[str] = []
    for action in scene.get("action_units", []):
        subject_id = action.get("subject_id")
        if not subject_id or subject_id in {
            "unknown_subject",
            "male_subject",
            "female_subject",
            "group_subject",
            "speaker_subject",
            "listener_subject",
        }:
            continue
        if subject_id not in derived:
            derived.append(subject_id)
    return derived


def _location_id_for_scene(scene: VisualScene) -> str | None:
    location = scene.get("location", "Unknown")
    if location.lower() != "unknown":
        return _slugify_identifier(location)

    for action in scene.get("action_units", []):
        target = action.get("target")
        if target:
            return _slugify_identifier(target)
    return None


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

    scene_to_shot_ids: dict[str, list[str]] = {scene["scene_id"]: [] for scene in scenes}
    for shot in shots:
        shot_id = shot.get("shot_id")
        scene_id = shot.get("scene_id")
        if isinstance(shot_id, str) and isinstance(scene_id, str):
            scene_to_shot_ids.setdefault(scene_id, []).append(shot_id)

    try:
        pydantic_scenes = [
            Scene(
                **cast(
                    Any,
                    {
                        **{k: v for k, v in s.items() if k in _SCENE_KNOWN_KEYS},
                        "character_ids": _character_ids_for_scene(s),
                        "location_id": _location_id_for_scene(s),
                        "shot_ids": scene_to_shot_ids.get(s["scene_id"], []),
                    },
                )
            )
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
            shot_payload = dict(shot)
            action_payload = shot_payload.get("action")
            if action_payload is not None:
                shot_payload["action"] = dict(cast(Any, action_payload))
            validated_shots.append(Shot(**cast(Any, shot_payload)))
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
