"""
pipeline/tests/test_v4_pipeline.py
===================================
Tests unitaires — Pipeline V4 (Semaines 3–6)

Couvre :
    V4-01  NullStylizationBackend — retourne les bytes source
    V4-02  _build_stylization_prompt — tous shot_types
    V4-03  _find_shot — trouvé / introuvable
    V4-04  _exr_depth_to_png — fallback sans cv2
    V4-05  stylize_shot dry-run — 0 appel API
    V4-06  stylize_shot null backend — skip si out_path existe
    V4-07  frames_to_clip — dry-run (pas de FFmpeg)
    V4-08  process_shot — dry-run
    V4-09  concat_clips — vide → ValueError
    V4-10  assemble_episode — dry-run, ordre storyboard correct
    V4-11  evaluate_shot — 0 frames → passed=False
    V4-12  evaluate_shot — SSIM mock pass/fail
    V4-13  gen_shots_v4 run_all — dry-run budget tracking
    V4-14  _resolve_clip — priorité _final > standard
    V4-15  _load_checkpoint / _save_checkpoint — round-trip JSON
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# ── imports des modules V4
from pipeline.shot_pipeline_v4 import (
    NullStylizationBackend,
    _build_stylization_prompt,
    _exr_depth_to_png,
    _find_shot,
    stylize_shot,
)
from pipeline.video_pipeline import (
    concat_clips,
    frames_to_clip,
    process_shot,
)
from pipeline.assembly import (
    _resolve_clip,
    assemble_episode,
)
from production.quality_gate_v4 import (
    _make_result,
    evaluate_shot,
)
from production.gen_shots_v4 import (
    _load_checkpoint,
    _save_checkpoint,
    run_all,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def minimal_storyboard(tmp_path: Path) -> Path:
    """Storyboard minimal avec 2 shots."""
    data = {
        "title": "Test EP",
        "total_shots": 2,
        "shots": [
            {
                "shot_id": "SCN_001_SHOT_001",
                "shot_type": "wide",
                "duration_sec": 5,
                "primary_character": "nara",
                "action_brief": "Nara runs through corridor.",
                "lighting_context": "Neon backlighting.",
                "emotion_intent": "Tension.",
                "material_state": "Wet asphalt.",
                "camera_spec": "ARRI Alexa 35",
            },
            {
                "shot_id": "SCN_001_SHOT_002",
                "shot_type": "close",
                "duration_sec": 3,
                "primary_character": None,
                "action_brief": "Lock mechanism activates.",
                "lighting_context": "Red ambient.",
                "emotion_intent": "Dread.",
                "material_state": "Rusted metal.",
                "camera_spec": "ARRI Alexa 35",
            },
        ],
    }
    p = tmp_path / "storyboard.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture()
def frames_dir(tmp_path: Path) -> Path:
    """Crée 5 frames PNG factices (1×1 pixel PNG valide)."""
    d = tmp_path / "frames"
    d.mkdir()
    # 1×1 pixel PNG minimal (67 bytes)
    _PIXEL_PNG = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
        b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    for i in range(5):
        (d / f"frame_{i:04d}.png").write_bytes(_PIXEL_PNG)
    return d


# ---------------------------------------------------------------------------
# V4-01  NullStylizationBackend
# ---------------------------------------------------------------------------

class TestNullStylizationBackend:
    def test_returns_source_bytes(self, tmp_path: Path) -> None:
        """Le backend null retourne les bytes de la frame source inchangés."""
        frame = tmp_path / "frame_0000.png"
        frame.write_bytes(b"fake_png_bytes")

        backend = NullStylizationBackend()
        result = backend.stylize_frame(
            frame_png=frame,
            depth_exr=frame,
            char_ref_png=frame,
            prompt="test",
            seed=42,
            shot_type="wide",
        )
        assert result == b"fake_png_bytes"

    def test_cost_zero(self) -> None:
        assert NullStylizationBackend().cost_per_frame == 0.0

    def test_name(self) -> None:
        assert NullStylizationBackend().name == "null"


# ---------------------------------------------------------------------------
# V4-02  _build_stylization_prompt
# ---------------------------------------------------------------------------

class TestBuildStylizationPrompt:
    _STORYBOARD = {"shots": []}  # non utilisé par la fonction

    def _make_shot(self, shot_type: str) -> dict:
        return {
            "shot_type": shot_type,
            "action_brief": "Action.",
            "lighting_context": "Dark.",
            "emotion_intent": "Fear.",
            "material_state": "Wet.",
            "camera_spec": "ARRI Alexa 35",
        }

    @pytest.mark.parametrize(
        "shot_type,expected_label",
        [
            ("ultra_wide", "Ultra-wide establishing shot"),
            ("wide", "Wide shot"),
            ("wide_handheld", "Wide handheld shot"),
            ("medium_wide", "Medium-wide shot"),
            ("medium", "Medium shot"),
            ("close", "Close-up shot"),
            ("unknown_type", "Shot"),
        ],
    )
    def test_shot_type_label(self, shot_type: str, expected_label: str) -> None:
        prompt = _build_stylization_prompt(self._make_shot(shot_type), self._STORYBOARD)
        assert prompt.startswith(expected_label)

    def test_contains_action_and_camera(self) -> None:
        shot = self._make_shot("medium")
        prompt = _build_stylization_prompt(shot, self._STORYBOARD)
        assert "Action." in prompt
        assert "ARRI Alexa 35" in prompt
        assert "No AI artefacts" in prompt


# ---------------------------------------------------------------------------
# V4-03  _find_shot
# ---------------------------------------------------------------------------

class TestFindShot:
    def test_found(self) -> None:
        storyboard = {
            "shots": [
                {"shot_id": "SCN_001_SHOT_001"},
                {"shot_id": "SCN_001_SHOT_002"},
            ]
        }
        result = _find_shot(storyboard, "SCN_001_SHOT_002")
        assert result is not None
        assert result["shot_id"] == "SCN_001_SHOT_002"

    def test_not_found(self) -> None:
        storyboard = {"shots": [{"shot_id": "SCN_001_SHOT_001"}]}
        assert _find_shot(storyboard, "SCN_999_SHOT_001") is None

    def test_empty_storyboard(self) -> None:
        assert _find_shot({}, "SCN_001_SHOT_001") is None


# ---------------------------------------------------------------------------
# V4-04  _exr_depth_to_png fallback
# ---------------------------------------------------------------------------

class TestExrDepthToPng:
    def test_fallback_without_cv2(self, tmp_path: Path) -> None:
        """Sans cv2 disponible, retourne les bytes bruts du fichier."""
        fake_exr = tmp_path / "depth_0000.exr"
        fake_exr.write_bytes(b"fake_exr_data")

        with patch.dict("sys.modules", {"cv2": None}):
            result = _exr_depth_to_png(fake_exr)

        assert result == b"fake_exr_data"


# ---------------------------------------------------------------------------
# V4-05  stylize_shot dry-run
# ---------------------------------------------------------------------------

class TestStylizeShotDryRun:
    def test_dry_run_no_api_call(self, tmp_path: Path, minimal_storyboard: Path) -> None:
        """dry_run=True doit retourner frames_stylized=0 sans appel API."""
        backend = NullStylizationBackend()

        with patch(
            "pipeline.shot_pipeline_v4.STORYBOARD_FILE", minimal_storyboard
        ), patch(
            "pipeline.shot_pipeline_v4.ANIMATIONS_FILE",
            minimal_storyboard.parent / "anims.json",
        ):
            # Créer un fichier d'animations minimal
            anims = {"shots": {}}
            (minimal_storyboard.parent / "anims.json").write_text(
                json.dumps(anims), encoding="utf-8"
            )

            result = stylize_shot(
                shot_id="SCN_001_SHOT_001",
                backend=backend,
                renders_dir=tmp_path / "renders",
                char_refs_dir=tmp_path / "char_refs",
                out_dir=tmp_path / "stylized",
                dry_run=True,
            )

        assert result["frames_stylized"] == 0
        assert result["cost_usd"] == 0.0

    def test_wrong_shot_id_raises(self, tmp_path: Path, minimal_storyboard: Path) -> None:
        backend = NullStylizationBackend()
        anims = {"shots": {}}
        anims_file = tmp_path / "anims.json"
        anims_file.write_text(json.dumps(anims), encoding="utf-8")

        with patch("pipeline.shot_pipeline_v4.STORYBOARD_FILE", minimal_storyboard), patch(
            "pipeline.shot_pipeline_v4.ANIMATIONS_FILE", anims_file
        ):
            with pytest.raises(ValueError, match="introuvable"):
                stylize_shot(
                    shot_id="SCN_999_SHOT_001",
                    backend=backend,
                    renders_dir=tmp_path / "renders",
                    char_refs_dir=tmp_path / "char_refs",
                    out_dir=tmp_path / "stylized",
                    dry_run=True,
                )


# ---------------------------------------------------------------------------
# V4-06  stylize_shot null backend — skip si out_path existe
# ---------------------------------------------------------------------------

class TestStylizeShotSkip:
    def test_skips_existing_output(self, tmp_path: Path, minimal_storyboard: Path, frames_dir: Path) -> None:
        """Les frames déjà stylisées ne sont pas retraitées."""
        backend = NullStylizationBackend()
        anims = {"shots": {"SCN_001_SHOT_001": {"camera": {"fov_mm": 32}}}}
        anims_file = tmp_path / "anims.json"
        anims_file.write_text(json.dumps(anims), encoding="utf-8")

        renders_dir = tmp_path / "renders"
        shot_frames = renders_dir / "SCN_001_SHOT_001" / "frames"
        shot_frames.mkdir(parents=True)
        for frame in frames_dir.iterdir():
            (shot_frames / frame.name).write_bytes(frame.read_bytes())

        # Pré-créer les outputs → ils doivent être skippés
        out_dir = tmp_path / "stylized"
        out_shot = out_dir / "SCN_001_SHOT_001" / "frames"
        out_shot.mkdir(parents=True)
        for frame in shot_frames.iterdir():
            (out_shot / frame.name).write_bytes(b"already_stylized")

        with patch("pipeline.shot_pipeline_v4.STORYBOARD_FILE", minimal_storyboard), patch(
            "pipeline.shot_pipeline_v4.ANIMATIONS_FILE", anims_file
        ):
            result = stylize_shot(
                shot_id="SCN_001_SHOT_001",
                backend=backend,
                renders_dir=renders_dir,
                char_refs_dir=tmp_path / "char_refs",
                out_dir=out_dir,
                dry_run=False,
            )

        assert result["frames_stylized"] == 5
        # Vérifier que les outputs existants ne sont pas écrasés
        for f in out_shot.iterdir():
            assert f.read_bytes() == b"already_stylized"


# ---------------------------------------------------------------------------
# V4-07  frames_to_clip dry-run (pas de FFmpeg)
# ---------------------------------------------------------------------------

class TestFramesToClip:
    def test_no_frames_raises(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            frames_to_clip(empty_dir)

    def test_calls_ffmpeg(self, tmp_path: Path, frames_dir: Path) -> None:
        """Vérifie que FFmpeg est appelé avec les bons arguments."""
        out_path = tmp_path / "clip.mp4"
        with patch("pipeline.video_pipeline._run") as mock_run:
            frames_to_clip(frames_dir, fps=24, out_path=out_path, ffmpeg_exe="ffmpeg")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "ffmpeg" in cmd
        assert "-framerate" in cmd
        assert "24" in cmd


# ---------------------------------------------------------------------------
# V4-08  process_shot dry-run
# ---------------------------------------------------------------------------

class TestProcessShot:
    def test_dry_run_returns_clip_path(self, tmp_path: Path, frames_dir: Path) -> None:
        stylized_dir = tmp_path / "stylized"
        shot_id = "SCN_001_SHOT_001"
        (stylized_dir / shot_id / "frames").mkdir(parents=True)

        result = process_shot(
            shot_id=shot_id,
            stylized_dir=stylized_dir,
            clips_dir=tmp_path / "clips",
            dry_run=True,
        )
        assert result["shot_id"] == shot_id
        assert result["clip_path"].endswith(".mp4")
        assert result["has_audio"] is False

    def test_no_frames_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            process_shot(
                shot_id="SCN_001_SHOT_001",
                stylized_dir=tmp_path / "empty",
                clips_dir=tmp_path / "clips",
                dry_run=False,
            )


# ---------------------------------------------------------------------------
# V4-09  concat_clips — vide → ValueError
# ---------------------------------------------------------------------------

class TestConcatClips:
    def test_empty_list_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="vide"):
            concat_clips([], out_path=tmp_path / "out.mp4")

    def test_calls_ffmpeg(self, tmp_path: Path) -> None:
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"fake")
        out_path = tmp_path / "out.mp4"
        with patch("pipeline.video_pipeline._run") as mock_run:
            concat_clips([clip], out_path=out_path, ffmpeg_exe="ffmpeg")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-f" in cmd
        assert "concat" in cmd


# ---------------------------------------------------------------------------
# V4-10  assemble_episode dry-run
# ---------------------------------------------------------------------------

class TestAssembleEpisode:
    def test_dry_run_lists_35_shots(self, tmp_path: Path) -> None:
        """dry_run doit lire le vrai storyboard et lister 35 shots."""
        result = assemble_episode(
            clips_dir=tmp_path / "clips",
            out_path=tmp_path / "ep01.mp4",
            dry_run=True,
        )
        assert result["shots_assembled"] == 0  # aucun clip dispo
        assert len(result["missing_clips"]) == 35
        assert result["duration_s_estimate"] > 0

    def test_dry_run_with_clips(self, tmp_path: Path) -> None:
        """Quand des clips existent, ils sont inclus dans shots_assembled."""
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        (clips_dir / "SCN_001_SHOT_001.mp4").write_bytes(b"fake")
        (clips_dir / "SCN_001_SHOT_002.mp4").write_bytes(b"fake")

        result = assemble_episode(
            clips_dir=clips_dir,
            out_path=tmp_path / "ep01.mp4",
            dry_run=True,
        )
        assert result["shots_assembled"] == 2
        assert len(result["missing_clips"]) == 33

    def test_resolve_clip_prefers_final(self, tmp_path: Path) -> None:
        """_resolve_clip préfère le clip _final au clip standard."""
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        (clips_dir / "SCN_001_SHOT_001.mp4").write_bytes(b"standard")
        (clips_dir / "SCN_001_SHOT_001_final.mp4").write_bytes(b"final")

        resolved = _resolve_clip(clips_dir, "SCN_001_SHOT_001")
        assert resolved is not None
        assert resolved.read_bytes() == b"final"


# ---------------------------------------------------------------------------
# V4-11  evaluate_shot — 0 frames → passed=False
# ---------------------------------------------------------------------------

class TestEvaluateShot:
    def test_no_frames_fails(self, tmp_path: Path, minimal_storyboard: Path) -> None:
        with patch(
            "production.quality_gate_v4.STORYBOARD_FILE", minimal_storyboard
        ):
            result = evaluate_shot(
                shot_id="SCN_001_SHOT_001",
                stylized_dir=tmp_path / "empty",
                write_metrics=False,
            )
        assert result["passed"] is False
        assert result["frame_count"] == 0
        assert len(result["issues"]) > 0

    def test_wrong_shot_id_raises(self, tmp_path: Path, minimal_storyboard: Path) -> None:
        with patch("production.quality_gate_v4.STORYBOARD_FILE", minimal_storyboard):
            with pytest.raises(ValueError, match="introuvable"):
                evaluate_shot(
                    shot_id="SCN_999_SHOT_001",
                    stylized_dir=tmp_path,
                    write_metrics=False,
                )


# ---------------------------------------------------------------------------
# V4-12  evaluate_shot — SSIM mock pass/fail
# ---------------------------------------------------------------------------

class TestEvaluateShotSSIM:
    def _make_stylized_frames(self, tmp_path: Path, shot_id: str, n: int = 5) -> None:
        d = tmp_path / shot_id / "frames"
        d.mkdir(parents=True)
        _PIXEL_PNG = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        for i in range(n):
            (d / f"frame_{i:04d}.png").write_bytes(_PIXEL_PNG)

    def test_ssim_above_threshold_passes(self, tmp_path: Path, minimal_storyboard: Path) -> None:
        """Avec SSIM mock = 0.95 → passed=True."""
        self._make_stylized_frames(tmp_path, "SCN_001_SHOT_001")
        with patch("production.quality_gate_v4.STORYBOARD_FILE", minimal_storyboard), patch(
            "production.quality_gate_v4._compute_ssim_sequence", return_value=[0.95, 0.96, 0.94, 0.97]
        ), patch(
            "production.quality_gate_v4._compute_luminance_stability", return_value=[2.0, 3.0, 1.5, 2.5]
        ), patch(
            "production.quality_gate_v4._compute_arcface_sequence", return_value=[]
        ):
            result = evaluate_shot(
                shot_id="SCN_001_SHOT_001",
                stylized_dir=tmp_path,
                write_metrics=False,
            )
        assert result["passed"] is True
        assert result["ssim_mean"] >= 0.85

    def test_ssim_below_threshold_fails(self, tmp_path: Path, minimal_storyboard: Path) -> None:
        """Avec SSIM mock = 0.60 → passed=False (flickering détecté)."""
        self._make_stylized_frames(tmp_path, "SCN_001_SHOT_001")
        with patch("production.quality_gate_v4.STORYBOARD_FILE", minimal_storyboard), patch(
            "production.quality_gate_v4._compute_ssim_sequence", return_value=[0.60, 0.62, 0.58, 0.65]
        ), patch(
            "production.quality_gate_v4._compute_luminance_stability", return_value=[2.0, 2.0, 2.0, 2.0]
        ), patch(
            "production.quality_gate_v4._compute_arcface_sequence", return_value=[]
        ):
            result = evaluate_shot(
                shot_id="SCN_001_SHOT_001",
                stylized_dir=tmp_path,
                write_metrics=False,
            )
        assert result["passed"] is False
        assert any("SSIM" in issue for issue in result["issues"])


# ---------------------------------------------------------------------------
# V4-13  gen_shots_v4 run_all — dry-run budget tracking
# ---------------------------------------------------------------------------

class TestRunAll:
    def test_dry_run_zero_cost(self, tmp_path: Path) -> None:
        """dry_run ne comptabilise aucun coût."""
        with patch("production.gen_shots_v4.CHECKPOINT_FILE", tmp_path / "checkpoint.json"), patch(
            "production.gen_shots_v4.METRICS_FILE", tmp_path / "metrics.jsonl"
        ), patch("production.gen_shots_v4._run_step", return_value=(True, "ok")):
            result = run_all(
                shot_ids=["SCN_001_SHOT_001"],
                backend="null",
                dry_run=True,
            )
        assert result["total_cost_usd"] == 0.0
        assert result["budget_ok"] is True

    def test_dry_run_does_not_write_checkpoint(self, tmp_path: Path) -> None:
        """dry_run ne doit pas écrire dans le checkpoint."""
        checkpoint_file = tmp_path / "checkpoint.json"
        with patch("production.gen_shots_v4.CHECKPOINT_FILE", checkpoint_file), patch(
            "production.gen_shots_v4.METRICS_FILE", tmp_path / "metrics.jsonl"
        ), patch("production.gen_shots_v4._run_step", return_value=(True, "ok")):
            run_all(
                shot_ids=["SCN_001_SHOT_001"],
                backend="null",
                dry_run=True,
            )
        assert not checkpoint_file.exists()


# ---------------------------------------------------------------------------
# V4-14  _resolve_clip
# ---------------------------------------------------------------------------

class TestResolveClip:
    def test_returns_none_when_absent(self, tmp_path: Path) -> None:
        assert _resolve_clip(tmp_path, "SCN_001_SHOT_001") is None

    def test_standard_clip(self, tmp_path: Path) -> None:
        (tmp_path / "SCN_001_SHOT_001.mp4").write_bytes(b"x")
        resolved = _resolve_clip(tmp_path, "SCN_001_SHOT_001")
        assert resolved is not None
        assert resolved.name == "SCN_001_SHOT_001.mp4"

    def test_final_takes_priority_over_standard(self, tmp_path: Path) -> None:
        (tmp_path / "SCN_001_SHOT_001.mp4").write_bytes(b"standard")
        (tmp_path / "SCN_001_SHOT_001_final.mp4").write_bytes(b"final")
        resolved = _resolve_clip(tmp_path, "SCN_001_SHOT_001")
        assert resolved is not None
        assert "_final" in resolved.name


# ---------------------------------------------------------------------------
# V4-15  _load_checkpoint / _save_checkpoint
# ---------------------------------------------------------------------------

class TestCheckpoint:
    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        checkpoint_file = tmp_path / "checkpoint.json"
        data = {"processed": ["SCN_001_SHOT_001"], "total_cost_usd": 1.23}

        with patch("production.gen_shots_v4.CHECKPOINT_FILE", checkpoint_file):
            _save_checkpoint(data)
            loaded = _load_checkpoint()

        assert loaded["processed"] == ["SCN_001_SHOT_001"]
        assert loaded["total_cost_usd"] == 1.23

    def test_load_returns_defaults_when_absent(self, tmp_path: Path) -> None:
        with patch(
            "production.gen_shots_v4.CHECKPOINT_FILE", tmp_path / "nonexistent.json"
        ):
            loaded = _load_checkpoint()
        assert loaded["processed"] == []
        assert loaded["total_cost_usd"] == 0.0

    def test_load_recovers_from_corrupt_json(self, tmp_path: Path) -> None:
        checkpoint_file = tmp_path / "checkpoint.json"
        checkpoint_file.write_text("{corrupt json", encoding="utf-8")
        with patch("production.gen_shots_v4.CHECKPOINT_FILE", checkpoint_file):
            loaded = _load_checkpoint()
        assert loaded == {"processed": [], "total_cost_usd": 0.0}
