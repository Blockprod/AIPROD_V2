"""
pytest test suite for AIPROD ADAPTATION ENGINE v2.

Covered cases (per spec):
  1. Empty input → ValueError
  2. Multi-location segmentation
  3. Time-jump segmentation
  4. Internal-thought conversion (Pass 2)
  5. Deterministic consistency (same input → identical output twice)
  6. Invalid duration → ValueError from Pass 4 / schema
  7. Full pipeline smoke test on sample text
"""

from __future__ import annotations

import copy
import pathlib
import pytest

from aiprod_adaptation.core.pass1_segment import segment
from aiprod_adaptation.core.pass2_visual import transform_visuals
from aiprod_adaptation.core.pass3_shots import atomize_shots
from aiprod_adaptation.core.pass4_compile import compile_output
from aiprod_adaptation.core.engine import run_pipeline
from aiprod_adaptation.models.schema import Shot


# ---------------------------------------------------------------------------
# 1. Empty input → ValueError
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_pass1_empty_string(self) -> None:
        with pytest.raises(ValueError, match="PASS 1"):
            segment("")

    def test_pass1_whitespace_only(self) -> None:
        with pytest.raises(ValueError, match="PASS 1"):
            segment("   \n\n   ")

    def test_pass2_empty_list(self) -> None:
        with pytest.raises(ValueError, match="PASS 2"):
            transform_visuals([])

    def test_pass3_empty_list(self) -> None:
        with pytest.raises(ValueError, match="PASS 3"):
            atomize_shots([])

    def test_pass4_empty_scenes(self) -> None:
        with pytest.raises(ValueError, match="PASS 4"):
            compile_output("title", [], [{"shot_id": "SH0001", "scene_id": "SC001",
                                          "prompt": "x", "duration_sec": 3, "emotion": "neutral"}])

    def test_pass4_empty_shots(self) -> None:
        scene = {
            "scene_id": "SC001", "characters": [], "location": "a place",
            "time_of_day": None, "visual_actions": ["someone walks"],
            "dialogues": [], "emotion": "neutral",
        }
        with pytest.raises(ValueError, match="PASS 4"):
            compile_output("title", [scene], [])

    def test_pass4_empty_title(self) -> None:
        scene = {
            "scene_id": "SC001", "characters": [], "location": "a place",
            "time_of_day": None, "visual_actions": ["someone walks"],
            "dialogues": [], "emotion": "neutral",
        }
        shot = {"shot_id": "SH0001", "scene_id": "SC001",
                "prompt": "someone walks, in a place.", "duration_sec": 4, "emotion": "neutral"}
        with pytest.raises(ValueError, match="PASS 4"):
            compile_output("", [scene], [shot])

    def test_engine_empty_string(self) -> None:
        with pytest.raises(ValueError):
            run_pipeline("", "Title")


# ---------------------------------------------------------------------------
# 2. Multi-location segmentation
# ---------------------------------------------------------------------------

class TestMultiLocation:
    _TEXT = (
        "Alice walked through the park. "
        "She noticed the birds singing.\n\n"
        "Later she arrived at the old library. "
        "She opened a dusty book."
    )

    def test_two_scenes_produced(self) -> None:
        scenes = segment(self._TEXT)
        assert len(scenes) >= 2

    def test_scene_ids_unique_and_ordered(self) -> None:
        scenes = segment(self._TEXT)
        ids = [s["scene_id"] for s in scenes]
        assert ids == sorted(ids)  # SC001 < SC002 < …

    def test_location_captured(self) -> None:
        scenes = segment(self._TEXT)
        locations = [s["location"] for s in scenes]
        # At least one scene should reference "old library"
        assert any("library" in loc for loc in locations)


# ---------------------------------------------------------------------------
# 3. Time-jump segmentation
# ---------------------------------------------------------------------------

