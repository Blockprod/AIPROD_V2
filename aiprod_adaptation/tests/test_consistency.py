"""
pytest test suite — Consistency Engine v5.0

Covers:
  1. ContinuityChecker — character/location/prompt coherence (CC-01..05)
  2. TimelineEngine    — timestamp monotonicity and validation (TE-01..03)
  3. AudioNormalizer   — LUFS target validation (AN-01..02)
  4. AssetRegistry     — build from output, canon violation detection (AR-01..02)
  5. ColorManager      — LUT assignment and forbidden grade detection (CM-01..03)
"""

from __future__ import annotations

from aiprod_adaptation.consistency import (
    AssetRegistry,
    AudioNormalizer,
    ColorManager,
    ContinuityChecker,
    TimelineEngine,
)
from aiprod_adaptation.models.schema import (
    AIPRODOutput,
    Episode,
    GlobalAsset,
    Scene,
    Shot,
    Timeline,
)

# ---------------------------------------------------------------------------
# Helpers — minimal fixtures
# ---------------------------------------------------------------------------

def _make_shot(
    shot_id: str = "SCN_001_SHOT_001",
    scene_id: str = "SCN_001",
    prompt: str = "A character stands in a corridor.",
    duration_sec: int = 4,
    emotion: str = "neutral",
    feasibility_score: int = 85,
    reference_anchor_strength: float = 1.0,
    metadata: dict | None = None,
) -> Shot:
    return Shot(
        shot_id=shot_id,
        scene_id=scene_id,
        prompt=prompt,
        duration_sec=duration_sec,
        emotion=emotion,
        feasibility_score=feasibility_score,
        reference_anchor_strength=reference_anchor_strength,
        metadata=metadata or {},
    )


def _make_scene(
    scene_id: str = "SCN_001",
    character_ids: list[str] | None = None,
    location_id: str = "district_zero_outer_wall_night",
    location: str = "Outer Wall",
) -> Scene:
    return Scene(
        scene_id=scene_id,
        characters=character_ids or ["nara"],
        character_ids=character_ids or ["nara"],
        location=location,
        location_id=location_id,
        visual_actions=["Nara scans the perimeter."],
        dialogues=[],
        emotion="tense",
    )


def _make_output(
    shots: list[Shot] | None = None,
    scenes: list[Scene] | None = None,
    global_assets: list[GlobalAsset] | None = None,
    color_luts: dict[str, str] | None = None,
) -> AIPRODOutput:
    shots = shots or [_make_shot()]
    scenes = scenes or [_make_scene()]
    episode = Episode(
        episode_id="EP_01",
        scenes=scenes,
        shots=shots,
    )
    return AIPRODOutput(
        title="District Zero EP01 Test",
        episodes=[episode],
        global_assets=global_assets or [],
        color_luts=color_luts or {},
    )


# ---------------------------------------------------------------------------
# CC-01 — Character appearance consistent (no empty character_ids)
# ---------------------------------------------------------------------------

class TestContinuityChecker:

    def test_character_appearance_consistent(self) -> None:
        """CC-01: Scenes with declared character_ids should not produce E1 errors
        when those characters are registered in global_assets."""
        assets = [
            GlobalAsset(
                asset_id="nara",
                asset_type="character",
                attributes={"display_name": "Nara Voss"},
                first_occurrence="SCN_001_SHOT_001",
            )
        ]
        output = _make_output(global_assets=assets)
        result = ContinuityChecker().check(output)
        assert result.valid
        e1_errors = [e for e in result.blocking_errors if "E1" in e]
        assert not e1_errors, f"Unexpected E1 errors: {e1_errors}"

    def test_location_consistency(self) -> None:
        """CC-02: Location registered in global_assets should not trigger E2 warning."""
        assets = [
            GlobalAsset(
                asset_id="nara",
                asset_type="character",
                attributes={},
                first_occurrence="SCN_001_SHOT_001",
            ),
            GlobalAsset(
                asset_id="district_zero_outer_wall_night",
                asset_type="location",
                attributes={"display_name": "Outer Wall", "lighting_condition": "night"},
                first_occurrence="SCN_001_SHOT_001",
            ),
        ]
        output = _make_output(global_assets=assets)
        result = ContinuityChecker().check(output)
        e2_warnings = [w for w in result.warnings if "E2" in w]
        assert not e2_warnings, f"Unexpected E2 warnings: {e2_warnings}"

    def test_empty_prompt_triggers_error(self) -> None:
        """CC-03: A shot with empty prompt must produce an A1 blocking error."""
        shot = _make_shot(prompt="")
        output = _make_output(shots=[shot])
        result = ContinuityChecker().check(output)
        assert not result.valid
        assert any("A1" in e for e in result.blocking_errors)

    def test_low_feasibility_triggers_error(self) -> None:
        """CC-04: feasibility_score < 70 must produce a B6 blocking error."""
        shot = _make_shot(feasibility_score=50)
        output = _make_output(shots=[shot])
        result = ContinuityChecker().check(output)
        assert not result.valid
        assert any("B6" in e for e in result.blocking_errors)

    def test_causal_chain_valid(self) -> None:
        """CC-05: Monotone shot_ids within a scene must pass A3."""
        shots = [
            _make_shot("SCN_001_SHOT_001", "SCN_001"),
            _make_shot("SCN_001_SHOT_002", "SCN_001"),
            _make_shot("SCN_001_SHOT_003", "SCN_001"),
        ]
        output = _make_output(shots=shots)
        result = ContinuityChecker().check(output)
        a3_errors = [e for e in result.blocking_errors if "A3" in e]
        assert not a3_errors, f"Unexpected A3 errors: {a3_errors}"


