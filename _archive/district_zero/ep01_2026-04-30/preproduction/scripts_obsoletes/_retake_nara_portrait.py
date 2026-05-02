"""
_retake_nara_portrait.py
========================
Retake portrait Nara — Flux Fill Pro v5 — inpainting fond uniquement

Stratégie (fidélité faciale 100%, ~$0.05) :
  1. Charger nara_hero_ref_01.png (image de référence canonique)
  2. Détecter le visage avec InsightFace
  3. Crop serré tête+épaules (2.5× fh, 1:1) centré sur le visage
     → on travaille sur un crop isolé : le personnage occupe 80%+ du cadre
  4. Sur ce crop : masque avec GRANDE ellipse de préservation (buste entier)
     → corps/visage = noir (préservé), seul le fond périphérique = blanc (inpainté)
     → AUCUNE place pour un deuxième personnage
  5. Flux Fill Pro v5 inpainte uniquement le fond
  6. Resize → 1008×1008 → nara_ref.png

Coût : ~$0.05

Usage : python _retake_nara_portrait.py [--dry-run]
"""
from __future__ import annotations

import argparse
import base64
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.shot_pipeline import (
    LOCKED_PARAMS,
    LOCKED_NARA_CANONICAL,
    _load_env,
    _get_largest_face,
    _score_arcface,
    _remove_watermark,
)

REF_FRAME    = ROOT / "_archive/district_zero/ep01_2026-04-30/preproduction/district_zero/characters/nara_voss/nara_hero_ref_01.png"
OUT_PORTRAIT = ROOT / "production/character_refs/nara_ref.png"

MODEL_P2      = "black-forest-labs/flux-fill-pro"
COST_P2       = 0.05
PORTRAIT_SIZE = 1008   # carré 1:1

# Prompt portrait neutre — fond studio sombre, aucune scène spécifique
PORTRAIT_PROMPT = (
    "Character reference portrait for a dystopian TV series. "
    + LOCKED_NARA_CANONICAL
    + " "
    "Dark neutral studio background, soft directional key light from upper-left, "
    "cool blue-grey ambient fill, slight rim light. "
    "Tight shoulders-to-crown framing, face perfectly sharp, natural skin detail. "
    "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 800, "
    "desaturated teal-steel colour grade, organic film grain, "
    "no HDR clipping, no AI artefact, solo figure only."
)

# Facteur de crop serré autour du visage (en unités de face-height)
# 2.5 → tête + cou + épaules ; contraint à l'espace disponible pour produire un vrai carré
CROP_HALF_FACTOR  = 2.5
# Décalage vertical vers le bas pour inclure les épaules
CROP_SHIFT_FACTOR = 0.25
# Ellipse de préservation sur le crop : couvre buste complet
# Grand facteur → ne laisse que le fond périphérique à inpainter
BUST_PRESERVE_EXPAND = 2.20


