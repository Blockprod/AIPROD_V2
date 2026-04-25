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
        # v3.0 cinematic fields — passed through to compiled Scene
        "beat_type",
        "scene_tone",
        "emotional_beat_index",
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
    visual_bible: object | None = None,
    ref_invariants: object | None = None,
    episode_index: int = 1,
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

    # ------------------------------------------------------------------
    # Pass 4 global coherence layer
    # ------------------------------------------------------------------
    from aiprod_adaptation.core.global_coherence.consistency_checker import check_and_enrich
    from aiprod_adaptation.core.global_coherence.pacing_analyzer import analyze
    from aiprod_adaptation.core.global_coherence.prompt_finalizer import finalize_prompts

    validated_shots, consistency_report = check_and_enrich(
        pydantic_scenes, validated_shots, visual_bible
    )

    # ------------------------------------------------------------------
    # Pass 4 rule engine layer — per-shot conflict detection + resolution
    # ------------------------------------------------------------------
    from aiprod_adaptation.core.rule_engine.builtin_rules import make_default_evaluator
    from aiprod_adaptation.core.rule_engine.conflict_resolver import ConflictResolutionEngine
    from aiprod_adaptation.core.rule_engine.models import EvalContext
    from aiprod_adaptation.models.schema import RuleEngineReport

    _evaluator = make_default_evaluator()
    _resolver = ConflictResolutionEngine()
    _scene_index = {s.scene_id: s for s in pydantic_scenes}
    _all_res_records: list[Any] = []
    _resolved_shots: list[Shot] = []
    for _shot in validated_shots:
        _scene = _scene_index.get(_shot.scene_id, pydantic_scenes[0])
        _ctx = EvalContext(
            shot=_shot,
            scene=_scene,
            visual_bible=visual_bible,
            ref_invariants=ref_invariants,
            episode_id=episode_id,
            episode_index=episode_index,
        )
        _eval_results = _evaluator.evaluate(_ctx)
        _resolved_shot, _records = _resolver.resolve(_shot, _ctx, _eval_results)
        _resolved_shots.append(_resolved_shot)
        _all_res_records.extend(_records)
    validated_shots = _resolved_shots

    _hard_count = sum(
        1 for r in _all_res_records
        if r.conflict.conflict_type.value == "HARD" and r.was_modified
    )
    _soft_count = sum(
        1 for r in _all_res_records
        if r.conflict.conflict_type.value == "SOFT" and r.was_modified
    )
    _modified_shot_ids = sorted({r.conflict.shot_id for r in _all_res_records if r.was_modified})
    _fired_rule_ids = sorted({r.conflict.rule_id for r in _all_res_records if r.was_modified})
    rule_engine_report = RuleEngineReport(
        rules_evaluated=len(_evaluator.rules) * len(validated_shots),
        hard_conflicts_resolved=_hard_count,
        soft_conflicts_annotated=_soft_count,
        total_shots_modified=len(_modified_shot_ids),
        conflict_shot_ids=_modified_shot_ids,
        rule_ids_fired=_fired_rule_ids,
    )

    validated_shots, enrichment_count = finalize_prompts(validated_shots, visual_bible)
    consistency_report = consistency_report.model_copy(
        update={"prompt_enrichments": enrichment_count}
    )
    pacing_profile = analyze(validated_shots)

    # ------------------------------------------------------------------
    # Assemble final Episode + AIPRODOutput
    # ------------------------------------------------------------------
    try:
        episode = Episode(
            episode_id=episode_id,
            scenes=pydantic_scenes,
            shots=validated_shots,
            pacing_profile=pacing_profile,
            consistency_report=consistency_report,
            rule_engine_report=rule_engine_report,
        )
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    bible_summary: dict[str, Any] = {}
    if visual_bible is not None:
        try:
            vb_data = visual_bible.data  # type: ignore[union-attr]
            bible_summary = {
                "series_title": vb_data.get("series_title", ""),
                "character_count": len(vb_data.get("characters", {})),
                "location_count": len(vb_data.get("locations", {})),
            }
        except Exception:  # noqa: BLE001 — never crash on optional enrichment
            pass

    try:
        return AIPRODOutput(
            title=title,
            episodes=[episode],
            visual_bible_summary=bible_summary,
            rule_engine_report=rule_engine_report,
        )
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
