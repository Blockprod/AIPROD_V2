from __future__ import annotations

import pytest

from aiprod_adaptation.core.comparison import compare_outputs
from aiprod_adaptation.models.schema import AIPRODOutput


def _make_output(
    *,
    title: str,
    scenes: list[dict[str, object]],
    shots: list[dict[str, object]],
) -> AIPRODOutput:
    return AIPRODOutput.model_validate(
        {
            "title": title,
            "episodes": [
                {
                    "episode_id": "EP01",
                    "scenes": scenes,
                    "shots": shots,
                }
            ],
        }
    )


class TestComparison:
    def test_compare_outputs_captures_structural_deltas(self) -> None:
        rules_output = _make_output(
            title="T",
            scenes=[
                {
                    "scene_id": "SCN_001",
                    "characters": ["Alice"],
                    "location": "Unknown",
                    "time_of_day": None,
                    "visual_actions": ["Alice enters the room."],
                    "dialogues": [],
                    "emotion": "neutral",
                },
                {
                    "scene_id": "SCN_002",
                    "characters": ["Bob"],
                    "location": "Harbor",
                    "time_of_day": None,
                    "visual_actions": ["Bob waits by the pier."],
                    "dialogues": ["We are late."],
                    "emotion": "nervous",
                },
            ],
            shots=[
                {
                    "shot_id": "SHOT_001",
                    "scene_id": "SCN_001",
                    "prompt": "Alice enters the room.",
                    "duration_sec": 3,
                    "emotion": "neutral",
                    "shot_type": "medium",
                    "camera_movement": "static",
                    "metadata": {},
                },
                {
                    "shot_id": "SHOT_002",
                    "scene_id": "SCN_002",
                    "prompt": "Bob waits by the pier.",
                    "duration_sec": 4,
                    "emotion": "nervous",
                    "shot_type": "wide",
                    "camera_movement": "static",
                    "metadata": {},
                },
            ],
        )
        llm_output = _make_output(
            title="T",
            scenes=[
                {
                    "scene_id": "SCN_001",
                    "characters": ["Alice"],
                    "location": "Library interior",
                    "time_of_day": None,
                    "visual_actions": ["Alice enters the library."],
                    "dialogues": ["Keep moving."],
                    "emotion": "neutral",
                }
            ],
            shots=[
                {
                    "shot_id": "SHOT_001",
                    "scene_id": "SCN_001",
                    "prompt": "Alice enters the library.",
                    "duration_sec": 3,
                    "emotion": "neutral",
                    "shot_type": "medium",
                    "camera_movement": "static",
                    "metadata": {},
                }
            ],
        )

        comparison = compare_outputs(rules_output, llm_output, "router")

        assert comparison.rules_dialogue_line_count == 1
        assert comparison.llm_dialogue_line_count == 1
        assert comparison.rules_known_location_scene_count == 1
        assert comparison.llm_known_location_scene_count == 1
        assert comparison.rules_only_scene_ids == ["SCN_002"]
        assert comparison.llm_only_scene_ids == []
        assert comparison.rules_only_locations == ["Harbor"]
        assert comparison.llm_only_locations == ["Library interior"]

    def test_to_summary_str_includes_structural_lines(self) -> None:
        rules_output = _make_output(
            title="T",
            scenes=[
                {
                    "scene_id": "SCN_001",
                    "characters": ["Alice"],
                    "location": "Unknown",
                    "time_of_day": None,
                    "visual_actions": ["Alice enters the room."],
                    "dialogues": [],
                    "emotion": "neutral",
                }
            ],
            shots=[],
        )
        llm_output = _make_output(
            title="T",
            scenes=[
                {
                    "scene_id": "SCN_001",
                    "characters": ["Alice"],
                    "location": "Library interior",
                    "time_of_day": None,
                    "visual_actions": ["Alice enters the library."],
                    "dialogues": ["Now."],
                    "emotion": "neutral",
                },
                {
                    "scene_id": "SCN_002",
                    "characters": ["Bob"],
                    "location": "Harbor",
                    "time_of_day": None,
                    "visual_actions": ["Bob waves."],
                    "dialogues": [],
                    "emotion": "happy",
                },
            ],
            shots=[],
        )

        summary = compare_outputs(rules_output, llm_output, "gemini").to_summary_str()

        assert "Dialogue lines: rules=0, llm=1, delta=1" in summary
        assert "Known-location scenes: rules=0, llm=2, delta=2" in summary
        assert "Scene IDs only in LLM: SCN_002" in summary
        assert "Locations only in LLM: Library interior | Harbor" in summary

    def test_to_dict_returns_structured_json_ready_payload(self) -> None:
        rules_output = _make_output(
            title="T",
            scenes=[
                {
                    "scene_id": "SCN_001",
                    "characters": ["Alice"],
                    "location": "Unknown",
                    "time_of_day": None,
                    "visual_actions": ["Alice enters the room."],
                    "dialogues": [],
                    "emotion": "neutral",
                }
            ],
            shots=[],
        )
        llm_output = _make_output(
            title="T",
            scenes=[
                {
                    "scene_id": "SCN_001",
                    "characters": ["Alice"],
                    "location": "Library interior",
                    "time_of_day": None,
                    "visual_actions": ["Alice enters the library."],
                    "dialogues": ["Now."],
                    "emotion": "neutral",
                }
            ],
            shots=[],
        )

        payload = compare_outputs(rules_output, llm_output, "router").to_dict()

        assert payload["title"] == "T"
        assert payload["llm_adapter"] == "router"
        assert payload["scene_counts"] == {"rules": 1, "llm": 1, "delta": 0}
        assert payload["dialogue_line_counts"] == {"rules": 0, "llm": 1, "delta": 1}
        assert payload["locations_only_in"] == {
            "rules": [],
            "llm": ["Library interior"],
        }
        assert payload["shared_scene_diffs"] == [
            {
                "scene_id": "SCN_001",
                "locations": {
                    "rules": "Unknown",
                    "llm": "Library interior",
                    "equal": False,
                },
                "action_counts": {"rules": 1, "llm": 1, "delta": 0},
                "dialogue_counts": {"rules": 0, "llm": 1, "delta": 1},
                "first_actions": {
                    "rules": "Alice enters the room.",
                    "llm": "Alice enters the library.",
                    "equal": False,
                },
            }
        ]
        assert payload["aligned_scene_diffs"] == [
            {
                "rules_scene_id": "SCN_001",
                "llm_scene_id": "SCN_001",
                "similarity": 0.42,
                "locations": {
                    "rules": "Unknown",
                    "llm": "Library interior",
                    "equal": False,
                },
                "action_counts": {"rules": 1, "llm": 1, "delta": 0},
                "dialogue_counts": {"rules": 0, "llm": 1, "delta": 1},
                "first_actions": {
                    "rules": "Alice enters the room.",
                    "llm": "Alice enters the library.",
                    "equal": False,
                },
            }
        ]

    def test_to_dict_aligns_shared_scene_diffs_by_scene_id(self) -> None:
        rules_output = _make_output(
            title="T",
            scenes=[
                {
                    "scene_id": "SCN_001",
                    "characters": ["Alice"],
                    "location": "Unknown",
                    "time_of_day": None,
                    "visual_actions": ["Alice enters the room."],
                    "dialogues": [],
                    "emotion": "neutral",
                },
                {
                    "scene_id": "SCN_002",
                    "characters": ["Bob"],
                    "location": "Harbor",
                    "time_of_day": None,
                    "visual_actions": ["Bob waits by the pier."],
                    "dialogues": ["We are late."],
                    "emotion": "nervous",
                },
            ],
            shots=[],
        )
        llm_output = _make_output(
            title="T",
            scenes=[
                {
                    "scene_id": "SCN_001",
                    "characters": ["Alice"],
                    "location": "Market street",
                    "time_of_day": None,
                    "visual_actions": ["Alice hurries through the market."],
                    "dialogues": [],
                    "emotion": "neutral",
                },
                {
                    "scene_id": "SCN_003",
                    "characters": ["Clara"],
                    "location": "Library interior",
                    "time_of_day": None,
                    "visual_actions": ["Clara studies the map."],
                    "dialogues": [],
                    "emotion": "neutral",
                },
            ],
            shots=[],
        )

        payload = compare_outputs(rules_output, llm_output, "router").to_dict()

        assert [item["scene_id"] for item in payload["shared_scene_diffs"]] == ["SCN_001"]
        assert [item["rules_scene_id"] for item in payload["aligned_scene_diffs"]] == ["SCN_001"]
        assert [item["llm_scene_id"] for item in payload["aligned_scene_diffs"]] == ["SCN_001"]

    def test_to_dict_can_realign_scene_beyond_identical_scene_id(self) -> None:
        rules_output = _make_output(
            title="T",
            scenes=[
                {
                    "scene_id": "SCN_001",
                    "characters": ["Alice"],
                    "location": "Town square",
                    "time_of_day": None,
                    "visual_actions": ["Alice waits in the square."],
                    "dialogues": [],
                    "emotion": "neutral",
                },
                {
                    "scene_id": "SCN_002",
                    "characters": ["Bob"],
                    "location": "Harbor",
                    "time_of_day": None,
                    "visual_actions": ["Bob loads the crates."],
                    "dialogues": [],
                    "emotion": "neutral",
                },
                {
                    "scene_id": "SCN_003",
                    "characters": ["Clara"],
                    "location": "Ship cabin interior",
                    "time_of_day": None,
                    "visual_actions": ["Clara studies the map in the cabin."],
                    "dialogues": ["The route still works."],
                    "emotion": "neutral",
                },
            ],
            shots=[],
        )
        llm_output = _make_output(
            title="T",
            scenes=[
                {
                    "scene_id": "SCN_001",
                    "characters": ["Alice"],
                    "location": "Market street",
                    "time_of_day": None,
                    "visual_actions": ["Alice rushes through the market."],
                    "dialogues": [],
                    "emotion": "neutral",
                },
                {
                    "scene_id": "SCN_002",
                    "characters": ["Clara"],
                    "location": "Ship cabin interior",
                    "time_of_day": None,
                    "visual_actions": ["Clara studies the map in the cabin."],
                    "dialogues": ["The route still works."],
                    "emotion": "neutral",
                },
            ],
            shots=[],
        )

        payload = compare_outputs(rules_output, llm_output, "router").to_dict()

        assert payload["aligned_scene_diffs"][1]["rules_scene_id"] == "SCN_003"
        assert payload["aligned_scene_diffs"][1]["llm_scene_id"] == "SCN_002"

    def test_output_validation_rejects_unknown_shot_metadata_keys(self) -> None:
        with pytest.raises(ValueError, match="Invalid metadata keys"):
            _make_output(
                title="T",
                scenes=[
                    {
                        "scene_id": "SCN_001",
                        "characters": ["Alice"],
                        "location": "Harbor",
                        "time_of_day": None,
                        "visual_actions": ["Alice waits by the pier."],
                        "dialogues": [],
                        "emotion": "neutral",
                    }
                ],
                shots=[
                    {
                        "shot_id": "SHOT_001",
                        "scene_id": "SCN_001",
                        "prompt": "Alice waits by the pier.",
                        "duration_sec": 4,
                        "emotion": "neutral",
                        "shot_type": "wide",
                        "camera_movement": "static",
                        "metadata": {"camera_hint": "crane"},
                    }
                ],
            )
