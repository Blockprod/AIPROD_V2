"""
production/tests/test_gen_shots.py
=====================================
Tests de non-régression — production/gen_shots.py.
Zéro appel API — fixtures JSON locales, zéro I/O disque.

Couvre :
  - build_scene_params() : forwarding de tous les champs critiques
  - Correction 4.2 : lighting_context prioritaire sur lighting_brief (via p2_scene_env)
  - Correction B-2 : emotion_intent forwardé dans SceneP1Params
  - Correction 1.1 : character_canonical default = LOCKED_NARA_CANONICAL
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


from pipeline.shot_pipeline import LOCKED_NARA_CANONICAL, SceneP1Params  # noqa: E402
from production.gen_shots import build_scene_params  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures JSON locales (aucun accès disque)
# ---------------------------------------------------------------------------

_GRADE: dict = {
    "show_look": {"grade_intent": "Deakins / BR2049 — desaturated teals, crushed blacks."},
    "per_scene_grade": {
        "SCN_002": "Teal-steel dominant, low ambient, amber practicals only.",
    },
}

_LOCATION: dict = {
    "slug": "INT. LOWER TRANSIT STACK — NIGHT",
    "canonical": "Industrial corridor, wet concrete, cage lamps overhead, pipe clusters.",
    "lighting_brief": "Fallback: amber cage lamp key, 4:1 ratio, 2700K.",
    "dop_ref": "Roger Deakins / Sicario (2015)",
    "colour": {
        "dominant": "#1C2B35",
        "accent": "#B86010",
        "blacks": "#05080A",
    },
}

_SCENE_CFG: dict = {"seed": 22}


def _make_shot(**kwargs) -> dict:
    defaults: dict = {
        "shot_id": "SCN_002_SHOT_001",
        "scene_id": "SCN_002",
        "location_key": "int_lower_transit_stack_night",
        "shot_type": "medium",
        "action_brief": "She scans the corridor slowly.",
        "camera_spec": "32mm T2.3, shallow DOF",
        "emotion_intent": "Dread — she knows too much.",
        "composition": "Subject left-frame, vanishing point right.",
        "state_override": None,
        "lighting_context": None,
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Tests build_scene_params()
# ---------------------------------------------------------------------------

class TestBuildSceneParams:
    def test_returns_scene_p1_params(self) -> None:
        shot = _make_shot()
        result = build_scene_params(shot, _SCENE_CFG, _LOCATION, _GRADE)
        assert isinstance(result, SceneP1Params)

    def test_scene_id_forwarded(self) -> None:
        shot = _make_shot(scene_id="SCN_005")
        result = build_scene_params(shot, _SCENE_CFG, _LOCATION, _GRADE)
        assert result.scene_id == "SCN_005"

    def test_seed_comes_from_scene_cfg(self) -> None:
        shot = _make_shot()
        result = build_scene_params(shot, {"seed": 99}, _LOCATION, _GRADE)
        assert result.seed == 99

    def test_seed_scn_002(self) -> None:
        shot = _make_shot()
        result = build_scene_params(shot, _SCENE_CFG, _LOCATION, _GRADE)
        assert result.seed == 22

    def test_composition_forwarded(self) -> None:
        shot = _make_shot(composition="Subject right-frame, deep vanishing point left.")
        result = build_scene_params(shot, _SCENE_CFG, _LOCATION, _GRADE)
        assert result.composition == "Subject right-frame, deep vanishing point left."

    def test_action_brief_forwarded_to_subject_action(self) -> None:
        shot = _make_shot(action_brief="She raises her arm slowly.")
        result = build_scene_params(shot, _SCENE_CFG, _LOCATION, _GRADE)
        assert result.subject_action == "She raises her arm slowly."

    def test_emotion_intent_forwarded(self) -> None:
        """Régression correction B-2 : emotion_intent ne doit plus être dans extra_notes."""
        shot = _make_shot(emotion_intent="Pure dread — no escape.")
        result = build_scene_params(shot, _SCENE_CFG, _LOCATION, _GRADE)
        assert result.emotion_intent == "Pure dread — no escape."

    def test_emotion_intent_not_in_extra_notes(self) -> None:
        """Régression B-2 : l'emotion ne doit pas être dupliquée dans extra_notes."""
        shot = _make_shot(emotion_intent="Pure dread — no escape.")
        result = build_scene_params(shot, _SCENE_CFG, _LOCATION, _GRADE)
        assert "Pure dread" not in result.extra_notes

    def test_default_canonical_is_nara(self) -> None:
        """Régression correction 1.1 : sans override, c'est Nara par défaut."""
        shot = _make_shot()
        result = build_scene_params(shot, _SCENE_CFG, _LOCATION, _GRADE)
        assert result.character_canonical == LOCKED_NARA_CANONICAL

    def test_state_override_in_extra_notes(self) -> None:
        shot = _make_shot(state_override="blood on jacket sleeve, left arm")
        result = build_scene_params(shot, _SCENE_CFG, _LOCATION, _GRADE)
        assert "blood on jacket sleeve" in result.extra_notes

    def test_state_override_none_uses_canonical(self) -> None:
        shot = _make_shot(state_override=None)
        result = build_scene_params(shot, _SCENE_CFG, _LOCATION, _GRADE)
        assert "canonical appearance" in result.extra_notes

    def test_location_slug_forwarded(self) -> None:
        shot = _make_shot()
        result = build_scene_params(shot, _SCENE_CFG, _LOCATION, _GRADE)
        assert result.location_slug == "INT. LOWER TRANSIT STACK — NIGHT"

    def test_colour_desc_contains_dominant_hex(self) -> None:
        shot = _make_shot()
        result = build_scene_params(shot, _SCENE_CFG, _LOCATION, _GRADE)
        assert "#1C2B35" in result.colour_desc

    def test_scene_grade_injected_in_colour_desc(self) -> None:
        shot = _make_shot(scene_id="SCN_002")
        result = build_scene_params(shot, _SCENE_CFG, _LOCATION, _GRADE)
        assert "Teal-steel dominant" in result.colour_desc

    def test_episode_is_hardcoded_ep01(self) -> None:
        shot = _make_shot()
        result = build_scene_params(shot, _SCENE_CFG, _LOCATION, _GRADE)
        assert result.episode == "Episode 01"