class TestTimeJump:
    _TEXT = (
        "Bob stood at the window. "
        "He watched the rain fall. "
        "The next day, he packed his bags quickly. "
        "Hours later he arrived at the station."
    )

    def test_time_phrase_creates_new_scene(self) -> None:
        scenes = segment(self._TEXT)
        time_values = [s["time_of_day"] for s in scenes if s.get("time_of_day")]
        assert len(time_values) >= 1

    def test_known_time_phrases_detected(self) -> None:
        scenes = segment(self._TEXT)
        time_values = [s["time_of_day"] for s in scenes if s.get("time_of_day")]
        found = {t for t in time_values if t is not None}
        assert any("next day" in t or "hours later" in t for t in found)


# ---------------------------------------------------------------------------
# 4. Internal-thought conversion (Pass 2)
# ---------------------------------------------------------------------------

class TestInternalThoughts:
    _THOUGHT_SCENE: dict = {
        "scene_id": "SC001",
        "characters": ["Emma"],
        "location": "the dark corridor",
        "time_of_day": None,
        "raw_text": (
            "Emma felt nervous in the corridor. "
            "She thought about the future. "
            "Emma walked to the door."
        ),
    }

    def test_thought_replaced_by_physical_action(self) -> None:
        result = transform_visuals([self._THOUGHT_SCENE])
        actions = result[0]["visual_actions"]
        # Thought sentence must be replaced
        assert "thought" not in actions[0].lower()
        # Physical action keywords for 'nervous' must appear
        assert "fidgets" in actions[0] or "paces" in actions[0] or "bites" in actions[0]

    def test_non_thought_sentence_unchanged(self) -> None:
        result = transform_visuals([self._THOUGHT_SCENE])
        actions = result[0]["visual_actions"]
        assert actions[1] == "Emma walked to the door."

    def test_dialogues_unchanged(self) -> None:
        scene = copy.deepcopy(self._THOUGHT_SCENE)
        scene["raw_text"] = 'Emma felt nervous. "I will find a way," she said.'
        result = transform_visuals([scene])
        assert result[0]["dialogues"] == ["I will find a way,"]

    def test_abstract_noun_replaced(self) -> None:
        scene = copy.deepcopy(self._THOUGHT_SCENE)
        scene["raw_text"] = "She was terrified of the darkness."
        result = transform_visuals([scene])
        actions = result[0]["visual_actions"]
        assert "trembles" in actions[0] or "eyes widen" in actions[0]


# ---------------------------------------------------------------------------
# 5. Deterministic consistency
# ---------------------------------------------------------------------------

class TestDeterminism:
    _SAMPLE = (
        "John walked quickly through the busy city streets. "
        "He felt very excited about the important meeting. "
        "Suddenly dark clouds appeared and it started raining heavily. "
        "Later that evening, inside the old wooden house, Sarah waited nervously. "
        "She thought about their difficult past. "
        "John finally entered the room and gave her a warm smile."
    )

    def test_identical_output_twice(self) -> None:
        out1 = run_pipeline(self._SAMPLE, "Test Title")
        out2 = run_pipeline(self._SAMPLE, "Test Title")
        assert out1.model_dump() == out2.model_dump()

    def test_rule_pipeline_byte_identical(self) -> None:
        # Teste le déterminisme byte-level du pipeline rules-based (NullLLMAdapter path).
        # Le novel pipe LLM réel (ClaudeAdapter) est non-déterministe par nature.
        import json
        out1 = run_pipeline(self._SAMPLE, "Test Title")
        out2 = run_pipeline(self._SAMPLE, "Test Title")
        assert json.dumps(out1.model_dump(), sort_keys=False) == \
               json.dumps(out2.model_dump(), sort_keys=False)


# ---------------------------------------------------------------------------
# 6. Invalid duration → ValueError
# ---------------------------------------------------------------------------

