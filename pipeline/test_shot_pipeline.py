"""
pipeline/test_shot_pipeline.py
=================================
Tests de non-régression — pipeline hybride v2 (shot_pipeline.py).
Zéro appel API — tests unitaires purs sur les constructeurs de prompts.

Couvre :
  - SceneP1Params : defaults, __post_init__ validation, canonical par personnage
  - build_p1_prompt() : structure JSON, ordre des clés, dramatic_intent en premier
  - build_p2_prompt() : nom personnage, canonical, zéro hardcoding Nara
"""
from __future__ import annotations

import json

import pytest

from pipeline.shot_pipeline import (
    LOCKED_NARA_CANONICAL,
    SceneP1Params,
    build_p1_prompt,
    build_p2_prompt,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

VALE_CANONICAL = (
    "Male supporting character, lean athletic build, sharp defined features. "
    "Close-cropped dark hair, angular jawline. Focused dark eyes, no expression. "
    "Dark grey technical shirt, matte-black tactical trousers, no insignia."
)


def _make_params(**kwargs) -> SceneP1Params:
    defaults: dict = dict(
        scene_id="SCN_TEST",
        episode="Episode 01",
        location_slug="INT. TEST CORRIDOR — NIGHT",
        location_desc="Industrial corridor, wet concrete, cage lamps.",
        lighting_desc="Key: amber cage lamp, 4:1 ratio, 2700K.",
        colour_desc="Dominant: deep teal-steel. Grade: desaturated, crushed blacks.",
        composition="Subject centred, deep vanishing point.",
        subject_action="stands still, scanning the corridor.",
        seed=42,
    )
    defaults.update(kwargs)
    return SceneP1Params(**defaults)


# ---------------------------------------------------------------------------
# SceneP1Params
# ---------------------------------------------------------------------------

class TestSceneP1Params:
    def test_default_canonical_is_nara(self) -> None:
        p = _make_params()
        assert p.character_canonical == LOCKED_NARA_CANONICAL

    def test_custom_canonical_overrides_nara(self) -> None:
        p = _make_params(character_canonical=VALE_CANONICAL)
        assert p.character_canonical == VALE_CANONICAL
        assert p.character_canonical != LOCKED_NARA_CANONICAL

    def test_vale_canonical_different_from_nara(self) -> None:
        """Régression correction 1.1 : Vale ne reçoit pas le canonical de Nara."""
        p_nara = _make_params()
        p_vale = _make_params(character_canonical=VALE_CANONICAL)
        assert p_nara.character_canonical != p_vale.character_canonical

    def test_default_seed(self) -> None:
        p = _make_params()
        assert p.seed == 42

    def test_default_emotion_intent_is_empty(self) -> None:
        p = _make_params()
        assert p.emotion_intent == ""

    def test_emotion_intent_set(self) -> None:
        p = _make_params(emotion_intent="Dread — she knows too much.")
        assert p.emotion_intent == "Dread — she knows too much."

    def test_post_init_raises_on_empty_scene_id(self) -> None:
        with pytest.raises(ValueError, match="scene_id"):
            _make_params(scene_id="")

    def test_post_init_raises_on_empty_canonical(self) -> None:
        with pytest.raises(ValueError, match="character_canonical"):
            _make_params(character_canonical="")

    def test_locked_fields_not_in_constructor(self) -> None:
        """locked_dop_ref et locked_camera sont init=False : vérifier qu'ils existent."""
        p = _make_params()
        assert "Deakins" in p.locked_dop_ref
        assert "ARRI Alexa 35" in p.locked_camera


# ---------------------------------------------------------------------------
# build_p1_prompt()
# ---------------------------------------------------------------------------

class TestBuildP1Prompt:
    def test_returns_valid_json(self) -> None:
        p = _make_params()
        prompt = build_p1_prompt(p)
        doc = json.loads(prompt)
        assert isinstance(doc, dict)

    def test_required_keys_present(self) -> None:
        p = _make_params()
        doc = json.loads(build_p1_prompt(p))
        for key in (
            "production_note", "location", "lighting_design",
            "colour_grade_intent", "composition", "technical_quality", "subject",
        ):
            assert key in doc, f"Clé obligatoire manquante : '{key}'"

    def test_subject_contains_nara_canonical_by_default(self) -> None:
        p = _make_params()
        doc = json.loads(build_p1_prompt(p))
        assert doc["subject"]["costume"] == LOCKED_NARA_CANONICAL

    def test_vale_canonical_injected_in_subject(self) -> None:
        """Régression correction 1.1 : le canonical de Vale est bien dans subject."""
        p = _make_params(character_canonical=VALE_CANONICAL)
        doc = json.loads(build_p1_prompt(p))
        assert doc["subject"]["costume"] == VALE_CANONICAL

    def test_emotion_intent_is_first_key_when_set(self) -> None:
        """Régression correction B-2 : dramatic_intent doit être la première clé."""
        p = _make_params(emotion_intent="Dread — she knows too much.")
        doc = json.loads(build_p1_prompt(p))
        keys = list(doc.keys())
        assert keys[0] == "dramatic_intent"
        assert doc["dramatic_intent"] == "Dread — she knows too much."

    def test_no_dramatic_intent_key_when_emotion_empty(self) -> None:
        p = _make_params(emotion_intent="")
        doc = json.loads(build_p1_prompt(p))
        assert "dramatic_intent" not in doc

    def test_production_note_contains_scene_id(self) -> None:
        p = _make_params(scene_id="SCN_002")
        doc = json.loads(build_p1_prompt(p))
        assert "SCN_002" in doc["production_note"]

    def test_technical_quality_key_present_and_nonempty(self) -> None:
        p = _make_params()
        doc = json.loads(build_p1_prompt(p))
        assert len(doc["technical_quality"]) > 50

    def test_seed_has_no_effect_on_prompt_content(self) -> None:
        """La seed ne doit pas apparaître dans le prompt (elle est un paramètre API)."""
        p = _make_params(seed=99999)
        doc = json.loads(build_p1_prompt(p))
        assert "99999" not in json.dumps(doc)


# ---------------------------------------------------------------------------
# build_p2_prompt()
# ---------------------------------------------------------------------------

class TestBuildP2Prompt:
    def test_default_character_is_nara(self) -> None:
        result = build_p2_prompt("Dark industrial corridor.", "walks forward.")
        assert "Nara Voss" in result

    def test_vale_name_in_prompt(self) -> None:
        """Régression correction 1.1 : Vale reçoit son propre nom."""
        result = build_p2_prompt(
            "Service spine, amber practicals.",
            "pauses, checking display.",
            character_name="Vale Chen",
        )
        assert "Vale Chen" in result

    def test_vale_canonical_in_prompt(self) -> None:
        result = build_p2_prompt(
            "Service spine.",
            "pauses.",
            character_name="Vale Chen",
            character_canonical=VALE_CANONICAL,
        )
        assert VALE_CANONICAL in result

    def test_nara_canonical_not_in_vale_prompt(self) -> None:
        """Régression critique : le canonical de Nara ne doit pas contaminer Vale."""
        result = build_p2_prompt(
            "Service spine.",
            "pauses.",
            character_name="Vale Chen",
            character_canonical=VALE_CANONICAL,
        )
        assert LOCKED_NARA_CANONICAL not in result

    def test_nara_name_not_in_vale_prompt(self) -> None:
        result = build_p2_prompt(
            "Service spine.",
            "pauses.",
            character_name="Vale Chen",
            character_canonical=VALE_CANONICAL,
        )
        assert "Nara Voss" not in result

    def test_scene_env_in_prompt(self) -> None:
        result = build_p2_prompt("Amber cage lamp corridor.", "stands still.")
        assert "Amber cage lamp corridor." in result
