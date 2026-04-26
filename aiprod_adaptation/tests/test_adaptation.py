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

import os
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from aiprod_adaptation.core.adaptation.classifier import InputClassifier
from aiprod_adaptation.core.adaptation.llm_adapter import (
    LLMAdapter,
    LLMFailureCategory,
    LLMProviderError,
    NullLLMAdapter,
)
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


class TestProviderAdapters:
    def test_gemini_adapter_defaults_to_flash_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "dummy")

        from aiprod_adaptation.core.adaptation.gemini_adapter import GeminiAdapter

        adapter = GeminiAdapter()

        assert adapter._model == "gemini-2.5-flash"
        assert adapter._fallback_models == (
            "gemini-2.5-flash-lite",
            "gemini-flash-lite-latest",
        )

    def test_gemini_adapter_uses_deterministic_json_config(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "dummy")

        from aiprod_adaptation.core.adaptation.gemini_adapter import GeminiAdapter

        adapter = GeminiAdapter()
        seen: dict[str, object] = {}

        class _Response:
            text = '{"scenes": []}'

        class _CapturingModels:
            def generate_content(
                self,
                *,
                model: str,
                contents: str,
                config: object,
            ) -> _Response:
                seen["model"] = model
                seen["contents"] = contents
                seen["config"] = config
                return _Response()

        class _CapturingClient:
            models = _CapturingModels()

        adapter._client = _CapturingClient()

        assert adapter.generate_json("prompt") == {"scenes": []}
        assert seen["model"] == "gemini-2.5-flash"
        assert seen["contents"] == "prompt"
        config = seen["config"]
        assert getattr(config, "temperature") == 0.0
        assert getattr(config, "candidate_count") == 1
        assert getattr(config, "seed") == 0
        assert getattr(config, "response_mime_type") == "application/json"

    def test_gemini_adapter_retries_transient_error_then_succeeds(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "dummy")

        from aiprod_adaptation.core.adaptation.gemini_adapter import GeminiAdapter

        adapter = GeminiAdapter()
        adapter._retry_delay_sec = 0.0
        calls = {"count": 0}

        class _Response:
            text = '{"scenes": []}'

        class _RetryingModels:
            def generate_content(self, **_kwargs: object) -> _Response:
                calls["count"] += 1
                if calls["count"] == 1:
                    raise RuntimeError("503 UNAVAILABLE high demand, try again later")
                return _Response()

        class _RetryingClient:
            models = _RetryingModels()

        adapter._client = _RetryingClient()

        assert adapter.generate_json("prompt") == {"scenes": []}
        assert calls["count"] == 2

    def test_gemini_adapter_falls_back_to_secondary_model(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "dummy")

        from aiprod_adaptation.core.adaptation.gemini_adapter import GeminiAdapter

        adapter = GeminiAdapter()
        adapter._retry_delay_sec = 0.0
        seen_models: list[str] = []

        class _Response:
            text = '{"scenes": []}'

        class _FallbackModels:
            def generate_content(self, *, model: str, **_kwargs: object) -> _Response:
                seen_models.append(model)
                if model == "gemini-2.5-flash":
                    raise RuntimeError("503 UNAVAILABLE high demand")
                return _Response()

        class _FallbackClient:
            models = _FallbackModels()

        adapter._client = _FallbackClient()

        assert adapter.generate_json("prompt") == {"scenes": []}
        assert seen_models[0] == "gemini-2.5-flash"
        assert seen_models[-1] == "gemini-2.5-flash-lite"

    def test_gemini_adapter_raises_provider_error_on_request_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "dummy")

        from aiprod_adaptation.core.adaptation.gemini_adapter import GeminiAdapter

        adapter = GeminiAdapter()
        adapter._fallback_models = ()

        class _FailingModels:
            def generate_content(self, **_kwargs: object) -> dict[str, str]:
                raise RuntimeError("quota exceeded")

        class _FailingClient:
            models = _FailingModels()

        adapter._client = _FailingClient()

        with pytest.raises(
            LLMProviderError,
            match=(
                r"Gemini request failed across all configured models: "
                r"Gemini request failed \(gemini-2.5-flash\): quota exceeded"
            ),
        ) as exc_info:
            adapter.generate_json("prompt")

        assert exc_info.value.category == LLMFailureCategory.QUOTA
        assert len(exc_info.value.failures) == 1
        assert exc_info.value.failures[0].category == LLMFailureCategory.QUOTA

    def test_claude_adapter_raises_provider_error_on_request_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")

        from aiprod_adaptation.core.adaptation.claude_adapter import ClaudeAdapter

        adapter = ClaudeAdapter()

        class _FailingMessages:
            def create(self, **_kwargs: object) -> dict[str, str]:
                raise RuntimeError("unauthorized: invalid api key")

        class _FailingClient:
            messages = _FailingMessages()

        adapter._client = _FailingClient()

        with pytest.raises(
            LLMProviderError,
            match="Claude request failed: unauthorized: invalid api key",
        ) as exc_info:
            adapter.generate_json("prompt")

        assert exc_info.value.category == LLMFailureCategory.AUTH

    def test_gemini_adapter_marks_json_decode_error_as_schema_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "dummy")

        from aiprod_adaptation.core.adaptation.gemini_adapter import GeminiAdapter

        adapter = GeminiAdapter()
        adapter._fallback_models = ()

        class _MalformedResponse:
            text = '{"scenes": [}]'

        class _MalformedModels:
            def generate_content(self, **_kwargs: object) -> _MalformedResponse:
                return _MalformedResponse()

        class _MalformedClient:
            models = _MalformedModels()

        adapter._client = _MalformedClient()

        with pytest.raises(
            LLMProviderError,
            match="Gemini request failed across all configured models",
        ) as exc_info:
            adapter.generate_json("prompt")

        assert exc_info.value.category == LLMFailureCategory.SCHEMA
        assert exc_info.value.failures[0].category == LLMFailureCategory.SCHEMA


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

    def test_direction_lines_are_not_treated_as_characters(self) -> None:
        script = (
            "INT. OFFICE - DAY\n"
            "WIDE SHOT\n"
            "JOHN\n"
            "He looks up.\n"
            "CUT TO:\n"
        )

        scenes = self.parser.parse(script)

        assert scenes[0]["characters"] == ["JOHN"]
        assert "WIDE SHOT" not in scenes[0]["visual_actions"]
        assert "CUT TO:" not in scenes[0]["visual_actions"]

    def test_dialogue_line_after_character_cue_goes_to_dialogues(self) -> None:
        script = "INT. OFFICE - DAY\nJOHN\nWe need to leave now.\n"

        scenes = self.parser.parse(script)

        assert scenes[0]["characters"] == ["JOHN"]
        assert scenes[0]["dialogues"] == ["We need to leave now."]
        assert "We need to leave now." not in scenes[0]["visual_actions"]

    def test_direction_prefix_line_is_ignored(self) -> None:
        script = (
            "INT. OFFICE - DAY\n"
            "INSERT SHOT - WRIST DISPLAY\n"
            "John checks the map.\n"
        )

        scenes = self.parser.parse(script)

        assert scenes[0]["visual_actions"] == ["John checks the map."]

    def test_scene_heading_extracts_time_of_day(self) -> None:
        scenes = self.parser.parse("EXT. STREET - NIGHT\nJohn runs.\n")

        assert scenes[0]["time_of_day"] == "night"

    def test_uppercase_ambience_line_is_not_treated_as_character_cue(self) -> None:
        script = (
            "INT. MARKET - DAY\n"
            "LOW LIGHT, HANDHELD FEEL\n"
            "Crowds push through the corridor.\n"
        )

        scenes = self.parser.parse(script)

        assert scenes[0]["characters"] == []
        assert scenes[0]["dialogues"] == []
        assert scenes[0]["visual_actions"] == ["Crowds push through the corridor."]

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

    def test_deterministic_mode_skips_llm_novel_extraction(self) -> None:
        from unittest.mock import patch

        with patch(
            "aiprod_adaptation.core.adaptation.story_extractor.StoryExtractor.extract_all"
        ) as extract_all:
            result = run_pipeline(
                self._NOVEL,
                "Deterministic Mode",
                llm=MagicMock(),
                pipeline_mode="deterministic",
            )

        assert len(result.episodes[0].shots) > 0
        extract_all.assert_not_called()

    def test_generative_mode_requires_non_null_llm_adapter(self) -> None:
        with pytest.raises(
            ValueError,
            match="Generative mode requires a non-null LLM adapter",
        ):
            run_pipeline(
                self._NOVEL,
                "Generative Mode",
                pipeline_mode="generative",
            )

    def test_generative_mode_with_script_input_still_uses_script_parser(self) -> None:
        result = run_pipeline(
            self._SCRIPT,
            "Script Generative Mode",
            pipeline_mode="generative",
        )
        assert result.title == "Script Generative Mode"
        assert len(result.episodes[0].scenes) >= 1


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
    @pytest.mark.parametrize(
        ("prompt", "token_threshold", "short_preference", "expected_provider"),
        [
            ("short text", 1000, "claude", "claude"),
            (
                "ABSOLUTE CONSTRAINTS\n"
                "CONTEXT FROM PREVIOUS SCENES:\nLast scenes: harbor, cabin.\n"
                "TEXT:\nshort text",
                1000,
                "claude",
                "gemini",
            ),
            ("x" * 100, 1, "claude", "gemini"),
        ],
    )
    def test_router_profile_matrix_direct_selection(
        self,
        prompt: str,
        token_threshold: int,
        short_preference: str,
        expected_provider: str,
    ) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": [{"location": "claude"}]}
        gemini.generate_json.return_value = {"scenes": [{"location": "gemini"}]}

        result = LLMRouter(
            claude,
            gemini,
            token_threshold=token_threshold,
            short_preference=short_preference,
        ).generate_json(prompt)

        assert result == {"scenes": [{"location": expected_provider}]}

    @pytest.mark.parametrize(
        ("prompt", "token_threshold", "short_preference", "expected_fallback"),
        [
            ("short text", 1000, "claude", "gemini"),
            (
                "ABSOLUTE CONSTRAINTS\n"
                "CONTEXT FROM PREVIOUS SCENES:\nLast scenes: harbor, cabin.\n"
                "TEXT:\nshort text",
                1000,
                "claude",
                "claude",
            ),
            ("x" * 100, 1, "claude", "claude"),
        ],
    )
    def test_router_profile_matrix_fallback_selection(
        self,
        prompt: str,
        token_threshold: int,
        short_preference: str,
        expected_fallback: str,
    ) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": [{"location": "claude"}]}
        gemini.generate_json.return_value = {"scenes": [{"location": "gemini"}]}
        if expected_fallback == "gemini":
            claude.generate_json.side_effect = LLMProviderError(
                "claude unavailable",
                category=LLMFailureCategory.TRANSIENT,
            )
        else:
            gemini.generate_json.side_effect = LLMProviderError(
                "gemini unavailable",
                category=LLMFailureCategory.TRANSIENT,
            )

        result = LLMRouter(
            claude,
            gemini,
            token_threshold=token_threshold,
            short_preference=short_preference,
        ).generate_json(prompt)

        assert result == {"scenes": [{"location": expected_fallback}]}

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

    def test_router_falls_back_to_gemini_when_claude_provider_fails(self) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.side_effect = LLMProviderError("claude unavailable")
        gemini.generate_json.return_value = {"scenes": [{"location": "dock"}]}

        result = LLMRouter(claude, gemini, token_threshold=1000).generate_json("short text")

        assert result == {"scenes": [{"location": "dock"}]}
        assert claude.generate_json.call_count == 1
        assert gemini.generate_json.call_count == 1

    def test_router_falls_back_to_claude_when_gemini_provider_fails(self) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": [{"location": "cabin"}]}
        gemini.generate_json.side_effect = LLMProviderError("gemini unavailable")

        result = LLMRouter(claude, gemini, token_threshold=1).generate_json("x" * 100)

        assert result == {"scenes": [{"location": "cabin"}]}
        assert gemini.generate_json.call_count == 1
        assert claude.generate_json.call_count == 1

    def test_router_can_prefer_gemini_for_short_input(self) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": [{"location": "claude"}]}
        gemini.generate_json.return_value = {"scenes": [{"location": "gemini"}]}

        result = LLMRouter(
            claude,
            gemini,
            token_threshold=1000,
            short_preference="gemini",
        ).generate_json("short text")

        assert result == {"scenes": [{"location": "gemini"}]}
        assert gemini.generate_json.call_count == 1
        assert claude.generate_json.call_count == 0

    def test_router_prefers_gemini_for_contextual_short_prompt(self) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": [{"location": "claude"}]}
        gemini.generate_json.return_value = {"scenes": [{"location": "gemini"}]}
        prompt = (
            "ABSOLUTE CONSTRAINTS\n"
            "CONTEXT FROM PREVIOUS SCENES:\nLast scenes: harbor, cabin.\n"
            "TEXT:\nshort text"
        )

        result = LLMRouter(claude, gemini, token_threshold=1000).generate_json(prompt)

        assert result == {"scenes": [{"location": "gemini"}]}
        assert gemini.generate_json.call_count == 1
        assert claude.generate_json.call_count == 0

    def test_router_contextual_short_prompt_falls_back_to_claude(self) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": [{"location": "claude"}]}
        gemini.generate_json.side_effect = LLMProviderError("gemini unavailable")
        prompt = (
            "ABSOLUTE CONSTRAINTS\n"
            "CONTEXT FROM PREVIOUS SCENES:\nLast scenes: harbor, cabin.\n"
            "TEXT:\nshort text"
        )

        result = LLMRouter(claude, gemini, token_threshold=1000).generate_json(prompt)

        assert result == {"scenes": [{"location": "claude"}]}
        assert gemini.generate_json.call_count == 1
        assert claude.generate_json.call_count == 1

    def test_router_skips_recently_failed_provider_on_next_request(self) -> None:
        now = [100.0]
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.side_effect = LLMProviderError("claude unavailable")
        gemini.generate_json.return_value = {"scenes": [{"location": "dock"}]}
        router = LLMRouter(
            claude,
            gemini,
            token_threshold=1000,
            cooldown_sec=30.0,
            time_fn=lambda: now[0],
        )

        first_result = router.generate_json("short text")
        second_result = router.generate_json("short text again")

        assert first_result == {"scenes": [{"location": "dock"}]}
        assert second_result == {"scenes": [{"location": "dock"}]}
        assert claude.generate_json.call_count == 1
        assert gemini.generate_json.call_count == 2

    def test_router_retries_failed_provider_after_cooldown_expires(self) -> None:
        now = [100.0]
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.side_effect = [
            LLMProviderError("claude unavailable"),
            {"scenes": [{"location": "cabin"}]},
        ]
        gemini.generate_json.return_value = {"scenes": [{"location": "dock"}]}
        router = LLMRouter(
            claude,
            gemini,
            token_threshold=1000,
            cooldown_sec=30.0,
            time_fn=lambda: now[0],
        )

        first_result = router.generate_json("short text")
        now[0] += 31.0
        second_result = router.generate_json("short text after cooldown")

        assert first_result == {"scenes": [{"location": "dock"}]}
        assert second_result == {"scenes": [{"location": "cabin"}]}
        assert claude.generate_json.call_count == 2
        assert gemini.generate_json.call_count == 1

    def test_router_increases_cooldown_after_repeated_failures(self) -> None:
        now = [100.0]
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.side_effect = [
            LLMProviderError("claude unavailable once"),
            LLMProviderError("claude unavailable twice"),
        ]
        gemini.generate_json.return_value = {"scenes": [{"location": "dock"}]}
        router = LLMRouter(
            claude,
            gemini,
            token_threshold=1000,
            cooldown_sec=10.0,
            max_cooldown_sec=40.0,
            time_fn=lambda: now[0],
        )

        first_result = router.generate_json("short text")
        now[0] += 11.0
        second_result = router.generate_json("short text after first cooldown")
        now[0] += 15.0
        third_result = router.generate_json("short text before extended cooldown ends")

        assert first_result == {"scenes": [{"location": "dock"}]}
        assert second_result == {"scenes": [{"location": "dock"}]}
        assert third_result == {"scenes": [{"location": "dock"}]}
        assert claude.generate_json.call_count == 2
        assert gemini.generate_json.call_count == 3

    def test_router_resets_failure_streak_after_success(self) -> None:
        now = [100.0]
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.side_effect = [
            LLMProviderError("claude unavailable"),
            {"scenes": [{"location": "cabin"}]},
            LLMProviderError("claude unavailable again"),
        ]
        gemini.generate_json.return_value = {"scenes": [{"location": "dock"}]}
        router = LLMRouter(
            claude,
            gemini,
            token_threshold=1000,
            cooldown_sec=10.0,
            max_cooldown_sec=40.0,
            time_fn=lambda: now[0],
        )

        first_result = router.generate_json("short text")
        now[0] += 11.0
        second_result = router.generate_json("short text after recovery")
        now[0] += 11.0
        third_result = router.generate_json("short text after reset")

        assert first_result == {"scenes": [{"location": "dock"}]}
        assert second_result == {"scenes": [{"location": "cabin"}]}
        assert third_result == {"scenes": [{"location": "dock"}]}
        assert claude.generate_json.call_count == 3
        assert gemini.generate_json.call_count == 2

    def test_router_success_only_partially_restores_provider_health(self) -> None:
        now = [100.0]
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.side_effect = [
            LLMProviderError("claude unavailable"),
            LLMProviderError("claude unavailable again"),
            {"scenes": [{"location": "cabin"}]},
        ]
        gemini.generate_json.return_value = {"scenes": [{"location": "dock"}]}
        router = LLMRouter(
            claude,
            gemini,
            token_threshold=1000,
            cooldown_sec=10.0,
            max_cooldown_sec=40.0,
            time_fn=lambda: now[0],
        )

        first_result = router.generate_json("short text")
        now[0] += 11.0
        second_result = router.generate_json("short text after first cooldown")
        now[0] += 21.0
        third_result = router.generate_json("short text after extended cooldown")
        fourth_result = router.generate_json("short text immediately after success")

        assert first_result == {"scenes": [{"location": "dock"}]}
        assert second_result == {"scenes": [{"location": "dock"}]}
        assert third_result == {"scenes": [{"location": "cabin"}]}
        assert fourth_result == {"scenes": [{"location": "dock"}]}
        assert claude.generate_json.call_count == 3
        assert gemini.generate_json.call_count == 3

    def test_router_health_penalty_decays_back_to_primary_order(self) -> None:
        now = [100.0]
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.side_effect = [
            LLMProviderError("claude unavailable"),
            LLMProviderError("claude unavailable again"),
            {"scenes": [{"location": "cabin"}]},
            {"scenes": [{"location": "cabin again"}]},
        ]
        gemini.generate_json.return_value = {"scenes": [{"location": "dock"}]}
        router = LLMRouter(
            claude,
            gemini,
            token_threshold=1000,
            cooldown_sec=10.0,
            max_cooldown_sec=40.0,
            time_fn=lambda: now[0],
        )

        first_result = router.generate_json("short text")
        now[0] += 11.0
        second_result = router.generate_json("short text after first cooldown")
        now[0] += 21.0
        third_result = router.generate_json("short text after extended cooldown")
        fourth_result = router.generate_json("short text immediately after success")
        now[0] += 11.0
        fifth_result = router.generate_json("short text after health recovery")

        assert first_result == {"scenes": [{"location": "dock"}]}
        assert second_result == {"scenes": [{"location": "dock"}]}
        assert third_result == {"scenes": [{"location": "cabin"}]}
        assert fourth_result == {"scenes": [{"location": "dock"}]}
        assert fifth_result == {"scenes": [{"location": "cabin again"}]}
        assert claude.generate_json.call_count == 4
        assert gemini.generate_json.call_count == 3

    def test_router_long_prompt_failure_does_not_penalize_contextual_short_priority(self) -> None:
        now = [100.0]
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": [{"location": "claude"}]}
        gemini.generate_json.side_effect = [
            LLMProviderError("gemini long prompt failure"),
            {"scenes": [{"location": "gemini"}]},
        ]
        router = LLMRouter(
            claude,
            gemini,
            token_threshold=1000,
            cooldown_sec=10.0,
            max_cooldown_sec=40.0,
            time_fn=lambda: now[0],
        )
        contextual_prompt = (
            "ABSOLUTE CONSTRAINTS\n"
            "CONTEXT FROM PREVIOUS SCENES:\nLast scenes: harbor, cabin.\n"
            "TEXT:\nshort text"
        )

        first_result = router.generate_json("x" * 5000)
        now[0] += 11.0
        second_result = router.generate_json(contextual_prompt)

        assert first_result == {"scenes": [{"location": "claude"}]}
        assert second_result == {"scenes": [{"location": "gemini"}]}
        assert gemini.generate_json.call_count == 2
        assert claude.generate_json.call_count == 1

    def test_router_raises_both_provider_categories_in_final_error(self) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.side_effect = LLMProviderError(
            "claude unavailable",
            category=LLMFailureCategory.TRANSIENT,
        )
        gemini.generate_json.side_effect = LLMProviderError(
            "gemini quota exceeded",
            category=LLMFailureCategory.QUOTA,
        )

        with pytest.raises(
            LLMProviderError,
            match="LLMRouter failed on both providers",
        ) as exc_info:
            LLMRouter(claude, gemini, token_threshold=1000).generate_json("short text")

        assert exc_info.value.category == LLMFailureCategory.QUOTA
        assert [failure.category for failure in exc_info.value.failures] == [
            LLMFailureCategory.TRANSIENT,
            LLMFailureCategory.QUOTA,
        ]
        assert "primary=claude[transient]" in str(exc_info.value)
        assert "secondary=gemini[quota]" in str(exc_info.value)

    def test_router_auth_failure_quarantines_provider_longer(self) -> None:
        now = [100.0]
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": [{"location": "claude"}]}
        gemini.generate_json.side_effect = [
            LLMProviderError(
                "gemini unauthorized",
                category=LLMFailureCategory.AUTH,
            ),
        ]
        router = LLMRouter(
            claude,
            gemini,
            token_threshold=1,
            cooldown_sec=10.0,
            max_cooldown_sec=40.0,
            time_fn=lambda: now[0],
        )

        first_result = router.generate_json("x" * 100)
        now[0] += 41.0
        second_result = router.generate_json("x" * 100)

        assert first_result == {"scenes": [{"location": "claude"}]}
        assert second_result == {"scenes": [{"location": "claude"}]}
        assert gemini.generate_json.call_count == 1
        assert claude.generate_json.call_count == 2

    def test_router_rate_limit_uses_retry_backoff_not_hard_quarantine(self) -> None:
        now = [100.0]
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": [{"location": "claude"}]}
        gemini.generate_json.side_effect = [
            LLMProviderError(
                "gemini rate limited",
                category=LLMFailureCategory.RATE_LIMIT,
            ),
            {"scenes": [{"location": "gemini"}]},
        ]
        router = LLMRouter(
            claude,
            gemini,
            token_threshold=1,
            cooldown_sec=10.0,
            max_cooldown_sec=40.0,
            time_fn=lambda: now[0],
        )

        first_result = router.generate_json("x" * 100)
        now[0] += 41.0
        second_result = router.generate_json("x" * 100)

        assert first_result == {"scenes": [{"location": "claude"}]}
        assert second_result == {"scenes": [{"location": "gemini"}]}
        assert gemini.generate_json.call_count == 2
        assert claude.generate_json.call_count == 1

    def test_router_schema_failure_penalizes_current_profile_only(self) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": [{"location": "claude"}]}
        gemini.generate_json.side_effect = [
            LLMProviderError(
                "gemini malformed json",
                category=LLMFailureCategory.SCHEMA,
            ),
            {"scenes": [{"location": "gemini"}]},
        ]
        router = LLMRouter(
            claude,
            gemini,
            token_threshold=1000,
        )
        contextual_prompt = (
            "ABSOLUTE CONSTRAINTS\n"
            "CONTEXT FROM PREVIOUS SCENES:\nLast scenes: harbor, cabin.\n"
            "TEXT:\nshort text"
        )

        first_result = router.generate_json(contextual_prompt)
        second_result = router.generate_json("x" * 5000)

        assert first_result == {"scenes": [{"location": "claude"}]}
        assert second_result == {"scenes": [{"location": "gemini"}]}
        assert gemini.generate_json.call_count == 2
        assert claude.generate_json.call_count == 1

    def test_router_trace_reports_contextual_short_profile(self) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": [{"location": "claude"}]}
        gemini.generate_json.return_value = {"scenes": [{"location": "gemini"}]}
        router = LLMRouter(claude, gemini, token_threshold=1000)
        prompt = (
            "ABSOLUTE CONSTRAINTS\n"
            "CONTEXT FROM PREVIOUS SCENES:\nLast scenes: harbor, cabin.\n"
            "TEXT:\nshort text"
        )

        result = router.generate_json(prompt)
        trace = router.get_last_trace()

        assert result == {"scenes": [{"location": "gemini"}]}
        assert trace is not None
        assert trace["prompt_profile"] == "contextual_short"
        assert trace["base_order"] == ["gemini", "claude"]
        assert trace["final_order"] == ["gemini", "claude"]
        assert trace["selected_provider"] == "gemini"
        assert trace["decision_reason"] == "contextual short prompt prefers gemini"

    def test_router_trace_reports_penalty_and_availability(self) -> None:
        now = [100.0]
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.side_effect = LLMProviderError(
            "claude unavailable",
            category=LLMFailureCategory.TRANSIENT,
        )
        gemini.generate_json.return_value = {"scenes": [{"location": "dock"}]}
        router = LLMRouter(
            claude,
            gemini,
            token_threshold=1000,
            cooldown_sec=30.0,
            time_fn=lambda: now[0],
        )

        router.generate_json("short text")
        router.generate_json("short text again")
        trace = router.get_last_trace()

        assert trace is not None
        assert trace["provider_availability"]["claude"] is False
        assert trace["health_penalties"]["claude"] > trace["health_penalties"]["gemini"]
        assert trace["selected_provider"] == "gemini"

    def test_router_trace_reports_failure_category(self) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": [{"location": "claude"}]}
        gemini.generate_json.side_effect = LLMProviderError(
            "gemini malformed json",
            category=LLMFailureCategory.SCHEMA,
        )
        router = LLMRouter(claude, gemini, token_threshold=1000)
        prompt = (
            "ABSOLUTE CONSTRAINTS\n"
            "CONTEXT FROM PREVIOUS SCENES:\nLast scenes: harbor, cabin.\n"
            "TEXT:\nshort text"
        )

        result = router.generate_json(prompt)
        trace = router.get_last_trace()

        assert result == {"scenes": [{"location": "claude"}]}
        assert trace is not None
        assert trace["failure_category"] == "schema"
        assert trace["result"] == "fallback_success"
        assert trace["selected_provider"] == "claude"

    def test_router_trace_does_not_change_selected_provider(self) -> None:
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.return_value = {"scenes": [{"location": "claude"}]}
        gemini.generate_json.return_value = {"scenes": [{"location": "gemini"}]}
        router = LLMRouter(claude, gemini, token_threshold=1000)

        result = router.generate_json("short text")
        trace = router.get_last_trace()

        assert result == {"scenes": [{"location": "claude"}]}
        assert trace is not None
        assert trace["selected_provider"] == "claude"
        assert trace["result"] == "success"


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
        assert any("CONTINUITY_SNAPSHOT_JSON" in p for p in received_prompts[1:])

    def test_extract_all_routes_contextual_follow_up_chunks_to_gemini(self) -> None:
        claude_prompts: list[str] = []
        gemini_prompts: list[str] = []

        class RecordingAdapter(LLMAdapter):
            def __init__(self, prompts: list[str], location: str) -> None:
                self._prompts = prompts
                self._location = location

            def generate_json(self, prompt: str) -> dict[str, object]:
                self._prompts.append(prompt)
                return {
                    "scenes": [
                        {
                            "location": self._location,
                            "characters": [],
                            "actions": ["looks around"],
                            "emotion": "neutral",
                        }
                    ]
                }

        router = LLMRouter(
            claude=RecordingAdapter(claude_prompts, "Park"),
            gemini=RecordingAdapter(gemini_prompts, "Harbor"),
            token_threshold=1000,
        )
        text = (
            "First paragraph at the park."
            "\n\nSecond paragraph on the harbor."
        )
        budget = ProductionBudget(max_chars_per_chunk=40)

        result = StoryExtractor().extract_all(router, text, budget)

        assert len(result) == 2
        assert len(claude_prompts) == 1
        assert len(gemini_prompts) == 1
        assert "CONTEXT FROM PREVIOUS SCENES" not in claude_prompts[0]
        assert "CONTEXT FROM PREVIOUS SCENES" in gemini_prompts[0]
        assert "CONTINUITY_SNAPSHOT_JSON" in gemini_prompts[0]
        assert '"location": "Park"' in gemini_prompts[0]

    def test_normalizer_uses_continuity_snapshot_for_missing_fields(self) -> None:
        from aiprod_adaptation.core.adaptation.normalizer import Normalizer

        normalized = Normalizer().normalize(
            [
                {
                    "location": "",
                    "characters": [],
                    "actions": ["Looks around."],
                    "emotion": "neutral",
                }
            ],
            continuity_snapshot={
                "active_characters": ["Clara", "Marcus"],
                "active_locations": ["Harbor"],
                "recent_scenes": [],
            },
        )

        assert normalized[0]["characters"] == ["Clara", "Marcus"]
        assert normalized[0]["location"] == "Harbor"


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

    def test_engine_require_llm_raises_when_extractor_returns_no_scenes(self) -> None:
        from aiprod_adaptation.core.adaptation.llm_adapter import NullLLMAdapter
        from aiprod_adaptation.core.engine import run_pipeline
        from aiprod_adaptation.core.production_budget import ProductionBudget

        text = "Alice walked in the park. She sat on a bench."
        with pytest.raises(
            ValueError,
            match="LLM extraction produced no scenes; rule-based fallback is disabled.",
        ):
            run_pipeline(
                text,
                "T",
                llm=NullLLMAdapter(),
                require_llm=True,
                budget=ProductionBudget(),
            )


