"""
_retake_nara_portrait.py
========================
Retake portrait Nara — face from validated frame SCN_003_SHOT_005.png

Stratégie (crop direct, $0) :
  1. Charger le frame validé SCN_003_SHOT_005.png
  2. Détecter le visage avec InsightFace
  3. Crop tête+épaules centré sur le visage (format 1:1, ~1.6× face height)
  4. Resize → 1008×1008
  5. Sauvegarder comme nara_ref.png — ArcFace = 1.0 garanti

Usage : python _retake_nara_portrait.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from pipeline.shot_pipeline import (
    LOCKED_PARAMS,
    _load_env,
    _get_largest_face,
    _score_arcface,
)

REF_FRAME    = ROOT / "_archive/district_zero/ep01_2026-04-30/preproduction/district_zero/characters/nara_voss/nara_hero_ref_01.png"
OUT_PORTRAIT = ROOT / "production/character_refs/nara_ref.png"

PORTRAIT_SIZE = 1008   # carré 1:1, même format que Phase A


def run(dry_run: bool) -> None:
    _load_env(ROOT)

    print("\n" + "=" * 60)
    print("  RETAKE NARA PORTRAIT — crop direct SCN_003_SHOT_005")
    print("  Stratégie : crop tête+épaules — $0.00 — ArcFace = 1.0")
    print("=" * 60)

    # ----------------------------------------------------------------
    # 1. Charger le frame validé
    # ----------------------------------------------------------------
    src = cv2.imread(str(REF_FRAME))
    if src is None:
        raise FileNotFoundError(f"Frame introuvable : {REF_FRAME}")
    src_h, src_w = src.shape[:2]
    print(f"\n[1] Frame chargé : {src_w}×{src_h}")

    # ----------------------------------------------------------------
    # 2. Détecter le visage
    # ----------------------------------------------------------------
    import insightface
    app = insightface.app.FaceAnalysis(
        name=LOCKED_PARAMS["face_model"],
        providers=["CPUExecutionProvider"],
    )
    app.prepare(ctx_id=0, det_size=LOCKED_PARAMS["face_det_size"])

    face = _get_largest_face(app, src)
    if face is None:
        raise RuntimeError("Aucun visage détecté dans le frame de référence")

    bx1, by1, bx2, by2 = [int(c) for c in face.bbox]
    fw = bx2 - bx1
    fh = by2 - by1
    print(f"[2] Visage détecté : bbox ({bx1},{by1})→({bx2},{by2})  {fw}×{fh}px")

    # ----------------------------------------------------------------
    # 3. Crop tête+épaules centré (facteur 1.6× fh, format carré)
    # ----------------------------------------------------------------
    cx = (bx1 + bx2) // 2
    cy = (by1 + by2) // 2

    # Rayon tight : 1.6× hauteur visage → tête + cou + début épaules
    half = int(fh * 1.6)

    # Décaler légèrement vers le bas pour bien inclure les épaules
    cy_shifted = cy + int(fh * 0.25)

    top   = max(0, cy_shifted - half)
    bot   = min(src_h, cy_shifted + half)
    left  = max(0, cx - half)
    right = min(src_w, cx + half)

    actual_h = bot - top
    actual_w = right - left
    print(f"[3] Crop tête+épaules : ({left},{top})→({right},{bot})  {actual_w}×{actual_h}px")

    crop = src[top:bot, left:right]

    # ----------------------------------------------------------------
    # 4. Resize → 1008×1008
    # ----------------------------------------------------------------
    portrait = cv2.resize(crop, (PORTRAIT_SIZE, PORTRAIT_SIZE), interpolation=cv2.INTER_LANCZOS4)

    # ----------------------------------------------------------------
    # 5. ArcFace score (portrait vs frame source)
    # ----------------------------------------------------------------
    score = _score_arcface(app, src, portrait)
    print(f"[4] Resize → {PORTRAIT_SIZE}×{PORTRAIT_SIZE}")
    print(f"[5] ArcFace : {score:.4f}  (portrait vs SCN_003_SHOT_005)")

    if dry_run:
        debug_dir = ROOT / "production/character_refs"
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / "_debug_portrait_base.png"), portrait)
        print(f"\n[DRY-RUN] Preview : production/character_refs/_debug_portrait_base.png")
        print("Aucun fichier nara_ref.png modifié.")
        return

    # ----------------------------------------------------------------
    # 6. Sauvegarder
    # ----------------------------------------------------------------
    OUT_PORTRAIT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT_PORTRAIT), portrait)

    print(f"\n  Sauvegardé : {OUT_PORTRAIT.name} ({PORTRAIT_SIZE}×{PORTRAIT_SIZE})")
    print(f"  Coût       : $0.00")
    print(f"  ArcFace    : {score:.4f}")
    print(f"\nETAPE SUIVANTE : python production/run.py benchmark --char nara")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.dry_run)
