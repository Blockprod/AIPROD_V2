"""
pytest test suite — Adaptation Layer v1

Covers:
  1. InputClassifier — AL-01
  2. NullLLMAdapter  — AL-02
  3. ScriptParser    — AL-03
  4. NovelPipe       — AL-04
  5. Engine routing  — AL-06
"""

from __future__ import annotations

from aiprod_adaptation.core.adaptation.classifier import InputClassifier
from aiprod_adaptation.core.adaptation.llm_adapter import NullLLMAdapter
from aiprod_adaptation.core.adaptation.novel_pipe import run_novel_pipe
from aiprod_adaptation.core.adaptation.script_parser import ScriptParser
from aiprod_adaptation.core.engine import run_pipeline


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
# 4. NovelPipe (NullLLMAdapter)
# ---------------------------------------------------------------------------

class TestNovelPipe:
    def test_novel_pipe_null_adapter_returns_list(self) -> None:
        result = run_novel_pipe(NullLLMAdapter(), "John walked into the room.")
        assert isinstance(result, list)

    def test_novel_pipe_null_adapter_deterministic(self) -> None:
        text = "John walked into the room. He smiled at Sarah."
        r1 = run_novel_pipe(NullLLMAdapter(), text)
        r2 = run_novel_pipe(NullLLMAdapter(), text)
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
