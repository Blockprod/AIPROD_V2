"""
pytest test suite — VideoSequencer + RunwayAdapter Phase 1

Covers:
  VS-01 — build_requests propagates reference_image_url into character_reference_urls
  VS-02 — build_requests yields character_reference_urls == [] when reference_image_url is empty
  VS-03 — RunwayAdapter with model=gen4_aleph calls video_to_video.create, NOT image_to_video.create
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aiprod_adaptation.image_gen.image_request import (
    ShotStoryboardFrame,
    StoryboardOutput,
)
from aiprod_adaptation.models.schema import AIPRODOutput, Episode, Scene, Shot
from aiprod_adaptation.video_gen.runway_adapter import RunwayAdapter
from aiprod_adaptation.video_gen.video_adapter import NullVideoAdapter
from aiprod_adaptation.video_gen.video_request import VideoRequest
from aiprod_adaptation.video_gen.video_sequencer import VideoSequencer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_storyboard(ref_url: str = "") -> StoryboardOutput:
    frame = ShotStoryboardFrame(
        shot_id="SH0001",
        scene_id="SC001",
        image_url="http://example.com/frame.png",
        model_used="null",
        latency_ms=100,
        prompt_used="a frame",
        reference_image_url=ref_url,
    )
    return StoryboardOutput(title="Test", frames=[frame], total_shots=1, generated=1)


def _make_output() -> AIPRODOutput:
    shot = Shot(
        shot_id="SH0001",
        scene_id="SC001",
        prompt="A man walks.",
        duration_sec=5,
        emotion="neutral",
    )
    scene = Scene(
        scene_id="SC001",
        characters=["John"],
        location="city",
        visual_actions=["John walks"],
        dialogues=[],
        emotion="neutral",
    )
    episode = Episode(episode_id="EP01", scenes=[scene], shots=[shot])
    return AIPRODOutput(title="Test", episodes=[episode])


# ---------------------------------------------------------------------------
# VS-01 — propagation non-empty reference_image_url
# ---------------------------------------------------------------------------


class TestBuildRequestsPropagation:
    def test_reference_image_url_propagated(self) -> None:
        storyboard = _make_storyboard(ref_url="http://example.com/char_ref.png")
        output = _make_output()
        sequencer = VideoSequencer(adapter=NullVideoAdapter())
        requests = sequencer.build_requests(storyboard, output)

        assert len(requests) == 1
        assert requests[0].character_reference_urls == ["http://example.com/char_ref.png"]

    def test_empty_reference_image_url_yields_empty_list(self) -> None:
        storyboard = _make_storyboard(ref_url="")
        output = _make_output()
        sequencer = VideoSequencer(adapter=NullVideoAdapter())
        requests = sequencer.build_requests(storyboard, output)

        assert len(requests) == 1
        assert requests[0].character_reference_urls == []


# ---------------------------------------------------------------------------
# VS-03 — RunwayAdapter routing gen4_aleph → video_to_video.create
# ---------------------------------------------------------------------------


class TestRunwayAdapterAlephRouting:
    def test_aleph_uses_video_to_video(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_result = MagicMock()
        mock_result.output = ["http://video.url/clip.mp4"]
        mock_task = MagicMock()
        mock_task.wait_for_task_output.return_value = mock_result
        mock_client = MagicMock()
        mock_client.video_to_video.create.return_value = mock_task

        monkeypatch.setattr(
            "aiprod_adaptation.video_gen.runway_adapter._build_runway_client",
            lambda _token: mock_client,
        )

        adapter = RunwayAdapter(api_token="fake-token", model="gen4_aleph")
        request = VideoRequest(
            shot_id="SH0001",
            scene_id="SC001",
            image_url="http://prev-clip.mp4",
            prompt="test prompt",
            duration_sec=5,
            character_reference_urls=["http://char-ref.png"],
        )
        result = adapter.generate(request)

        mock_client.video_to_video.create.assert_called_once()
        mock_client.image_to_video.create.assert_not_called()
        assert result.model_used == "gen4_aleph"
        assert result.video_url == "http://video.url/clip.mp4"
