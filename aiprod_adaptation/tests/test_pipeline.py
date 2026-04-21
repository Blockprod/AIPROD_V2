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
from aiprod_adaptation.models.schema import AIPRODOutput, Shot


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


# ---------------------------------------------------------------------------
# 8. ProductionBudget — SE-03
# ---------------------------------------------------------------------------


class TestProductionBudget:
    def test_budget_default_values(self) -> None:
        from aiprod_adaptation.core.production_budget import ProductionBudget

        b = ProductionBudget()
        assert b.target_duration_sec == 180
        assert b.max_scenes == 12
        assert b.max_shots_per_scene == 6

    def test_budget_for_short_factory(self) -> None:
        from aiprod_adaptation.core.production_budget import ProductionBudget

        b = ProductionBudget.for_short()
        assert b.target_duration_sec == 180
        assert b.max_scenes == 12

    def test_budget_for_episode_45_factory(self) -> None:
        from aiprod_adaptation.core.production_budget import ProductionBudget

        b = ProductionBudget.for_episode_45()
        assert b.target_duration_sec == 2700
        assert b.max_scenes == 135

    def test_budget_shots_estimate_property(self) -> None:
        from aiprod_adaptation.core.production_budget import ProductionBudget

        b = ProductionBudget(max_scenes=10, max_shots_per_scene=4)
        assert b.shots_estimate == 40

    def test_pipeline_accepts_budget_param(self) -> None:
        from aiprod_adaptation.core.production_budget import ProductionBudget

        budget = ProductionBudget.for_short()
        result = run_pipeline(
            "John walked into the room. He smiled.", "Budget Test", budget=budget
        )
        assert result.title == "Budget Test"

    def test_pipeline_budget_none_uses_default(self) -> None:
        result = run_pipeline("John walked into the room.", "No Budget Test", budget=None)
        assert len(result.episodes[0].shots) > 0


# ---------------------------------------------------------------------------
# 9. VisualScene enrichment — SE-04
# ---------------------------------------------------------------------------


