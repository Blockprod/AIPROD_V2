"""
pytest test suite — Video Generation Connector v1

Covers:
  1. VideoRequest validation           — VG-01
  2. NullVideoAdapter                  — VG-02
  3. VideoSequencer                    — VG-04
  4. run_pipeline_with_video()         — VG-05
"""

from __future__ import annotations

import json

import pytest

from aiprod_adaptation.image_gen.image_adapter import NullImageAdapter
from aiprod_adaptation.video_gen.video_adapter import NullVideoAdapter
from aiprod_adaptation.video_gen.video_request import (
    VideoClipResult,
    VideoOutput,
    VideoRequest,
)
from aiprod_adaptation.video_gen.video_sequencer import VideoSequencer
from aiprod_adaptation.core.engine import run_pipeline, run_pipeline_with_video


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOVEL = (
    "John walked quickly through the busy city streets. "
    "He felt very excited about the important meeting. "
    "Sarah waited nervously inside the old wooden house."
)

_REQ = VideoRequest(
    shot_id="SH0001",
    scene_id="SC001",
    image_url="null://storyboard/SH0001.png",
    prompt="A man walks fast.",
    duration_sec=4,
)


def _storyboard_and_output():
    from aiprod_adaptation.image_gen.storyboard import StoryboardGenerator
    output = run_pipeline(_NOVEL, "T")
    storyboard = StoryboardGenerator(
        adapter=NullImageAdapter(), base_seed=0
    ).generate(output)
    return storyboard, output


# ---------------------------------------------------------------------------
# 1. VideoRequest
# ---------------------------------------------------------------------------

class TestVideoRequest:
    def test_video_request_default_motion_score(self) -> None:
        assert _REQ.motion_score == 5.0

    def test_video_request_duration_preserved(self) -> None:
        assert _REQ.duration_sec == 4

    def test_video_output_generated_lte_total(self) -> None:
        vo = VideoOutput(title="T", clips=[], total_shots=5, generated=3)
        assert vo.generated <= vo.total_shots

    def test_video_request_invalid_motion_score_raises(self) -> None:
        with pytest.raises(Exception):
            VideoRequest(
                shot_id="S1", scene_id="SC001",
                image_url="http://x.png", prompt="test",
                duration_sec=4, motion_score=0.5,
            )


# ---------------------------------------------------------------------------
# 2. NullVideoAdapter
# ---------------------------------------------------------------------------

class TestNullVideoAdapter:
    def setup_method(self) -> None:
        self.adapter = NullVideoAdapter()

    def test_null_adapter_returns_video_clip_result(self) -> None:
        result = self.adapter.generate(_REQ)
        assert isinstance(result, VideoClipResult)

    def test_null_adapter_is_deterministic(self) -> None:
        r1 = self.adapter.generate(_REQ)
        r2 = self.adapter.generate(_REQ)
        assert r1.video_url == r2.video_url

    def test_null_adapter_shot_id_preserved(self) -> None:
        result = self.adapter.generate(_REQ)
        assert result.shot_id == _REQ.shot_id


# ---------------------------------------------------------------------------
# 3. VideoSequencer
# ---------------------------------------------------------------------------

class TestVideoSequencer:
    def setup_method(self) -> None:
        self.adapter = NullVideoAdapter()
        self.seq = VideoSequencer(adapter=self.adapter, base_seed=0)

    def test_sequencer_generates_one_clip_per_shot(self) -> None:
        storyboard, output = _storyboard_and_output()
        video = self.seq.generate(storyboard, output)
        assert len(video.clips) == storyboard.total_shots

    def test_sequencer_is_deterministic(self) -> None:
        storyboard, output = _storyboard_and_output()
        v1 = self.seq.generate(storyboard, output)
        v2 = self.seq.generate(storyboard, output)
        assert json.dumps(v1.model_dump(), sort_keys=False) == \
               json.dumps(v2.model_dump(), sort_keys=False)

    def test_sequencer_title_preserved(self) -> None:
        storyboard, output = _storyboard_and_output()
        video = self.seq.generate(storyboard, output)
        assert video.title == "T"

    def test_sequencer_generated_count_correct(self) -> None:
        storyboard, output = _storyboard_and_output()
        video = self.seq.generate(storyboard, output)
        assert video.generated == video.total_shots

    def test_sequencer_build_requests_count(self) -> None:
        storyboard, output = _storyboard_and_output()
        reqs = self.seq.build_requests(storyboard, output)
        assert len(reqs) == storyboard.total_shots

    def test_sequencer_error_does_not_crash(self) -> None:
        class BrokenAdapter(NullVideoAdapter):
            def generate(self, request: VideoRequest) -> VideoClipResult:
                raise RuntimeError("API down")

        seq = VideoSequencer(adapter=BrokenAdapter(), base_seed=0)
        storyboard, output = _storyboard_and_output()
        video = seq.generate(storyboard, output)
        assert all(c.model_used == "error" for c in video.clips)
        assert video.generated == 0


# ---------------------------------------------------------------------------
# 4. run_pipeline_with_video
# ---------------------------------------------------------------------------

class TestRunPipelineWithVideo:
    def test_run_with_video_null_adapters(self) -> None:
        output, storyboard, video = run_pipeline_with_video(
            _NOVEL, "T",
            image_adapter=NullImageAdapter(),
            video_adapter=NullVideoAdapter(),
        )
        assert storyboard is not None
        assert video is not None
        assert video.total_shots > 0

    def test_run_with_video_no_video_adapter(self) -> None:
        output, storyboard, video = run_pipeline_with_video(
            _NOVEL, "T",
            image_adapter=NullImageAdapter(),
        )
        assert storyboard is not None
        assert video is None

    def test_run_with_video_no_image_adapter(self) -> None:
        output, storyboard, video = run_pipeline_with_video(_NOVEL, "T")
        assert storyboard is None
        assert video is None
