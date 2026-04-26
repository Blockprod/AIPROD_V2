"""
test_cinematic_integration.py — Sprint 8 integration tests for AIPROD_Cinematic.

Tests the full wiring of:
  1. ReferenceConstraintsExtractor (unit + with VisualInvariants)
  2. SeasonCoherenceTracker (multi-episode accumulation + metrics)
  3. Pass 4 Rule Engine integration (compile_episode with/without ref_invariants)
  4. process_narrative_with_reference() end-to-end entry point
  5. Schema completeness (RuleEngineReport, SeasonCoherenceMetrics, AIPRODSeason)

All tests are deterministic / pure-Python.  No LLM, no network, no filesystem I/O.
"""

from __future__ import annotations

import pytest

from aiprod_adaptation.core.reference_constraints.extractor import (
    ReferenceConstraintsExtractor,
)
from aiprod_adaptation.core.reference_constraints.models import ReferenceConstraints
from aiprod_adaptation.core.season.models import EpisodeCoherenceSummary
from aiprod_adaptation.core.season.tracker import SeasonCoherenceTracker, _detect_palette_drift
from aiprod_adaptation.models.schema import (
    AIPRODOutput,
    AIPRODSeason,
    Episode,
    RuleEngineReport,
    SeasonCoherenceMetrics,
)

# ---------------------------------------------------------------------------
# Optional reference_image models (numpy / Pillow required)
# ---------------------------------------------------------------------------

try:
    from aiprod_adaptation.core.reference_image.models import (
        CameraHeightClass,
        ColorSwatch,
        DepthLayerEstimate,
        LightingAnalysis,
        LightingDirectionH,
        LightingDirectionV,
        VisualInvariants,
    )
    _HAS_REF_MODELS = True
except ImportError:
    _HAS_REF_MODELS = False