class TestInvalidDuration:
    _BASE_SCENE: dict = {
        "scene_id": "SC001",
        "characters": [],
        "location": "a room",
        "time_of_day": None,
        "visual_actions": ["someone stands"],
        "dialogues": [],
        "emotion": "neutral",
    }

    def test_duration_too_low_raises(self) -> None:
        shot = {
            "shot_id": "SH0001", "scene_id": "SC001",
            "prompt": "someone stands, in a room.",
            "duration_sec": 2,
            "emotion": "neutral",
        }
        with pytest.raises(ValueError):
            compile_output("title", [self._BASE_SCENE], [shot])

    def test_duration_too_high_raises(self) -> None:
        shot = {
            "shot_id": "SH0001", "scene_id": "SC001",
            "prompt": "someone stands, in a room.",
            "duration_sec": 9,
            "emotion": "neutral",
        }
        with pytest.raises(ValueError):
            compile_output("title", [self._BASE_SCENE], [shot])

    def test_duration_boundary_low_valid(self) -> None:
        shot = {
            "shot_id": "SH0001", "scene_id": "SC001",
            "prompt": "someone stands, in a room.",
            "duration_sec": 3,
            "emotion": "neutral",
        }
        result = compile_output("title", [self._BASE_SCENE], [shot])
        assert result.episodes[0].shots[0].duration_sec == 3

    def test_duration_boundary_high_valid(self) -> None:
        shot = {
            "shot_id": "SH0001", "scene_id": "SC001",
            "prompt": "someone stands, in a room.",
            "duration_sec": 8,
            "emotion": "neutral",
        }
        result = compile_output("title", [self._BASE_SCENE], [shot])
        assert result.episodes[0].shots[0].duration_sec == 8

    def test_shot_model_rejects_invalid_duration_directly(self) -> None:
        shot = {
            "shot_id": "SH0001", "scene_id": "SC001",
            "prompt": "x", "duration_sec": 0, "emotion": "neutral",
        }
        with pytest.raises(ValueError):
            compile_output("title", [self._BASE_SCENE], [shot])

    def test_shot_references_unknown_scene_raises(self) -> None:
        shot = {
            "shot_id": "SH0001", "scene_id": "SC999",
            "prompt": "someone stands, in a room.",
            "duration_sec": 4,
            "emotion": "neutral",
        }
        with pytest.raises(ValueError, match="unknown scene_id"):
            compile_output("title", [self._BASE_SCENE], [shot])


# ---------------------------------------------------------------------------
# 7. Full pipeline smoke test on sample text
# ---------------------------------------------------------------------------

class TestFullPipeline:
    _SAMPLE = (
        "John walked quickly through the busy city streets. "
        "He felt very excited about the important meeting. "
        "Suddenly dark clouds appeared and it started raining heavily. "
        "Later that evening, inside the old wooden house, Sarah waited nervously. "
        "She thought about their difficult past. "
        "John finally entered the room and gave her a warm smile."
    )

    def test_pipeline_returns_aiprod_output(self) -> None:
        from aiprod_adaptation.models.schema import AIPRODOutput
        result = run_pipeline(self._SAMPLE, "Sample Title")
        assert isinstance(result, AIPRODOutput)

    def test_single_episode_ep01(self) -> None:
        result = run_pipeline(self._SAMPLE, "Sample Title")
        assert len(result.episodes) == 1
        assert result.episodes[0].episode_id == "EP01"

    def test_all_shot_durations_valid(self) -> None:
        result = run_pipeline(self._SAMPLE, "Sample Title")
        for shot in result.episodes[0].shots:
            assert 3 <= shot.duration_sec <= 8, (
                f"Shot {shot.shot_id} has invalid duration {shot.duration_sec}"
            )

    def test_shot_scene_ids_reference_known_scenes(self) -> None:
        result = run_pipeline(self._SAMPLE, "Sample Title")
        ep = result.episodes[0]
        known = {s.scene_id for s in ep.scenes}
        for shot in ep.shots:
            assert shot.scene_id in known

    def test_title_preserved(self) -> None:
        result = run_pipeline(self._SAMPLE, "My Epic Title")
        assert result.title == "My Epic Title"

    def test_at_least_one_scene_produced(self) -> None:
        result = run_pipeline(self._SAMPLE, "Sample Title")
        assert len(result.episodes[0].scenes) >= 1

    def test_at_least_one_shot_produced(self) -> None:
        result = run_pipeline(self._SAMPLE, "Sample Title")
        assert len(result.episodes[0].shots) >= 1

    def test_no_internal_thought_in_visual_actions(self) -> None:
        result = run_pipeline(self._SAMPLE, "Sample Title")
        thought_words = {"thought", "wondered", "realized", "remembered", "imagined", "believed"}
        for scene in result.episodes[0].scenes:
            for action in scene.visual_actions:
                words = set(action.lower().split())
                overlap = words & thought_words
                assert not overlap, (
                    f"Scene {scene.scene_id} has internal-thought word in visual_actions: "
                    f"{overlap!r} — action: {action!r}"
                )


