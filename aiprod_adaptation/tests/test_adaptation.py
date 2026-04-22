"""
pytest test suite — Adaptation Layer v1 + Story Engine (SE-01, SE-02, SE-05)

Covers:
  1. InputClassifier           — AL-01
  2. NullLLMAdapter            — AL-02
  3. ScriptParser              — AL-03
  4. NovelPipe                 — AL-04
  5. Engine routing            — AL-06
  6. StoryExtractor            — SE-01
  7. StoryValidator            — SE-02
  8. LLMRouter                 — SE-05
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

from aiprod_adaptation.core.adaptation.classifier import InputClassifier
from aiprod_adaptation.core.adaptation.llm_adapter import LLMAdapter, NullLLMAdapter
from aiprod_adaptation.core.adaptation.llm_router import LLMRouter
from aiprod_adaptation.core.adaptation.script_parser import ScriptParser
from aiprod_adaptation.core.adaptation.story_extractor import StoryExtractor, split_into_chunks
from aiprod_adaptation.core.adaptation.story_validator import StoryValidator
from aiprod_adaptation.core.engine import run_pipeline
from aiprod_adaptation.core.production_budget import ProductionBudget
from aiprod_adaptation.models.intermediate import VisualScene

# ---------------------------------------------------------------------------
# 1. InputClassifier
# ---------------------------------------------------------------------------

class TestInputClassifier:
    def setup_method(self) -> None:
        self.clf = InputClassifier()

    def test_novel_text_classified_as_novel(self) -> None:
        text = (
            "John walked quickly through the busy streets. "
            "He felt very excited about the important meeting."
        )
        assert self.clf.classify(text) == "novel"

    def test_script_int_classified_as_script(self) -> None:
        text = "INT. OFFICE - DAY\nJohn sits at his desk, staring at the screen."
        assert self.clf.classify(text) == "script"

    def test_script_fade_in_classified_as_script(self) -> None:
        text = "FADE IN:\nEXT. STREET - NIGHT\nRain falls heavily."
        assert self.clf.classify(text) == "script"


# ---------------------------------------------------------------------------
# 2. NullLLMAdapter
# ---------------------------------------------------------------------------

class TestNullLLMAdapter:
    def setup_method(self) -> None:
        self.adapter = NullLLMAdapter()

    def test_null_adapter_returns_dict(self) -> None:
        result = self.adapter.generate_json("any prompt")
        assert isinstance(result, dict)

    def test_null_adapter_is_deterministic(self) -> None:
        r1 = self.adapter.generate_json("same prompt")
        r2 = self.adapter.generate_json("same prompt")
        assert r1 == r2


# ---------------------------------------------------------------------------
# 3. ScriptParser
# ---------------------------------------------------------------------------

class TestScriptParser:
    def setup_method(self) -> None:
        self.parser = ScriptParser()

    _SIMPLE_SCRIPT = (
        "INT. OFFICE - DAY\n"
        "John sits at his desk.\n"
        "He picks up the phone.\n"
    )

    _MULTI_SCRIPT = (
        "INT. OFFICE - DAY\n"
        "John sits at his desk.\n"
        "\n"
        "EXT. STREET - NIGHT\n"
        "Sarah walks quickly.\n"
        "\n"
        "INT. APARTMENT - MORNING\n"
        "John paces around the room.\n"
    )

    def test_single_scene_parsed(self) -> None:
        scenes = self.parser.parse(self._SIMPLE_SCRIPT)
        assert len(scenes) == 1

    def test_character_extracted(self) -> None:
        script = "INT. OFFICE - DAY\nJOHN\nHe looks up.\n"
        scenes = self.parser.parse(script)
        assert "JOHN" in scenes[0]["characters"]

    def test_action_line_in_visual_actions(self) -> None:
        scenes = self.parser.parse(self._SIMPLE_SCRIPT)
        assert len(scenes[0]["visual_actions"]) > 0

    def test_multiple_scenes_ordered(self) -> None:
        scenes = self.parser.parse(self._MULTI_SCRIPT)
        assert len(scenes) == 3
        assert scenes[0]["scene_id"] == "SCN_001"
        assert scenes[1]["scene_id"] == "SCN_002"
        assert scenes[2]["scene_id"] == "SCN_003"

    def test_empty_script_returns_empty(self) -> None:
        scenes = self.parser.parse("")
        assert scenes == []


# ---------------------------------------------------------------------------
# 4. StoryExtractor — déterminisme (TestNovelPipe migré)
# ---------------------------------------------------------------------------

class TestStoryExtractorDeterminism:
    def test_novel_pipe_null_adapter_returns_list(self) -> None:
        result = StoryExtractor().extract(
            NullLLMAdapter(), "John walked into the room.", ProductionBudget.for_short()
        )
        assert isinstance(result, list)

    def test_novel_pipe_null_adapter_deterministic(self) -> None:
        text = "John walked into the room. He smiled at Sarah."
        r1 = StoryExtractor().extract(NullLLMAdapter(), text, ProductionBudget.for_short())
        r2 = StoryExtractor().extract(NullLLMAdapter(), text, ProductionBudget.for_short())
        assert r1 == r2


# ---------------------------------------------------------------------------
# 5. Engine routing
# ---------------------------------------------------------------------------

class TestEngineRouting:
    _NOVEL = (
        "John walked quickly through the busy city streets. "
        "He felt very excited about the important meeting. "
        "Sarah waited nervously inside the old wooden house."
    )

    _SCRIPT = (
        "INT. OFFICE - DAY\n"
        "John sits at his desk, staring at the screen.\n"
        "He picks up the phone and dials a number.\n"
        "\n"
        "EXT. STREET - NIGHT\n"
        "Sarah walks quickly, glancing over her shoulder.\n"
    )

    def test_novel_input_uses_rule_fallback(self) -> None:
        # NullLLMAdapter → empty scenes → rule-based fallback
        result = run_pipeline(self._NOVEL, "Novel Test")
        assert len(result.episodes[0].shots) > 0

    def test_script_input_produces_output(self) -> None:
        result = run_pipeline(self._SCRIPT, "Script Test")
        assert result.title == "Script Test"
        assert len(result.episodes) == 1

    def test_null_adapter_novel_byte_identical(self) -> None:
        import json
        r1 = run_pipeline(self._NOVEL, "T")
        r2 = run_pipeline(self._NOVEL, "T")
        assert json.dumps(r1.model_dump(), sort_keys=False) == \
               json.dumps(r2.model_dump(), sort_keys=False)


# ---------------------------------------------------------------------------
# 6. StoryExtractor — SE-01
# ---------------------------------------------------------------------------


class TestStoryExtractor:
    def test_extractor_returns_list(self) -> None:
        result = StoryExtractor().extract(
            NullLLMAdapter(), "John walked into the room.", ProductionBudget.for_short()
        )
        assert isinstance(result, list)

    def test_extractor_fallback_on_empty_llm_output(self) -> None:
        result = StoryExtractor().extract(
            NullLLMAdapter(), "any text", ProductionBudget.for_short()
        )
        assert result == []

    def test_extractor_single_call_not_three(self) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_json.return_value = {"scenes": []}
        StoryExtractor().extract(mock_llm, "text", ProductionBudget.for_short())
        assert mock_llm.generate_json.call_count == 1

    def test_extractor_respects_max_scenes_in_prompt(self) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_json.return_value = {"scenes": []}
        budget = ProductionBudget(max_scenes=7)
        StoryExtractor().extract(mock_llm, "text", budget)
        prompt = mock_llm.generate_json.call_args[0][0]
        assert "7" in prompt

    def test_extractor_prior_summary_injected_in_prompt(self) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_json.return_value = {"scenes": []}
        StoryExtractor().extract(
            mock_llm, "text", ProductionBudget.for_short(), prior_summary="PREV_CONTEXT"
        )
        prompt = mock_llm.generate_json.call_args[0][0]
        assert "PREV_CONTEXT" in prompt


# ---------------------------------------------------------------------------
# 7. StoryValidator — SE-02
# ---------------------------------------------------------------------------


class TestStoryValidator:
    def _make_scene(self, **kwargs: Any) -> VisualScene:
        d: dict[str, Any] = {
            "scene_id": "SCN_001",
            "characters": ["John"],
            "location": "the park",
            "time_of_day": None,
            "visual_actions": ["John walks toward the bench."],
            "dialogues": [],
            "emotion": "neutral",
        }
        d.update(kwargs)
        return cast(VisualScene, d)

    def test_valid_scene_scores_1_0(self) -> None:
        result = StoryValidator().validate(self._make_scene())
        assert result.score == 1.0
        assert result.is_valid is True

    def test_missing_location_detected(self) -> None:
        result = StoryValidator().validate(self._make_scene(location="Unknown"))
        assert "location_missing" in result.issues

    def test_internal_thought_detected(self) -> None:
        scene = self._make_scene(visual_actions=["John thought about the future."])
        result = StoryValidator().validate(scene)
        assert any("internal_thought" in i for i in result.issues)

    def test_impossible_action_detected(self) -> None:
        scene = self._make_scene(visual_actions=["John dreamed of flying over the city."])
        result = StoryValidator().validate(scene)
        assert any("impossible_action" in i for i in result.issues)

    def test_too_many_characters_detected(self) -> None:
        scene = self._make_scene(characters=["A", "B", "C"])
        result = StoryValidator().validate(scene)
        assert any("too_many_characters" in i for i in result.issues)

    def test_invalid_emotion_detected(self) -> None:
        scene = self._make_scene(emotion="confused")
        result = StoryValidator().validate(scene)
        assert any("invalid_emotion" in i for i in result.issues)

    def test_validate_all_filters_below_threshold(self) -> None:
        valid = self._make_scene()
        invalid = self._make_scene(
            scene_id="SCN_002",
            location="Unknown",
            visual_actions=[],
            emotion="bad",
            characters=["A", "B", "C"],
        )
        result = StoryValidator().validate_all([valid, invalid], threshold=0.5)
        assert len(result) == 1
        assert result[0]["scene_id"] == "SCN_001"

    def test_validate_all_returns_all_valid_scenes(self) -> None:
        s1 = self._make_scene(scene_id="SCN_001")
        s2 = self._make_scene(scene_id="SCN_002")
        result = StoryValidator().validate_all([s1, s2], threshold=0.5)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# 8. LLMRouter — SE-05
# ---------------------------------------------------------------------------


class TestLLMRouter:
    def test_router_uses_claude_for_short_input(self) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": []}
        gemini.generate_json.return_value = {"scenes": []}
        LLMRouter(claude, gemini, token_threshold=1000).generate_json("short text")
        assert claude.generate_json.call_count == 1
        assert gemini.generate_json.call_count == 0

    def test_router_uses_gemini_for_long_input(self) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": []}
        gemini.generate_json.return_value = {"scenes": []}
        LLMRouter(claude, gemini, token_threshold=1).generate_json("x" * 100)
        assert gemini.generate_json.call_count == 1
        assert claude.generate_json.call_count == 0

    def test_router_threshold_boundary(self) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": []}
        gemini.generate_json.return_value = {"scenes": []}
        # 4 chars // 4 = 1 token == threshold → claude
        LLMRouter(claude, gemini, token_threshold=1).generate_json("abcd")
        assert claude.generate_json.call_count == 1

    def test_router_custom_threshold(self) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": []}
        gemini.generate_json.return_value = {"scenes": []}
        # 1000 chars // 4 = 250 <= 500 → claude
        LLMRouter(claude, gemini, token_threshold=500).generate_json("a" * 1000)
        assert claude.generate_json.call_count == 1

    def test_router_null_adapters_both_paths(self) -> None:
        router_short = LLMRouter(NullLLMAdapter(), NullLLMAdapter(), token_threshold=1000)
        assert router_short.generate_json("x") == {"scenes": []}
        router_long = LLMRouter(NullLLMAdapter(), NullLLMAdapter(), token_threshold=1)
        assert router_long.generate_json("x" * 100) == {"scenes": []}


# ---------------------------------------------------------------------------
# 9. split_into_chunks + ProductionBudget.max_chars_per_chunk (SO-01, SO-02)
# ---------------------------------------------------------------------------

class TestSplitIntoChunks:
    def test_split_into_chunks_respects_max_chars(self) -> None:
        text = "\n\n".join(["x" * 100] * 20)
        chunks = split_into_chunks(text, max_chars=300)
        assert all(len(c) <= 300 for c in chunks)

    def test_split_into_chunks_splits_at_paragraph_boundaries(self) -> None:
        text = "paragraph one.\n\nparagraph two.\n\nparagraph three."
        chunks = split_into_chunks(text, max_chars=20)
        # each paragraph is ~14-16 chars < 20 → each lands in its own chunk
        assert len(chunks) == 3

    def test_split_into_chunks_single_paragraph_truncated(self) -> None:
        long_para = "A very long sentence. " * 100
        chunks = split_into_chunks(long_para, max_chars=200)
        assert all(len(c) <= 200 for c in chunks)
        assert len(chunks) >= 1

    def test_split_into_chunks_empty_text_returns_empty_list(self) -> None:
        assert split_into_chunks("", max_chars=1000) == []
        assert split_into_chunks("   \n\n  ", max_chars=1000) == []

    def test_extract_all_single_chunk_equivalent_to_extract(self) -> None:
        extractor = StoryExtractor()
        budget = ProductionBudget(max_chars_per_chunk=100_000)
        text = "Alice walks in the park. She sits on the bench."
        result_extract = extractor.extract(NullLLMAdapter(), text, budget)
        result_all = extractor.extract_all(NullLLMAdapter(), text, budget)
        assert result_extract == result_all

    def test_extract_all_multiple_chunks_passes_prior_summary(self) -> None:
        received_prompts: list[str] = []

        class TrackingLLM(NullLLMAdapter):
            def generate_json(self, prompt: str) -> dict[str, object]:
                received_prompts.append(prompt)
                # Return a minimal scene so prior_summary gets populated
                return {"scenes": [{"location": "Park", "description": "test",
                                    "mood": "neutral", "characters": []}]}

        # Force 3 chunks by setting a tiny max_chars_per_chunk
        text = (
            "First paragraph with content here."
            "\n\nSecond paragraph with content."
            "\n\nThird paragraph here."
        )
        budget = ProductionBudget(max_chars_per_chunk=40)
        StoryExtractor().extract_all(TrackingLLM(), text, budget)
        # From chunk 2 onwards, prompt should contain prior_summary context
        assert any("CONTEXT FROM PREVIOUS SCENES" in p for p in received_prompts[1:])


class TestProductionBudgetChunk:
    def test_budget_default_max_chars_per_chunk(self) -> None:
        assert ProductionBudget().max_chars_per_chunk == 8_000

    def test_budget_for_episode_45_has_larger_chunk(self) -> None:
        assert ProductionBudget.for_episode_45().max_chars_per_chunk > 8_000

    def test_extract_all_respects_budget_max_chars(self) -> None:
        received_texts: list[str] = []

        class TrackingLLM(NullLLMAdapter):
            def generate_json(self, prompt: str) -> dict[str, object]:
                received_texts.append(prompt)
                return {"scenes": []}

        text = "\n\n".join(["word " * 20] * 10)  # ~10 paragraphs
        budget = ProductionBudget(max_chars_per_chunk=200)
        StoryExtractor().extract_all(TrackingLLM(), text, budget)
        # Each LLM call prompt ends with "TEXT:\n{chunk}", chunk must be <= 200 chars
        for p in received_texts:
            chunk = p.split("TEXT:\n")[-1] if "TEXT:\n" in p else ""
            assert len(chunk) <= 200

    def test_budget_frozen_dataclass_max_chars_immutable(self) -> None:
        budget = ProductionBudget()
        mutable: Any = budget
        try:
            mutable.max_chars_per_chunk = 999
            assert False, "Should have raised"
        except Exception:
            pass


# ---------------------------------------------------------------------------
# PC-08 — LLM router completeness
# ---------------------------------------------------------------------------

class TestLLMRouterCompleteness:
    def test_llm_router_calls_extract_all_not_extract(self) -> None:
        from aiprod_adaptation.core.adaptation.llm_adapter import NullLLMAdapter
        from aiprod_adaptation.core.adaptation.story_extractor import StoryExtractor
        from aiprod_adaptation.core.production_budget import ProductionBudget
        extract_all_called = [False]
        extract_called = [False]

        class TrackingExtractor(StoryExtractor):
            def extract(
                self, llm: LLMAdapter, text: str, budget: ProductionBudget,
                prior_summary: str = "",
            ) -> list[VisualScene]:
                extract_called[0] = True
                return super().extract(llm, text, budget, prior_summary)
            def extract_all(
                self, llm: LLMAdapter, text: str, budget: ProductionBudget,
            ) -> list[VisualScene]:
                extract_all_called[0] = True
                return super().extract_all(llm, text, budget)

        text = "Alice walked in the park. She sat on a bench."
        budget = ProductionBudget()
        TrackingExtractor().extract_all(NullLLMAdapter(), text, budget)
        assert extract_all_called[0] is True

    def test_llm_router_passes_budget_to_extractor(self) -> None:
        from aiprod_adaptation.core.adaptation.llm_adapter import NullLLMAdapter
        from aiprod_adaptation.core.adaptation.story_extractor import StoryExtractor
        from aiprod_adaptation.core.production_budget import ProductionBudget
        received_budgets: list[object] = []

        class TrackingExtractor(StoryExtractor):
            def extract_chunk(
                self, llm: LLMAdapter, text: str, budget: ProductionBudget,
                prior_summary: str = "",
            ) -> list[VisualScene]:
                received_budgets.append(budget)
                return super().extract_chunk(llm, text, budget, prior_summary)

        budget = ProductionBudget(max_chars_per_chunk=500)
        text = "Alice walked in the park. She sat on a bench."
        TrackingExtractor().extract_all(NullLLMAdapter(), text, budget)
        assert all(b is budget for b in received_budgets)

    def test_llm_router_is_llm_adapter(self) -> None:
        from aiprod_adaptation.core.adaptation.llm_adapter import LLMAdapter, NullLLMAdapter
        from aiprod_adaptation.core.adaptation.llm_router import LLMRouter
        router = LLMRouter(claude=NullLLMAdapter(), gemini=NullLLMAdapter())
        assert isinstance(router, LLMAdapter)

    def test_engine_uses_extract_all_with_llm(self) -> None:
        from aiprod_adaptation.core.adaptation.llm_adapter import NullLLMAdapter
        from aiprod_adaptation.core.engine import run_pipeline
        from aiprod_adaptation.core.production_budget import ProductionBudget
        text = "Alice walked in the park. She sat on a bench."
        output = run_pipeline(text, "T", llm=NullLLMAdapter(), budget=ProductionBudget())
        assert output is not None


# ---------------------------------------------------------------------------
# TA04 — engine raises when StoryValidator filters all scenes
# ---------------------------------------------------------------------------

class TestEngineStoryValidatorAllFiltered:
    def test_engine_raises_when_story_validator_filters_all_scenes(self) -> None:
        from unittest.mock import patch

        import pytest

        with patch(
            "aiprod_adaptation.core.adaptation.story_validator.StoryValidator.validate_all",
            return_value=[],
        ):
            with pytest.raises(ValueError, match="StoryValidator produced no filmable scenes"):
                run_pipeline("John walked into the room.", "T")