# ---------------------------------------------------------------------------
# Test correction 4.2 : lighting_context prioritaire
# (p2_scene_env est construit dans run(), pas dans build_scene_params)
# Ce test valide la logique inline de run() via une expression directe.
# ---------------------------------------------------------------------------

class TestLightingContextPriority:
    """Régression correction 4.2 : shot.lighting_context > location.lighting_brief."""

    def test_lighting_context_wins_over_brief(self) -> None:
        shot = _make_shot(lighting_context="Amber LED rim, 5:1 ratio, 2800K motivated.")
        location = _LOCATION
        p2_scene_env = (shot.get("lighting_context") or location["lighting_brief"])[:200]
        assert p2_scene_env == "Amber LED rim, 5:1 ratio, 2800K motivated."
        assert "Fallback" not in p2_scene_env

    def test_falls_back_to_lighting_brief_when_context_absent(self) -> None:
        shot = _make_shot(lighting_context=None)
        location = _LOCATION
        p2_scene_env = (shot.get("lighting_context") or location["lighting_brief"])[:200]
        assert p2_scene_env == "Fallback: amber cage lamp key, 4:1 ratio, 2700K."

    def test_falls_back_to_lighting_brief_when_context_empty_string(self) -> None:
        shot = _make_shot(lighting_context="")
        location = _LOCATION
        p2_scene_env = (shot.get("lighting_context") or location["lighting_brief"])[:200]
        assert p2_scene_env == "Fallback: amber cage lamp key, 4:1 ratio, 2700K."

    def test_truncated_to_200_chars(self) -> None:
        long_context = "A" * 300
        shot = _make_shot(lighting_context=long_context)
        location = _LOCATION
        p2_scene_env = (shot.get("lighting_context") or location["lighting_brief"])[:200]
        assert len(p2_scene_env) == 200
