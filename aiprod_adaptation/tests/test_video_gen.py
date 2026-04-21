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


# ---------------------------------------------------------------------------
# 5. LastFrameChaining — PQ-03
# ---------------------------------------------------------------------------

class TestLastFrameChaining:
    def test_first_shot_has_no_last_frame_hint(self) -> None:
        received: list[str] = []

        class TrackingAdapter(NullVideoAdapter):
            def generate(self, request: VideoRequest) -> VideoClipResult:
                received.append(request.last_frame_hint_url)
                return super().generate(request)

        storyboard, output = _storyboard_and_output()
        VideoSequencer(adapter=TrackingAdapter(), base_seed=0).generate(storyboard, output)
        assert received[0] == ""

    def test_shots_different_scenes_not_chained(self) -> None:
        """Shots in different scenes must never receive a last_frame_hint."""
        received_hints: list[tuple[str, str]] = []  # (scene_id, hint)

        class TrackingAdapter(NullVideoAdapter):
            def generate(self, request: VideoRequest) -> VideoClipResult:
                received_hints.append((request.scene_id, request.last_frame_hint_url))
                return super().generate(request)

        storyboard, output = _storyboard_and_output()
        VideoSequencer(adapter=TrackingAdapter(), base_seed=0).generate(storyboard, output)
        # For any shot that has a hint, its scene_id must equal the previous shot's scene_id
        prev_scene = ""
        for i, (scene_id, hint) in enumerate(received_hints):
            if hint:
                assert scene_id == prev_scene, (
                    f"Shot {i} got a cross-scene hint: {prev_scene!r} → {scene_id!r}"
                )
            prev_scene = scene_id

    def test_empty_last_frame_url_does_not_chain(self) -> None:
        """NullVideoAdapter returns last_frame_url="" → no chaining should occur."""
        storyboard, output = _storyboard_and_output()
        video = VideoSequencer(adapter=NullVideoAdapter(), base_seed=0).generate(
            storyboard, output
        )
        # NullVideoAdapter never sets last_frame_url → all hints remain ""
        for clip in video.clips:
            assert clip.last_frame_url == ""

    def test_last_frame_url_field_exists_on_clip_result(self) -> None:
        result = NullVideoAdapter().generate(_REQ)
        assert hasattr(result, "last_frame_url")
        assert result.last_frame_url == ""


# ---------------------------------------------------------------------------
# 6. SmartVideoRouter — PQ-04
# ---------------------------------------------------------------------------

class TestSmartVideoRouter:
    def setup_method(self) -> None:
        from aiprod_adaptation.video_gen.smart_video_router import SmartVideoRouter

        class _TaggedAdapter(NullVideoAdapter):
            def __init__(self, tag: str) -> None:
                self.tag = tag

            def generate(self, request: VideoRequest) -> VideoClipResult:
                result = super().generate(request)
                return result.model_copy(update={"model_used": self.tag})

        self.runway = _TaggedAdapter("runway")
        self.kling = _TaggedAdapter("kling")
        self.router = SmartVideoRouter(
            runway_adapter=self.runway,
            kling_adapter=self.kling,
            threshold_sec=5,
        )

    def _req(self, duration: int) -> VideoRequest:
        return VideoRequest(
            shot_id="S1", scene_id="SC001",
            image_url="null://img.png", prompt="test",
            duration_sec=duration,
        )

    def test_router_uses_runway_for_short_shot(self) -> None:
        result = self.router.generate(self._req(3))
        assert result.model_used == "runway"

    def test_router_uses_kling_for_long_shot(self) -> None:
        result = self.router.generate(self._req(8))
        assert result.model_used == "kling"

    def test_router_threshold_boundary_uses_runway(self) -> None:
        result = self.router.generate(self._req(5))
        assert result.model_used == "runway"

    def test_router_threshold_boundary_plus1_uses_kling(self) -> None:
        result = self.router.generate(self._req(6))
        assert result.model_used == "kling"

    def test_router_custom_threshold(self) -> None:
        from aiprod_adaptation.video_gen.smart_video_router import SmartVideoRouter

        router = SmartVideoRouter(self.runway, self.kling, threshold_sec=3)
        assert router.generate(self._req(3)).model_used == "runway"
        assert router.generate(self._req(4)).model_used == "kling"
