"""
pytest test suite — Continuity Engine v1

Covers:
  1. CharacterRegistry  — CE-01
  2. EmotionArcTracker  — CE-02
  3. PromptEnricher     — CE-03
  4. Engine integration — CE-04
"""

from __future__ import annotations

import json

from aiprod_adaptation.core.continuity.character_registry import CharacterRegistry
from aiprod_adaptation.core.continuity.emotion_arc import EmotionArcTracker
from aiprod_adaptation.core.continuity.prompt_enricher import PromptEnricher
from aiprod_adaptation.core.engine import run_pipeline


# ---------------------------------------------------------------------------
# Helpers — minimal AIPRODOutput fixtures
# ---------------------------------------------------------------------------

def _make_output(characters_per_scene: list[list[str]], emotions: list[str]):
    """Build a minimal AIPRODOutput for testing."""
    from aiprod_adaptation.models.schema import AIPRODOutput, Episode, Scene, Shot

    scenes = [
        Scene(
            scene_id=f"SC{i+1:03d}",
            characters=chars,
            location="a room",
            time_of_day=None,
            visual_actions=["someone stands."],
            dialogues=[],
            emotion=emotions[i] if i < len(emotions) else "neutral",
        )
        for i, chars in enumerate(characters_per_scene)
    ]
    shots = [
        Shot(
            shot_id=f"SH{i+1:04d}",
            scene_id=f"SC{i+1:03d}",
            prompt="someone stands, in a room.",
            duration_sec=4,
            emotion=emotions[i] if i < len(emotions) else "neutral",
        )
        for i in range(len(characters_per_scene))
    ]
    episode = Episode(episode_id="EP01", scenes=scenes, shots=shots)
    return AIPRODOutput(title="Test", episodes=[episode])


# ---------------------------------------------------------------------------
# 1. CharacterRegistry
# ---------------------------------------------------------------------------

class TestCharacterRegistry:
    def setup_method(self) -> None:
        self.reg = CharacterRegistry()

    def test_registry_extracts_all_characters(self) -> None:
        output = _make_output([["John"], ["Sarah"]], ["neutral", "neutral"])
        registry = self.reg.build(output)
        assert "John" in registry
        assert "Sarah" in registry
        assert len(registry) == 2

    def test_registry_deduplicates_characters(self) -> None:
        output = _make_output([["John"], ["John"]], ["neutral", "neutral"])
        registry = self.reg.build(output)
        assert len(registry) == 1
        assert registry["John"]["name"] == "John"

    def test_registry_tracks_all_scenes(self) -> None:
        output = _make_output([["John"], ["John"], ["John"]], ["neutral"] * 3)
        registry = self.reg.build(output)
        assert len(registry["John"]["scenes"]) == 3

    def test_registry_empty_output_returns_empty(self) -> None:
        output = _make_output([], [])
        registry = self.reg.build(output)
        assert registry == {}

    def test_enrich_from_text_updates_description(self) -> None:
        output = _make_output([["John"]], ["neutral"])
        registry = self.reg.build(output)
        registry = self.reg.enrich_from_text(registry, {"John": "30s, dark hair, blue jacket"})
        assert registry["John"]["description"] == "30s, dark hair, blue jacket"


# ---------------------------------------------------------------------------
# 2. EmotionArcTracker
# ---------------------------------------------------------------------------

