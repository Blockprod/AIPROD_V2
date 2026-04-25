"""
PASS 3 — CINEMATIC SHOT ATOMIZATION v3.1 (AIPROD_Cinematic)

Input : List[VisualScene]   (enriched output of Pass 2 v3.0)
Output: List[ShotDict]      (shots with full cinematic metadata)

Shot dict keys (v3.1):
    shot_id, scene_id, prompt, shot_type, camera_movement, duration_sec,
    emotion, action, metadata,
    # v3.1 cinematic fields
    shot_role, composition_description, lighting_directives,
    framing_note, rhythm_purpose, visual_invariants_applied,
    feasibility_score, reference_anchor_strength

Pipeline (deterministic, rule-based, no LLM):
  1. Extract scene context from VisualScene
  2. Select base shot sequence from (beat_type x action_intensity)
  3. Apply continuity-flag injections (FIRST_APPEARANCE, CLIFFHANGER, ACT_BREAK)
  4. Apply scene_type overrides (flashback, montage, dream, cliffhanger)
  5. Per-shot: apply physical layer overrides (PhysicalAction -> shot_type/movement)
  6. Per-shot: apply gaze_direction override (BodyLanguageState)
  7. Per-shot: apply emotional_layer modifiers (disguised, erupting, surface_neutral)
  8. Per-shot: enforce 180-degree rule guard (over_shoulder pairs -> neutral cut)
  9. Per-shot: compute composition, lighting, framing_note, rhythm_purpose
  10. Per-shot: compute feasibility_score and reference_anchor_strength
  11. Build prompt (enriched with cinematic directives)
  12. Build metadata dict

Backward compatibility:
  - atomize_shots() is preserved as deprecated alias for simplify_shots()
  - All existing metadata keys are preserved
  - Existing shot_type / camera_movement values remain valid
"""

from __future__ import annotations

import re
from typing import cast

from aiprod_adaptation.models.intermediate import ActionSpec, BodyLanguageState, PhysicalAction, ShotDict, VisualScene

from .rules.cinematography_rules_v3 import (
    CAMERA_MOVEMENT_DEFAULT_V3,
    CAMERA_MOVEMENT_RULES_V3,
    COMPOSITION_DEFAULT,
    COMPOSITION_DESCRIPTIONS,
    CONTINUITY_FLAG_INJECTIONS,
    DURATION_TABLE,
    EMOTIONAL_LAYER_MODIFIERS,
    FEASIBILITY_BASE_SCORES,
    FEASIBILITY_DEFAULT_SCORE,
    FEASIBILITY_EXPLOSIVE_PENALTY,
    FEASIBILITY_STATIC_BONUS,
    FRAMING_NOTE_DEFAULT,
    FRAMING_NOTES,
    GAZE_DIRECTION_RULES,
    INTENSITY_SHOT_SEQUENCES,
    LIGHTING_DIRECTIVES,
    NEUTRAL_CUT_CAMERA_MOVEMENT,
    NEUTRAL_CUT_DURATION,
    NEUTRAL_CUT_SHOT_ROLE,
    NEUTRAL_CUT_SHOT_TYPE,
    OVER_SHOULDER_PAIR,
    PHYSICAL_LAYER_SHOT_OVERRIDES,
    SCENE_TYPE_CAMERA_OVERRIDES,
    SHOT_ROLE_DEFAULT,
    SHOT_ROLE_MAP,
    SHOT_SEQUENCE_DEFAULT_V3,
)
from .rules.dop_style_rules import (
    resolve_color_grade,
    resolve_dof,
    resolve_lens_mm,
)

_AMBIGUOUS_RE = re.compile(r"\b(seems?|appears?|perhaps|maybe)\b", re.IGNORECASE)

_SPEECH_VERBS_SOUND: list[str] = [
    "said", "asked", "replied", "whispered", "shouted", "spoke", "speaks",
    "answered", "told", "says", "exclaimed",
]


# ===========================================================================
# Section 1: Legacy v2 helpers (kept for backward compat / fallback)
# ===========================================================================

