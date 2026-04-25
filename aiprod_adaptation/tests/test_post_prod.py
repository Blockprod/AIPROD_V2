"""
pytest test suite — Post-production v1 + Pipeline Quality (PQ-02, PQ-05, PQ-06)

Covers:
  1. AudioRequest validation           — PP-01
  2. NullAudioAdapter                  — PP-02
  3. AudioSynchronizer                 — PP-04
  4. run_pipeline_full()               — PP-05
  5. AudioDurationSync                 — PQ-02
  6. SSMLBuilder                       — PQ-05
  7. FFmpegExporter                    — PQ-06
"""

from __future__ import annotations

import json

import pytest

from aiprod_adaptation.core.engine import run_pipeline, run_pipeline_full
from aiprod_adaptation.image_gen.image_adapter import NullImageAdapter
from aiprod_adaptation.models.schema import AIPRODOutput
from aiprod_adaptation.post_prod.audio_adapter import NullAudioAdapter
from aiprod_adaptation.post_prod.audio_request import (
    AudioRequest,
    AudioResult,
    ProductionOutput,
    TimelineClip,
)
from aiprod_adaptation.post_prod.audio_synchronizer import AudioSynchronizer
from aiprod_adaptation.post_prod.runway_tts_adapter import RunwayTTSAdapter
from aiprod_adaptation.video_gen.video_adapter import NullVideoAdapter
from aiprod_adaptation.video_gen.video_request import VideoOutput

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


def _video_and_output() -> tuple[VideoOutput, AIPRODOutput]:
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

    def test_audio_request_accepts_structured_action(self) -> None:
        req = AudioRequest(
            shot_id="S1",
            scene_id="SC001",
            text="x",
            action={
                "subject_id": "john",
                "action_type": "walked",
                "target": "door",
                "modifiers": ["quickly"],
                "location_id": "hallway",
                "camera_intent": "follow",
                "source_text": "John walked quickly to the door.",
            },
        )
        assert req.action is not None
        assert req.action.source_text == "John walked quickly to the door."


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


class TestRunwayTTSAdapter:
    def test_runway_tts_adapter_requires_token(self) -> None:
        adapter = RunwayTTSAdapter(api_token="")

        with pytest.raises(ValueError, match="RUNWAY_API_TOKEN"):
            adapter.generate(_REQ)


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

    def test_synchronizer_raises_on_unknown_video_shot_id(self) -> None:
        video, output = _video_and_output()
        broken_video = video.model_copy(
            update={
                "clips": [video.clips[0].model_copy(update={"shot_id": "SHOT_MISSING"})]
            }
        )

        with pytest.raises(
            ValueError,
            match="Video clip references unknown shot_id: SHOT_MISSING",
        ):
            self.sync.build_requests(broken_video, output)

    def test_synchronizer_build_requests_include_structured_action(self) -> None:
        video, output = _video_and_output()
        requests = self.sync.build_requests(video, output)
        assert requests[0].action is not None
        assert requests[0].action.source_text == output.episodes[0].shots[0].action.source_text

    def test_synchronizer_error_does_not_crash(self) -> None:
        from unittest.mock import MagicMock, patch

        class _BrokenAdapter(NullAudioAdapter):
            def generate(self, _request: AudioRequest) -> AudioResult:
                raise RuntimeError("boom")

        sync = AudioSynchronizer(adapter=_BrokenAdapter())
        video, output = _video_and_output()
        logger = MagicMock()
        with patch("aiprod_adaptation.post_prod.audio_synchronizer.logger", logger):
            audio_results, production = sync.generate(video, output)
        assert len(audio_results) == video.total_shots
        assert all(r.model_used == "error" for r in audio_results)
        assert len(production.timeline) == video.total_shots
        logger.warning.assert_called()

    def test_synchronizer_with_empty_clips(self) -> None:
        video = VideoOutput(title="T", clips=[], total_shots=0, generated=0)
        _, output = _video_and_output()
        audio_results, production = AudioSynchronizer(
            adapter=NullAudioAdapter()
        ).generate(video, output)
        assert audio_results == []
        assert production.timeline == []
        assert production.total_duration_sec == 0

    def test_synchronizer_build_requests_propagates_structured_action(self) -> None:
        video, output = _video_and_output()
        requests = self.sync.build_requests(video, output)
        assert requests[0].action is not None
        assert requests[0].action.subject_id != ""


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


# ---------------------------------------------------------------------------
# 5. AudioDurationSync — PQ-02
# ---------------------------------------------------------------------------


class TestAudioDurationSync:
    def test_timeline_clip_has_audio_duration_field(self) -> None:
        from aiprod_adaptation.post_prod.audio_request import TimelineClip

        clip = TimelineClip(
            shot_id="S1", scene_id="SC001",
            video_url="v", audio_url="a",
            duration_sec=4, start_sec=0,
        )
        assert clip.audio_duration_sec == 0
        assert clip.silence_padding_sec == 0

    def test_timeline_clip_silence_padding_when_audio_shorter(self) -> None:
        from aiprod_adaptation.post_prod.audio_request import TimelineClip

        clip = TimelineClip(
            shot_id="S1", scene_id="SC001",
            video_url="v", audio_url="a",
            duration_sec=6, start_sec=0,
            audio_duration_sec=4, silence_padding_sec=2,
        )
        assert clip.silence_padding_sec == clip.duration_sec - clip.audio_duration_sec

    def test_synchronizer_uses_real_duration_when_available(self) -> None:
        # NullAudioAdapter returns audio_b64="" → fallback to duration_hint_sec
        # duration_hint_sec == clip.duration_sec → silence_padding should be 0
        sync = AudioSynchronizer(adapter=NullAudioAdapter())
        video, output = _video_and_output()
        _, production = sync.generate(video, output)
        for clip in production.timeline:
            assert clip.audio_duration_sec >= 1

    def test_audio_utils_fallback_without_mutagen(self) -> None:
        from aiprod_adaptation.post_prod.audio_utils import audio_duration_from_b64

        # Empty b64 → fallback
        assert audio_duration_from_b64("", duration_hint_sec=5) == 5
        # Invalid b64 → fallback
        assert audio_duration_from_b64("NOT_VALID_B64!!!", duration_hint_sec=3) == 3