class TestEmotionArcTracker:
    def setup_method(self) -> None:
        self.tracker = EmotionArcTracker()

    def test_arc_tracks_all_shots_in_order(self) -> None:
        output = _make_output([["John"], ["John"], ["John"]], ["neutral", "joy", "fear"])
        states = self.tracker.track(output)
        assert len(states) == 3
        assert states[0]["emotion"] == "neutral"
        assert states[1]["emotion"] == "joy"
        assert states[2]["emotion"] == "fear"

    def test_arc_first_shot_has_no_previous(self) -> None:
        output = _make_output([["John"]], ["neutral"])
        states = self.tracker.track(output)
        assert "previous" not in states[0]

    def test_arc_detects_abrupt_transition(self) -> None:
        output = _make_output([["John"], ["John"]], ["fear", "joy"])
        states = self.tracker.track(output)
        assert states[1]["transition_ok"] is False

    def test_arc_accepts_smooth_transition(self) -> None:
        output = _make_output([["John"], ["John"]], ["neutral", "joy"])
        states = self.tracker.track(output)
        assert states[1]["transition_ok"] is True

    def test_arc_get_warnings_returns_messages(self) -> None:
        output = _make_output([["John"], ["John"]], ["fear", "joy"])
        states = self.tracker.track(output)
        warnings = self.tracker.get_warnings(states)
        assert len(warnings) == 1
        assert "fear" in warnings[0]
        assert "joy" in warnings[0]


# ---------------------------------------------------------------------------
# 3. PromptEnricher
# ---------------------------------------------------------------------------

class TestPromptEnricher:
    def setup_method(self) -> None:
        self.enricher = PromptEnricher()
        self.reg_builder = CharacterRegistry()
        self.tracker = EmotionArcTracker()

    def _enriched(self, descriptions: dict[str, str], emotions: list[str]) -> str:
        output = _make_output([list(descriptions.keys())], emotions)
        registry = self.reg_builder.build(output)
        registry = self.reg_builder.enrich_from_text(registry, descriptions)
        arc_states = self.tracker.track(output)
        enriched = self.enricher.enrich(output, registry, arc_states)
        return enriched.episodes[0].shots[0].prompt

    def test_enrich_injects_character_description(self) -> None:
        prompt = self._enriched({"John": "30s, dark hair, blue jacket"}, ["neutral"])
        assert "30s, dark hair, blue jacket" in prompt

    def test_enrich_skips_empty_description(self) -> None:
        output = _make_output([["John"]], ["neutral"])
        registry = self.reg_builder.build(output)
        arc_states = self.tracker.track(output)
        enriched = self.enricher.enrich(output, registry, arc_states)
        # No description → prompt unchanged
        assert enriched.episodes[0].shots[0].prompt == output.episodes[0].shots[0].prompt

    def test_enrich_is_deterministic(self) -> None:
        output = _make_output([["John"]], ["neutral"])
        registry = self.reg_builder.build(output)
        registry = self.reg_builder.enrich_from_text(registry, {"John": "30s, dark hair"})
        arc_states = self.tracker.track(output)
        r1 = self.enricher.enrich(output, registry, arc_states)
        r2 = self.enricher.enrich(output, registry, arc_states)
        assert json.dumps(r1.model_dump(), sort_keys=False) == \
               json.dumps(r2.model_dump(), sort_keys=False)

    def test_enrich_does_not_mutate_input(self) -> None:
        output = _make_output([["John"]], ["neutral"])
        original_prompt = output.episodes[0].shots[0].prompt
        registry = self.reg_builder.build(output)
        registry = self.reg_builder.enrich_from_text(registry, {"John": "30s, dark hair"})
        arc_states = self.tracker.track(output)
        self.enricher.enrich(output, registry, arc_states)
        assert output.episodes[0].shots[0].prompt == original_prompt


# ---------------------------------------------------------------------------
# 4. Engine integration
# ---------------------------------------------------------------------------

_NOVEL = (
    "John walked quickly through the busy city streets. "
    "He felt very excited about the important meeting. "
    "Sarah waited nervously inside the old wooden house."
)


class TestEngineWithContinuity:
    def test_engine_without_continuity_unchanged(self) -> None:
        r1 = run_pipeline(_NOVEL, "T")
        r2 = run_pipeline(_NOVEL, "T", character_descriptions=None)
        assert json.dumps(r1.model_dump(), sort_keys=False) == \
               json.dumps(r2.model_dump(), sort_keys=False)

    def test_engine_with_descriptions_enriches_prompts(self) -> None:
        result = run_pipeline(
            _NOVEL,
            "T",
            character_descriptions={"Sarah": "40s, red hair, grey coat"},
        )
        prompts = [s.prompt for ep in result.episodes for s in ep.shots]
        # At least one prompt should contain the injected description
        assert any("red hair" in p for p in prompts)


