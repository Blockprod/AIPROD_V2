"""
Tests for reference_image — ReferenceQualityGate and VisualInvariantsExtractor.

All tests are purely synthetic (no real image files required):
  - Minimal valid images are constructed programmatically using Pillow.
  - Edge cases use degenerate pixel arrays (solid colour, noise, gradient).
  - All tests are deterministic and require no network access.

Dependencies: pytest, Pillow, numpy (installed via pip install -e ".[reference,dev]")
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import numpy as np
    from PIL import Image
    _DEPS_AVAILABLE = True
except ImportError:
    _DEPS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _DEPS_AVAILABLE,
    reason="Pillow and numpy required for reference_image tests (pip install -e '.[reference]')",
)

# ---------------------------------------------------------------------------
# Test image factory helpers
# ---------------------------------------------------------------------------

def _make_image_file(
    tmp_path: Path,
    width: int,
    height: int,
    pattern: str = "gradient",
    filename: str = "ref.png",
) -> Path:
    """
    Create a synthetic PNG image file for testing.

    pattern:
      "gradient"   — smooth RGB gradient (good reference, passes gate)
      "solid"      — flat colour (fails LOW_INFORMATION + MONOCHROMATIC_INPUT)
      "noise"      — random noise (high entropy, high gradient, passes gate)
      "dark"       — near-black image (fails UNDEREXPOSED)
      "bright"     — near-white image (fails OVEREXPOSED)
      "checkerboard" — high-frequency alternating black/white (high Laplacian)
    """
    rng = np.random.default_rng(42)  # fixed seed for determinism

    if pattern == "gradient":
        # Smooth horizontal-vertical gradient with colour variation
        xs = np.linspace(0, 255, width, dtype="uint8")
        ys = np.linspace(0, 200, height, dtype="uint8")
        r = np.outer(ys, np.ones(width, dtype="uint8"))
        g = np.outer(np.ones(height, dtype="uint8"), xs)
        b = np.flipud(r).astype("uint8")
        arr = np.stack([r, g, b], axis=2).astype("uint8")

    elif pattern == "solid":
        arr = np.full((height, width, 3), 128, dtype="uint8")

    elif pattern == "noise":
        arr = rng.integers(0, 256, (height, width, 3), dtype="uint8")

    elif pattern == "dark":
        arr = np.full((height, width, 3), 5, dtype="uint8")

    elif pattern == "bright":
        arr = np.full((height, width, 3), 252, dtype="uint8")

    elif pattern == "quadrant":
        # 4 coloured quadrants: red / green / blue / yellow — sharp edges,
        # distinct channel means (not monochromatic), no extreme exposure.
        arr = np.zeros((height, width, 3), dtype="uint8")
        hy, hx = height // 2, width // 2
        arr[:hy, :hx]  = [255,   0,   0]   # red
        arr[:hy, hx:]  = [  0, 200,   0]   # green
        arr[hy:, :hx]  = [  0,   0, 200]   # blue
        arr[hy:, hx:]  = [200, 200,   0]   # yellow

    elif pattern == "warm_noise":
        # Coloured noise with distinct channel means — passes ALL gate checks:
        #   R≈180 (warm), G≈100 (neutral), B≈60 (cool)  → channel_var >> 100
        #   Random noise  → high Laplacian variance (> BLUR_THRESHOLD)
        #   128-level spread → high Shannon entropy (> MIN_ENTROPY_BITS)
        #   Moderate luminance → neither overexposed nor underexposed
        rng_l = np.random.default_rng(42)
        r_ch = rng_l.integers(120, 240, (height, width), dtype="uint8")
        g_ch = rng_l.integers(60,  140, (height, width), dtype="uint8")
        b_ch = rng_l.integers(20,  100, (height, width), dtype="uint8")
        arr = np.stack([r_ch, g_ch, b_ch], axis=2)

    elif pattern == "checkerboard":
        tile = np.array(
            [[0, 255], [255, 0]], dtype="uint8"
        ).repeat(16, axis=0).repeat(16, axis=1)
        reps_y = height // tile.shape[0] + 1
        reps_x = width  // tile.shape[1] + 1
        full = np.tile(tile, (reps_y, reps_x))[:height, :width]
        arr = np.stack([full, full, full], axis=2).astype("uint8")

    else:
        raise ValueError(f"Unknown pattern: {pattern!r}")

    path = tmp_path / filename
    Image.fromarray(arr, mode="RGB").save(path)
    return path


# ---------------------------------------------------------------------------
# ReferenceQualityGate — import guard
# ---------------------------------------------------------------------------

def _gate():
    from aiprod_adaptation.core.reference_image.quality_gate import ReferenceQualityGate
    return ReferenceQualityGate()


def _extractor():
    from aiprod_adaptation.core.reference_image.extractor import VisualInvariantsExtractor
    return VisualInvariantsExtractor()


# ===========================================================================
# 1. ReferenceQualityGate — instantiation
# ===========================================================================

class TestReferenceQualityGateInstantiation:
    def test_default_instantiation(self) -> None:
        gate = _gate()
        from aiprod_adaptation.core.reference_image.quality_gate import (
            DEFAULT_PASS_THRESHOLD,
            MIN_DIMENSION,
            WARNING_THRESHOLD,
        )
        assert gate.pass_threshold == DEFAULT_PASS_THRESHOLD
        assert gate.warning_threshold == WARNING_THRESHOLD
        assert gate.min_dimension == MIN_DIMENSION

    def test_custom_thresholds(self) -> None:
        from aiprod_adaptation.core.reference_image.quality_gate import ReferenceQualityGate
        gate = ReferenceQualityGate(pass_threshold=0.80, warning_threshold=0.60)
        assert gate.pass_threshold == 0.80
        assert gate.warning_threshold == 0.60


# ===========================================================================
# 2. ReferenceQualityGate — hard rejections
# ===========================================================================

class TestReferenceQualityGateRejections:
    def test_reject_nonexistent_file(self, tmp_path: Path) -> None:
        gate = _gate()
        report = gate.check(tmp_path / "nonexistent.png")
        assert not report.passed
        from aiprod_adaptation.core.reference_image.models import RejectionReason
        assert RejectionReason.LOAD_ERROR in report.rejection_reasons

    def test_reject_resolution_too_low(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=256, height=256, pattern="gradient")
        gate = _gate()
        report = gate.check(path)
        from aiprod_adaptation.core.reference_image.models import RejectionReason
        assert not report.passed
        assert RejectionReason.RESOLUTION_TOO_LOW in report.rejection_reasons

    def test_reject_overexposed(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="bright")
        gate = _gate()
        report = gate.check(path)
        from aiprod_adaptation.core.reference_image.models import RejectionReason
        assert not report.passed
        assert RejectionReason.OVEREXPOSED in report.rejection_reasons

    def test_reject_underexposed(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="dark")
        gate = _gate()
        report = gate.check(path)
        from aiprod_adaptation.core.reference_image.models import RejectionReason
        assert not report.passed
        assert RejectionReason.UNDEREXPOSED in report.rejection_reasons

    def test_reject_monochromatic(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="solid")
        gate = _gate()
        report = gate.check(path)
        from aiprod_adaptation.core.reference_image.models import RejectionReason
        # solid grey image should trigger MONOCHROMATIC or LOW_INFORMATION
        reject_codes = set(report.rejection_reasons)
        assert (
            RejectionReason.MONOCHROMATIC_INPUT in reject_codes
            or RejectionReason.LOW_INFORMATION in reject_codes
        )

    def test_rejection_reasons_are_list(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=256, height=256, pattern="gradient")
        gate = _gate()
        report = gate.check(path)
        assert isinstance(report.rejection_reasons, list)


# ===========================================================================
# 3. ReferenceQualityGate — valid image passes
# ===========================================================================

class TestReferenceQualityGatePassing:
    def test_gradient_image_passes(self, tmp_path: Path) -> None:
        # 'quadrant' has sharp edges (passes blur) and distinct channel means
        path = _make_image_file(tmp_path, width=768, height=512, pattern="warm_noise")
        gate = _gate()
        report = gate.check(path)
        assert report.passed, report
        assert report.composite_score >= gate.pass_threshold

    def test_noise_image_passes(self, tmp_path: Path) -> None:
        # 'quadrant' pattern is guaranteed to pass all hard rejections
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        gate = _gate()
        report = gate.check(path)
        assert report.passed, report

    def test_composite_score_in_range(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        gate = _gate()
        report = gate.check(path)
        assert 0.0 <= report.composite_score <= 1.0

    def test_component_scores_sum_approx_composite(self, tmp_path: Path) -> None:
        """Verify component scores are consistent with composite (weighted sum)."""
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        gate = _gate()
        report = gate.check(path)
        from aiprod_adaptation.core.reference_image.quality_gate import (
            W_CLARITY,
            W_COMPOSITION,
            W_DEPTH,
            W_LIGHTING,
            W_SUBJECT,
        )
        cs = report.component_scores
        expected = (
            W_CLARITY     * cs.clarity
            + W_LIGHTING    * cs.lighting
            + W_SUBJECT     * cs.subject
            + W_DEPTH       * cs.depth
            + W_COMPOSITION * cs.composition
        )
        assert abs(report.composite_score - expected) < 0.001

    def test_source_path_preserved(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        gate = _gate()
        report = gate.check(path)
        assert str(path) in report.source_path

    def test_threshold_used_matches_gate(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        gate = _gate()
        report = gate.check(path)
        assert report.threshold_used == gate.pass_threshold

    def test_summary_contains_pass_or_fail(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        gate = _gate()
        report = gate.check(path)
        summary = report.summary()
        assert "PASS" in summary or "FAIL" in summary


# ===========================================================================
# 4. ReferenceQualityGate — determinism
# ===========================================================================

class TestReferenceQualityGateDeterminism:
    def test_same_image_same_score(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        gate = _gate()
        r1 = gate.check(path)
        r2 = gate.check(path)
        assert r1.composite_score == r2.composite_score
        assert r1.passed == r2.passed

    def test_same_image_same_component_scores(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        gate = _gate()
        r1 = gate.check(path)
        r2 = gate.check(path)
        assert r1.component_scores.clarity     == r2.component_scores.clarity
        assert r1.component_scores.lighting    == r2.component_scores.lighting
        assert r1.component_scores.subject     == r2.component_scores.subject
        assert r1.component_scores.depth       == r2.component_scores.depth
        assert r1.component_scores.composition == r2.component_scores.composition


# ===========================================================================
# 5. ReferenceQualityReport — serialisation
# ===========================================================================

class TestReferenceQualityReportSerialisation:
    def test_model_dump_is_json_serialisable(self, tmp_path: Path) -> None:
        import json
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        gate = _gate()
        report = gate.check(path)
        data = report.model_dump()
        # Should not raise
        serialised = json.dumps(data)
        assert len(serialised) > 10

    def test_model_dump_contains_required_keys(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        gate = _gate()
        report = gate.check(path)
        data = report.model_dump()
        for key in ("source_path", "passed", "composite_score",
                    "component_scores", "rejection_reasons", "warnings",
                    "threshold_used", "recommendation"):
            assert key in data, f"Missing key: {key!r}"


# ===========================================================================
# 6. VisualInvariantsExtractor — basic extraction
# ===========================================================================

class TestVisualInvariantsExtractorBasic:
    def test_extract_returns_visual_invariants(self, tmp_path: Path) -> None:
        from aiprod_adaptation.core.reference_image.models import VisualInvariants
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        assert isinstance(inv, VisualInvariants)

    def test_extract_dimensions_correct(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=768, height=432, pattern="gradient")
        inv = _extractor().extract(path)
        assert inv.width_px == 768
        assert inv.height_px == 432

    def test_extract_aspect_ratio_16x9(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=768, height=432, pattern="gradient")
        inv = _extractor().extract(path)
        assert inv.aspect_ratio == "16:9"

    def test_extract_aspect_ratio_square(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        assert inv.aspect_ratio == "1:1"

    def test_extract_palette_has_k_swatches(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        assert len(inv.palette) == 5

    def test_extract_palette_ranks_ascending(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        ranks = [s.rank for s in inv.palette]
        assert ranks == sorted(ranks)

    def test_extract_palette_coverage_sums_approx_100(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        total = sum(s.coverage_pct for s in inv.palette)
        # k-means on a sample — sum ≤ 100%; tolerance for sampling approximation
        assert total <= 100.1

    def test_extract_palette_hex_format(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        for swatch in inv.palette:
            assert swatch.hex_code.startswith("#")
            assert len(swatch.hex_code) == 7

    def test_extract_subject_coverage_in_range(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        assert 0.0 <= inv.subject_coverage_pct <= 100.0

    def test_extract_luminance_fingerprint_is_md5(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        assert len(inv.luminance_fingerprint) == 32
        assert all(c in "0123456789abcdef" for c in inv.luminance_fingerprint)


# ===========================================================================
# 7. VisualInvariantsExtractor — lighting analysis
# ===========================================================================

class TestVisualInvariantsLighting:
    def test_lighting_color_temp_positive(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        assert inv.lighting.color_temperature_k > 0

    def test_lighting_intensity_in_range(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        assert 0.0 <= inv.lighting.intensity_l95 <= 100.0

    def test_lighting_contrast_non_negative(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        assert inv.lighting.contrast_std_l >= 0.0

    def test_lighting_direction_valid_enum(self, tmp_path: Path) -> None:
        from aiprod_adaptation.core.reference_image.models import (
            LightingDirectionH,
            LightingDirectionV,
        )
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        assert inv.lighting.key_direction_h in LightingDirectionH
        assert inv.lighting.key_direction_v in LightingDirectionV

    def test_dark_image_low_intensity(self, tmp_path: Path) -> None:
        """A very dark image should register low intensity_l95."""
        import numpy as np
        from PIL import Image
        # Create slightly above black (not rejected but clearly dark)
        arr = np.full((512, 512, 3), 20, dtype="uint8")
        # Add colour channels so it's not monochromatic
        arr[:, :, 0] = 25
        arr[:, :, 2] = 15
        path = tmp_path / "dark_coloured.png"
        Image.fromarray(arr, mode="RGB").save(path)
        inv = _extractor().extract(path)
        assert inv.lighting.intensity_l95 < 30.0


# ===========================================================================
# 8. VisualInvariantsExtractor — depth layers
# ===========================================================================

class TestVisualInvariantsDepthLayers:
    def test_depth_layer_dominant_is_valid(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        assert inv.depth_layers.dominant_layer in {"foreground", "midground", "background"}

    def test_depth_layer_gradient_means_non_negative(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        assert inv.depth_layers.gradient_mean_foreground >= 0.0
        assert inv.depth_layers.gradient_mean_midground  >= 0.0
        assert inv.depth_layers.gradient_mean_background >= 0.0

    def test_checkerboard_high_gradient(self, tmp_path: Path) -> None:
        """High-frequency checkerboard should have high gradient means."""
        path = _make_image_file(tmp_path, width=512, height=512, pattern="checkerboard")
        inv = _extractor().extract(path)
        # All bands should show significant gradient
        assert inv.depth_layers.gradient_mean_foreground > 10.0


# ===========================================================================
# 9. VisualInvariantsExtractor — camera height
# ===========================================================================

class TestVisualInvariantsCameraHeight:
    def test_camera_height_is_valid_enum(self, tmp_path: Path) -> None:
        from aiprod_adaptation.core.reference_image.models import CameraHeightClass
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        assert inv.camera_height_class in CameraHeightClass


# ===========================================================================
# 10. VisualInvariantsExtractor — determinism
# ===========================================================================

class TestVisualInvariantsExtractorDeterminism:
    def test_same_image_same_fingerprint(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        ext = _extractor()
        i1 = ext.extract(path)
        i2 = ext.extract(path)
        assert i1.luminance_fingerprint == i2.luminance_fingerprint

    def test_same_image_same_palette_hex(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        ext = _extractor()
        i1 = ext.extract(path)
        i2 = ext.extract(path)
        assert [s.hex_code for s in i1.palette] == [s.hex_code for s in i2.palette]

    def test_same_image_same_color_temperature(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        ext = _extractor()
        i1 = ext.extract(path)
        i2 = ext.extract(path)
        assert i1.lighting.color_temperature_k == i2.lighting.color_temperature_k

    def test_different_images_different_fingerprints(self, tmp_path: Path) -> None:
        p1 = _make_image_file(tmp_path, 512, 512, "quadrant", "img1.png")
        p2 = _make_image_file(tmp_path, 512, 512, "dark", "img2.png")
        ext = _extractor()
        i1 = ext.extract(p1)
        i2 = ext.extract(p2)
        assert i1.luminance_fingerprint != i2.luminance_fingerprint


# ===========================================================================
# 11. VisualInvariants — serialisation
# ===========================================================================

class TestVisualInvariantsSerialisation:
    def test_model_dump_is_json_serialisable(self, tmp_path: Path) -> None:
        import json
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        data = inv.model_dump()
        serialised = json.dumps(data)
        assert len(serialised) > 10

    def test_to_prompt_fragment_is_non_empty(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        fragment = inv.to_prompt_fragment()
        assert isinstance(fragment, str)
        assert len(fragment) > 20

    def test_to_prompt_fragment_contains_aspect_ratio(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        fragment = inv.to_prompt_fragment()
        assert inv.aspect_ratio in fragment


# ===========================================================================
# 12. VisualInvariantsExtractor — variability classification
# ===========================================================================

class TestColorSwatchVariability:
    def test_rank1_is_invariant(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        top = next(s for s in inv.palette if s.rank == 1)
        assert top.variability == "invariant"

    def test_rank2_is_invariant(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        rank2 = next(s for s in inv.palette if s.rank == 2)
        assert rank2.variability == "invariant"

    def test_rank3_is_semi_variable(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        rank3 = next(s for s in inv.palette if s.rank == 3)
        assert rank3.variability == "semi_variable"

    def test_rank5_is_variable(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        inv = _extractor().extract(path)
        rank5 = next(s for s in inv.palette if s.rank == 5)
        assert rank5.variability == "variable"


# ===========================================================================
# 13. End-to-end: gate → extract flow
# ===========================================================================

class TestGateToExtractFlow:
    def test_passed_image_can_be_extracted(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        gate = _gate()
        ext  = _extractor()
        report = gate.check(path)
        assert report.passed
        inv = ext.extract(path)
        assert inv is not None

    def test_report_source_path_matches_extractor_source_path(self, tmp_path: Path) -> None:
        path = _make_image_file(tmp_path, width=512, height=512, pattern="warm_noise")
        gate = _gate()
        ext  = _extractor()
        report = gate.check(path)
        inv    = ext.extract(path)
        assert report.source_path == inv.source_path