# ---------------------------------------------------------------------------
# 8. Real narrative text — smoke test
# ---------------------------------------------------------------------------

class TestRealText:
    _CHAPTER1 = (
        pathlib.Path(__file__).parent.parent / "examples" / "chapter1.txt"
    )

    def test_real_text_no_crash(self) -> None:
        from aiprod_adaptation.models.schema import AIPRODOutput
        raw = self._CHAPTER1.read_text(encoding="utf-8")
        result = run_pipeline(raw, "Chapter 1")
        assert isinstance(result, AIPRODOutput)
        assert len(result.episodes[0].scenes) >= 3
        assert len(result.episodes[0].shots) >= 1
        for shot in result.episodes[0].shots:
            assert 3 <= shot.duration_sec <= 8


# ---------------------------------------------------------------------------
# 9. Shot structure — shot_type and camera_movement
# ---------------------------------------------------------------------------

class TestShotStructure:
    _VALID_SHOT_TYPES = {"wide", "medium", "close_up", "pov"}
    _VALID_CAMERA_MOVEMENTS = {"static", "follow", "pan"}

    _SAMPLE = (
        "John walked quickly through the busy city streets. "
        "He felt very excited about the important meeting. "
        "Suddenly dark clouds appeared and it started raining heavily. "
        "Later that evening, inside the old wooden house, Sarah waited nervously. "
        "She thought about their difficult past. "
        "John finally entered the room and gave her a warm smile."
    )

    def _get_shots(self) -> list:
        result = run_pipeline(self._SAMPLE, "Structure Test")
        return result.episodes[0].shots

    def test_shot_type_field_present_and_valid(self) -> None:
        for shot in self._get_shots():
            assert shot.shot_type in self._VALID_SHOT_TYPES, (
                f"Shot {shot.shot_id} has unexpected shot_type {shot.shot_type!r}"
            )

    def test_camera_movement_field_present_and_valid(self) -> None:
        for shot in self._get_shots():
            assert shot.camera_movement in self._VALID_CAMERA_MOVEMENTS, (
                f"Shot {shot.shot_id} has unexpected camera_movement {shot.camera_movement!r}"
            )

    def test_prompt_has_no_shot_type_prefix(self) -> None:
        prefixes = {"WIDE SHOT:", "MEDIUM SHOT:", "CLOSE UP:", "POV:"}
        for shot in self._get_shots():
            for prefix in prefixes:
                assert not shot.prompt.startswith(prefix), (
                    f"Shot {shot.shot_id} prompt still contains legacy prefix: {shot.prompt!r}"
                )

    def test_shot_invalid_shot_type_raises(self) -> None:
        with pytest.raises(ValueError, match="shot_type"):
            Shot(
                shot_id="SH0001", scene_id="SC001",
                prompt="someone stands.", duration_sec=4, emotion="neutral",
                shot_type="extreme_close_up",
            )

    def test_shot_invalid_camera_movement_raises(self) -> None:
        with pytest.raises(ValueError, match="camera_movement"):
            Shot(
                shot_id="SH0001", scene_id="SC001",
                prompt="someone stands.", duration_sec=4, emotion="neutral",
                camera_movement="zoom",
            )
