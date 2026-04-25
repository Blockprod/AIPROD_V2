"""
test_pass4_cinematic.py — Sprint 6 test suite for Pass 4 global coherence layer.

Tests 7 functional areas:
  1. TestPacingAnalyzer          — pacing_analyzer.analyze()
  2. TestConsistencyChecker      — consistency_checker.check_and_enrich()
  3. TestPromptFinalizer         — prompt_finalizer.finalize_prompts()
  4. TestEpisodePacingProfile    — pacing_profile present on Episode after compile_episode
  5. TestConsistencyReportOnEpisode — consistency_report present on Episode
  6. TestSceneV3FieldsPassThrough — beat_type / scene_tone / emotional_beat_index
  7. TestBackwardCompat          — existing compile_episode signature unchanged

All tests are deterministic / pure-Python. No LLM, no network, no filesystem I/O.
"""

from __future__ import annotations

from typing import Any

import pytest

from aiprod_adaptation.core.global_coherence.consistency_checker import check_and_enrich
from aiprod_adaptation.core.global_coherence.pacing_analyzer import analyze
from aiprod_adaptation.core.global_coherence.prompt_finalizer import finalize_prompts
from aiprod_adaptation.core.pass4_compile import compile_episode
from aiprod_adaptation.core.rules.pass4_coherence_rules import (
    CONSISTENCY_PENALTY_MOVEMENT_SIMPLIFICATION,
    CONSISTENCY_PENALTY_TONE_CONFLICT,
    FEASIBILITY_MOVEMENT_MINIMUM,
    PACING_LABEL_RULES,
    PROMPT_ENRICHMENT_SEPARATOR,
    PROMPT_LABEL_COMPOSITION,
    PROMPT_LABEL_LIGHTING,
    TONE_COLOR_GRADE_DEFAULTS,
)
from aiprod_adaptation.models.schema import (
    ActionSpec,
    ConsistencyReport,
    PacingProfile,
    Scene,
    Shot,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _action(subject_id: str = "char_a") -> ActionSpec:
    return ActionSpec(
        subject_id=subject_id,
        action_type="moves",
        target=None,
        modifiers=[],
        location_id="loc_x",
        camera_intent="static",
        source_text="moves forward",
    )


def _shot(
    shot_id: str = "S01",
    scene_id: str = "SC01",
    shot_type: str = "medium",
    camera_movement: str = "static",
    duration_sec: int = 5,
    feasibility_score: int = 100,
    prompt: str = "A shot.",
    composition_description: str | None = None,
    lighting_directives: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Shot:
    return Shot(
        shot_id=shot_id,
        scene_id=scene_id,
        prompt=prompt,
        duration_sec=duration_sec,
        emotion="neutral",
        shot_type=shot_type,
        camera_movement=camera_movement,
        action=_action(),
        metadata=metadata or {},
        feasibility_score=feasibility_score,
        composition_description=composition_description,
        lighting_directives=lighting_directives,
    )


def _scene(
    scene_id: str = "SC01",
    scene_tone: str = "neutral",
    beat_type: str | None = None,
    emotional_beat_index: float | None = None,
) -> Scene:
    return Scene(
        scene_id=scene_id,
        characters=["Alice"],
        location="Office",
        visual_actions=["walks"],
        dialogues=["Hello"],
        emotion="neutral",
        scene_tone=scene_tone,
        beat_type=beat_type,
        emotional_beat_index=emotional_beat_index,
    )


# Minimal VisualScene/ShotDict dicts for compile_episode
_MINIMAL_SCENE: dict[str, Any] = {
    "scene_id": "SC01",
    "characters": ["Alice"],
    "location": "Office",
    "visual_actions": ["walks"],
    "dialogues": ["Hello"],
    "emotion": "neutral",
}

_MINIMAL_SHOT: dict[str, Any] = {
    "shot_id": "SH01",
    "scene_id": "SC01",
    "prompt": "Alice walks through the office.",
    "duration_sec": 5,
    "emotion": "neutral",
    "shot_type": "medium",
    "camera_movement": "static",
}


# ===========================================================================
# 1. TestPacingAnalyzer
# ===========================================================================


class TestPacingAnalyzer:
    """Tests for pacing_analyzer.analyze()."""

    def test_empty_list_returns_medium_profile(self):
        profile = analyze([])
        assert profile.pacing_label == "medium"
        assert profile.shot_count == 0
        assert profile.total_duration_sec == 0
        assert profile.mean_shot_duration == 0.0

    def test_single_shot_correct_total(self):
        shots = [_shot(duration_sec=5)]
        profile = analyze(shots)
        assert profile.total_duration_sec == 5
        assert profile.shot_count == 1
        assert profile.mean_shot_duration == 5.0

    def test_all_boundaries_covered(self):
        """Every PACING_LABEL_RULES entry must be reachable."""
        expected_labels = {lbl for _, lbl in PACING_LABEL_RULES}
        # inject shots whose mean equals each boundary
        label_set: set[str] = set()
        for boundary, lbl in PACING_LABEL_RULES:
            import math
            if math.isinf(boundary):
                dur = 8  # max allowed → mean = 8 > 6.0 → "slow"
            else:
                # use int() (truncate) rather than round() to stay at or below the boundary
                dur = int(boundary)
                dur = max(3, min(8, dur))
            shots = [_shot(duration_sec=dur)]
            profile = analyze(shots)
            label_set.add(profile.pacing_label)
        # every defined label must appear at least once
        assert expected_labels <= label_set | {"slow"}  # slow covers inf

    def test_montage_label_mean_leq_35(self):
        # 4 shots × 3 s = mean 3.0 → montage
        shots = [_shot(f"S{i}", duration_sec=3) for i in range(4)]
        assert analyze(shots).pacing_label == "montage"

    def test_fast_label_mean_leq_45(self):
        # 2 shots: 3+5 = 8, mean 4.0 → fast
        shots = [_shot("S1", duration_sec=3), _shot("S2", duration_sec=5)]
        assert analyze(shots).pacing_label == "fast"

    def test_medium_label_mean_leq_60(self):
        # mean 5.5 → medium
        shots = [_shot("S1", duration_sec=5), _shot("S2", duration_sec=6)]
        assert analyze(shots).pacing_label == "medium"

    def test_slow_label_mean_gt_60(self):
        # mean 7.0 → slow
        shots = [_shot("S1", duration_sec=7), _shot("S2", duration_sec=7)]
        assert analyze(shots).pacing_label == "slow"

    def test_mean_shot_duration_rounded_to_2dp(self):
        # 3 shots: 3+4+5 = 12, mean = 4.0 (exact)
        shots = [_shot("S1", duration_sec=3), _shot("S2", duration_sec=4), _shot("S3", duration_sec=5)]
        profile = analyze(shots)
        assert profile.mean_shot_duration == round(12 / 3, 2)

    def test_total_duration_correct_multi_shots(self):
        shots = [_shot(f"S{i}", duration_sec=d) for i, d in enumerate([3, 4, 5, 6, 7])]
        assert analyze(shots).total_duration_sec == 25

    def test_returns_pacing_profile_instance(self):
        profile = analyze([_shot(duration_sec=5)])
        assert isinstance(profile, PacingProfile)


# ===========================================================================
# 2. TestConsistencyChecker
# ===========================================================================


class TestConsistencyChecker:
    """Tests for consistency_checker.check_and_enrich()."""

    # --- R01: Feasibility gate ---

    def test_r01_low_feasibility_downgrades_to_static(self):
        shot = _shot(
            camera_movement="dolly_in",
            feasibility_score=FEASIBILITY_MOVEMENT_MINIMUM - 1,
        )
        result, report = check_and_enrich([_scene()], [shot])
        assert result[0].camera_movement == "static"
        assert shot.shot_id in report.movement_simplifications

    def test_r01_boundary_exactly_minimum_not_downgraded(self):
        shot = _shot(
            camera_movement="pan",
            feasibility_score=FEASIBILITY_MOVEMENT_MINIMUM,
        )
        result, _ = check_and_enrich([_scene()], [shot])
        assert result[0].camera_movement == "pan"

    def test_r01_already_static_no_record(self):
        shot = _shot(camera_movement="static", feasibility_score=10)
        _, report = check_and_enrich([_scene()], [shot])
        assert shot.shot_id not in report.movement_simplifications

    def test_r01_high_feasibility_not_downgraded(self):
        shot = _shot(camera_movement="tracking", feasibility_score=80)
        result, report = check_and_enrich([_scene()], [shot])
        assert result[0].camera_movement == "tracking"
        assert len(report.movement_simplifications) == 0

    # --- R02: Colour grade homogeneity ---

    def test_r02_conflicting_grades_normalised_to_tone_default(self):
        """3 distinct colour grades in scene → all normalised to tone default."""
        scene = _scene(scene_id="SC01", scene_tone="noir")
        expected = TONE_COLOR_GRADE_DEFAULTS["noir"]  # "high_contrast"
        shots = [
            _shot("S1", scene_id="SC01", metadata={"color_grade_hint": "warm"}),
            _shot("S2", scene_id="SC01", metadata={"color_grade_hint": "cool"}),
            _shot("S3", scene_id="SC01", metadata={"color_grade_hint": "neutral"}),
        ]
        result, report = check_and_enrich([scene], shots)
        for s in result:
            assert s.metadata["color_grade_hint"] == expected
        assert "SC01" in report.tone_conflicts

    def test_r02_within_limit_no_normalisation(self):
        """2 distinct grades (≤ COLOR_GRADE_MAX_DISTINCT) → no change."""
        scene = _scene(scene_id="SC01", scene_tone="neutral")
        shots = [
            _shot("S1", scene_id="SC01", metadata={"color_grade_hint": "warm"}),
            _shot("S2", scene_id="SC01", metadata={"color_grade_hint": "cool"}),
        ]
        result, report = check_and_enrich([scene], shots)
        assert result[0].metadata["color_grade_hint"] == "warm"
        assert result[1].metadata["color_grade_hint"] == "cool"
        assert "SC01" not in report.tone_conflicts

    def test_r02_no_color_grade_no_conflict(self):
        scene = _scene()
        shots = [_shot()]
        _, report = check_and_enrich([scene], shots)
        assert len(report.tone_conflicts) == 0

    # --- R03: Establishing shot ---

    def test_r03_warn_no_wide_in_first_scene(self):
        scene = _scene()
        shots = [_shot(shot_type="medium")]  # no wide
        _, report = check_and_enrich([scene], shots)
        assert any("no_establishing_shot" in w for w in report.continuity_warnings)

    def test_r03_no_warn_when_wide_ratio_sufficient(self):
        scene = _scene()
        shots = [_shot("S1", shot_type="wide"), _shot("S2", shot_type="medium")]
        _, report = check_and_enrich([scene], shots)
        assert not any("no_establishing_shot" in w for w in report.continuity_warnings)

    def test_r03_extreme_wide_counts_as_establishing(self):
        scene = _scene()
        shots = [_shot("S1", shot_type="extreme_wide"), _shot("S2", shot_type="medium")]
        _, report = check_and_enrich([scene], shots)
        assert not any("no_establishing_shot" in w for w in report.continuity_warnings)

    # --- R04: Dramatic arc flatness ---

    def test_r04_flat_arc_warns(self):
        """All shots with the same emotional_beat_index → arc_range=0 → flat."""
        shots = [
            _shot(f"S{i}", metadata={"emotional_beat_index": 0.5}) for i in range(5)
        ]
        _, report = check_and_enrich([_scene()], shots)
        assert "dramatic_arc_flat" in report.continuity_warnings

    def test_r04_varied_arc_no_warn(self):
        shots = [
            _shot("S1", metadata={"emotional_beat_index": 0.0}),
            _shot("S2", metadata={"emotional_beat_index": 0.5}),
            _shot("S3", metadata={"emotional_beat_index": 1.0}),
        ]
        _, report = check_and_enrich([_scene()], shots)
        assert "dramatic_arc_flat" not in report.continuity_warnings

    def test_r04_no_ebi_no_warn(self):
        """Shots without emotional_beat_index → arc check skipped."""
        shots = [_shot(f"S{i}") for i in range(5)]
        _, report = check_and_enrich([_scene()], shots)
        assert "dramatic_arc_flat" not in report.continuity_warnings

    # --- consistency_score computation ---

    def test_score_perfect_when_no_issues(self):
        scene = _scene()
        shots = [_shot("S1", shot_type="wide"), _shot("S2", shot_type="medium")]
        _, report = check_and_enrich([scene], shots)
        assert report.consistency_score == 1.0

    def test_score_reduced_by_tone_conflict(self):
        scene = _scene(scene_id="SC01", scene_tone="noir")
        shots = [
            _shot("S1", scene_id="SC01", metadata={"color_grade_hint": "warm"}),
            _shot("S2", scene_id="SC01", metadata={"color_grade_hint": "cool"}),
            _shot("S3", scene_id="SC01", metadata={"color_grade_hint": "neutral"}),
        ]
        _, report = check_and_enrich([scene], shots)
        expected = round(
            1.0 - CONSISTENCY_PENALTY_TONE_CONFLICT * len(report.tone_conflicts), 4
        )
        assert report.consistency_score == pytest.approx(expected, abs=0.001)

    def test_score_reduced_by_movement_simplification(self):
        shot = _shot(
            camera_movement="dolly_in",
            feasibility_score=FEASIBILITY_MOVEMENT_MINIMUM - 1,
        )
        _, report = check_and_enrich([_scene()], [shot])
        expected = round(
            1.0
            - CONSISTENCY_PENALTY_MOVEMENT_SIMPLIFICATION
            * len(report.movement_simplifications),
            4,
        )
        assert report.consistency_score == pytest.approx(expected, abs=0.001)

    def test_score_reduced_by_arc_flat(self):
        shots = [_shot(f"S{i}", metadata={"emotional_beat_index": 0.5}) for i in range(3)]
        _, report = check_and_enrich([_scene()], shots)
        assert report.consistency_score < 1.0

    def test_score_clamped_at_zero(self):
        """Stack enough penalties that raw score would go negative."""
        # 11 tone conflicts each subtract 0.10 → -0.10 raw → clamped at 0.0
        scenes = [_scene(scene_id=f"SC{i:02d}", scene_tone="noir") for i in range(11)]
        shots_list: list[Shot] = []
        for sc in scenes:
            for j, grade in enumerate(["warm", "cool", "neutral"]):
                shots_list.append(
                    _shot(
                        f"S{sc.scene_id}_{j}",
                        scene_id=sc.scene_id,
                        metadata={"color_grade_hint": grade},
                    )
                )
        _, report = check_and_enrich(scenes, shots_list)
        assert report.consistency_score >= 0.0

    def test_returns_consistency_report_instance(self):
        _, report = check_and_enrich([_scene()], [_shot()])
        assert isinstance(report, ConsistencyReport)

    def test_empty_shots_returns_clean_report(self):
        _, report = check_and_enrich([_scene()], [])
        assert report.consistency_score == 1.0
        assert len(report.tone_conflicts) == 0
        assert len(report.movement_simplifications) == 0


# ===========================================================================
# 3. TestPromptFinalizer
# ===========================================================================


class TestPromptFinalizer:
    """Tests for prompt_finalizer.finalize_prompts()."""

    def test_r05_composition_appended(self):
        shot = _shot(prompt="A scene.", composition_description="Rule of thirds.")
        enriched, count = finalize_prompts([shot])
        assert PROMPT_LABEL_COMPOSITION in enriched[0].prompt
        assert "Rule of thirds." in enriched[0].prompt
        assert count == 1

    def test_r05_composition_not_appended_if_already_in_prompt(self):
        comp = "Rule of thirds."
        shot = _shot(
            prompt=f"A scene. {PROMPT_LABEL_COMPOSITION}: {comp}",
            composition_description=comp,
        )
        _, count = finalize_prompts([shot])
        assert count == 0

    def test_r06_lighting_appended(self):
        shot = _shot(prompt="A scene.", lighting_directives="Hard backlight.")
        enriched, count = finalize_prompts([shot])
        assert PROMPT_LABEL_LIGHTING in enriched[0].prompt
        assert "Hard backlight." in enriched[0].prompt
        assert count == 1

    def test_r06_lighting_not_appended_if_already_in_prompt(self):
        shot = _shot(
            prompt=f"A scene. {PROMPT_LABEL_LIGHTING}: Hard backlight.",
            lighting_directives="Hard backlight.",
        )
        _, count = finalize_prompts([shot])
        assert count == 0

    def test_both_composition_and_lighting_appended(self):
        shot = _shot(
            prompt="A scene.",
            composition_description="Golden spiral.",
            lighting_directives="Rim light.",
        )
        enriched, count = finalize_prompts([shot])
        assert "Golden spiral." in enriched[0].prompt
        assert "Rim light." in enriched[0].prompt
        assert count == 1  # one shot enriched (with 2 additions)

    def test_prompt_separator_present_when_enriched(self):
        shot = _shot(prompt="A scene.", composition_description="Symmetry.")
        enriched, _ = finalize_prompts([shot])
        assert PROMPT_ENRICHMENT_SEPARATOR in enriched[0].prompt

    def test_no_additions_original_prompt_unchanged(self):
        shot = _shot(prompt="A scene.")
        enriched, count = finalize_prompts([shot])
        assert enriched[0].prompt == "A scene."
        assert count == 0

    def test_empty_shot_list(self):
        enriched, count = finalize_prompts([])
        assert enriched == []
        assert count == 0

    def test_none_composition_not_appended(self):
        shot = _shot(prompt="A scene.", composition_description=None)
        _, count = finalize_prompts([shot])
        assert count == 0

    def test_none_lighting_not_appended(self):
        shot = _shot(prompt="A scene.", lighting_directives=None)
        _, count = finalize_prompts([shot])
        assert count == 0

    def test_idempotent_second_call(self):
        """Calling finalize_prompts twice on an already-enriched shot is safe."""
        shot = _shot(prompt="A scene.", composition_description="Rule of thirds.")
        enriched1, _ = finalize_prompts([shot])
        enriched2, count2 = finalize_prompts(enriched1)
        # Second pass: composition already in prompt → no new addition
        assert count2 == 0
        assert enriched2[0].prompt == enriched1[0].prompt

    def test_multiple_shots_all_processed(self):
        shots = [
            _shot("S1", prompt="Shot one.", composition_description="A."),
            _shot("S2", prompt="Shot two.", composition_description="B."),
            _shot("S3", prompt="Shot three."),
        ]
        enriched, count = finalize_prompts(shots)
        assert len(enriched) == 3
        assert count == 2

    def test_visual_bible_none_no_character_injection(self):
        shot = _shot(prompt="A scene.")
        enriched, count = finalize_prompts([shot], visual_bible=None)
        assert count == 0

    def test_count_reflects_shots_enriched_not_additions(self):
        """count = number of shots that got at least one addition."""
        shot = _shot(
            prompt="A scene.",
            composition_description="Symmetry.",
            lighting_directives="Backlight.",
        )
        _, count = finalize_prompts([shot])
        assert count == 1  # one shot, two additions → count=1


# ===========================================================================
# 4. TestEpisodePacingProfile
# ===========================================================================


class TestEpisodePacingProfile:
    """compile_episode must populate episode.pacing_profile."""

    def test_pacing_profile_present(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "TestTitle")
        assert out.episodes[0].pacing_profile is not None

    def test_pacing_profile_is_instance(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "TestTitle")
        assert isinstance(out.episodes[0].pacing_profile, PacingProfile)

    def test_pacing_profile_shot_count(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "TestTitle")
        assert out.episodes[0].pacing_profile.shot_count == 1  # type: ignore[union-attr]

    def test_pacing_profile_total_duration(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "TestTitle")
        assert out.episodes[0].pacing_profile.total_duration_sec == 5  # type: ignore[union-attr]

    def test_pacing_profile_label_is_string(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "TestTitle")
        label = out.episodes[0].pacing_profile.pacing_label  # type: ignore[union-attr]
        assert isinstance(label, str)
        assert label in {"montage", "fast", "medium", "slow"}


# ===========================================================================
# 5. TestConsistencyReportOnEpisode
# ===========================================================================


class TestConsistencyReportOnEpisode:
    """compile_episode must populate episode.consistency_report."""

    def test_consistency_report_present(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "TestTitle")
        assert out.episodes[0].consistency_report is not None

    def test_consistency_report_is_instance(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "TestTitle")
        assert isinstance(out.episodes[0].consistency_report, ConsistencyReport)

    def test_consistency_score_in_range(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "TestTitle")
        score = out.episodes[0].consistency_report.consistency_score  # type: ignore[union-attr]
        assert 0.0 <= score <= 1.0

    def test_tone_conflicts_is_list(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "TestTitle")
        assert isinstance(out.episodes[0].consistency_report.tone_conflicts, list)  # type: ignore[union-attr]

    def test_continuity_warnings_is_list(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "TestTitle")
        assert isinstance(out.episodes[0].consistency_report.continuity_warnings, list)  # type: ignore[union-attr]

    def test_movement_simplifications_is_list(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "TestTitle")
        assert isinstance(out.episodes[0].consistency_report.movement_simplifications, list)  # type: ignore[union-attr]

    def test_prompt_enrichments_is_int(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "TestTitle")
        assert isinstance(out.episodes[0].consistency_report.prompt_enrichments, int)  # type: ignore[union-attr]


# ===========================================================================
# 6. TestSceneV3FieldsPassThrough
# ===========================================================================


class TestSceneV3FieldsPassThrough:
    """beat_type, scene_tone, emotional_beat_index pass through compile_episode."""

    _SCENE_V3: dict[str, Any] = {
        **_MINIMAL_SCENE,
        "beat_type": "climax",
        "scene_tone": "noir",
        "emotional_beat_index": 0.8,
    }

    def test_beat_type_preserved(self):
        out = compile_episode([self._SCENE_V3], [_MINIMAL_SHOT], "TestTitle")
        assert out.episodes[0].scenes[0].beat_type == "climax"

    def test_scene_tone_preserved(self):
        out = compile_episode([self._SCENE_V3], [_MINIMAL_SHOT], "TestTitle")
        assert out.episodes[0].scenes[0].scene_tone == "noir"

    def test_emotional_beat_index_preserved(self):
        out = compile_episode([self._SCENE_V3], [_MINIMAL_SHOT], "TestTitle")
        assert out.episodes[0].scenes[0].emotional_beat_index == pytest.approx(0.8)

    def test_missing_v3_fields_default_to_none(self):
        """Scenes without v3.0 fields should still compile cleanly."""
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "TestTitle")
        scene = out.episodes[0].scenes[0]
        assert scene.beat_type is None
        assert scene.scene_tone is None
        assert scene.emotional_beat_index is None


# ===========================================================================
# 7. TestBackwardCompat
# ===========================================================================


class TestBackwardCompat:
    """Pass 4 v4.0 changes must be 100% backward compatible."""

    def test_three_positional_args_still_work(self):
        """Original compile_episode(scenes, shots, title) signature unchanged."""
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "My Title")
        assert out.title == "My Title"

    def test_episode_id_default(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "T")
        assert out.episodes[0].episode_id == "EP01"

    def test_episode_id_custom(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "T", episode_id="EP03")
        assert out.episodes[0].episode_id == "EP03"

    def test_visual_bible_none_by_default(self):
        """No visual_bible argument → still produces valid output."""
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "T")
        assert out is not None

    def test_visual_bible_summary_empty_when_no_bible(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "T")
        assert out.visual_bible_summary == {}

    def test_existing_scenes_shots_unchanged(self):
        """Existing output structure still holds: episodes[0].scenes and .shots."""
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "T")
        assert len(out.episodes[0].scenes) == 1
        assert len(out.episodes[0].shots) >= 1

    def test_aiprod_output_title_preserved(self):
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "Episode Alpha")
        assert out.title == "Episode Alpha"

    def test_new_episode_fields_have_safe_defaults(self):
        """pacing_profile / consistency_report are populated by pipeline — not None."""
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "T")
        # v4.0 pipeline always fills these (not None after compile_episode)
        assert out.episodes[0].pacing_profile is not None
        assert out.episodes[0].consistency_report is not None

    def test_visual_bible_summary_default_factory(self):
        """AIPRODOutput default for visual_bible_summary is an empty dict (not None)."""
        out = compile_episode([_MINIMAL_SCENE], [_MINIMAL_SHOT], "T")
        assert isinstance(out.visual_bible_summary, dict)