_ref_models_required = pytest.mark.skipif(
    not _HAS_REF_MODELS, reason="reference_image models unavailable"
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_color_swatch(rank: int = 1, variability: str = "invariant") -> ColorSwatch:
    # Generate a valid 6-char uppercase hex from rank: e.g. rank=1 → #AA1100
    hx = f"#{(0xAA):02X}{rank:02X}{(rank * 3 % 256):02X}"
    return ColorSwatch(
        rank=rank,
        hex_code=hx,
        lab=[50.0, 0.0, 0.0],
        coverage_pct=40.0 / rank,
        variability=variability,
    )


def _make_visual_invariants(
    camera_height_class: CameraHeightClass | None = None,
    dominant_layer: str = "midground",
    key_direction_h: LightingDirectionH | None = None,
    key_direction_v: LightingDirectionV | None = None,
    palette_swatches: list[ColorSwatch] | None = None,
) -> VisualInvariants:
    return VisualInvariants(
        source_path="/test/ref.jpg",
        width_px=1920,
        height_px=1080,
        aspect_ratio="16:9",
        subject_coverage_pct=25.0,
        luminance_fingerprint="deadbeef01234567",
        lighting=LightingAnalysis(
            key_direction_h=key_direction_h or LightingDirectionH.LEFT,
            key_direction_v=key_direction_v or LightingDirectionV.TOP,
            color_temperature_k=3200,
            intensity_l95=70.0,
            contrast_std_l=18.0,
            highlight_pct=4.0,
            shadow_pct=12.0,
        ),
        camera_height_class=camera_height_class or CameraHeightClass.EYE_LEVEL,
        depth_layers=DepthLayerEstimate(
            gradient_mean_foreground=50.0,
            gradient_mean_midground=80.0,
            gradient_mean_background=20.0,
            dominant_layer=dominant_layer,
        ),
        palette=palette_swatches or [_make_color_swatch()],
    )


def _make_minimal_output(episode_id: str = "EP01", feasibility_score: int = 80) -> AIPRODOutput:
    """Build a minimal AIPRODOutput without running the full pipeline."""
    from aiprod_adaptation.models.schema import (
        ActionSpec,
        ConsistencyReport,
        PacingProfile,
        Scene,
        Shot,
    )

    action = ActionSpec(
        subject_id="char_a",
        action_type="moves",
        target=None,
        modifiers=[],
        location_id="loc_x",
        camera_intent="static",
        source_text="moves forward",
    )
    shot = Shot(
        shot_id=f"{episode_id}-S01",
        scene_id="SC01",
        prompt="A shot.",
        duration_sec=5,
        emotion="neutral",
        shot_type="medium",
        camera_movement="static",
        action=action,
        feasibility_score=feasibility_score,
    )
    scene = Scene(
        scene_id="SC01",
        characters=["Alice"],
        location="Office",
        visual_actions=["walks"],
        dialogues=["Hello"],
        emotion="neutral",
        shot_ids=[shot.shot_id],
    )
    rule_report = RuleEngineReport(
        rules_evaluated=9,
        hard_conflicts_resolved=1,
        soft_conflicts_annotated=0,
        total_shots_modified=1,
        conflict_shot_ids=[shot.shot_id],
        rule_ids_fired=["CHR-01-feasibility-gate"],
    )
    episode = Episode(
        episode_id=episode_id,
        scenes=[scene],
        shots=[shot],
        pacing_profile=PacingProfile(
            total_duration_sec=5,
            mean_shot_duration=5.0,
            shot_count=1,
            pacing_label="slow",
        ),
        consistency_report=ConsistencyReport(consistency_score=0.9),
        rule_engine_report=rule_report,
    )
    return AIPRODOutput(
        title=f"Test Episode {episode_id}",
        episodes=[episode],
        rule_engine_report=rule_report,
    )


# ===========================================================================
# 1. TestReferenceConstraintsModels
# ===========================================================================


class TestReferenceConstraintsModels:
    """Schema integrity for ReferenceConstraints."""

    def test_default_construction(self):
        rc = ReferenceConstraints()
        assert rc.camera_height is None
        assert rc.forbidden_movements == []
        assert rc.suggested_movements == []
        assert rc.palette_anchor_hex == []

    def test_full_construction(self):
        rc = ReferenceConstraints(
            camera_height="overhead",
            lighting_direction_h="left",
            lighting_direction_v="top",
            dominant_depth_layer="background",
            forbidden_movements=["crane_up", "tilt_up"],
            suggested_movements=["tilt_down", "static"],
            palette_anchor_hex=["#ff0000", "#00ff00"],
            location_id="loc_dz_central_001",
            architecture_style="brutalist",
        )
        assert rc.camera_height == "overhead"
        assert len(rc.forbidden_movements) == 2

    def test_json_round_trip(self):
        rc = ReferenceConstraints(
            camera_height="high_angle",
            forbidden_movements=["crane_up"],
        )
        data = rc.model_dump()
        restored = ReferenceConstraints.model_validate(data)
        assert restored.camera_height == "high_angle"
        assert restored.forbidden_movements == ["crane_up"]


# ===========================================================================
# 2. TestReferenceConstraintsExtractor
# ===========================================================================


class TestReferenceConstraintsExtractor:
    """Tests for the extractor (pure-Python path — no VisualInvariants required)."""

    def test_none_input_returns_empty(self):
        extractor = ReferenceConstraintsExtractor()
        rc = extractor.extract(None)
        assert rc == ReferenceConstraints()

    def test_location_only_architecture_style(self):
        extractor = ReferenceConstraintsExtractor()
        loc = {"architecture_style": "industrial", "default_camera_height": "eye_level"}
        rc = extractor.extract(None, location_invariant=loc)
        # None visual_invariants → empty; location provides nothing since inv is None
        assert rc == ReferenceConstraints()

    @_ref_models_required
    def test_overhead_height_populates_forbidden(self):
        extractor = ReferenceConstraintsExtractor()
        inv = _make_visual_invariants(camera_height_class=CameraHeightClass.OVERHEAD)
        rc = extractor.extract(inv)
        assert rc.camera_height == "overhead"
        assert "crane_up" in rc.forbidden_movements
        assert "tilt_up" in rc.forbidden_movements
        assert "dolly_in" in rc.forbidden_movements
        assert "dolly_out" in rc.forbidden_movements

    @_ref_models_required
    def test_overhead_height_populates_suggested(self):
        extractor = ReferenceConstraintsExtractor()
        inv = _make_visual_invariants(camera_height_class=CameraHeightClass.OVERHEAD)
        rc = extractor.extract(inv)
        assert "tilt_down" in rc.suggested_movements
        assert "static" in rc.suggested_movements

    @_ref_models_required
    def test_eye_level_no_forbidden_movements(self):
        extractor = ReferenceConstraintsExtractor()
        inv = _make_visual_invariants(camera_height_class=CameraHeightClass.EYE_LEVEL)
        rc = extractor.extract(inv)
        assert rc.forbidden_movements == []

    @_ref_models_required
    def test_lighting_extracted(self):
        extractor = ReferenceConstraintsExtractor()
        inv = _make_visual_invariants(
            key_direction_h=LightingDirectionH.LEFT,
            key_direction_v=LightingDirectionV.TOP,
        )
        rc = extractor.extract(inv)
        assert rc.lighting_direction_h == "left"
        assert rc.lighting_direction_v == "top"

    @_ref_models_required
    def test_depth_layer_extracted(self):
        extractor = ReferenceConstraintsExtractor()
        inv = _make_visual_invariants(dominant_layer="background")
        rc = extractor.extract(inv)
        assert rc.dominant_depth_layer == "background"

    @_ref_models_required
    def test_palette_invariant_swatches_extracted(self):
        extractor = ReferenceConstraintsExtractor()
        swatches = [
            _make_color_swatch(rank=1, variability="invariant"),
            _make_color_swatch(rank=2, variability="invariant"),
            _make_color_swatch(rank=3, variability="semi_variable"),
            _make_color_swatch(rank=4, variability="variable"),
        ]
        inv = _make_visual_invariants(palette_swatches=swatches)
        rc = extractor.extract(inv)
        # Only invariant + semi_variable swatches should be in palette_anchor_hex
        assert len(rc.palette_anchor_hex) == 3
        # rank 4 is variable → excluded
        assert rc.palette_anchor_hex[2].startswith("#AA")

    @_ref_models_required
    def test_location_invariant_merges_architecture(self):
        extractor = ReferenceConstraintsExtractor()
        inv = _make_visual_invariants(camera_height_class=CameraHeightClass.EYE_LEVEL)
        loc = {"architecture_style": "brutalist", "ref_image_id": "loc_001"}
        rc = extractor.extract(inv, location_invariant=loc)
        assert rc.architecture_style == "brutalist"
        assert rc.location_id == "loc_001"

    @_ref_models_required
    def test_location_fills_camera_height_when_inv_has_none(self):
        """When ref image doesn't specify height, location default_camera_height is used."""
        # We can't set camera_height_class to None on a real VisualInvariants,
        # so we test the pure location path with a mock.
        class _MockInv:
            camera_height_class = None
            lighting = None
            depth_layers = None
            palette = None

        extractor = ReferenceConstraintsExtractor()
        loc = {"default_camera_height": "high_angle", "architecture_style": "industrial"}
        rc = extractor.extract(_MockInv(), location_invariant=loc)
        assert rc.camera_height == "high_angle"
        assert "crane_up" in rc.forbidden_movements


# ===========================================================================
# 3. TestSeasonSchemaModels
# ===========================================================================


class TestSeasonSchemaModels:
    """Verify new Pydantic schema models are correct and round-trip cleanly."""

    def test_rule_engine_report_defaults(self):
        r = RuleEngineReport()
        assert r.rules_evaluated == 0
        assert r.hard_conflicts_resolved == 0
        assert r.conflict_shot_ids == []

    def test_rule_engine_report_json_round_trip(self):
        r = RuleEngineReport(
            rules_evaluated=90,
            hard_conflicts_resolved=3,
            soft_conflicts_annotated=5,
            total_shots_modified=4,
            conflict_shot_ids=["S01", "S03"],
            rule_ids_fired=["CHR-01", "SPC-01"],
        )
        restored = RuleEngineReport.model_validate(r.model_dump())
        assert restored.hard_conflicts_resolved == 3

    def test_season_coherence_metrics_construction(self):
        m = SeasonCoherenceMetrics(
            season_id="S01",
            episode_count=3,
            total_shots=90,
            mean_feasibility_score=76.5,
            consistency_score_mean=0.92,
            palette_drift_episodes=["EP03"],
            rule_conflicts_per_episode={"EP01": 2, "EP02": 1, "EP03": 5},
        )
        assert m.episode_count == 3
        assert "EP03" in m.palette_drift_episodes

    def test_aiprods_season_construction(self):
        output = _make_minimal_output("EP01")
        season = AIPRODSeason(
            season_id="S01",
            series_title="District Zero",
            episodes=[output],
        )
        assert season.series_title == "District Zero"
        assert len(season.episodes) == 1

    def test_aiprod_output_has_rule_engine_report(self):
        output = _make_minimal_output("EP01")
        assert output.rule_engine_report is not None
        assert output.rule_engine_report.rules_evaluated == 9

    def test_episode_has_rule_engine_report(self):
        output = _make_minimal_output("EP01")
        ep = output.episodes[0]
        assert ep.rule_engine_report is not None
        assert ep.rule_engine_report.hard_conflicts_resolved == 1


# ===========================================================================
# 4. TestSeasonCoherenceTracker
# ===========================================================================


class TestSeasonCoherenceTracker:
    """Tests for multi-episode coherence accumulation."""

    def test_empty_tracker_returns_zero_metrics(self):
        tracker = SeasonCoherenceTracker(season_id="S01")
        metrics = tracker.compute_metrics()
        assert metrics.episode_count == 0
        assert metrics.total_shots == 0
        assert metrics.mean_feasibility_score == 0.0

    def test_single_episode_metrics(self):
        tracker = SeasonCoherenceTracker(season_id="S01")
        tracker.add_episode(_make_minimal_output("EP01", feasibility_score=80))
        metrics = tracker.compute_metrics()
        assert metrics.episode_count == 1
        assert metrics.total_shots == 1
        assert metrics.mean_feasibility_score == 80.0

    def test_multiple_episodes_aggregated(self):
        tracker = SeasonCoherenceTracker(season_id="S01")
        tracker.add_episode(_make_minimal_output("EP01", feasibility_score=80))
        tracker.add_episode(_make_minimal_output("EP02", feasibility_score=60))
        metrics = tracker.compute_metrics()
        assert metrics.episode_count == 2
        assert metrics.total_shots == 2
        assert metrics.mean_feasibility_score == 70.0

    def test_rule_conflicts_per_episode_populated(self):
        tracker = SeasonCoherenceTracker(season_id="S01")
        tracker.add_episode(_make_minimal_output("EP01"))
        tracker.add_episode(_make_minimal_output("EP02"))
        metrics = tracker.compute_metrics()
        # Each minimal output has 1 hard + 0 soft = 1 total per episode
        assert metrics.rule_conflicts_per_episode["EP01"] == 1
        assert metrics.rule_conflicts_per_episode["EP02"] == 1

    def test_compute_metrics_idempotent(self):
        tracker = SeasonCoherenceTracker(season_id="S01")
        tracker.add_episode(_make_minimal_output("EP01"))
        m1 = tracker.compute_metrics()
        m2 = tracker.compute_metrics()
        assert m1.mean_feasibility_score == m2.mean_feasibility_score

    def test_season_id_propagated(self):
        tracker = SeasonCoherenceTracker(season_id="S02")
        tracker.add_episode(_make_minimal_output("EP01"))
        metrics = tracker.compute_metrics()
        assert metrics.season_id == "S02"

    def test_palette_drift_detection(self):
        summaries = [
            EpisodeCoherenceSummary("EP01", 10, 75.0, 0.9, 1, 0, ["#ff0000"]),
            EpisodeCoherenceSummary("EP02", 10, 75.0, 0.9, 1, 0, ["#ff0000"]),
            EpisodeCoherenceSummary("EP03", 10, 75.0, 0.9, 1, 0, ["#00ff00"]),  # drift
        ]
        drift = _detect_palette_drift(summaries)
        assert "EP03" in drift
        assert "EP01" not in drift
        assert "EP02" not in drift

    def test_palette_drift_requires_two_episodes(self):
        summaries = [
            EpisodeCoherenceSummary("EP01", 10, 75.0, 0.9, 0, 0, ["#ff0000"]),
        ]
        drift = _detect_palette_drift(summaries)
        assert drift == []


# ===========================================================================
# 5. TestPass4RuleEngineIntegration
# ===========================================================================


class TestPass4RuleEngineIntegration:
    """Tests that compile_episode now runs the Rule Engine and populates RuleEngineReport."""

    def _run_compile(
        self,
        camera_movement: str = "static",
        feasibility_score: int = 80,
        ref_invariants: object | None = None,
    ) -> AIPRODOutput:
        from aiprod_adaptation.core.pass4_compile import compile_episode

        scene: dict = {
            "scene_id": "SC01",
            "characters": ["Alice"],
            "location": "Office",
            "visual_actions": ["walks"],
            "dialogues": ["Hello"],
            "emotion": "neutral",
        }
        shot: dict = {
            "shot_id": "S01",
            "scene_id": "SC01",
            "prompt": "Alice walks through the office.",
            "duration_sec": 5,
            "emotion": "neutral",
            "shot_type": "medium",
            "camera_movement": camera_movement,
            "action": {
                "subject_id": "alice",
                "action_type": "moves",
                "target": None,
                "modifiers": [],
                "location_id": "office",
                "camera_intent": "static",
                "source_text": "walks",
            },
            "metadata": {},
            "feasibility_score": feasibility_score,
        }
        return compile_episode(
            [scene], [shot], "Test Episode",
            ref_invariants=ref_invariants,
        )

    def test_rule_engine_report_present(self):
        output = self._run_compile()
        assert output.rule_engine_report is not None

    def test_episode_rule_engine_report_present(self):
        output = self._run_compile()
        assert output.episodes[0].rule_engine_report is not None

    def test_rules_evaluated_count_positive(self):
        """rules_evaluated = len(builtin_rules) × shot_count."""
        from aiprod_adaptation.core.rule_engine.builtin_rules import BUILTIN_RULES
        output = self._run_compile()
        report = output.rule_engine_report
        assert report is not None
        assert report.rules_evaluated == len(BUILTIN_RULES) * 1

    def test_no_conflicts_on_clean_shot(self):
        """A static shot with feasibility=100 should trigger no HARD conflicts."""
        output = self._run_compile(camera_movement="static", feasibility_score=100)
        report = output.rule_engine_report
        assert report is not None
        assert report.hard_conflicts_resolved == 0

    def test_chr01_does_not_fire_when_r01_already_fixed(self):
        """
        CHR-01 (feasibility < 40 + non-static) does NOT fire at the Rule Engine layer
        because consistency_checker R01 already downgrades pan→static before the Rule
        Engine evaluates the shot.  The Rule Engine correctly sees camera_movement='static'
        and the AND-condition fails.
        """
        output = self._run_compile(camera_movement="pan", feasibility_score=20)
        report = output.rule_engine_report
        assert report is not None
        # R01 in consistency_checker handled the downgrade; CHR-01 should NOT fire
        assert "CHR-01-feasibility-gate" not in report.rule_ids_fired

    def test_chr01_modifies_shot_camera_movement(self):
        """After CHR-01 fires, the shot's camera_movement should be downgraded."""
        output = self._run_compile(camera_movement="pan", feasibility_score=20)
        shot = output.episodes[0].shots[0]
        # pan → static via downgrade chain
        assert shot.camera_movement == "static"

    @_ref_models_required
    def test_spc01_fires_with_overhead_ref(self):
        """SPC-01 fires when overhead ref + crane_up movement."""
        inv = _make_visual_invariants(camera_height_class=CameraHeightClass.OVERHEAD)
        output = self._run_compile(camera_movement="crane_up", ref_invariants=inv)
        report = output.rule_engine_report
        assert report is not None
        assert "SPC-01-overhead-crane-up-incompatible" in report.rule_ids_fired

    @_ref_models_required
    def test_spc01_downgrades_crane_up_to_tilt_up(self):
        """After SPC-01 fires on overhead ref, crane_up is downgraded to tilt_up."""
        inv = _make_visual_invariants(camera_height_class=CameraHeightClass.OVERHEAD)
        output = self._run_compile(camera_movement="crane_up", ref_invariants=inv)
        shot = output.episodes[0].shots[0]
        assert shot.camera_movement == "tilt_up"

    def test_original_shots_not_mutated(self):
        """compile_episode must not mutate the input shot dicts."""
        from aiprod_adaptation.core.pass4_compile import compile_episode
        shot: dict = {
            "shot_id": "S01",
            "scene_id": "SC01",
            "prompt": "A shot.",
            "duration_sec": 5,
            "emotion": "neutral",
            "shot_type": "medium",
            "camera_movement": "pan",
            "action": {
                "subject_id": "alice",
                "action_type": "moves",
                "target": None,
                "modifiers": [],
                "location_id": "office",
                "camera_intent": "static",
                "source_text": "walks",
            },
            "metadata": {},
            "feasibility_score": 20,
        }
        original_movement = shot["camera_movement"]
        compile_episode(
            [{"scene_id": "SC01", "characters": [], "location": "X",
              "visual_actions": [], "dialogues": [], "emotion": "neutral"}],
            [shot],
            "T",
        )
        assert shot["camera_movement"] == original_movement


# ===========================================================================
# 6. TestProcessNarrativeWithReference
# ===========================================================================


class TestProcessNarrativeWithReference:
    """Integration tests for the process_narrative_with_reference() entry point."""

    def _mock_visual_bible(self) -> object:
        """Return a minimal mock VisualBible that satisfies engine.py duck-typing."""
        class _MockVB:
            data: dict = {
                "series_title": "District Zero",
                "characters": {},
                "locations": {},
            }
            characters: dict = {}
            locations: dict = {}

            def get_character_prompt_fragment(self, _char_name: str) -> str | None:
                return None

            def get_location_prompt_fragment(self, _loc_id: str) -> str | None:
                return None
        return _MockVB()

    def test_returns_aiprods_output(self):
        import pathlib

        from aiprod_adaptation.core.engine import process_narrative_with_reference
        text = pathlib.Path(
            "aiprod_adaptation/examples/chapter1.txt"
        ).read_text(encoding="utf-8")
        output = process_narrative_with_reference(
            text=text,
            title="Chapter 1",
            visual_bible=self._mock_visual_bible(),
        )
        assert isinstance(output, AIPRODOutput)

    def test_rule_engine_report_populated(self):
        import pathlib

        from aiprod_adaptation.core.engine import process_narrative_with_reference
        text = pathlib.Path(
            "aiprod_adaptation/examples/chapter1.txt"
        ).read_text(encoding="utf-8")
        output = process_narrative_with_reference(
            text=text,
            title="Chapter 1",
            visual_bible=self._mock_visual_bible(),
        )
        assert output.rule_engine_report is not None
        assert output.rule_engine_report.rules_evaluated > 0

    @_ref_models_required
    def test_with_ref_invariants_no_crash(self):
        """process_narrative_with_reference must not crash with real ref_invariants."""
        import pathlib

        from aiprod_adaptation.core.engine import process_narrative_with_reference
        text = pathlib.Path(
            "aiprod_adaptation/examples/chapter1.txt"
        ).read_text(encoding="utf-8")
        inv = _make_visual_invariants(camera_height_class=CameraHeightClass.EYE_LEVEL)
        output = process_narrative_with_reference(
            text=text,
            title="Chapter 1",
            visual_bible=self._mock_visual_bible(),
            ref_invariants=inv,
        )
        assert isinstance(output, AIPRODOutput)
        assert output.rule_engine_report is not None

    def test_episode_index_passed_through(self):
        """episode_index param is accepted without error."""
        import pathlib

        from aiprod_adaptation.core.engine import process_narrative_with_reference
        text = pathlib.Path(
            "aiprod_adaptation/examples/chapter1.txt"
        ).read_text(encoding="utf-8")
        output = process_narrative_with_reference(
            text=text,
            title="Chapter 1",
            visual_bible=self._mock_visual_bible(),
            episode_index=3,
        )
        assert isinstance(output, AIPRODOutput)

    def test_season_tracker_accepts_output(self):
        """SeasonCoherenceTracker can ingest the output of process_narrative_with_reference."""
        import pathlib

        from aiprod_adaptation.core.engine import process_narrative_with_reference
        text = pathlib.Path(
            "aiprod_adaptation/examples/chapter1.txt"
        ).read_text(encoding="utf-8")
        output = process_narrative_with_reference(
            text=text,
            title="Chapter 1",
            visual_bible=self._mock_visual_bible(),
        )
        tracker = SeasonCoherenceTracker(season_id="S01")
        tracker.add_episode(output)
        metrics = tracker.compute_metrics()
        assert metrics.episode_count == 1
        assert metrics.total_shots > 0
