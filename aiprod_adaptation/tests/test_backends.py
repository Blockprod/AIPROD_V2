"""
pytest test suite for AIPROD backends.

Covered cases:
  1. CsvExport — header columns
  2. CsvExport — row count matches shot count
  3. CsvExport — deterministic (byte-identical twice)
  4. JsonFlatExport — output is a JSON list
  5. JsonFlatExport — each item contains episode_id
  6. JsonFlatExport — deterministic (byte-identical twice)
"""

from __future__ import annotations

import csv
import io
import json
from aiprod_adaptation.backends.csv_export import CsvExport
from aiprod_adaptation.backends.json_flat_export import JsonFlatExport
from aiprod_adaptation.core.engine import run_pipeline
from aiprod_adaptation.models.schema import AIPRODOutput

_SAMPLE = (
    "John walked quickly through the busy city streets. "
    "He felt very excited about the important meeting. "
    "Suddenly dark clouds appeared and it started raining heavily. "
    "Later that evening, inside the old wooden house, Sarah waited nervously. "
    "She thought about their difficult past. "
    "John finally entered the room and gave her a warm smile."
)


def _get_output():  # type: ignore[return]
    return run_pipeline(_SAMPLE, "Test Title")


# ---------------------------------------------------------------------------
# CsvExport
# ---------------------------------------------------------------------------

class TestCsvExport:
    def test_csv_export_header(self) -> None:
        result = CsvExport().export(_get_output())
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        assert header == ["episode_id", "scene_id", "shot_id", "shot_type", "camera_movement", "prompt", "duration_sec", "emotion"]

    def test_csv_export_row_count(self) -> None:
        output = _get_output()
        result = CsvExport().export(output)
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        expected_shots = sum(len(ep.shots) for ep in output.episodes)
        # rows[0] = header, rest = data
        assert len(rows) - 1 == expected_shots

    def test_csv_export_deterministic(self) -> None:
        out1 = CsvExport().export(_get_output())
        out2 = CsvExport().export(_get_output())
        assert out1 == out2


# ---------------------------------------------------------------------------
# JsonFlatExport
# ---------------------------------------------------------------------------

class TestJsonFlatExport:
    def test_json_flat_export_is_list(self) -> None:
        result = JsonFlatExport().export(_get_output())
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) >= 1

    def test_json_flat_export_episode_id_present(self) -> None:
        result = JsonFlatExport().export(_get_output())
        parsed = json.loads(result)
        for item in parsed:
            assert "episode_id" in item

    def test_json_flat_export_deterministic(self) -> None:
        out1 = JsonFlatExport().export(_get_output())
        out2 = JsonFlatExport().export(_get_output())
        assert out1 == out2


# ---------------------------------------------------------------------------
# Multi-épisodes backends (SO-07)
# ---------------------------------------------------------------------------

def _multi_episode_output() -> AIPRODOutput:
    from aiprod_adaptation.core.pass3_shots import simplify_shots
    from aiprod_adaptation.core.pass4_compile import compile_episode
    from aiprod_adaptation.models.schema import AIPRODOutput

    scenes_a = [
        {
            "scene_id": "SCN_A01", "characters": ["Alice"], "location": "the park",
            "time_of_day": "day",
            "visual_actions": ["Alice walks.", "Alice sits."],
            "dialogues": [], "emotion": "neutral",
        },
    ]
    scenes_b = [
        {
            "scene_id": "SCN_B01", "characters": ["Bob"], "location": "the office",
            "time_of_day": "interior",
            "visual_actions": ["Bob opens the door.", "Bob walks in."],
            "dialogues": [], "emotion": "nervous",
        },
    ]
    shots_a = simplify_shots(scenes_a)  # type: ignore[arg-type]
    shots_b = simplify_shots(scenes_b)  # type: ignore[arg-type]
    ep_a = compile_episode(scenes_a, shots_a, "T", "EP01")  # type: ignore[arg-type]
    ep_b = compile_episode(scenes_b, shots_b, "T", "EP02")  # type: ignore[arg-type]
    return AIPRODOutput(title="T", episodes=ep_a.episodes + ep_b.episodes)


class TestMultiEpisodeBackends:
    def test_csv_export_includes_all_episodes(self) -> None:
        output = _multi_episode_output()
        result = CsvExport().export(output)
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)[1:]  # skip header
        total_shots = sum(len(ep.shots) for ep in output.episodes)
        assert len(rows) == total_shots

    def test_json_flat_export_includes_all_episodes(self) -> None:
        output = _multi_episode_output()
        result = JsonFlatExport().export(output)
        parsed = json.loads(result)
        total_shots = sum(len(ep.shots) for ep in output.episodes)
        assert len(parsed) == total_shots

    def test_json_flat_export_both_episode_ids_present(self) -> None:
        output = _multi_episode_output()
        result = JsonFlatExport().export(output)
        parsed = json.loads(result)
        ep_ids = {item["episode_id"] for item in parsed}
        assert "EP01" in ep_ids
        assert "EP02" in ep_ids
