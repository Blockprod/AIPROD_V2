"""
production/quality_gate_v4.py
==============================
Quality gate pour le pipeline V4 — validation des frames stylisées.

Métriques :
    SSIM inter-frames     : cohérence temporelle (cible ≥ 0.85)
    ArcFace inter-frames  : cohérence identité visage (cible ≥ 0.85)
    Luminance stability   : détection de flickering lumineux

Flag automatique si flickering détecté ou identité dégradée.
Motion_scale par shot_type pour calibrer l'espérance de variation.

Usage :
    python production/quality_gate_v4.py --shot SCN_002_SHOT_001 --stylized-dir production/stylized
    python production/quality_gate_v4.py --all --stylized-dir production/stylized
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STORYBOARD_FILE = ROOT / "production/storyboard.json"
CHAR_REFS_DIR = ROOT / "production/character_refs"
STYLIZED_DIR = ROOT / "production/stylized"
METRICS_FILE = ROOT / "production/metrics_v4.jsonl"

# Seuils de qualité
_SSIM_THRESHOLD = 0.85
_ARCFACE_THRESHOLD = 0.85
_LUMINANCE_STD_THRESHOLD = 15.0  # écart-type max de luminance entre frames consécutives

# Motion scale attendu par shot_type — les shots rapides ont plus de variation normale
_MOTION_SCALE: dict[str, float] = {
    "ultra_wide": 0.12,       # grand angle — mouvement de caméra acceptable
    "wide": 0.10,
    "wide_handheld": 0.15,    # handheld — variation plus élevée attendue
    "medium_wide": 0.08,
    "medium": 0.07,
    "close": 0.05,            # close-up — stabilité visage critique
}


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def evaluate_shot(
    shot_id: str,
    stylized_dir: Path = STYLIZED_DIR,
    char_refs_dir: Path = CHAR_REFS_DIR,
    write_metrics: bool = True,
) -> dict[str, Any]:
    """Évalue la qualité d'un shot stylisé.

    Args:
        shot_id:       Identifiant du shot.
        stylized_dir:  Racine des frames stylisées.
        char_refs_dir: Racine des références personnages.
        write_metrics: Si True, ajoute les métriques dans metrics_v4.jsonl.

    Returns:
        dict avec {"shot_id", "passed", "ssim_mean", "arcface_mean", "flickering", "issues"}.
    """
    storyboard = _load_json(STORYBOARD_FILE)
    shot = _find_shot(storyboard, shot_id)
    if shot is None:
        raise ValueError(f"Shot '{shot_id}' introuvable dans storyboard.json")

    frames_dir = stylized_dir / shot_id / "frames"
    frames = sorted(frames_dir.glob("frame_*.png")) if frames_dir.exists() else []

    shot_type = shot.get("shot_type", "medium")
    primary_char = shot.get("primary_character")
    expected_motion = _MOTION_SCALE.get(shot_type, 0.08)

    print(f"[quality_gate_v4] {shot_id}")
    print(f"  Frames         : {len(frames)}")
    print(f"  Shot type      : {shot_type}")
    print(f"  Primary char   : {primary_char or 'aucun'}")
    print(f"  Motion scale   : {expected_motion}")

    if len(frames) < 2:
        issue = f"Seulement {len(frames)} frame(s) — impossible d'évaluer la cohérence temporelle"
        print(f"  [WARN] {issue}")
        return _make_result(shot_id, passed=False, issues=[issue])

    # ── Métriques SSIM inter-frames
    ssim_scores = _compute_ssim_sequence(frames)
    ssim_mean = sum(ssim_scores) / len(ssim_scores) if ssim_scores else 0.0
    ssim_min = min(ssim_scores) if ssim_scores else 0.0
    flickering_frames = [i for i, s in enumerate(ssim_scores) if s < _SSIM_THRESHOLD]

    # ── Luminance stability
    lum_stds = _compute_luminance_stability(frames)
    lum_std_mean = sum(lum_stds) / len(lum_stds) if lum_stds else 0.0
    flickering_lum = [i for i, v in enumerate(lum_stds) if v > _LUMINANCE_STD_THRESHOLD]

    # ── ArcFace (seulement si personnage avec visage présent)
    arcface_mean = 0.0
    arcface_scores: list[float] = []
    if primary_char:
        char_ref = _resolve_char_ref(primary_char, char_refs_dir)
        if char_ref and char_ref.exists():
            arcface_scores = _compute_arcface_sequence(frames, char_ref)
            arcface_mean = sum(arcface_scores) / len(arcface_scores) if arcface_scores else 0.0

    # ── Évaluation globale
    issues: list[str] = []
    if ssim_mean < _SSIM_THRESHOLD:
        issues.append(f"SSIM moyen {ssim_mean:.4f} < {_SSIM_THRESHOLD} (flickering détecté)")
    if flickering_frames:
        issues.append(f"Frames avec SSIM < seuil : {flickering_frames[:10]}")
    if flickering_lum:
        issues.append(f"Frames avec flickering lumineux : {flickering_lum[:10]}")
    if primary_char and arcface_scores and arcface_mean < _ARCFACE_THRESHOLD:
        issues.append(f"ArcFace moyen {arcface_mean:.4f} < {_ARCFACE_THRESHOLD} (identité dégradée)")

    passed = len(issues) == 0

    result = {
        "shot_id": shot_id,
        "passed": passed,
        "shot_type": shot_type,
        "frame_count": len(frames),
        "ssim_mean": round(ssim_mean, 4),
        "ssim_min": round(ssim_min, 4),
        "ssim_threshold": _SSIM_THRESHOLD,
        "arcface_mean": round(arcface_mean, 4) if arcface_scores else None,
        "arcface_threshold": _ARCFACE_THRESHOLD if primary_char else None,
        "luminance_std_mean": round(lum_std_mean, 2),
        "luminance_std_threshold": _LUMINANCE_STD_THRESHOLD,
        "flickering_frames_ssim": len(flickering_frames),
        "flickering_frames_lum": len(flickering_lum),
        "issues": issues,
    }

    if passed:
        arcface_str = f"{arcface_mean:.4f}" if arcface_scores else "N/A"
        print(f"  [PASS] SSIM {ssim_mean:.4f} | ArcFace {arcface_str}")
    else:
        print(f"  [FAIL] {len(issues)} probleme(s)")
        for issue in issues:
            print(f"     • {issue}")

    if write_metrics:
        _append_metrics(result)

    return result


# ------------------------------------------------------------------
# Métriques internes
# ------------------------------------------------------------------

def _compute_ssim_sequence(frames: list[Path]) -> list[float]:
    """Calcule le SSIM entre chaque paire de frames consécutives."""
    try:
        import cv2
        from skimage.metrics import structural_similarity as ssim
        import numpy as np
    except ImportError:
        print("  [WARN] skimage/cv2 non disponible -- SSIM ignore")
        return []

    scores: list[float] = []
    prev_gray: Any = None

    for frame_path in frames:
        img = cv2.imread(str(frame_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        img = cv2.resize(img, (320, 180))  # réduire pour la vitesse
        if prev_gray is not None:
            score = float(ssim(prev_gray, img))
            scores.append(score)
        prev_gray = img

    return scores


def _compute_luminance_stability(frames: list[Path]) -> list[float]:
    """Calcule l'écart-type de luminance entre frames consécutives."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []

    stds: list[float] = []
    prev_lum: float | None = None

    for frame_path in frames:
        img = cv2.imread(str(frame_path))
        if img is None:
            continue
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lum = float(hsv[:, :, 2].mean())
        if prev_lum is not None:
            stds.append(abs(lum - prev_lum))
        prev_lum = lum

    return stds