# ---------------------------------------------------------------------------
# TE-01..03 — Timeline Engine: timestamp monotonicity
# ---------------------------------------------------------------------------

class TestTimelineEngine:

    def test_timestamps_monotonic(self) -> None:
        """TE-01: Built timeline has strictly increasing offset_in_episode."""
        shots = [
            _make_shot("SCN_001_SHOT_001", duration_sec=4),
            _make_shot("SCN_001_SHOT_002", duration_sec=5),
            _make_shot("SCN_001_SHOT_003", duration_sec=6),
        ]
        output = _make_output(shots=shots)
        engine = TimelineEngine()
        timeline = engine.build(output)
        offsets = [entry["offset_in_episode"] for entry in timeline.absolute_timestamps]
        assert offsets == sorted(offsets), f"Timestamps not monotonic: {offsets}"

    def test_timestamps_contiguous(self) -> None:
        """TE-02: end_offset[n] == offset_in_episode[n+1] (no gaps or overlaps)."""
        shots = [
            _make_shot("SCN_001_SHOT_001", duration_sec=4),
            _make_shot("SCN_001_SHOT_002", duration_sec=5),
            _make_shot("SCN_001_SHOT_003", duration_sec=3),
        ]
        output = _make_output(shots=shots)
        engine = TimelineEngine()
        timeline = engine.build(output)
        ts = timeline.absolute_timestamps
        for i in range(1, len(ts)):
            assert ts[i]["offset_in_episode"] == ts[i - 1]["end_offset"], (
                f"Gap/overlap between shot {i-1} and {i}: "
                f"end={ts[i-1]['end_offset']}, start={ts[i]['offset_in_episode']}"
            )

    def test_validate_detects_invalid_duration(self) -> None:
        """TE-03: validate() reports error when duration is out of [3, 8]."""
        engine = TimelineEngine()
        # Manually inject an invalid timestamp (bypasses Pydantic validator)
        timeline = Timeline(
            episode_offsets={"EP_01": 0},
            absolute_timestamps=[
                {
                    "shot_id": "SCN_001_SHOT_001",
                    "episode_id": "EP_01",
                    "offset_in_episode": 0,
                    "offset_in_season": 0,
                    "duration_sec": 10,  # invalid
                    "end_offset": 10,
                }
            ],
        )
        result = engine.validate(timeline)
        assert not result.valid
        assert any("duration_sec" in e for e in result.errors)


# ---------------------------------------------------------------------------
# AN-01..02 — AudioNormalizer: LUFS target validation
# ---------------------------------------------------------------------------

