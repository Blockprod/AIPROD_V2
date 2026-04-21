"""
pytest test suite — Post-production v1

Covers:
  1. AudioRequest validation           — PP-01
  2. NullAudioAdapter                  — PP-02
  3. AudioSynchronizer                 — PP-04
  4. run_pipeline_full()               — PP-05
"""

from __future__ import annotations

import json

import pytest

from aiprod_adaptation.image_gen.image_adapter import NullImageAdapter
from aiprod_adaptation.post_prod.audio_adapter import NullAudioAdapter
from aiprod_adaptation.post_prod.audio_request import (
    AudioRequest,
    AudioResult,
    ProductionOutput,
    TimelineClip,
)
from aiprod_adaptation.post_prod.audio_synchronizer import AudioSynchronizer
from aiprod_adaptation.video_gen.video_adapter import NullVideoAdapter
from aiprod_adaptation.core.engine import run_pipeline, run_pipeline_full

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOVEL = (
    "John walked quickly through the busy city streets. "
    "He felt very excited about the important meeting. "
    "Sarah waited nervously inside the old wooden house."
)

_REQ = AudioRequest(
    shot_id="SH0001",
    scene_id="SC001",
    text="A man walks fast through the city.",
)


def _video_and_output():
    from aiprod_adaptation.image_gen.storyboard import StoryboardGenerator
    from aiprod_adaptation.video_gen.video_sequencer import VideoSequencer

    output = run_pipeline(_NOVEL, "T")
    storyboard = StoryboardGenerator(
        adapter=NullImageAdapter(), base_seed=0
    ).generate(output)
    video = VideoSequencer(adapter=NullVideoAdapter(), base_seed=0).generate(
        storyboard, output
    )
    return video, output


# ---------------------------------------------------------------------------
# 1. AudioRequest
# ---------------------------------------------------------------------------


class TestAudioRequest:
    def test_audio_request_default_voice_id(self) -> None:
        assert _REQ.voice_id == "default"

    def test_audio_request_default_language(self) -> None:
        assert _REQ.language == "en"

    def test_production_output_total_duration_sum(self) -> None:
        clips = [
            TimelineClip(
                shot_id="S1", scene_id="SC001",
                video_url="v1", audio_url="a1",
                duration_sec=4, start_sec=0,
            ),
            TimelineClip(
                shot_id="S2", scene_id="SC001",
                video_url="v2", audio_url="a2",
                duration_sec=6, start_sec=4,
            ),
        ]
        po = ProductionOutput(title="T", timeline=clips, total_duration_sec=10)
        assert po.total_duration_sec == sum(c.duration_sec for c in clips)

    def test_audio_request_invalid_duration_hint_raises(self) -> None:
        with pytest.raises(Exception):
            AudioRequest(shot_id="S1", scene_id="SC001", text="x", duration_hint_sec=0)


# ---------------------------------------------------------------------------
# 2. NullAudioAdapter
# ---------------------------------------------------------------------------


class TestNullAudioAdapter:
    def setup_method(self) -> None:
        self.adapter = NullAudioAdapter()

    def test_null_adapter_returns_audio_result(self) -> None:
        result = self.adapter.generate(_REQ)
        assert isinstance(result, AudioResult)

    def test_null_adapter_is_deterministic(self) -> None:
        r1 = self.adapter.generate(_REQ)
        r2 = self.adapter.generate(_REQ)
        assert r1.audio_url == r2.audio_url

    def test_null_adapter_shot_id_preserved(self) -> None:
        result = self.adapter.generate(_REQ)
        assert result.shot_id == _REQ.shot_id


# ---------------------------------------------------------------------------
# 3. AudioSynchronizer
# ---------------------------------------------------------------------------


class TestAudioSynchronizer:
    def setup_method(self) -> None:
        self.adapter = NullAudioAdapter()
        self.sync = AudioSynchronizer(adapter=self.adapter)

    def test_synchronizer_one_audio_per_shot(self) -> None:
        video, output = _video_and_output()
        audio_results, production = self.sync.generate(video, output)
        assert len(audio_results) == video.total_shots

    def test_synchronizer_start_sec_cumulative(self) -> None:
        video, output = _video_and_output()
        _, production = self.sync.generate(video, output)
        expected = 0
        for clip in production.timeline:
            assert clip.start_sec == expected
            expected += clip.duration_sec

    def test_synchronizer_total_duration_sum(self) -> None:
        video, output = _video_and_output()
        _, production = self.sync.generate(video, output)
        assert production.total_duration_sec == sum(
            c.duration_sec for c in production.timeline
        )

    def test_synchronizer_is_deterministic(self) -> None:
        video, output = _video_and_output()
        _, p1 = self.sync.generate(video, output)
        _, p2 = self.sync.generate(video, output)
        assert json.dumps(p1.model_dump(), sort_keys=False) == json.dumps(
            p2.model_dump(), sort_keys=False
        )

    def test_synchronizer_title_preserved(self) -> None:
        video, output = _video_and_output()
        _, production = self.sync.generate(video, output)
        assert production.title == video.title

    def test_synchronizer_error_does_not_crash(self) -> None:
        class _BrokenAdapter(NullAudioAdapter):
            def generate(self, request: AudioRequest) -> AudioResult:
                raise RuntimeError("boom")

        sync = AudioSynchronizer(adapter=_BrokenAdapter())
        video, output = _video_and_output()
        audio_results, production = sync.generate(video, output)
        assert len(audio_results) == video.total_shots
        assert all(r.model_used == "error" for r in audio_results)


# ---------------------------------------------------------------------------
# 4. run_pipeline_full()
# ---------------------------------------------------------------------------


class TestRunPipelineFull:
    def test_full_pipeline_null_adapters(self) -> None:
        output, storyboard, video, production = run_pipeline_full(
            _NOVEL,
            title="T",
            image_adapter=NullImageAdapter(),
            video_adapter=NullVideoAdapter(),
            audio_adapter=NullAudioAdapter(),
        )
        assert production is not None
        assert isinstance(production, ProductionOutput)
        assert production.total_duration_sec > 0

    def test_full_pipeline_no_audio_adapter(self) -> None:
        output, storyboard, video, production = run_pipeline_full(
            _NOVEL,
            title="T",
            image_adapter=NullImageAdapter(),
            video_adapter=NullVideoAdapter(),
            audio_adapter=None,
        )
        assert production is None

    def test_full_pipeline_output_unchanged(self) -> None:
        from aiprod_adaptation.core.engine import run_pipeline

        baseline = run_pipeline(_NOVEL, title="T")
        output, _, _, _ = run_pipeline_full(_NOVEL, title="T")
        assert output.title == baseline.title
        assert len(output.episodes) == len(baseline.episodes)
