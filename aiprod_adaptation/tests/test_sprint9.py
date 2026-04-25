"""
test_sprint9.py — Sprint 9 tests: metrics, post-production, exports, CLI.

Coverage
--------
  TestQualityMetricsModels      (5)  — schema + constants
  TestMetricsEngine             (12) — all 6 KPIs + season + broadcast gate
  TestPostProductionModels      (5)  — dataclass + Pydantic construction
  TestAudioDirectivesBuilder    (6)  — tone/emotion → cue mapping + timecodes
  TestContinuityBuilder         (5)  — detecting establishing / lighting / color violations
  TestTimelineBuilder           (5)  — transitions + timecode accumulation
  TestEDLJsonExport             (4)  — EDL JSON structure
  TestResolveTimelineExport     (4)  — Resolve JSON tracks
  TestAudioCueSheetExport       (3)  — cue sheet JSON
  TestBatchGenerationExport     (4)  — batch manifest JSON
  TestSeasonReportExport        (4)  — season report JSON
  TestCLIMetricsCommand         (4)  — CLI metrics subcommand
  TestCLIExportCommand          (4)  — CLI export subcommand

Total: 65 tests
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import sys
import tempfile

import pytest

from aiprod_adaptation.core.metrics import MetricsEngine
from aiprod_adaptation.core.metrics.models import (
    NETFLIX_TARGET_CINEMATIC_RICHNESS,
    NETFLIX_TARGET_CONFLICT_RESOLUTION,
    NETFLIX_TARGET_CONTINUITY,
    NETFLIX_TARGET_FEASIBILITY,
    NETFLIX_TARGET_OVERALL_COHERENCE,
    NETFLIX_TARGET_REFERENCE_QUALITY,
    NETFLIX_TARGET_VISUAL_CONSISTENCY,
    EpisodeMetrics,
    SeasonMetrics,
    ShotMetrics,
)
from aiprod_adaptation.core.postproduction import build_manifest_for_episode
from aiprod_adaptation.core.postproduction._timecode import frames_to_timecode, timecode_to_frames
from aiprod_adaptation.core.postproduction.audio_directives import AudioDirectivesBuilder
from aiprod_adaptation.core.postproduction.continuity import ContinuityBuilder
from aiprod_adaptation.core.postproduction.models import (
    AudioCue,
    ContinuityNote,
    PostProductionManifest,
    TimelineClip,
)
from aiprod_adaptation.core.postproduction.timeline import TimelineBuilder
from aiprod_adaptation.models.schema import (
    ActionSpec,
    AIPRODOutput,
    ConsistencyReport,
    Episode,
    PacingProfile,
    RuleEngineReport,
    Scene,
    Shot,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_action(subject_id: str = "char_a") -> ActionSpec:
    return ActionSpec(
        subject_id=subject_id,
        action_type="moves",
        target=None,
        modifiers=[],
        location_id="loc_x",
        camera_intent="static",
        source_text="moves",
    )


def _make_shot(
    shot_id: str = "S01",
    scene_id: str = "SC01",
    shot_type: str = "medium",
    camera_movement: str = "static",
    emotion: str = "neutral",
    duration_sec: int = 5,
    feasibility_score: int = 100,
    reference_anchor_strength: float = 1.0,
    metadata: dict | None = None,
    lighting_directives: str | None = None,
    composition_description: str | None = None,
) -> Shot:
    return Shot(
        shot_id=shot_id,
        scene_id=scene_id,
        prompt=f"A {shot_type} shot.",
        duration_sec=duration_sec,
        emotion=emotion,
        shot_type=shot_type,
        camera_movement=camera_movement,
        action=_make_action(),
        metadata=metadata or {},
        feasibility_score=feasibility_score,
        reference_anchor_strength=reference_anchor_strength,
        lighting_directives=lighting_directives,
        composition_description=composition_description,
    )


def _make_scene(scene_id: str = "SC01", scene_tone: str | None = None) -> Scene:
    return Scene(
        scene_id=scene_id,
        characters=["Alice"],
        location="Office",
        visual_actions=["walks"],
        dialogues=["Hello"],
        emotion="neutral",
        scene_tone=scene_tone,
    )


def _make_episode(
    episode_id: str = "EP01",
    shots: list[Shot] | None = None,
    scenes: list[Scene] | None = None,
    consistency_score: float = 0.9,
    rule_engine_report: RuleEngineReport | None = None,
) -> Episode:
    _shots = shots or [_make_shot()]
    _scenes = scenes or [_make_scene()]
    return Episode(
        episode_id=episode_id,
        scenes=_scenes,
        shots=_shots,
        pacing_profile=PacingProfile(
            total_duration_sec=sum(s.duration_sec for s in _shots),
            mean_shot_duration=sum(s.duration_sec for s in _shots) / len(_shots),
            shot_count=len(_shots),
            pacing_label="medium",
        ),
        consistency_report=ConsistencyReport(consistency_score=consistency_score),
        rule_engine_report=rule_engine_report,
    )


def _make_output(episode_id: str = "EP01", **kwargs) -> AIPRODOutput:
    ep = _make_episode(episode_id=episode_id, **kwargs)
    return AIPRODOutput(title="Test", episodes=[ep])


# ===========================================================================
# 1. TestQualityMetricsModels
# ===========================================================================

class TestQualityMetricsModels:

    def test_shot_metrics_construction(self):
        sm = ShotMetrics(shot_id="S01", reference_quality_score=0.8, feasibility_normalized=0.9)
        assert sm.shot_id == "S01"
        assert sm.reference_quality_score == 0.8

    def test_episode_metrics_json_round_trip(self):
        em = EpisodeMetrics(
            episode_id="EP01",
            shot_count=5,
            total_duration_sec=25,
            reference_quality_score=0.8,
            visual_consistency_score=0.9,
            feasibility_score=0.85,
            cinematic_richness_score=0.6,
            continuity_accuracy=0.95,
            conflict_resolution_accuracy=0.98,
            overall_episode_quality=0.84,
        )
        restored = EpisodeMetrics.model_validate(em.model_dump())
        assert restored.episode_id == "EP01"
        assert restored.overall_episode_quality == 0.84

    def test_season_metrics_json_round_trip(self):
        sm = SeasonMetrics(
            season_id="S01",
            episode_count=2,
            reference_quality_score=0.8,
            visual_consistency_score=0.9,
            feasibility_score=0.85,
            cinematic_richness_score=0.6,
            continuity_accuracy=0.95,
            conflict_resolution_accuracy=0.98,
            overall_season_coherence_score=0.84,
        )
        restored = SeasonMetrics.model_validate(sm.model_dump())
        assert restored.season_id == "S01"
        assert restored.overall_season_coherence_score == 0.84

    def test_netflix_targets_values(self):
        assert NETFLIX_TARGET_REFERENCE_QUALITY == 0.75
        assert NETFLIX_TARGET_VISUAL_CONSISTENCY == 0.85
        assert NETFLIX_TARGET_FEASIBILITY == 0.72
        assert NETFLIX_TARGET_CINEMATIC_RICHNESS == 0.55
        assert NETFLIX_TARGET_CONTINUITY == 0.80
        assert NETFLIX_TARGET_CONFLICT_RESOLUTION == 0.92
        assert NETFLIX_TARGET_OVERALL_COHERENCE == 0.78

    def test_broadcast_gate_pass(self):
        em = EpisodeMetrics(
            episode_id="EP01",
            shot_count=10,
            total_duration_sec=50,
            reference_quality_score=0.80,
            visual_consistency_score=0.90,
            feasibility_score=0.80,
            cinematic_richness_score=0.60,
            continuity_accuracy=0.85,
            conflict_resolution_accuracy=0.95,
            overall_episode_quality=0.80,
        )
        assert em.passes_broadcast_gate() is True

    def test_broadcast_gate_fail(self):
        em = EpisodeMetrics(
            episode_id="EP01",
            shot_count=5,
            total_duration_sec=25,
            reference_quality_score=0.70,  # below 0.75
            visual_consistency_score=0.90,
            feasibility_score=0.80,
            cinematic_richness_score=0.60,
            continuity_accuracy=0.85,
            conflict_resolution_accuracy=0.95,
            overall_episode_quality=0.75,
        )
        assert em.passes_broadcast_gate() is False


# ===========================================================================
# 2. TestMetricsEngine
# ===========================================================================

class TestMetricsEngine:

    def test_empty_output_returns_zero_metrics(self):
        engine = MetricsEngine()
        output = AIPRODOutput(title="T", episodes=[])
        m = engine.compute_episode(output)
        assert m.episode_id == "UNKNOWN"
        assert m.shot_count == 0
        assert m.overall_episode_quality == 0.0

    def test_single_shot_rqs_is_product(self):
        """RQS_i = anchor_strength × feasibility / 100"""
        engine = MetricsEngine()
        shot = _make_shot(feasibility_score=80, reference_anchor_strength=0.5)
        output = _make_output(shots=[shot])
        m = engine.compute_episode(output)
        expected_rqs = 0.5 * (80 / 100.0)
        assert abs(m.reference_quality_score - expected_rqs) < 0.001

    def test_rqs_duration_weighted(self):
        """Duration-weighted: longer shots pull the mean toward their RQS."""
        engine = MetricsEngine()
        s1 = _make_shot("S01", duration_sec=3, feasibility_score=100, reference_anchor_strength=1.0)
        s2 = _make_shot("S02", duration_sec=7, feasibility_score=0, reference_anchor_strength=0.0)
        # RQS_s1=1.0, RQS_s2=0.0; weighted = (1.0×3 + 0.0×7)/10 = 0.3
        output = _make_output(shots=[s1, s2])
        m = engine.compute_episode(output)
        assert abs(m.reference_quality_score - 0.3) < 0.001

    def test_feasibility_normalized(self):
        engine = MetricsEngine()
        shots = [_make_shot(f"S{i:02d}", feasibility_score=60) for i in range(5)]
        output = _make_output(shots=shots)
        m = engine.compute_episode(output)
        assert abs(m.feasibility_score - 0.60) < 0.001

    def test_cinematic_richness_diverse_shots(self):
        """4 distinct shot types + 4 distinct movements → CRS > 0"""
        engine = MetricsEngine()
        shots = [
            _make_shot("S1", shot_type="wide", camera_movement="static"),
            _make_shot("S2", shot_type="medium", camera_movement="pan"),
            _make_shot("S3", shot_type="close_up", camera_movement="dolly_in"),
            _make_shot("S4", shot_type="pov", camera_movement="tracking"),
        ]
        output = _make_output(shots=shots)
        m = engine.compute_episode(output)
        assert m.cinematic_richness_score > 0.0

    def test_cinematic_richness_uniform_shots(self):
        """All static mediums → no movement/type diversity → low CRS"""
        engine = MetricsEngine()
        shots = [_make_shot(f"S{i}", shot_type="medium", camera_movement="static") for i in range(4)]
        output = _make_output(shots=shots)
        m = engine.compute_episode(output)
        # shot_type_div = 1/11, movement_div = 1/16, arc_range = 0
        expected = 0.40 * (1 / 11) + 0.30 * (1 / 16)
        assert abs(m.cinematic_richness_score - expected) < 0.001

    def test_cinematic_richness_beat_index_range(self):
        """Beat indices [0.1, 0.9] → arc_range = 0.8"""
        engine = MetricsEngine()
        shots = [
            _make_shot("S1", metadata={"emotional_beat_index": 0.1}),
            _make_shot("S2", metadata={"emotional_beat_index": 0.9}),
        ]
        output = _make_output(shots=shots)
        m = engine.compute_episode(output)
        # shot_type_div = 1/11, movement_div = 1/16, arc_range = 0.8
        expected = 0.40 * (1 / 11) + 0.30 * (1 / 16) + 0.30 * 0.8
        assert abs(m.cinematic_richness_score - expected) < 0.001

    def test_continuity_accuracy_clean_scene(self):
        """Wide shot first → no CA violation even with close_up later."""
        engine = MetricsEngine()
        shots = [
            _make_shot("S1", scene_id="SC01", shot_type="wide"),
            _make_shot("S2", scene_id="SC01", shot_type="close_up"),
        ]
        scene = _make_scene("SC01")
        output = _make_output(shots=shots, scenes=[scene])
        m = engine.compute_episode(output)
        assert m.continuity_accuracy == 1.0

    def test_continuity_accuracy_missing_establishing(self):
        """Close_up without preceding wide → 1 violation."""
        engine = MetricsEngine()
        shots = [
            _make_shot("S1", scene_id="SC01", shot_type="medium"),
            _make_shot("S2", scene_id="SC01", shot_type="close_up"),
        ]
        scene = _make_scene("SC01")
        output = _make_output(shots=shots, scenes=[scene])
        m = engine.compute_episode(output)
        # 1 violation / 1 multi_shot_scene = CA = 0.0
        assert m.continuity_accuracy == 0.0

    def test_conflict_resolution_from_rule_engine(self):
        """CRA = 1 - hard_resolved / rules_evaluated"""
        engine = MetricsEngine()
        rer = RuleEngineReport(rules_evaluated=100, hard_conflicts_resolved=5)
        output = _make_output(rule_engine_report=rer)
        m = engine.compute_episode(output)
        expected_cra = 1.0 - 5 / 100
        assert abs(m.conflict_resolution_accuracy - expected_cra) < 0.001

    def test_overall_episode_quality_formula(self):
        """OEQ = 0.25·VCS + 0.20·FS + 0.20·CRS + 0.15·CA + 0.10·CRA + 0.10·RQS"""
        engine = MetricsEngine()
        output = _make_output(consistency_score=1.0)
        m = engine.compute_episode(output)
        # vcs=1.0, FS=1.0, CRS=shot_type_div only, CA=1.0, CRA=1.0, RQS=1.0
        crs = 0.40 * (1 / 11) + 0.30 * (1 / 16)  # no beat indices, 1 type, 1 movement
        expected = 0.25 * 1.0 + 0.20 * 1.0 + 0.20 * crs + 0.15 * 1.0 + 0.10 * 1.0 + 0.10 * 1.0
        assert abs(m.overall_episode_quality - expected) < 0.005

    def test_season_aggregation_two_episodes(self):
        """Season mean of two episodes with equal shot count."""
        engine = MetricsEngine()
        output1 = _make_output("EP01", consistency_score=0.8)
        output2 = _make_output("EP02", consistency_score=0.6)
        season = engine.compute_season([output1, output2], season_id="S01")
        assert season.episode_count == 2
        # Both have 1 shot; VCS is shot-count weighted → (0.8+0.6)/2 = 0.7
        assert abs(season.visual_consistency_score - 0.7) < 0.001


# ===========================================================================
# 3. TestPostProductionModels
# ===========================================================================

class TestPostProductionModels:

    def test_audio_cue_construction(self):
        cue = AudioCue(
            shot_id="S01", scene_id="SC01", cue_index=0,
            timecode_in="00:00:00:00", timecode_out="00:00:05:00",
            duration_sec=5.0, cue_type="ambiance", mood_tag="tense",
        )
        assert cue.cue_type == "ambiance"
        assert dataclasses.asdict(cue)["shot_id"] == "S01"

    def test_continuity_note_construction(self):
        note = ContinuityNote(
            note_id="CONT-001", shot_id="S01", scene_id="SC01",
            continuity_type="establishing",
            note="missing wide shot", severity="warning",
        )
        assert note.severity == "warning"

    def test_timeline_clip_construction(self):
        clip = TimelineClip(
            clip_id="V001", shot_id="S01", scene_id="SC01", episode_id="EP01",
            track=0, timecode_in="00:00:00:00", timecode_out="00:00:05:00",
            duration_frames=120, fps=24.0, prompt="A shot.",
            shot_type="medium", camera_movement="static",
            transition_in="fade_in", transition_out="fade_out",
        )
        assert clip.duration_frames == 120
        assert dataclasses.asdict(clip)["clip_id"] == "V001"

    def test_manifest_json_round_trip(self):
        manifest = PostProductionManifest(
            episode_id="EP01", fps=24.0,
            total_duration_sec=5.0, total_frames=120,
            timeline_clips=[], audio_cues=[], continuity_notes=[],
            created_at="2026-01-01T00:00:00+00:00",
        )
        restored = PostProductionManifest.model_validate(manifest.model_dump())
        assert restored.episode_id == "EP01"

    def test_build_manifest_for_episode_returns_manifest(self):
        output = _make_output()
        manifest = build_manifest_for_episode(output)
        assert isinstance(manifest, PostProductionManifest)
        assert manifest.episode_id == "EP01"
        assert manifest.total_frames == 5 * 24  # 5 seconds at 24fps
        assert len(manifest.timeline_clips) == 1
        assert len(manifest.audio_cues) == 1


# ===========================================================================
# 4. TestAudioDirectivesBuilder
# ===========================================================================

class TestAudioDirectivesBuilder:

    def test_empty_shots_returns_empty(self):
        builder = AudioDirectivesBuilder()
        cues = builder.build([], [])
        assert cues == []

    def test_noir_scene_tone_gives_ambiance_cue(self):
        builder = AudioDirectivesBuilder()
        scene = _make_scene("SC01", scene_tone="noir")
        shot = _make_shot(scene_id="SC01", emotion="tense")
        cues = builder.build([shot], [scene])
        assert cues[0].cue_type == "ambiance"
        assert cues[0].mood_tag == "tense"

    def test_epic_scene_tone_gives_music_cue_with_bpm(self):
        builder = AudioDirectivesBuilder()
        scene = _make_scene("SC01", scene_tone="epic")
        shot = _make_shot(scene_id="SC01", emotion="excitement")
        cues = builder.build([shot], [scene])
        assert cues[0].cue_type == "music"
        assert cues[0].music_bpm_hint == 96  # uplifting → 96 BPM

    def test_dialogue_dominant_sound_overrides_tone(self):
        builder = AudioDirectivesBuilder()
        scene = _make_scene("SC01", scene_tone="epic")
        shot = _make_shot(scene_id="SC01", metadata={"dominant_sound": "dialogue"})
        cues = builder.build([shot], [scene])
        assert cues[0].cue_type == "dialogue"

    def test_timecode_accuracy_5sec_at_24fps(self):
        builder = AudioDirectivesBuilder()
        shot = _make_shot(duration_sec=5)
        cues = builder.build([shot], [_make_scene()])
        assert cues[0].timecode_in == "00:00:00:00"
        assert cues[0].timecode_out == "00:00:05:00"

    def test_second_shot_timecode_accumulates(self):
        builder = AudioDirectivesBuilder()
        s1 = _make_shot("S1", duration_sec=5)
        s2 = _make_shot("S2", duration_sec=3)
        cues = builder.build([s1, s2], [_make_scene()])
        assert cues[1].timecode_in == "00:00:05:00"
        assert cues[1].timecode_out == "00:00:08:00"


# ===========================================================================
# 5. TestContinuityBuilder
# ===========================================================================

class TestContinuityBuilder:

    def test_no_notes_for_wide_then_close_up(self):
        """Wide shot before close_up → no establishing violation."""
        builder = ContinuityBuilder()
        shots = [
            _make_shot("S1", scene_id="SC01", shot_type="wide"),
            _make_shot("S2", scene_id="SC01", shot_type="close_up"),
        ]
        notes = builder.build(shots, [_make_scene("SC01")])
        establishing_notes = [n for n in notes if n.continuity_type == "establishing"]
        assert establishing_notes == []

    def test_warning_for_close_up_without_establishing(self):
        builder = ContinuityBuilder()
        shots = [
            _make_shot("S1", scene_id="SC01", shot_type="medium"),
            _make_shot("S2", scene_id="SC01", shot_type="close_up"),
        ]
        notes = builder.build(shots, [_make_scene("SC01")])
        assert any(n.continuity_type == "establishing" and n.severity == "warning" for n in notes)

    def test_warning_for_mixed_color_grades(self):
        builder = ContinuityBuilder()
        shots = [
            _make_shot("S1", scene_id="SC01", metadata={"color_grade_hint": "warm"}),
            _make_shot("S2", scene_id="SC01", metadata={"color_grade_hint": "cool"}),
        ]
        notes = builder.build(shots, [_make_scene("SC01")])
        assert any(n.continuity_type == "color" and n.severity == "warning" for n in notes)

    def test_info_for_mixed_lighting_directives(self):
        builder = ContinuityBuilder()
        shots = [
            _make_shot("S1", scene_id="SC01", lighting_directives="key left, fill soft"),
            _make_shot("S2", scene_id="SC01", lighting_directives="key right, hard"),
        ]
        notes = builder.build(shots, [_make_scene("SC01")])
        assert any(n.continuity_type == "lighting" and n.severity == "info" for n in notes)

    def test_single_shot_scene_no_notes(self):
        """Single-shot scenes are not checked (no establishing context)."""
        builder = ContinuityBuilder()
        shot = _make_shot("S1", scene_id="SC01", shot_type="close_up")
        notes = builder.build([shot], [_make_scene("SC01")])
        assert notes == []


# ===========================================================================
# 6. TestTimelineBuilder
# ===========================================================================

class TestTimelineBuilder:

    def test_first_clip_fade_in(self):
        builder = TimelineBuilder()
        shots = [_make_shot("S1"), _make_shot("S2")]
        cues: list[AudioCue] = []
        clips = builder.build(shots, cues)
        assert clips[0].transition_in == "fade_in"

    def test_last_clip_fade_out(self):
        builder = TimelineBuilder()
        shots = [_make_shot("S1"), _make_shot("S2")]
        clips = builder.build(shots, [])
        assert clips[-1].transition_out == "fade_out"

    def test_dissolve_on_scene_boundary(self):
        builder = TimelineBuilder()
        shots = [
            _make_shot("S1", scene_id="SC01"),
            _make_shot("S2", scene_id="SC02"),
        ]
        clips = builder.build(shots, [])
        # S1 → next scene → transition_out = dissolve
        assert clips[0].transition_out == "dissolve"
        # S2 ← prev scene → transition_in = dissolve
        assert clips[1].transition_in == "dissolve"

    def test_cut_within_scene(self):
        builder = TimelineBuilder()
        shots = [
            _make_shot("S1", scene_id="SC01"),
            _make_shot("S2", scene_id="SC01"),
            _make_shot("S3", scene_id="SC01"),
        ]
        clips = builder.build(shots, [])
        assert clips[1].transition_in == "cut"
        assert clips[1].transition_out == "cut"

    def test_timecodes_accumulate_correctly(self):
        builder = TimelineBuilder()
        shots = [
            _make_shot("S1", duration_sec=5),
            _make_shot("S2", duration_sec=3),
        ]
        clips = builder.build(shots, [])
        assert clips[0].timecode_in == "00:00:00:00"
        assert clips[0].timecode_out == "00:00:05:00"
        assert clips[1].timecode_in == "00:00:05:00"
        assert clips[1].timecode_out == "00:00:08:00"


# ===========================================================================
# 7. TestEDLJsonExport
# ===========================================================================

class TestEDLJsonExport:

    def _output_with_2_shots(self) -> AIPRODOutput:
        shots = [
            _make_shot("S1", scene_id="SC01", shot_type="wide"),
            _make_shot("S2", scene_id="SC01", shot_type="close_up"),
        ]
        return _make_output(shots=shots, scenes=[_make_scene("SC01")])

    def test_valid_json(self):
        from aiprod_adaptation.core.exports.edl_json import export_edl_json
        result = export_edl_json(self._output_with_2_shots())
        data = json.loads(result)
        assert data["edl_version"] == "1.0"

    def test_correct_clip_count(self):
        from aiprod_adaptation.core.exports.edl_json import export_edl_json
        data = json.loads(export_edl_json(self._output_with_2_shots()))
        assert data["clip_count"] == 2
        assert len(data["clips"]) == 2

    def test_first_clip_fade_in(self):
        from aiprod_adaptation.core.exports.edl_json import export_edl_json
        data = json.loads(export_edl_json(self._output_with_2_shots()))
        assert data["clips"][0]["transition"] == "fade_in"

    def test_timecode_format_is_smpte(self):
        from aiprod_adaptation.core.exports.edl_json import export_edl_json
        data = json.loads(export_edl_json(self._output_with_2_shots()))
        tc = data["clips"][0]["record_tc_in"]
        parts = tc.split(":")
        assert len(parts) == 4
        assert all(len(p) == 2 for p in parts)


# ===========================================================================
# 8. TestResolveTimelineExport
# ===========================================================================

class TestResolveTimelineExport:

    def _output(self) -> AIPRODOutput:
        return _make_output(shots=[_make_shot("S1"), _make_shot("S2")])

    def test_valid_json(self):
        from aiprod_adaptation.core.exports.resolve_timeline import export_resolve_timeline
        data = json.loads(export_resolve_timeline(self._output()))
        assert data["schema"] == "aiprod_resolve_timeline"

    def test_has_v1_and_a1_tracks(self):
        from aiprod_adaptation.core.exports.resolve_timeline import export_resolve_timeline
        data = json.loads(export_resolve_timeline(self._output()))
        track_names = [t["name"] for t in data["tracks"]]
        assert "V1" in track_names
        assert "A1" in track_names

    def test_v1_clip_count_matches_shots(self):
        from aiprod_adaptation.core.exports.resolve_timeline import export_resolve_timeline
        data = json.loads(export_resolve_timeline(self._output()))
        v1 = next(t for t in data["tracks"] if t["name"] == "V1")
        assert len(v1["clips"]) == 2

    def test_a1_cue_count_matches_shots(self):
        from aiprod_adaptation.core.exports.resolve_timeline import export_resolve_timeline
        data = json.loads(export_resolve_timeline(self._output()))
        a1 = next(t for t in data["tracks"] if t["name"] == "A1")
        assert len(a1["clips"]) == 2


# ===========================================================================
# 9. TestAudioCueSheetExport
# ===========================================================================

class TestAudioCueSheetExport:

    def test_valid_json(self):
        from aiprod_adaptation.core.exports.audio_cue_sheet import export_audio_cue_sheet
        output = _make_output(shots=[_make_shot()])
        data = json.loads(export_audio_cue_sheet(output))
        assert "cues" in data

    def test_cue_count_matches_shots(self):
        from aiprod_adaptation.core.exports.audio_cue_sheet import export_audio_cue_sheet
        shots = [_make_shot(f"S{i}") for i in range(3)]
        output = _make_output(shots=shots)
        data = json.loads(export_audio_cue_sheet(output))
        assert data["cue_count"] == 3

    def test_cue_numbers_sequential(self):
        from aiprod_adaptation.core.exports.audio_cue_sheet import export_audio_cue_sheet
        shots = [_make_shot(f"S{i}") for i in range(3)]
        output = _make_output(shots=shots)
        data = json.loads(export_audio_cue_sheet(output))
        numbers = [c["cue_number"] for c in data["cues"]]
        assert numbers == ["Q001", "Q002", "Q003"]


# ===========================================================================
# 10. TestBatchGenerationExport
# ===========================================================================

class TestBatchGenerationExport:

    def test_valid_json(self):
        from aiprod_adaptation.core.exports.batch_generation import export_batch_generation
        output = _make_output()
        data = json.loads(export_batch_generation(output))
        assert data["batch_schema"] == "aiprod_batch_generation"

    def test_all_shots_present(self):
        from aiprod_adaptation.core.exports.batch_generation import export_batch_generation
        shots = [_make_shot(f"S{i}") for i in range(4)]
        output = _make_output(shots=shots)
        data = json.loads(export_batch_generation(output))
        assert data["shot_count"] == 4
        assert len(data["shots"]) == 4

    def test_reference_anchors_empty_without_invariants(self):
        from aiprod_adaptation.core.exports.batch_generation import export_batch_generation
        output = _make_output()
        data = json.loads(export_batch_generation(output))
        assert data["shots"][0]["reference_anchors"] == []

    def test_motion_intensity_static_is_none(self):
        from aiprod_adaptation.core.exports.batch_generation import export_batch_generation
        shot = _make_shot(camera_movement="static")
        output = _make_output(shots=[shot])
        data = json.loads(export_batch_generation(output))
        assert data["shots"][0]["generation_params"]["motion_intensity"] == "none"

    def test_motion_intensity_crane_up_is_high(self):
        from aiprod_adaptation.core.exports.batch_generation import export_batch_generation
        shot = _make_shot(camera_movement="crane_up")
        output = _make_output(shots=[shot])
        data = json.loads(export_batch_generation(output))
        assert data["shots"][0]["generation_params"]["motion_intensity"] == "high"


# ===========================================================================
# 11. TestSeasonReportExport
# ===========================================================================

class TestSeasonReportExport:

    def test_valid_json(self):
        from aiprod_adaptation.core.exports.season_report import export_season_report
        output = _make_output()
        data = json.loads(export_season_report([output]))
        assert data["report_type"] == "season_coherence_report"

    def test_has_season_metrics(self):
        from aiprod_adaptation.core.exports.season_report import export_season_report
        output = _make_output()
        data = json.loads(export_season_report([output]))
        assert "season_metrics" in data
        assert "overall_season_coherence_score" in data["season_metrics"]

    def test_has_per_episode(self):
        from aiprod_adaptation.core.exports.season_report import export_season_report
        output1 = _make_output("EP01")
        output2 = _make_output("EP02")
        data = json.loads(export_season_report([output1, output2], season_id="S01"))
        assert len(data["per_episode"]) == 2

    def test_broadcast_gate_field_present(self):
        from aiprod_adaptation.core.exports.season_report import export_season_report
        output = _make_output()
        data = json.loads(export_season_report([output]))
        assert data["broadcast_gate"] in {"PASS", "FAIL"}

    def test_recommendations_non_empty(self):
        from aiprod_adaptation.core.exports.season_report import export_season_report
        output = _make_output()
        data = json.loads(export_season_report([output]))
        assert len(data["recommendations"]) >= 1


# ===========================================================================
# 12. TestCLIMetricsCommand
# ===========================================================================

class TestCLIMetricsCommand:

    def _run_metrics_cli(self, output: AIPRODOutput) -> dict:
        from aiprod_adaptation.cli import cmd_metrics, build_parser
        import argparse
        with tempfile.TemporaryDirectory() as tmpdir:
            ir_path = pathlib.Path(tmpdir) / "output.json"
            metrics_path = pathlib.Path(tmpdir) / "metrics.json"
            ir_path.write_text(output.model_dump_json(), encoding="utf-8")
            # Build a minimal args namespace
            args = argparse.Namespace(
                input=str(ir_path),
                output=str(metrics_path),
                season_id="S01",
            )
            ret = cmd_metrics(args)
            assert ret == 0
            return json.loads(metrics_path.read_text(encoding="utf-8"))

    def test_metrics_command_returns_zero(self):
        output = _make_output()
        from aiprod_adaptation.cli import cmd_metrics, build_parser
        import argparse
        with tempfile.TemporaryDirectory() as tmpdir:
            ir_path = pathlib.Path(tmpdir) / "output.json"
            ir_path.write_text(output.model_dump_json(), encoding="utf-8")
            args = argparse.Namespace(input=str(ir_path), output=None, season_id="S01")
            # capture stdout
            import io
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            ret = cmd_metrics(args)
            sys.stdout = old_stdout
            assert ret == 0

    def test_metrics_output_is_valid_json(self):
        data = self._run_metrics_cli(_make_output())
        assert "episode_id" in data

    def test_metrics_has_overall_quality(self):
        data = self._run_metrics_cli(_make_output())
        assert "overall_episode_quality" in data
        assert 0.0 <= data["overall_episode_quality"] <= 1.0

    def test_metrics_has_broadcast_gate(self):
        data = self._run_metrics_cli(_make_output())
        assert data["broadcast_gate"] in {"PASS", "FAIL"}


# ===========================================================================
# 13. TestCLIExportCommand
# ===========================================================================

class TestCLIExportCommand:

    def _run_export_cli(self, fmt: str, output: AIPRODOutput | None = None) -> str:
        from aiprod_adaptation.cli import cmd_export
        import argparse
        _output = output or _make_output()
        with tempfile.TemporaryDirectory() as tmpdir:
            ir_path = pathlib.Path(tmpdir) / "output.json"
            export_path = pathlib.Path(tmpdir) / f"export.{fmt.replace('-', '_')}.json"
            ir_path.write_text(_output.model_dump_json(), encoding="utf-8")
            args = argparse.Namespace(
                input=str(ir_path),
                output=str(export_path),
                export_format=fmt,
                fps=24.0,
                adapter_target="runway",
                season_id="S01",
                series_title="Test Series",
            )
            ret = cmd_export(args)
            assert ret == 0
            return export_path.read_text(encoding="utf-8")

    def test_export_edl_command(self):
        result = self._run_export_cli("edl")
        data = json.loads(result)
        assert data["edl_version"] == "1.0"

    def test_export_resolve_command(self):
        result = self._run_export_cli("resolve")
        data = json.loads(result)
        assert data["schema"] == "aiprod_resolve_timeline"

    def test_export_audio_cue_command(self):
        result = self._run_export_cli("audio-cue")
        data = json.loads(result)
        assert "cues" in data

    def test_export_batch_command(self):
        result = self._run_export_cli("batch")
        data = json.loads(result)
        assert data["batch_schema"] == "aiprod_batch_generation"