class TestAudioNormalizer:

    def test_audio_normalized(self) -> None:
        """AN-01: Shot with audio_lufs at target (-23) should pass."""
        # audio_lufs is not in _ALLOWED_METADATA_KEYS — test via voice assets
        assets = [
            GlobalAsset(
                asset_id="voice_nara",
                asset_type="voice",
                attributes={
                    "character_id": "nara",
                    "timbre": "mezzo",
                    "accent": "neutral",
                    "lufs_target": -23.0,
                },
                first_occurrence="SCN_001_SHOT_001",
            )
        ]
        output = _make_output(global_assets=assets)
        result = AudioNormalizer().validate(output)
        assert result.valid
        assert not result.errors

    def test_missing_voice_asset_warns(self) -> None:
        """AN-02: Shot with dialogue dominant_sound and unregistered character warns."""
        shot = _make_shot(metadata={"dominant_sound": "dialogue"})
        # No voice assets registered
        output = _make_output(shots=[shot])
        result = AudioNormalizer().validate(output)
        # Should produce warnings (not errors) for missing voice asset
        assert result.valid  # warnings don't block
        assert any("voice asset" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# AR-01..02 — AssetRegistry: build and canon violation
# ---------------------------------------------------------------------------

class TestAssetRegistry:

    def test_builds_from_output(self) -> None:
        """AR-01: AssetRegistry.build() extracts at least one character and location."""
        output = _make_output()
        registry = AssetRegistry()
        assets = registry.build(output)
        types = {a.asset_type for a in assets}
        assert "character" in types, "Expected at least one character asset"
        assert "location" in types, "Expected at least one location asset"

    def test_canon_violation_detected(self) -> None:
        """AR-02: validate_canon() detects changed attributes on a canon_locked asset."""
        registry = AssetRegistry()
        prev_assets = [
            GlobalAsset(
                asset_id="nara",
                asset_type="character",
                attributes={"hair_color": "black"},
                first_occurrence="SCN_001_SHOT_001",
                canon_locked=True,
            )
        ]
        current_assets = [
            GlobalAsset(
                asset_id="nara",
                asset_type="character",
                attributes={"hair_color": "blonde"},  # changed!
                first_occurrence="SCN_001_SHOT_001",
                canon_locked=True,
            )
        ]
        violations = registry.validate_canon(current_assets, prev_assets)
        assert violations, "Expected a CANON_VIOLATION for changed hair_color"
        assert "nara" in violations[0]

    def test_reference_pack_injects_image_id(self) -> None:
        """AR-03: enrich_from_reference_pack() injects reference_image_id from a
        reference pack JSON with characters keyed by asset_id."""
        import json
        import os
        import tempfile
        registry = AssetRegistry()

        pack_data = {
            "characters": {
                "nara": {"reference_image_urls": ["refs/nara_01.png", "refs/nara_02.png"]},
                "vale": {"reference_image_urls": ["refs/vale_01.png"]},
            }
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(pack_data, f)
            pack_path = f.name

        try:
            assets = [
                GlobalAsset(
                    asset_id="nara",
                    asset_type="character",
                    attributes={"display_name": "Nara"},
                    first_occurrence="SCN_001_SHOT_001",
                ),
                GlobalAsset(
                    asset_id="vale",
                    asset_type="character",
                    attributes={"display_name": "Vale"},
                    first_occurrence="SCN_010_SHOT_001",
                ),
            ]

            enriched = registry.enrich_from_reference_pack(assets, pack_path)
        finally:
            os.unlink(pack_path)

        nara = next(a for a in enriched if a.asset_id == "nara")
        vale = next(a for a in enriched if a.asset_id == "vale")

        assert "reference_image_id" in nara.attributes, "Nara missing reference_image_id"
        assert "nara" in nara.attributes["reference_image_id"].lower()

        assert "reference_image_id" in vale.attributes, "Vale missing reference_image_id"
        assert "vale" in vale.attributes["reference_image_id"].lower()


# ---------------------------------------------------------------------------
# CM-01..03 — ColorManager: forbidden grades and LUT coverage
# ---------------------------------------------------------------------------

class TestColorManager:

    def test_color_lut_assigned(self) -> None:
        """CM-01: Shot with known location_id and matching color_lut passes."""
        scene = _make_scene(location_id="district_zero_outer_wall_night")
        shot = _make_shot(metadata={"color_grade_hint": "cool"})
        luts = {"district_zero_outer_wall_night": "dz_outer_wall_night"}
        output = _make_output(shots=[shot], scenes=[scene], color_luts=luts)
        result = ColorManager().validate(output)
        assert result.valid
        assert not result.errors
        # No LUT coverage warning either
        assert not result.warnings

    def test_forbidden_orange_teal_blocked(self) -> None:
        """CM-02: orange_teal color_grade_hint must produce a blocking error."""
        shot = _make_shot(metadata={"color_grade_hint": "orange_teal"})
        output = _make_output(shots=[shot])
        result = ColorManager().validate(output)
        assert not result.valid
        assert any("orange_teal" in e for e in result.errors)

    def test_desaturated_restricted_to_denouement(self) -> None:
        """CM-03: desaturated outside denouement/flashback must produce an error."""
        # beat_type=exposition is not allowed for desaturated
        shot = _make_shot(metadata={"color_grade_hint": "desaturated", "beat_type": "exposition"})
        output = _make_output(shots=[shot])
        result = ColorManager().validate(output)
        assert not result.valid
        assert any("desaturated" in e for e in result.errors)