# ---------------------------------------------------------------------------
# 6. SSMLBuilder — PQ-05
# ---------------------------------------------------------------------------


class TestSSMLBuilder:
    def setup_method(self) -> None:
        from aiprod_adaptation.post_prod.ssml_builder import SSMLBuilder

        self.builder = SSMLBuilder()

    def test_ssml_wraps_text_in_speak_tags(self) -> None:
        result = self.builder.build("Hello world.", "neutral")
        assert result.startswith("<speak>")
        assert result.endswith("</speak>")

    def test_ssml_fear_uses_slow_rate(self) -> None:
        result = self.builder.build("Run!", "fear")
        assert 'rate="slow"' in result

    def test_ssml_joy_uses_high_pitch(self) -> None:
        result = self.builder.build("Great!", "joy")
        assert 'pitch="high"' in result

    def test_ssml_unknown_emotion_falls_back_to_neutral(self) -> None:
        neutral = self.builder.build("X", "neutral")
        unknown = self.builder.build("X", "nonexistent_emotion")
        assert neutral == unknown

    def test_audio_request_ssml_flag_default_false(self) -> None:
        req = AudioRequest(shot_id="S1", scene_id="SC001", text="hello")
        assert req.ssml is False


# ---------------------------------------------------------------------------
# 7. FFmpegExporter — PQ-06
# ---------------------------------------------------------------------------


class TestFFmpegExporter:
    def _make_production(self) -> ProductionOutput:
        from aiprod_adaptation.post_prod.audio_request import ProductionOutput, TimelineClip

        clips = [
            TimelineClip(
                shot_id="S1", scene_id="SC001",
                video_url="/tmp/v1.mp4", audio_url="/tmp/a1.mp3",
                duration_sec=4, start_sec=0,
            ),
        ]
        return ProductionOutput(title="T", timeline=clips, total_duration_sec=4)

    def test_exporter_raises_if_ffmpeg_not_found(self) -> None:
        from aiprod_adaptation.post_prod.ffmpeg_exporter import FFmpegExporter

        exporter = FFmpegExporter("/tmp/out.mp4", ffmpeg_bin="ffmpeg_does_not_exist_xyz")
        production = self._make_production()
        with pytest.raises(FileNotFoundError):
            exporter.export(production)

    def test_exporter_builds_correct_command_args(self) -> None:
        """Verify the concat ffmpeg call includes resolution and fps."""
        from unittest.mock import patch

        from aiprod_adaptation.post_prod.ffmpeg_exporter import FFmpegExporter

        production = self._make_production()
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], **_: object) -> None:
            calls.append(cmd)

        with patch("subprocess.run", side_effect=fake_run):
            FFmpegExporter("/tmp/out.mp4").export(production)

        # Last call is the concat — should include resolution and fps
        concat_call = calls[-1]
        assert production.resolution in concat_call
        assert str(production.fps) in concat_call

    def test_exporter_respects_resolution_from_production(self) -> None:
        from unittest.mock import patch

        from aiprod_adaptation.post_prod.audio_request import ProductionOutput, TimelineClip
        from aiprod_adaptation.post_prod.ffmpeg_exporter import FFmpegExporter

        clips = [TimelineClip(
            shot_id="S1", scene_id="SC001",
            video_url="/v.mp4", audio_url="/a.mp3",
            duration_sec=4, start_sec=0,
        )]
        prod = ProductionOutput(
            title="T", timeline=clips, total_duration_sec=4, resolution="1920x1080"
        )
        calls: list[list[str]] = []
        with patch("subprocess.run", side_effect=lambda cmd, **_: calls.append(cmd)):
            FFmpegExporter("/tmp/out.mp4").export(prod)
        assert "1920x1080" in calls[-1]

    def test_exporter_respects_fps_from_production(self) -> None:
        from unittest.mock import patch

        from aiprod_adaptation.post_prod.audio_request import ProductionOutput, TimelineClip
        from aiprod_adaptation.post_prod.ffmpeg_exporter import FFmpegExporter

        clips = [TimelineClip(
            shot_id="S1", scene_id="SC001",
            video_url="/v.mp4", audio_url="/a.mp3",
            duration_sec=4, start_sec=0,
        )]
        prod = ProductionOutput(
            title="T", timeline=clips, total_duration_sec=4, fps=30
        )
        calls: list[list[str]] = []
        with patch("subprocess.run", side_effect=lambda cmd, **_: calls.append(cmd)):
            FFmpegExporter("/tmp/out.mp4").export(prod)
        assert "30" in calls[-1]
