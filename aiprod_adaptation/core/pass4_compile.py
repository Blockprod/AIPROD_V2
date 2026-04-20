"""
PASS 4 — COMPILATION
Input : title: str, scenes: List[dict], shots: List[dict]
Output: AIPRODOutput  (fully validated Pydantic v2 model)

Rules (applied strictly):
  1. Single episode with episode_id = "EP01".
  2. Validate every scene and shot before assembly.
  3. Raise ValueError on:
       - Empty title
       - Empty scenes list
       - Empty shots list
       - Any scene with empty visual_actions
       - Any scene with empty characters list  (warn only — not fatal per spec,
         but broken reference is fatal)
       - Any shot with duration_sec outside [3, 8]
       - Any shot whose scene_id does not reference a known scene
       - Any scene_id or shot_id that is an empty string
  4. All lists preserve strict input order.
  5. No sets, no sorting, no randomness.
"""

from __future__ import annotations

from typing import List

from aiprod_adaptation.models.schema import (
    AIPRODOutput,
    Episode,
    Scene,
    Shot,
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_title(title: str) -> None:
    if not title or not title.strip():
        raise ValueError("PASS 4: title must not be empty.")


def _validate_scenes(scenes: List[dict]) -> None:
    if not scenes:
        raise ValueError("PASS 4: scenes list must not be empty.")
    for scene in scenes:
        scene_id = scene.get("scene_id", "")
        if not scene_id or not scene_id.strip():
            raise ValueError("PASS 4: a scene has an empty scene_id.")
        if not scene.get("visual_actions"):
            raise ValueError(
                f"PASS 4: scene '{scene_id}' has empty visual_actions."
            )
        if not scene.get("location", "").strip():
            raise ValueError(
                f"PASS 4: scene '{scene_id}' has empty location."
            )
        emotion = scene.get("emotion", "")
        if not emotion or not emotion.strip():
            raise ValueError(
                f"PASS 4: scene '{scene_id}' has empty emotion."
            )


def _validate_shots(shots: List[dict], known_scene_ids: List[str]) -> None:
    if not shots:
        raise ValueError("PASS 4: shots list must not be empty.")
    for shot in shots:
        shot_id = shot.get("shot_id", "")
        if not shot_id or not shot_id.strip():
            raise ValueError("PASS 4: a shot has an empty shot_id.")

        scene_id = shot.get("scene_id", "")
        if scene_id not in known_scene_ids:
            raise ValueError(
                f"PASS 4: shot '{shot_id}' references unknown scene_id '{scene_id}'."
            )

        duration = shot.get("duration_sec")
        if duration is None or not isinstance(duration, int):
            raise ValueError(
                f"PASS 4: shot '{shot_id}' has missing or non-integer duration_sec."
            )
        if not (3 <= duration <= 8):
            raise ValueError(
                f"PASS 4: shot '{shot_id}' has invalid duration_sec={duration} "
                f"(must be 3–8)."
            )

        prompt = shot.get("prompt", "")
        if not prompt or not prompt.strip():
            raise ValueError(
                f"PASS 4: shot '{shot_id}' has empty prompt."
            )

        emotion = shot.get("emotion", "")
        if not emotion or not emotion.strip():
            raise ValueError(
                f"PASS 4: shot '{shot_id}' has empty emotion."
            )


# ---------------------------------------------------------------------------
# Assembly helpers
# ---------------------------------------------------------------------------

def _build_scene(scene_dict: dict) -> Scene:
    return Scene(
        scene_id=scene_dict["scene_id"],
        characters=list(scene_dict.get("characters", [])),
        location=scene_dict["location"],
        time_of_day=scene_dict.get("time_of_day"),
        visual_actions=list(scene_dict["visual_actions"]),
        dialogues=list(scene_dict.get("dialogues", [])),
        emotion=scene_dict["emotion"],
    )


def _build_shot(shot_dict: dict) -> Shot:
    return Shot(
        shot_id=shot_dict["shot_id"],
        scene_id=shot_dict["scene_id"],
        prompt=shot_dict["prompt"],
        duration_sec=shot_dict["duration_sec"],
        emotion=shot_dict["emotion"],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compile_output(
    title: str,
    scenes: List[dict],
    shots: List[dict],
) -> AIPRODOutput:
    """
    PASS 4 — Validate and assemble the final AIPRODOutput.

    Raises ValueError on any validation failure.
    Returns a fully validated AIPRODOutput with a single Episode 'EP01'.
    """
    _validate_title(title)
    _validate_scenes(scenes)

    known_scene_ids: List[str] = [s["scene_id"] for s in scenes]
    _validate_shots(shots, known_scene_ids)

    pydantic_scenes: List[Scene] = [_build_scene(s) for s in scenes]
    pydantic_shots:  List[Shot]  = [_build_shot(sh) for sh in shots]

    episode = Episode(
        episode_id="EP01",
        scenes=pydantic_scenes,
        shots=pydantic_shots,
    )

    return AIPRODOutput(
        title=title,
        episodes=[episode],
    )