# ---------------------------------------------------------------------------
# PC-04 — LocationRegistry + PropRegistry
# ---------------------------------------------------------------------------

class TestLocationRegistry:
    def test_location_registry_builds_from_output(self) -> None:
        from aiprod_adaptation.core.continuity.location_registry import LocationRegistry
        output = run_pipeline(_NOVEL, "T")
        reg = LocationRegistry().build_from_output(output)
        locations = {sc.location for ep in output.episodes for sc in ep.scenes}
        for loc in locations:
            hint = reg.get_prompt_hint(loc)
            assert hint != ""

    def test_location_registry_get_prompt_hint_contains_location_name(self) -> None:
        from aiprod_adaptation.core.continuity.location_registry import LocationRegistry
        output = run_pipeline(_NOVEL, "T")
        reg = LocationRegistry().build_from_output(output)
        loc = output.episodes[0].scenes[0].location
        hint = reg.get_prompt_hint(loc)
        assert "LOCATION CONTEXT" in hint

    def test_location_registry_unknown_location_returns_empty(self) -> None:
        from aiprod_adaptation.core.continuity.location_registry import LocationRegistry
        reg = LocationRegistry()
        assert reg.get_prompt_hint("nonexistent place") == ""


class TestPropRegistry:
    def test_prop_registry_register_and_retrieve(self) -> None:
        from aiprod_adaptation.core.continuity.prop_registry import PropRegistry
        reg = PropRegistry()
        reg.register("sword", "S001", held_by="Alice", description="silver sword")
        props = reg.get_active_props_for_character("Alice")
        assert len(props) == 1
        assert props[0].name == "sword"

    def test_prop_registry_get_active_props_for_character(self) -> None:
        from aiprod_adaptation.core.continuity.prop_registry import PropRegistry
        reg = PropRegistry()
        reg.register("book", "S001", held_by="Alice")
        reg.register("lamp", "S001", held_by="Bob")
        assert len(reg.get_active_props_for_character("Alice")) == 1
        assert len(reg.get_active_props_for_character("Bob")) == 1
        assert len(reg.get_active_props_for_character("Charlie")) == 0

    def test_prop_registry_get_prompt_hint_contains_prop_name(self) -> None:
        from aiprod_adaptation.core.continuity.prop_registry import PropRegistry
        reg = PropRegistry()
        reg.register("torch", "S001", held_by="Alice")
        hint = reg.get_prompt_hint("S001")
        assert "PROPS IN SCENE" in hint
        assert "torch" in hint


class TestPromptEnricherWithLocationAndProp:
    def test_prompt_enricher_injects_location_hint(self) -> None:
        from aiprod_adaptation.core.continuity.location_registry import LocationRegistry
        from aiprod_adaptation.core.continuity.prompt_enricher import PromptEnricher
        output = run_pipeline(_NOVEL, "T")
        reg = LocationRegistry().build_from_output(output)
        enriched = PromptEnricher().enrich(output, {}, [], location_registry=reg)
        prompts = [s.prompt for ep in enriched.episodes for s in ep.shots]
        assert any("LOCATION CONTEXT" in p for p in prompts)

    def test_prompt_enricher_injects_prop_hint(self) -> None:
        from aiprod_adaptation.core.continuity.prop_registry import PropRegistry
        from aiprod_adaptation.core.continuity.prompt_enricher import PromptEnricher
        output = run_pipeline(_NOVEL, "T")
        prop_reg = PropRegistry()
        first_shot_id = output.episodes[0].shots[0].shot_id
        prop_reg.register("lantern", first_shot_id, held_by="Alice")
        enriched = PromptEnricher().enrich(output, {}, [], prop_registry=prop_reg)
        prompts = [s.prompt for ep in enriched.episodes for s in ep.shots]
        assert any("PROPS IN SCENE" in p for p in prompts)