def _img_to_b64(img_bgr: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", img_bgr)
    if not ok:
        raise RuntimeError("imencode failed")
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def _remove_all_watermarks(img_bgr: np.ndarray) -> np.ndarray:
    """Supprime les watermarks/textes hallucinés en haut ET en bas de l'image.

    Flux Fill Pro peut générer du texte dans les 8% supérieurs et 10% inférieurs.
    On inpainte ces deux bandes horizontales complètes.
    """
    h, w = img_bgr.shape[:2]
    wm = np.zeros((h, w), dtype=np.uint8)
    # Bande supérieure (titre/texte en haut)
    wm[0:int(h * 0.08), :] = 255
    # Bande inférieure (légende/watermark en bas)
    wm[int(h * 0.90):h, :] = 255
    return cv2.inpaint(img_bgr, wm, inpaintRadius=8, flags=cv2.INPAINT_TELEA)


def _build_inverted_face_mask(h: int, w: int, bbox, expand: float = BUST_PRESERVE_EXPAND) -> np.ndarray:
    """Masque INVERSÉ sur un crop serré : buste entier = noir (préservé), fond périphérique = blanc.

    Avec un crop serré et expand élevé, l'ellipse couvre presque tout le personnage.
    Seul le fond autour du buste est inpainté — aucune place pour un second personnage.
    """
    bx1, by1, bx2, by2 = [int(c) for c in bbox]
    cx = (bx1 + bx2) // 2
    # Centre vertical légèrement plus bas pour couvrir aussi les épaules
    cy = (by1 + by2) // 2 + int((by2 - by1) * 0.20)
    fw, fh = bx2 - bx1, by2 - by1
    ax = int(fw * expand * 0.65)
    ay = int(fh * expand * 0.80)
    # Clamp aux bords de l'image pour ne pas déborder
    ax = min(ax, w // 2 - 2)
    ay = min(ay, h // 2 - 2)
    # Fond blanc (sera inpainté)
    mask = np.ones((h, w), dtype=np.uint8) * 255
    # Grande ellipse noire sur le buste (préservé)
    cv2.ellipse(mask, (cx, cy), (ax, ay), 0, 0, 360, 0, -1)
    mask = cv2.GaussianBlur(mask, (9, 9), 0)
    _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    return mask


def _crop_portrait(src: np.ndarray, bbox) -> tuple[np.ndarray, tuple]:
    """Crop carré tête+épaules centré sur le visage.

    Le côté du carré est contraint à l'espace réellement disponible
    (le visage peut être proche du bord supérieur). Retourne (crop_bgr, face_bbox_in_crop).
    """
    h, w = src.shape[:2]
    bx1, by1, bx2, by2 = [int(c) for c in bbox]
    fh = by2 - by1
    cx = (bx1 + bx2) // 2
    cy = (by1 + by2) // 2
    # Décalage vers le bas pour inclure les épaules
    cy_shifted = cy + int(fh * CROP_SHIFT_FACTOR)
    desired_half = int(fh * CROP_HALF_FACTOR)
    # Contraindre pour produire un vrai carré dans les limites de l'image
    half = min(desired_half, cy_shifted, h - cy_shifted, cx, w - cx)
    top   = cy_shifted - half
    bot   = cy_shifted + half
    left  = cx - half
    right = cx + half
    crop = src[top:bot, left:right]
    # Nouvelle bbox du visage dans le crop
    new_bbox = (bx1 - left, by1 - top, bx2 - left, by2 - top)
    return crop, new_bbox


def run(dry_run: bool) -> None:
    import os
    _load_env(ROOT)

    print("\n" + "=" * 60)
    print("  RETAKE NARA PORTRAIT — Flux Fill Pro v5 (fond seul inpainté)")
    print(f"  Stratégie : crop serré → préservation buste entier — ${COST_P2:.2f}")
    print("=" * 60)

    # ----------------------------------------------------------------
    # 1. Charger la référence canonique
    # ----------------------------------------------------------------
    src = cv2.imread(str(REF_FRAME))
    if src is None:
        raise FileNotFoundError(f"Référence introuvable : {REF_FRAME}")
    src_h, src_w = src.shape[:2]
    print(f"\n[1] Référence chargée : {src_w}×{src_h}")

    # ----------------------------------------------------------------
    # 2. Détecter le visage dans la source originale
    # ----------------------------------------------------------------
    import insightface
    app = insightface.app.FaceAnalysis(
        name=LOCKED_PARAMS["face_model"],
        providers=["CPUExecutionProvider"],
    )
    app.prepare(ctx_id=0, det_size=LOCKED_PARAMS["face_det_size"])

    face = _get_largest_face(app, src)
    if face is None:
        raise RuntimeError("Aucun visage détecté dans la référence")

    bx1, by1, bx2, by2 = [int(c) for c in face.bbox]
    fw = bx2 - bx1
    fh = by2 - by1
    print(f"[2] Visage : bbox ({bx1},{by1})→({bx2},{by2})  {fw}×{fh}px")

    # ----------------------------------------------------------------
    # 3. Crop serré tête+épaules (carré 1:1)
    #    → personnage occupe ~80% du cadre, fond réduit à la périphérie
    # ----------------------------------------------------------------
    crop, face_bbox_in_crop = _crop_portrait(src, face.bbox)
    ch, cw = crop.shape[:2]
    print(f"[3] Crop tête+épaules : {cw}×{ch}px")

    # ----------------------------------------------------------------
    # 4. Masque sur le CROP : grande ellipse buste = préservé,
    #    fond périphérique = inpainté
    #    → IMPOSSIBLE d'avoir un 2e personnage dans la zone inpaintée
    # ----------------------------------------------------------------
    mask = _build_inverted_face_mask(ch, cw, face_bbox_in_crop)
    # Vérification : zone blanche (inpaintée) doit être < 40% du crop
    white_pct = np.sum(mask == 255) / mask.size * 100
    print(f"[4] Masque buste : {100 - white_pct:.0f}% préservé, {white_pct:.0f}% fond inpainté")
    if white_pct > 50:
        print("    WARN : zone inpaintée > 50% — augmenter BUST_PRESERVE_EXPAND si doublons")

    # ----------------------------------------------------------------
    # 5. DRY-RUN : sauvegarder debug et quitter
    # ----------------------------------------------------------------
    if dry_run:
        debug_dir = ROOT / "production/character_refs"
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / "_debug_crop_input.png"), crop)
        cv2.imwrite(str(debug_dir / "_debug_mask_bust.png"), mask)
        print(f"\n[DRY-RUN] Debug dans production/character_refs/")
        print(f"  _debug_crop_input.png  — crop serré ({cw}×{ch})")
        print(f"  _debug_mask_bust.png   — masque (noir=préservé, blanc=fond inpainté)")
        print("Aucun appel API. Aucun fichier nara_ref.png modifié.")
        return

    # ----------------------------------------------------------------
    # 6. Flux Fill Pro v5 — inpainting fond périphérique uniquement
    # ----------------------------------------------------------------
    token = os.environ.get("REPLICATE_API_TOKEN", "")
    if not token:
        print("ERROR: REPLICATE_API_TOKEN non défini", file=sys.stderr)
        sys.exit(1)

    import replicate

    print(f"\n[5] Flux Fill Pro v5 — inpainting fond périphérique...")
    t0 = time.monotonic()

    out_p2 = replicate.run(
        MODEL_P2,
        input={
            "prompt":              PORTRAIT_PROMPT,
            "image":               _img_to_b64(crop),
            "mask":                _img_to_b64(mask),
            "output_format":       LOCKED_PARAMS["p2_output_format"],
            "output_quality":      LOCKED_PARAMS["p2_output_quality"],
            "safety_tolerance":    LOCKED_PARAMS["p2_safety_tolerance"],
            "num_inference_steps": LOCKED_PARAMS["p2_steps"],
            "guidance":            LOCKED_PARAMS["p2_guidance"],
            "prompt_upsampling":   LOCKED_PARAMS["p2_prompt_upsampling"],
        },
    )
    elapsed = time.monotonic() - t0

    result_url = str(out_p2)
    with urllib.request.urlopen(result_url, timeout=120) as resp:
        img_bytes = resp.read()
    result_bgr = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    if result_bgr is None:
        raise RuntimeError("Impossible de décoder le résultat Flux Fill Pro")
    print(f"    Terminé : {elapsed:.1f}s  |  {result_bgr.shape[1]}×{result_bgr.shape[0]}")

    # ----------------------------------------------------------------
    # 6b. Supprimer les watermarks/textes hallucinés (haut + bas)
    # ----------------------------------------------------------------
    result_bgr = _remove_all_watermarks(result_bgr)
    print(f"    Watermarks supprimés (bandes haut 8% + bas 10%)")

    # ----------------------------------------------------------------
    # 7. Resize → 1008×1008
    # ----------------------------------------------------------------
    portrait = cv2.resize(result_bgr, (PORTRAIT_SIZE, PORTRAIT_SIZE), interpolation=cv2.INTER_LANCZOS4)
    print(f"[6] Resize → {PORTRAIT_SIZE}×{PORTRAIT_SIZE}")

    # ----------------------------------------------------------------
    # 8. Score ArcFace (portrait résultat vs référence source originale)
    # ----------------------------------------------------------------
    score = _score_arcface(app, src, portrait)
    print(f"[7] ArcFace : {score:.4f}  (portrait résultat vs nara_hero_ref_01)")

    # ----------------------------------------------------------------
    # 9. Sauvegarder
    # ----------------------------------------------------------------
    OUT_PORTRAIT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT_PORTRAIT), portrait)

    print(f"\n{'='*60}")
    print(f"  Sauvegardé : {OUT_PORTRAIT.name} ({PORTRAIT_SIZE}×{PORTRAIT_SIZE})")
    print(f"  Coût       : ${COST_P2:.2f}")
    print(f"  ArcFace    : {score:.4f}")
    print(f"{'='*60}")
    print(f"\nETAPE SUIVANTE : python production/run.py benchmark --char nara")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.dry_run)