# ---------------------------------------------------------------------------
# TA04 — engine raises when StoryValidator filters all scenes
# ---------------------------------------------------------------------------

class TestEngineStoryValidatorAllFiltered:
    def test_engine_raises_when_story_validator_filters_all_scenes(self) -> None:
        from unittest.mock import patch

        with patch(
            "aiprod_adaptation.core.adaptation.story_validator.StoryValidator.validate_all",
            return_value=[],
        ):
            with pytest.raises(ValueError, match="StoryValidator produced no filmable scenes"):
                run_pipeline("John walked into the room.", "T")


# ---------------------------------------------------------------------------
# Integration — real LLM adapters (opt-in via API keys)
# ---------------------------------------------------------------------------

_JSON_CONTRACT_PROMPT = (
    "Return only valid JSON with this exact structure and no commentary: "
    '{"scenes": []}'
)

_PROVIDER_ENVIRONMENT_ERROR_FRAGMENTS = (
    "credit balance is too low",
    "insufficient credit",
    "quota",
    "rate limit",
    "billing",
    "resource exhausted",
    "service unavailable",
    "temporarily unavailable",
)


def _skip_on_provider_environment_issue(provider: str, exc: Exception) -> None:
    message = str(exc).lower()
    if any(fragment in message for fragment in _PROVIDER_ENVIRONMENT_ERROR_FRAGMENTS):
        pytest.skip(f"{provider} unavailable in current environment: {exc}")


