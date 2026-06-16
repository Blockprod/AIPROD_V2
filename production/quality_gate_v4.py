"""Fail-closed quality gate for V4 stylized frames."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STORYBOARD_FILE = ROOT / "production/storyboard.json"
CHAR_REFS_DIR = ROOT / "production/character_refs"
STYLIZED_DIR = ROOT / "production/stylized"
METRICS_FILE = ROOT / "production/metrics_v4.jsonl"

_SSIM_THRESHOLD = 0.85
_ARCFACE_THRESHOLD = 0.85
_ARCFACE_P10_THRESHOLD = 0.75
_FACE_COVERAGE_THRESHOLD = 0.80
_LUMINANCE_DELTA_THRESHOLD = 15.0
_MOTION_SCALE: dict[str, float] = {
    "ultra_wide": 0.12,
    "wide": 0.10,
    "wide_handheld": 0.15,
    "medium_wide": 0.08,
    "medium": 0.07,
    "close": 0.05,
}


class MetricUnavailableError(RuntimeError):
    """A mandatory metric could not be computed."""


def evaluate_shot(
    shot_id: str,
    stylized_dir: Path = STYLIZED_DIR,
    char_refs_dir: Path = CHAR_REFS_DIR,
    write_metrics: bool = True,
) -> dict[str, Any]:
    storyboard = _load_json(STORYBOARD_FILE)
    shot = _find_shot(storyboard, shot_id)
    if shot is None:
        raise ValueError(f"Shot '{shot_id}' introuvable dans storyboard.json")

    frames_dir = stylized_dir / shot_id / "frames"
    frames = sorted(frames_dir.glob("frame_*.png")) if frames_dir.exists() else []
    shot_type = str(shot.get("shot_type", "medium"))
    primary_char = shot.get("primary_character")
    ssim_threshold = _ssim_threshold_for_shot(shot_type)

    print(f"[quality_gate_v4] {shot_id}")
    print(f"  Frames         : {len(frames)}")
    print(f"  Shot type      : {shot_type}")
    print(f"  Primary char   : {primary_char or 'none'}")

    if len(frames) < 2:
        issue = f"Seulement {len(frames)} frame(s): coherence temporelle impossible"
        result = _make_result(shot_id, passed=False, issues=[issue])
        if write_metrics:
            _append_metrics(result)
        return result

    issues: list[str] = []
    try:
        ssim_scores = _compute_ssim_sequence(frames)
    except MetricUnavailableError as exc:
        ssim_scores = []
        issues.append(str(exc))
    if not ssim_scores:
        issues.append("SSIM obligatoire indisponible ou aucune paire valide")
    ssim_mean = sum(ssim_scores) / len(ssim_scores) if ssim_scores else 0.0
    ssim_min = min(ssim_scores) if ssim_scores else 0.0
    low_ssim = [index for index, score in enumerate(ssim_scores) if score < ssim_threshold]
    if ssim_scores and ssim_mean < ssim_threshold:
        issues.append(f"SSIM moyen {ssim_mean:.4f} < {ssim_threshold}")

    try:
        luminance_deltas = _compute_luminance_stability(frames)
    except MetricUnavailableError as exc:
        luminance_deltas = []
        issues.append(str(exc))
    if not luminance_deltas:
        issues.append("Mesure de luminance obligatoire indisponible")
    luminance_delta_mean = (
        sum(luminance_deltas) / len(luminance_deltas) if luminance_deltas else 0.0
    )
    luminance_failures = [
        index
        for index, value in enumerate(luminance_deltas)
        if value > _LUMINANCE_DELTA_THRESHOLD
    ]
    if luminance_failures:
        issues.append(f"Flickering lumineux sur paires {luminance_failures[:10]}")

    arcface_scores: list[float | None] = []
    arcface_mean = 0.0
    arcface_p10 = 0.0
    face_coverage = 0.0
    if primary_char:
        char_ref = _resolve_char_ref(str(primary_char), char_refs_dir)
        if char_ref is None:
            issues.append(f"Reference personnage obligatoire absente: {primary_char}")
        else:
            try:
                arcface_scores = _compute_arcface_sequence(frames, char_ref)
            except MetricUnavailableError as exc:
                issues.append(str(exc))
        valid_scores = [score for score in arcface_scores if score is not None]
        expected_samples = max(1, math.ceil(len(frames) / 4))
        face_coverage = len(valid_scores) / expected_samples
        if not valid_scores:
            issues.append("ArcFace obligatoire: aucun visage/embedding exploitable")
        else:
            arcface_mean = sum(valid_scores) / len(valid_scores)
            ordered = sorted(valid_scores)
            p10_index = max(0, math.ceil(0.10 * len(ordered)) - 1)
            arcface_p10 = ordered[p10_index]
            if arcface_mean < _ARCFACE_THRESHOLD:
                issues.append(f"ArcFace moyen {arcface_mean:.4f} < {_ARCFACE_THRESHOLD}")
            if arcface_p10 < _ARCFACE_P10_THRESHOLD:
                issues.append(f"ArcFace percentile 10 {arcface_p10:.4f} < {_ARCFACE_P10_THRESHOLD}")
            if face_coverage < _FACE_COVERAGE_THRESHOLD:
                issues.append(f"Couverture visage {face_coverage:.1%} < {_FACE_COVERAGE_THRESHOLD:.0%}")

    valid_scores = [score for score in arcface_scores if score is not None]
    result: dict[str, Any] = {
        "shot_id": shot_id,
        "passed": not issues,
        "shot_type": shot_type,
        "frame_count": len(frames),
        "ssim_mean": round(ssim_mean, 4),
        "ssim_min": round(ssim_min, 4),
        "ssim_threshold": ssim_threshold,
        "arcface_mean": round(arcface_mean, 4) if valid_scores else None,
        "arcface_p10": round(arcface_p10, 4) if valid_scores else None,
        "arcface_threshold": _ARCFACE_THRESHOLD if primary_char else None,
        "face_coverage": round(face_coverage, 4) if primary_char else None,
        "luminance_mean_delta": round(luminance_delta_mean, 2),
        "luminance_delta_threshold": _LUMINANCE_DELTA_THRESHOLD,
        "flickering_frames_ssim": len(low_ssim),
        "flickering_frames_lum": len(luminance_failures),
        "issues": issues,
    }
    if write_metrics:
        _append_metrics(result)
    return result


def _ssim_threshold_for_shot(shot_type: str) -> float:
    expected_motion = _MOTION_SCALE.get(shot_type, 0.08)
    return round(max(0.72, _SSIM_THRESHOLD - expected_motion * 0.5), 3)


def _compute_ssim_sequence(frames: list[Path]) -> list[float]:
    try:
        import cv2
        import numpy as np
        from skimage.metrics import structural_similarity as ssim
    except ImportError as exc:
        raise MetricUnavailableError("Dependance SSIM obligatoire absente (opencv/skimage)") from exc

    scores: list[float] = []
    previous: Any = None
    for frame_path in frames:
        current = cv2.imread(str(frame_path), cv2.IMREAD_GRAYSCALE)
        if current is None:
            continue
        current = cv2.resize(current, (320, 180))
        if previous is not None:
            shift, _ = cv2.phaseCorrelate(
                previous.astype(np.float32), current.astype(np.float32)
            )
            transform = np.float32([[1, 0, shift[0]], [0, 1, shift[1]]])
            aligned = cv2.warpAffine(previous, transform, (current.shape[1], current.shape[0]))
            margin_x = min(24, int(abs(shift[0])) + 2)
            margin_y = min(16, int(abs(shift[1])) + 2)
            if margin_x * 2 < current.shape[1] and margin_y * 2 < current.shape[0]:
                aligned = aligned[margin_y:-margin_y, margin_x:-margin_x]
                comparable = current[margin_y:-margin_y, margin_x:-margin_x]
            else:
                comparable = current
            scores.append(float(ssim(aligned, comparable)))
        previous = current
    return scores


def _compute_luminance_stability(frames: list[Path]) -> list[float]:
    try:
        import cv2
    except ImportError as exc:
        raise MetricUnavailableError("Dependance luminance obligatoire absente (opencv)") from exc

    deltas: list[float] = []
    previous_mean: float | None = None
    for frame_path in frames:
        image = cv2.imread(str(frame_path))
        if image is None:
            continue
        value = float(cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 2].mean())
        if previous_mean is not None:
            deltas.append(abs(value - previous_mean))
        previous_mean = value
    return deltas


def _compute_arcface_sequence(frames: list[Path], char_ref: Path) -> list[float | None]:
    try:
        import cv2
        import numpy as np
        from insightface.app import FaceAnalysis
    except ImportError as exc:
        raise MetricUnavailableError("Dependance ArcFace obligatoire absente (insightface)") from exc

    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    reference = cv2.imread(str(char_ref))
    if reference is None:
        raise MetricUnavailableError(f"Reference personnage illisible: {char_ref}")
    reference_faces = app.get(reference)
    if not reference_faces:
        raise MetricUnavailableError(f"Aucun visage detecte dans la reference: {char_ref}")
    reference_face = max(
        reference_faces, key=lambda face: float(getattr(face, "det_score", 0.0))
    )
    reference_embedding = reference_face.normed_embedding

    scores: list[float | None] = []
    for frame_path in frames[::4]:
        image = cv2.imread(str(frame_path))
        if image is None:
            scores.append(None)
            continue
        faces = app.get(image)
        if not faces:
            scores.append(None)
            continue
        scores.append(
            max(float(np.dot(reference_embedding, face.normed_embedding)) for face in faces)
        )
    return scores


def _resolve_char_ref(char_slug: str, char_refs_dir: Path) -> Path | None:
    for extension in (".png", ".jpg", ".jpeg"):
        candidate = char_refs_dir / f"{char_slug}_ref{extension}"
        if candidate.exists():
            return candidate
    return None


def _make_result(shot_id: str, passed: bool, issues: list[str]) -> dict[str, Any]:
    return {
        "shot_id": shot_id,
        "passed": passed,
        "issues": issues,
        "ssim_mean": 0.0,
        "ssim_min": 0.0,
        "arcface_mean": None,
        "frame_count": 0,
    }


def _append_metrics(result: dict[str, Any]) -> None:
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with METRICS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False) + "\n")


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _find_shot(storyboard: dict[str, Any], shot_id: str) -> dict[str, Any] | None:
    for shot in storyboard.get("shots", []):
        if isinstance(shot, dict) and shot.get("shot_id") == shot_id:
            return shot
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate V4 stylized frames.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--shot")
    group.add_argument("--all", action="store_true")
    parser.add_argument("--stylized-dir", default=str(STYLIZED_DIR))
    parser.add_argument("--char-refs", default=str(CHAR_REFS_DIR))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    stylized_dir = Path(args.stylized_dir)
    char_refs_dir = Path(args.char_refs)
    if args.all:
        shot_ids = (
            [path.name for path in sorted(stylized_dir.iterdir()) if path.is_dir()]
            if stylized_dir.exists()
            else []
        )
        if not shot_ids:
            return 1
        results = [
            evaluate_shot(shot_id, stylized_dir, char_refs_dir, not args.no_write)
            for shot_id in shot_ids
        ]
        return 0 if all(result["passed"] for result in results) else 1
    result = evaluate_shot(args.shot, stylized_dir, char_refs_dir, not args.no_write)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