def _compute_arcface_sequence(frames: list[Path], char_ref: Path) -> list[float]:
    """Calcule le score ArcFace de chaque frame vs la référence personnage."""
    try:
        import cv2
        import numpy as np
        from insightface.app import FaceAnalysis
    except ImportError:
        print("  [WARN] insightface non disponible -- ArcFace ignore")
        return []

    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))

    ref_bgr = cv2.imread(str(char_ref))
    if ref_bgr is None:
        return []
    ref_faces = app.get(ref_bgr)
    if not ref_faces:
        return []
    ref_emb = ref_faces[0].normed_embedding

    scores: list[float] = []
    for frame_path in frames[::4]:  # échantillonnage 1 frame sur 4 pour la vitesse
        img = cv2.imread(str(frame_path))
        if img is None:
            continue
        faces = app.get(img)
        if not faces:
            scores.append(0.0)
            continue
        score = float(np.dot(ref_emb, faces[0].normed_embedding))
        scores.append(score)

    return scores


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _resolve_char_ref(char_slug: str, char_refs_dir: Path) -> Path | None:
    for ext in (".png", ".jpg", ".jpeg"):
        p = char_refs_dir / f"{char_slug}_ref{ext}"
        if p.exists():
            return p
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
    with open(METRICS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_shot(storyboard: dict[str, Any], shot_id: str) -> dict[str, Any] | None:
    for shot in storyboard.get("shots", []):
        if shot["shot_id"] == shot_id:
            return shot
    return None


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Évalue la qualité des frames stylisées V4.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--shot", help="Shot ID (ex: SCN_002_SHOT_001)")
    group.add_argument("--all", action="store_true", help="Évaluer tous les shots présents")
    parser.add_argument("--stylized-dir", default=str(STYLIZED_DIR))
    parser.add_argument("--char-refs", default=str(CHAR_REFS_DIR))
    parser.add_argument("--no-write", action="store_true", help="Ne pas écrire metrics_v4.jsonl")
    args = parser.parse_args()

    stylized_dir = Path(args.stylized_dir)
    char_refs_dir = Path(args.char_refs)
    write = not args.no_write

    if args.all:
        shot_dirs = sorted(stylized_dir.iterdir()) if stylized_dir.exists() else []
        shot_ids = [d.name for d in shot_dirs if d.is_dir()]
        if not shot_ids:
            print(f"Aucun shot dans {stylized_dir}", file=sys.stderr)
            return 1
        results = []
        for shot_id in shot_ids:
            r = evaluate_shot(shot_id, stylized_dir, char_refs_dir, write_metrics=write)
            results.append(r)
        passed = sum(1 for r in results if r["passed"])
        print(f"\n{'='*60}")
        print(f"RÉSUMÉ : {passed}/{len(results)} shots valides")
        print(f"{'='*60}")
        return 0 if passed == len(results) else 1
    else:
        result = evaluate_shot(args.shot, stylized_dir, char_refs_dir, write_metrics=write)
        return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
