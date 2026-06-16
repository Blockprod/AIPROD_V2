from __future__ import annotations

import sys
from typing import Any

from pipeline.shot_pipeline import SceneP1Params

MESSAGE = (
    "production/gen_shots.py is deprecated and intentionally blocks execution. "
    "Use `aiprod production preflight` followed by "
    "`aiprod production execute --receipt <path>`."
)


def build_scene_params(
    shot: dict[str, Any],
    scene_cfg: dict[str, Any],
    location: dict[str, Any],
    grade: dict[str, Any],
) -> SceneP1Params:
    colour = location["colour"]
    state = shot.get("state_override") or "canonical appearance"
    scene_grade = grade["per_scene_grade"].get(shot["scene_id"], "")
    char_exp = grade.get("character_exposure", {})
    silhouette_shots: list[str] = char_exp.get("silhouette_override_shots", [])
    if char_exp and shot["shot_id"] not in silhouette_shots and shot.get("primary_character"):
        face_exposure = (
            f"Key side {char_exp['face_key_ire']}% IRE, "
            f"shadow side {char_exp['face_shadow_ire']}% IRE "
            f"({char_exp['ratio_label']})."
        )
    else:
        face_exposure = ""
    return SceneP1Params(
        scene_id=shot["scene_id"],
        episode="Episode 01",
        location_slug=location["slug"],
        location_desc=location["canonical"],
        lighting_desc=location["lighting_brief"],
        colour_desc=(
            f"Dominant: {colour['dominant']}. Accent: {colour['accent']}. "
            f"Blacks: {colour['blacks']}. Grade reference: {location['dop_ref']}. "
            f"Show look: {grade['show_look']['grade_intent']} Scene grade: {scene_grade}."
        ),
        composition=shot["composition"],
        subject_action=shot["action_brief"],
        seed=scene_cfg["seed"],
        emotion_intent=shot["emotion_intent"],
        reference_exact=shot.get("reference_exact", ""),
        off_frame_tension=shot.get("off_frame_tension", ""),
        material_state=shot.get("material_state") or location.get("canonical", ""),
        face_exposure=face_exposure,
        eyeline=shot.get("eyeline", ""),
        extra_notes=(
            f"Camera spec: {shot['camera_spec']}. "
            f"Character state: {state}."
        ),
    )


def run(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError(MESSAGE)


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