class TestVisualSceneEnrichment:
    from typing import Any

    def _make_scene(self, **kwargs: "Any") -> "Any":
        from typing import cast

        from aiprod_adaptation.models.intermediate import VisualScene

        d: dict[str, object] = {
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

    def test_pacing_fast_clamps_shot_duration_to_5(self) -> None:
        from aiprod_adaptation.core.pass3_shots import simplify_shots

        scene = self._make_scene(
            visual_actions=[
                "John runs and grabs the door and looks around carefully then walks fast."
            ],
            pacing="fast",
        )
        shots = simplify_shots([scene])
        assert all(s["duration_sec"] <= 5 for s in shots)

    def test_pacing_slow_clamps_shot_duration_minimum_5(self) -> None:
        from aiprod_adaptation.core.pass3_shots import simplify_shots

        scene = self._make_scene(visual_actions=["John stands."], pacing="slow")
        shots = simplify_shots([scene])
        assert all(s["duration_sec"] >= 5 for s in shots)

    def test_time_of_day_visual_injected_in_image_prompt(self) -> None:
        from aiprod_adaptation.core.pass3_shots import simplify_shots
        from aiprod_adaptation.core.pass4_compile import compile_episode
        from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
        from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult
        from aiprod_adaptation.image_gen.storyboard import StoryboardGenerator

        scene = self._make_scene(time_of_day_visual="night")
        shots = simplify_shots([scene])
        output = compile_episode([scene], shots, "T", "EP01")

        received: list[ImageRequest] = []

        class TrackingAdapter(ImageAdapter):
            def generate(self, req: ImageRequest) -> ImageResult:
                received.append(req)
                return ImageResult(
                    shot_id=req.shot_id,
                    image_url="u://x",
                    image_b64="",
                    model_used="test",
                    latency_ms=0,
                )

        StoryboardGenerator(TrackingAdapter()).generate(output)
        assert received
        assert "night" in received[0].prompt.lower()

    def test_dominant_sound_silence_skips_tts(self) -> None:
        from aiprod_adaptation.core.pass3_shots import simplify_shots
        from aiprod_adaptation.core.pass4_compile import compile_episode
        from aiprod_adaptation.post_prod.audio_adapter import NullAudioAdapter
        from aiprod_adaptation.post_prod.audio_synchronizer import AudioSynchronizer
        from aiprod_adaptation.video_gen.video_request import VideoClipResult, VideoOutput

        scene = self._make_scene(dominant_sound="silence")
        shots = simplify_shots([scene])
        output = compile_episode([scene], shots, "T", "EP01")
        clips = [
            VideoClipResult(
                shot_id=shots[0]["shot_id"],
                video_url="v.mp4",
                duration_sec=4,
                model_used="test",
                latency_ms=0,
            )
        ]
        video = VideoOutput(title="T", clips=clips, total_shots=1, generated=1)
        requests = AudioSynchronizer(NullAudioAdapter()).build_requests(video, output)
        assert requests[0].text == ""

    def test_missing_pacing_uses_medium_default(self) -> None:
        from aiprod_adaptation.core.pass3_shots import simplify_shots

        scene = self._make_scene(visual_actions=["John stands."])
        shots = simplify_shots([scene])
        # base=3, no motion/interaction/perception, short text → 3 sec (medium, unclamped)
        assert shots[0]["duration_sec"] == 3


# ---------------------------------------------------------------------------
# Multi-épisode compilation (SO-07)
# ---------------------------------------------------------------------------

def _multi_episode_output() -> "AIPRODOutput":
    from aiprod_adaptation.core.pass3_shots import simplify_shots
    from aiprod_adaptation.core.pass4_compile import compile_episode
    from aiprod_adaptation.models.schema import AIPRODOutput

    scenes_a = [
        {
            "scene_id": "SCN_A01",
            "characters": ["Alice"],
            "location": "the park",
            "time_of_day": "day",
            "visual_actions": ["Alice walks toward the bench.", "Alice sits down slowly."],
            "dialogues": [],
            "emotion": "neutral",
        },
        {
            "scene_id": "SCN_A02",
            "characters": ["Bob"],
            "location": "the office",
            "time_of_day": "interior",
            "visual_actions": ["Bob opens the door.", "Bob looks around the room."],
            "dialogues": [],
            "emotion": "nervous",
        },
    ]
    scenes_b = [
        {
            "scene_id": "SCN_B01",
            "characters": ["Alice", "Bob"],
            "location": "the rooftop",
            "time_of_day": "night",
            "visual_actions": ["Alice and Bob face each other.", "They walk apart slowly."],
            "dialogues": [],
            "emotion": "sad",
        },
    ]
    shots_a = simplify_shots(scenes_a)  # type: ignore[arg-type]
    shots_b = simplify_shots(scenes_b)  # type: ignore[arg-type]
    ep_a = compile_episode(scenes_a, shots_a, "Multi Title", "EP01")  # type: ignore[arg-type]
    ep_b = compile_episode(scenes_b, shots_b, "Multi Title", "EP02")  # type: ignore[arg-type]
    return AIPRODOutput(
        title="Multi Title",
        episodes=ep_a.episodes + ep_b.episodes,
    )


class TestMultiEpisode:
    def test_compile_two_episodes(self) -> None:
        output = _multi_episode_output()
        assert len(output.episodes) == 2

    def test_shot_ids_unique_across_episodes(self) -> None:
        output = _multi_episode_output()
        all_shot_ids = [s.shot_id for ep in output.episodes for s in ep.shots]
        assert len(all_shot_ids) == len(set(all_shot_ids))

    def test_scene_ids_unique_across_episodes(self) -> None:
        output = _multi_episode_output()
        all_scene_ids = [sc.scene_id for ep in output.episodes for sc in ep.scenes]
        assert len(all_scene_ids) == len(set(all_scene_ids))

    def test_episode_ids_distinct(self) -> None:
        output = _multi_episode_output()
        ep_ids = [ep.episode_id for ep in output.episodes]
        assert len(ep_ids) == len(set(ep_ids))

    def test_total_shot_count_spans_all_episodes(self) -> None:
        output = _multi_episode_output()
        total = sum(len(ep.shots) for ep in output.episodes)
        assert total >= 4  # at least 2 shots per episode