class TestRealLLMAdapters:
    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set",
    )
    def test_claude_adapter_returns_parseable_json(self) -> None:
        from aiprod_adaptation.core.adaptation.claude_adapter import ClaudeAdapter

        try:
            result = ClaudeAdapter().generate_json(_JSON_CONTRACT_PROMPT)
        except Exception as exc:
            _skip_on_provider_environment_issue("Anthropic", exc)
            raise

        assert isinstance(result, dict)
        assert "scenes" in result
        assert isinstance(result["scenes"], list)

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("GEMINI_API_KEY"),
        reason="GEMINI_API_KEY not set",
    )
    def test_gemini_adapter_returns_parseable_json(self) -> None:
        from aiprod_adaptation.core.adaptation.gemini_adapter import GeminiAdapter

        try:
            result = GeminiAdapter().generate_json(_JSON_CONTRACT_PROMPT)
        except Exception as exc:
            _skip_on_provider_environment_issue("Gemini", exc)
            raise

        assert isinstance(result, dict)
        assert "scenes" in result
        assert isinstance(result["scenes"], list)

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("GEMINI_API_KEY"),
        reason="GEMINI_API_KEY not set",
    )
    def test_gemini_chapter1_regression(self) -> None:
        from aiprod_adaptation.core.adaptation.gemini_adapter import GeminiAdapter

        chapter1 = Path(__file__).parent.parent / "examples" / "chapter1.txt"
        raw = chapter1.read_text(encoding="utf-8")

        try:
            result = run_pipeline(raw, "Chapter 1", llm=GeminiAdapter(), require_llm=True)
        except Exception as exc:
            _skip_on_provider_environment_issue("Gemini", exc)
            raise

        ep = result.episodes[0]
        scenes = {scene.scene_id: scene for scene in ep.scenes}
        locations = [scene.location.lower() for scene in ep.scenes]
        all_dialogue_text = " ".join(
            line for scene in ep.scenes for line in scene.dialogues
        ).lower()

        assert len(ep.scenes) == 12
        assert len(ep.shots) == 40
        assert [scene.scene_id for scene in ep.scenes] == [
            "SCN_001",
            "SCN_002",
            "SCN_003",
            "SCN_004",
            "SCN_005",
            "SCN_006",
            "SCN_007",
            "SCN_008",
            "SCN_009",
            "SCN_010",
            "SCN_011",
            "SCN_012",
        ]
        assert "market street" in locations[0]
        assert locations.count("old stone library interior") >= 3
        assert locations.count("old harbor docks") >= 2
        assert locations.count("ship cabin interior") >= 3
        assert scenes["SCN_001"].visual_actions[0].lower().startswith("marcus runs quickly")
        assert scenes["SCN_002"].visual_actions[0] == "Clara sits at a long wooden table."
        assert scenes["SCN_003"].visual_actions[0] == (
            "Clara traces a line on a map with her finger."
        )
        assert scenes["SCN_003"].dialogues == ["I found the passage."]
        assert "are you certain" in all_dialogue_text
        assert "the markings match exactly" in all_dialogue_text
        assert "the captain waited" in all_dialogue_text
        assert "we still have time" in all_dialogue_text
        assert "once we reach the island" in all_dialogue_text
        assert "we go forward" in all_dialogue_text
        assert scenes["SCN_012"].location == "Ship cabin interior"
        assert any(
            "dark water" in action.lower() or "hull" in action.lower()
            for action in scenes["SCN_012"].visual_actions
        )

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("GEMINI_API_KEY"),
        reason="GEMINI_API_KEY not set",
    )
    def test_router_chapter1_regression_prefers_gemini_for_short_input(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from aiprod_adaptation.cli import _load_llm_adapter

        chapter1 = Path(__file__).parent.parent / "examples" / "chapter1.txt"
        raw = chapter1.read_text(encoding="utf-8")
        monkeypatch.setenv("LLM_ROUTER_SHORT_PROVIDER", "gemini")

        try:
            result = run_pipeline(
                raw,
                "Chapter 1",
                llm=_load_llm_adapter("router"),
                require_llm=True,
            )
        except Exception as exc:
            _skip_on_provider_environment_issue("Router", exc)
            raise

        ep = result.episodes[0]
        locations = [scene.location.lower() for scene in ep.scenes]
        all_dialogue_text = " ".join(
            line for scene in ep.scenes for line in scene.dialogues
        ).lower()

        assert len(ep.scenes) >= 7
        assert len(ep.shots) >= 30
        assert ep.scenes[0].scene_id == "SCN_001"
        assert "market street" in locations[0]
        assert any("library" in location for location in locations)
        assert any("harbor docks" in location for location in locations)
        assert any("ship cabin" in location for location in locations)
        assert ep.scenes[0].visual_actions[0].lower().startswith("marcus runs quickly")
        assert "i found the passage" in all_dialogue_text
        assert "the captain waited" in all_dialogue_text
        assert "we go forward" in all_dialogue_text