def _has_any(text_lower: str, verbs: list[str]) -> bool:
    return any(re.search(r"\b" + re.escape(v) + r"\b", text_lower) for v in verbs)


def _slugify_identifier(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "unknown"


def _extract_subject_id(action: str, characters: list[str], fallback: str | None) -> str:
    lower = action.lower()
    for character in characters:
        if character.lower() in lower:
            return _slugify_identifier(character)
    if fallback:
        return fallback
    tokens = re.findall(r"[A-Za-z']+", action)
    if not tokens:
        return "unknown_subject"
    first = tokens[0].lower()
    if first in {"a", "an", "the"} and len(tokens) > 1:
        return _slugify_identifier(tokens[1])
    return _slugify_identifier(tokens[0])


def _extract_action_type_and_target(action: str) -> tuple[str, str | None, list[str]]:
    tokens = re.findall(r"[A-Za-z']+", action)
    lower_tokens = [token.lower() for token in tokens]
    if not lower_tokens:
        return "observe", None, []

    modifiers = [token for token in lower_tokens if token.endswith("ly")]
    index = 0
    while index < len(lower_tokens) and lower_tokens[index].endswith("ly"):
        index += 1

    if index < len(lower_tokens) and lower_tokens[index] in {"a", "an", "the"}:
        index += 2
    else:
        index += 1

    while index < len(lower_tokens) and lower_tokens[index] in {
        "am", "is", "are", "was", "were", "be", "been", "being",
        "has", "have", "had", "do", "does", "did",
    }:
        index += 1

    if index >= len(lower_tokens):
        action_type = lower_tokens[-1]
    else:
        action_type = lower_tokens[index]

    target: str | None = None
    target_markers = {
        "to", "toward", "towards", "into", "in",
        "at", "through", "inside", "onto", "on",
    }
    for target_index in range(index + 1, len(lower_tokens)):
        if lower_tokens[target_index] in target_markers:
            remainder = [
                token
                for token in lower_tokens[target_index + 1:]
                if token not in {"a", "an", "the"}
            ]
            if remainder:
                target = " ".join(remainder)
            break

    return action_type, target, modifiers


def _build_action_payload(
    action: str,
    characters: list[str],
    location: str,
    camera_movement: str,
    fallback: ActionSpec | None,
) -> ActionSpec:
    action_type, target, modifiers = _extract_action_type_and_target(action)
    fallback_location = fallback.get("location_id") if fallback is not None else None
    return {
        "subject_id": _extract_subject_id(
            action,
            characters,
            fallback.get("subject_id") if fallback is not None else None,
        ),
        "action_type": action_type,
        "target": target,
        "modifiers": modifiers,
        "location_id": (
            fallback_location
            if fallback_location is not None
            else None if location.lower() == "unknown location" else _slugify_identifier(location)
        ),
        "camera_intent": camera_movement,
        "source_text": action,
    }


def _compute_dominant_sound(action: str) -> str:
    if '"' in action or "\u201C" in action:
        return "dialogue"
    lower = action.lower()
    for v in _SPEECH_VERBS_SOUND:
        if re.search(r"\b" + v + r"\b\s*[,.]?\s*$", lower):
            return "dialogue"
        if re.search(r"\b" + v + r"\b\s*,", lower):
            return "dialogue"
    return "ambient"


def _build_prompt(action: str, location: str, lighting: str | None = None) -> str:
    clean = _AMBIGUOUS_RE.sub("", action).strip().rstrip(".!?,;")
    clean = re.sub(r"\s{2,}", " ", clean).strip()
    if location and location.lower() != "unknown" and location.lower() not in clean.lower():
        prompt = f"{clean}, in {location}."
    else:
        prompt = f"{clean}."
    if lighting:
        prompt = f"{prompt} {lighting}"
    return prompt


def _atomize_action(action: str) -> list[str]:
    if action.rstrip().endswith(('.', '!', '?')):
        return [action]
    if ", " in action:
        parts = [p.strip() for p in action.split(", ") if p.strip()]
        if len(parts) > 1:
            return parts
    return [action]


def _make_shot_id(scene_id: str, shot_num: int) -> str:
    return f"{scene_id}_SHOT_{shot_num:03d}"


# ===========================================================================
# Section 2: v3.1 Cinematic engine helpers
# ===========================================================================

def _resolve_shot_sequence(
    beat_type: str | None,
    action_intensity: str | None,
) -> tuple[list[str], list[int]]:
    if beat_type and action_intensity:
        key = (beat_type, action_intensity)
        if key in INTENSITY_SHOT_SEQUENCES:
            return INTENSITY_SHOT_SEQUENCES[key]
    if beat_type:
        key = (beat_type, "subtle")
        if key in INTENSITY_SHOT_SEQUENCES:
            return INTENSITY_SHOT_SEQUENCES[key]
    return SHOT_SEQUENCE_DEFAULT_V3


def _resolve_camera_movement(
    shot_type: str,
    beat_type: str | None,
    action_intensity: str | None,
    scene_tone: str | None,
) -> str:
    for rule_stype, rule_beat, rule_intensity, rule_tone, movement in CAMERA_MOVEMENT_RULES_V3:
        if rule_stype != shot_type:
            continue
        if rule_beat is not None and rule_beat != beat_type:
            continue
        if rule_intensity is not None and rule_intensity != action_intensity:
            continue
        if rule_tone is not None and rule_tone != scene_tone:
            continue
        return movement
    return CAMERA_MOVEMENT_DEFAULT_V3


def _apply_physical_layer_override(
    physical_action: PhysicalAction | None,
    base_shot_type: str,
    base_movement: str,
) -> tuple[str, str]:
    if physical_action is None:
        return base_shot_type, base_movement
    layer     = physical_action.get("layer", "")
    intensity = physical_action.get("intensity", "subtle")
    key = (layer, intensity)
    if key in PHYSICAL_LAYER_SHOT_OVERRIDES:
        return PHYSICAL_LAYER_SHOT_OVERRIDES[key]
    return base_shot_type, base_movement


def _apply_gaze_override(
    gaze_direction: str | None,
    base_shot_type: str,
    base_movement: str,
) -> tuple[str, str]:
    if gaze_direction and gaze_direction in GAZE_DIRECTION_RULES:
        return GAZE_DIRECTION_RULES[gaze_direction]
    return base_shot_type, base_movement


def _apply_emotional_layer_block(
    emotional_layer: str | None,
    shot_type: str,
) -> str:
    if not emotional_layer:
        return shot_type
    mod = EMOTIONAL_LAYER_MODIFIERS.get(emotional_layer, {})
    if mod.get("block_extreme_cu") and shot_type == "extreme_close_up":
        return "close_up"
    max_type = mod.get("max_shot_type")
    if max_type:
        order = ["extreme_wide", "wide", "medium_wide", "medium", "medium_close",
                 "over_shoulder", "close_up", "extreme_close_up"]
        current_rank = order.index(shot_type) if shot_type in order else 4
        max_rank = order.index(max_type) if max_type in order else len(order)
        if current_rank > max_rank:
            return str(max_type)
    return shot_type


def _resolve_lighting_directive(
    scene_tone: str | None,
    tod_visual: str | None,
) -> str | None:
    for rule_tone, rule_tod, directive in LIGHTING_DIRECTIVES:
        if rule_tone is not None and rule_tone != scene_tone:
            continue
        if rule_tod is not None and rule_tod != tod_visual:
            continue
        return directive
    return None


def _resolve_composition(shot_type: str) -> str:
    return COMPOSITION_DESCRIPTIONS.get(shot_type, COMPOSITION_DEFAULT)


def _resolve_framing_note(
    shot_type: str,
    emotional_layer: str | None,
    energy_level: str | None,
    gaze_direction: str | None,
) -> str | None:
    if emotional_layer:
        key = (shot_type, emotional_layer)
        if key in FRAMING_NOTES:
            return FRAMING_NOTES[key]
    if energy_level:
        key = (shot_type, energy_level)
        if key in FRAMING_NOTES:
            return FRAMING_NOTES[key]
    if gaze_direction:
        key = (shot_type, gaze_direction)
        if key in FRAMING_NOTES:
            return FRAMING_NOTES[key]
    return FRAMING_NOTE_DEFAULT


def _compute_feasibility_score(
    shot_type: str,
    camera_movement: str,
    action_intensity: str | None,
) -> int:
    base = FEASIBILITY_BASE_SCORES.get((shot_type, camera_movement), FEASIBILITY_DEFAULT_SCORE)
    if camera_movement == "static":
        base = min(100, base + FEASIBILITY_STATIC_BONUS)
    if action_intensity == "explosive":
        base -= FEASIBILITY_EXPLOSIVE_PENALTY
    return max(0, min(100, base))


def _resolve_duration(
    beat_type: str | None,
    action_intensity: str | None,
    shot_type: str,
    duration_cap: int,
    pacing: str,
) -> int:
    if beat_type and action_intensity:
        key = (beat_type, action_intensity, shot_type)
        if key in DURATION_TABLE:
            duration = min(DURATION_TABLE[key], duration_cap)
            return max(3, min(8, _apply_pacing(duration, pacing)))
    duration = duration_cap
    return max(3, min(8, _apply_pacing(duration, pacing)))


def _apply_pacing(duration: int, pacing: str) -> int:
    if pacing == "fast":
        return min(duration, 5)
    if pacing == "slow":
        return max(duration, 5)
    return duration


def _resolve_rhythm_purpose(
    shot_type: str,
    beat_type: str | None,
    action_intensity: str | None,
    shot_index: int,
    total_shots: int,
) -> str:
    if shot_index == 0:
        if shot_type in {"extreme_wide", "wide"}:
            return "geography establishment"
        return "scene entry coverage"
    if shot_index == total_shots - 1:
        if shot_type in {"extreme_close_up", "close_up"}:
            return "emotional apex close"
        if shot_type in {"wide", "extreme_wide"}:
            return "release and exit"
        return "scene resolution"
    if shot_type == "insert":
        return "narrative object emphasis"
    if shot_type == "pov":
        return "subjective threat / desire"
    if beat_type == "dialogue_scene" and shot_type == "over_shoulder":
        return "conversational coverage"
    if action_intensity == "explosive" and shot_type in {"close_up", "extreme_close_up"}:
        return "peak intensity reaction"
    return "continuity coverage"


def _resolve_shot_role(shot_type: str) -> str:
    return SHOT_ROLE_MAP.get(shot_type, SHOT_ROLE_DEFAULT)


# ===========================================================================
# Section 3: Injection helpers (continuity flags / scene_type)
# ===========================================================================

def _apply_continuity_injections(
    shots_plan: list[dict[str, object]],
    continuity_flags: list[str],
) -> list[dict[str, object]]:
    for flag in continuity_flags:
        flag_key = flag.split(":")[0]
        if flag_key not in CONTINUITY_FLAG_INJECTIONS:
            continue
        spec = CONTINUITY_FLAG_INJECTIONS[flag_key]

        if spec.get("inject_before"):
            sequence: list[str] = list(cast(list[str], spec.get("sequence", [spec.get("shot_type", "wide")])))
            movement: str = str(spec.get("camera_movement", "static"))
            duration_val: int = int(cast(int, spec.get("duration", 6)))
            s_role: str = str(spec.get("shot_role", "establishing"))
            f_note = spec.get("framing_note")
            for stype in reversed(sequence):
                injected: dict[str, object] = {
                    "_inject_type":     stype,
                    "_inject_movement": movement,
                    "_inject_duration": duration_val,
                    "_inject_role":     s_role,
                    "_inject_framing":  f_note,
                }
                shots_plan.insert(0, injected)

        if spec.get("inject_after"):
            stype = str(spec.get("shot_type", "extreme_close_up"))
            movement = str(spec.get("camera_movement", "dolly_in"))
            duration_val = int(cast(int, spec.get("duration", 4)))
            s_role = str(spec.get("shot_role", "reveal"))
            f_note = spec.get("framing_note")
            injected = {
                "_inject_type":     stype,
                "_inject_movement": movement,
                "_inject_duration": duration_val,
                "_inject_role":     s_role,
                "_inject_framing":  f_note,
            }
            shots_plan.append(injected)

    return shots_plan


def _apply_180_degree_guard(
    shots_plan: list[dict[str, object]],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for i, shot in enumerate(shots_plan):
        result.append(shot)
        if i == len(shots_plan) - 1:
            break
        next_shot = shots_plan[i + 1]
        current_type = str(shot.get("_sequence_type", shot.get("_inject_type", "medium")))
        next_type    = str(next_shot.get("_sequence_type", next_shot.get("_inject_type", "medium")))
        if current_type in OVER_SHOULDER_PAIR and next_type in OVER_SHOULDER_PAIR:
            neutral: dict[str, object] = {
                "_inject_type":     NEUTRAL_CUT_SHOT_TYPE,
                "_inject_movement": NEUTRAL_CUT_CAMERA_MOVEMENT,
                "_inject_duration": NEUTRAL_CUT_DURATION,
                "_inject_role":     NEUTRAL_CUT_SHOT_ROLE,
                "_inject_framing":  None,
            }
            result.append(neutral)
    return result


# ===========================================================================
# Section 4: Scene-level plan builder
# ===========================================================================

def _build_scene_shot_plan(
    visual_actions: list[str],
    physical_actions: list[PhysicalAction],
    beat_type: str | None,
    action_intensity: str | None,
    scene_type: str | None,
    emotional_layer: str | None,
    body_language_states: list[BodyLanguageState],
    scene_tone: str | None,
) -> list[dict[str, object]]:
    seq_types, seq_caps = _resolve_shot_sequence(beat_type, action_intensity)

    scene_override = SCENE_TYPE_CAMERA_OVERRIDES.get(scene_type or "", {})
    if "sequence_override" in scene_override:
        override_seq = list(cast(list[str], scene_override["sequence_override"]))
        override_dur = int(cast(int, scene_override.get("duration_override", 3)))
        seq_types = override_seq
        seq_caps  = [override_dur] * len(override_seq)

    action_parts_with_index: list[tuple[str, int, PhysicalAction | None]] = []
    for idx, action in enumerate(visual_actions):
        pa = physical_actions[idx] if idx < len(physical_actions) else None
        for part in _atomize_action(action):
            if part.strip():
                action_parts_with_index.append((part, idx, pa))

    gaze_dir: str | None = body_language_states[0].get("gaze_direction") if body_language_states else None

    plan: list[dict[str, object]] = []
    total_parts = len(action_parts_with_index)
    for part_idx, (part, action_idx, pa) in enumerate(action_parts_with_index):
        seq_pos  = part_idx % len(seq_types)
        seq_type = seq_types[seq_pos]
        dur_cap  = seq_caps[seq_pos]

        movement = _resolve_camera_movement(seq_type, beat_type, action_intensity, scene_tone)

        seq_type, movement = _apply_physical_layer_override(pa, seq_type, movement)

        if gaze_dir:
            seq_type, movement = _apply_gaze_override(gaze_dir, seq_type, movement)

        seq_type = _apply_emotional_layer_block(emotional_layer, seq_type)

        movement_override = scene_override.get("movement_override")
        if movement_override and part_idx < total_parts - 1:
            movement = str(movement_override)

        plan.append({
            "_sequence_type":     seq_type,
            "_sequence_movement": movement,
            "_duration_cap":      dur_cap,
            "_action_index":      action_idx,
            "_physical_action":   pa,
            "_shot_role":         _resolve_shot_role(seq_type),
            "_framing_override":  None,
        })

    return plan


# ===========================================================================
# Section 5: Public API
# ===========================================================================

def simplify_shots(scenes: list[VisualScene]) -> list[ShotDict]:
    """
    Decompose visual scenes into cinematic shots (v3.1).

    Args:
        scenes: List of enriched VisualScene dicts from pass2_visual.

    Returns:
        List of ShotDict with full cinematic metadata (v3.1).
    """
    if not scenes:
        raise ValueError("PASS 3: scenes list must not be empty.")

    shots: list[ShotDict] = []

    for scene in scenes:
        scene_id:       str = scene["scene_id"]
        location:       str = scene["location"]
        emotion:        str = scene["emotion"]
        visual_actions: list[str] = scene.get("visual_actions", [])
        action_units:   list[ActionSpec] = scene.get("action_units", [])
        dialogues:      list[str] = scene.get("dialogues", [])
        characters:     list[str] = list(scene["characters"])

        pacing:             str        = scene.get("pacing", "medium")
        tod_visual:         str        = scene.get("time_of_day_visual", "day")
        scene_dom_sound:    str | None = scene.get("dominant_sound")

        beat_type:          str | None   = scene.get("beat_type")
        scene_tone:         str | None   = scene.get("scene_tone")
        emotional_beat_idx: float | None = scene.get("emotional_beat_index")
        action_intensity:   str | None   = scene.get("action_intensity")
        emotional_layer:    str | None   = scene.get("emotional_layer")
        scene_type:         str | None   = scene.get("scene_type")
        continuity_flags:   list[str]    = list(scene.get("continuity_flags", []))
        physical_actions_raw = scene.get("physical_actions", [])
        physical_actions:   list[PhysicalAction] = list(physical_actions_raw) if physical_actions_raw else []
        body_language_states: list[BodyLanguageState] = list(scene.get("body_language_states", []))
        visual_invariants:  list[str]    = list(scene.get("visual_invariants_applied", []))
        reference_location_id: str | None = scene.get("reference_location_id")

        if not visual_actions:
            raise ValueError(f"PASS 3: scene '{scene_id}' has empty visual_actions.")

        lens_mm:     int = resolve_lens_mm(beat_type, scene_tone)
        color_grade: str = resolve_color_grade(scene_tone, tod_visual if tod_visual != "day" else None)
        lighting_dir: str | None = _resolve_lighting_directive(scene_tone, tod_visual)

        scene_override = SCENE_TYPE_CAMERA_OVERRIDES.get(scene_type or "", {})
        color_grade_override = scene_override.get("color_grade_override")
        if color_grade_override:
            color_grade = str(color_grade_override)
        min_lens_mm = int(cast(int, scene_override.get("min_lens_mm", 0)))
        if min_lens_mm > 0:
            lens_mm = max(lens_mm, min_lens_mm)

        plan = _build_scene_shot_plan(
            visual_actions, physical_actions, beat_type, action_intensity,
            scene_type, emotional_layer, body_language_states, scene_tone,
        )

        plan = _apply_continuity_injections(plan, continuity_flags)
        plan = _apply_180_degree_guard(plan)

        if scene_override.get("last_shot_type") and plan:
            last = plan[-1]
            last["_sequence_type"]     = str(scene_override["last_shot_type"])
            last["_sequence_movement"] = str(scene_override.get("last_shot_movement", "dolly_in"))
            last["_duration_cap"]      = int(cast(int, scene_override.get("last_duration_override", 4)))
            last["_framing_override"]  = scene_override.get("framing_note")
            last["_shot_role"]         = "reveal"

        action_parts_flat: list[tuple[str, ActionSpec | None]] = []
        for idx, action in enumerate(visual_actions):
            seed_action = action_units[idx] if idx < len(action_units) else None
            for part in _atomize_action(action):
                if part.strip():
                    action_parts_flat.append((part, seed_action))

        single_shot_dialogue_scene = bool(dialogues) and len(action_parts_flat) == 1

        total_shots_in_scene = len(plan)
        shot_num = 1
        non_injected_count = 0

        for plan_pos, plan_item in enumerate(plan):
            is_injected = "_inject_type" in plan_item

            if is_injected:
                stype    = str(plan_item["_inject_type"])
                movement = str(plan_item["_inject_movement"])
                dur_cap  = int(cast(int, plan_item["_inject_duration"]))
                s_role   = str(plan_item["_inject_role"])
                f_note   = cast("str | None", plan_item.get("_inject_framing"))
                if action_parts_flat:
                    part, seed_action = action_parts_flat[0]
                else:
                    part, seed_action = f"{emotion} scene", None
            else:
                stype    = str(plan_item["_sequence_type"])
                movement = str(plan_item["_sequence_movement"])
                dur_cap  = int(cast(int, plan_item["_duration_cap"]))
                s_role   = str(plan_item["_shot_role"])
                f_note   = cast("str | None", plan_item.get("_framing_override"))
                if action_parts_flat:
                    part_idx = non_injected_count % len(action_parts_flat)
                    part, seed_action = action_parts_flat[part_idx]
                else:
                    part, seed_action = f"{emotion} scene", None
                non_injected_count += 1

            duration = _resolve_duration(beat_type, action_intensity, stype, dur_cap, pacing)
            if scene_override.get("duration_override"):
                duration = int(cast(int, scene_override["duration_override"]))

            composition = _resolve_composition(stype)

            energy_level = body_language_states[0].get("energy_level") if body_language_states else None
            gaze_dir     = body_language_states[0].get("gaze_direction") if body_language_states else None
            if not f_note:
                f_note = _resolve_framing_note(stype, emotional_layer, energy_level, gaze_dir)

            rhythm = _resolve_rhythm_purpose(
                stype, beat_type, action_intensity, plan_pos, total_shots_in_scene,
            )

            feasibility = _compute_feasibility_score(stype, movement, action_intensity)
            anchor_strength: float = 0.9 if reference_location_id else 0.5

            prompt = _build_prompt(part, location, lighting_dir)

            dom_sound: str = (
                scene_dom_sound
                if scene_dom_sound is not None
                else "dialogue"
                if single_shot_dialogue_scene
                else _compute_dominant_sound(part)
            )

            action_payload = _build_action_payload(
                part, characters, location, movement, seed_action,
            )

            dof = resolve_dof(stype)
            shot_metadata: dict[str, object] = {
                "time_of_day_visual": tod_visual,
                "dominant_sound":     dom_sound,
                "depth_of_field":     dof,
            }
            if beat_type is not None:
                shot_metadata["beat_type"] = beat_type
            if scene_tone is not None:
                shot_metadata["scene_tone"] = scene_tone
            if color_grade != "neutral":
                shot_metadata["color_grade_hint"] = color_grade
            if lens_mm != 35:
                shot_metadata["lens_mm"] = lens_mm
            if emotional_beat_idx is not None:
                shot_metadata["emotional_beat_index"] = emotional_beat_idx

            shots.append({
                "shot_id":                   _make_shot_id(scene_id, shot_num),
                "scene_id":                  scene_id,
                "prompt":                    prompt,
                "duration_sec":              duration,
                "emotion":                   emotion,
                "shot_type":                 stype,
                "camera_movement":           movement,
                "action":                    action_payload,
                "metadata":                  shot_metadata,
                "shot_role":                 s_role,
                "composition_description":   composition,
                "lighting_directives":       lighting_dir,
                "framing_note":              f_note,
                "rhythm_purpose":            rhythm,
                "visual_invariants_applied": visual_invariants,
                "feasibility_score":         feasibility,
                "reference_anchor_strength": anchor_strength,
            })
            shot_num += 1

    if not shots:
        raise ValueError("PASS 3: atomization produced zero shots.")

    return shots


# ---------------------------------------------------------------------------
# Deprecated alias
# ---------------------------------------------------------------------------

def atomize_shots(scenes: list[VisualScene]) -> list[ShotDict]:
    """Deprecated. Use simplify_shots()."""
    import warnings
    warnings.warn(
        "atomize_shots() is deprecated. Use simplify_shots().",
        DeprecationWarning,
        stacklevel=2,
    )
    return simplify_shots(scenes)
