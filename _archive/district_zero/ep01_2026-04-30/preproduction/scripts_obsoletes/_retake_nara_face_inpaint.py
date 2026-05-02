"""
_retake_nara_face_inpaint.py
=============================
Inpainting VISAGE UNIQUEMENT sur nara_ref.png — Flux Fill Pro
Garde : corps, tenue, cheveux, écharpe, fond
Remplace : zone visage uniquement

Stratégie :
  1. Charger nara_flux_ultra_seed920.png
  2. InsightFace → bbox du visage
  3. Masque elliptique serré sur la face uniquement (sans cheveux ni écharpe)
  4. Flux Fill Pro inpainte uniquement le visage
  5. Sauvegarde → nara_ref.png

Coût : ~$0.05 (Flux Fill Pro)

Usage : python production/_retake_nara_face_inpaint.py [--dry-run]
"""
from __future__ import annotations

import argparse
import base64
import os
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
    _load_env,
    _get_largest_face,
)

MODEL        = "black-forest-labs/flux-fill-pro"
COST         = 0.05
SOURCE_IMG   = ROOT / "production/character_refs/nara_retake/nara_flux_ultra_seed920.png"
OUT_DIR      = ROOT / "production/character_refs/nara_retake"
OUT_PORTRAIT = ROOT / "production/character_refs/nara_ref.png"

# Prompt concentré sur le visage uniquement
FACE_PROMPT = (
    "Photorealistic cinematic close portrait of a woman in her late twenties, "
    "naturally striking face with balanced fine features and defined jawline — close to a model but imperfect and human, "
    "slightly sunken cheeks, lean face with subtle natural asymmetry, "
    "intense dark almond-shaped eyes carrying exhausted determination, watchful over-shoulder glance, "
    "tension in the brow, lips pressed together closed. "
    "Skin: warm matte olive-beige complexion, clearly visible pores, micro skin irregularities, "
    "stress lines around the mouth corners, bluish shadows under the orbital bones, "
    "low-sheen matte surface, no glow, no specularity, uneven natural skin tone, "
    "faint salt residue on the temple, small old scar above right eyebrow, "
    "zero makeup, zero lipstick, lips the exact same matte olive-beige tone as cheek skin, "
    "naturally weathered real human face. "
    "Kodak Portra 400 pushed one stop — visible grain on skin. "
    "Steve McCurry documentary portrait realism, no beauty filter, no AI skin texture."
)


def _load_env_local() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _img_to_b64(img_bgr: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", img_bgr)
    if not ok:
        raise RuntimeError("imencode failed")
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def _build_face_mask(h: int, w: int, bbox, expand: float = 0.15) -> np.ndarray:
    """Masque blanc sur le visage uniquement (ellipse serrée sur la face, sans cheveux ni cou).

    expand : marge en fraction de la bbox — petit pour ne toucher que la peau du visage
    """
    x1, y1, x2, y2 = bbox
    fw = x2 - x1
    fh = y2 - y1
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    # Ellipse serrée : légèrement élargie sur les côtés, mais pas vers le haut (cheveux) ni le bas (écharpe)
    rx = int(fw * (0.5 + expand))
    ry = int(fh * (0.5 + expand * 0.5))
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(mask, (cx, cy), (rx, ry), 0, 0, 360, 255, -1)
    return mask


def run(dry_run: bool) -> None:
    _load_env_local()

    print("\n" + "=" * 60)
    print("  NARA FACE INPAINT — Flux Fill Pro")
    print(f"  Source : {SOURCE_IMG.name}  |  Coût : ${COST:.2f}")
    print("=" * 60)

    if not SOURCE_IMG.exists():
        print(f"ERROR: source image introuvable : {SOURCE_IMG}", file=sys.stderr)
        sys.exit(1)

    # Charger l'image source
    img_bgr = cv2.imread(str(SOURCE_IMG))
    if img_bgr is None:
        print(f"ERROR: impossible de lire {SOURCE_IMG}", file=sys.stderr)
        sys.exit(1)
    h, w = img_bgr.shape[:2]
    print(f"  Image source : {w}×{h}")

    # Détecter le visage
    import insightface
    app = insightface.app.FaceAnalysis(
        name=LOCKED_PARAMS["face_model"],
        providers=["CPUExecutionProvider"],
    )
    app.prepare(ctx_id=0, det_size=LOCKED_PARAMS["face_det_size"])

    face = _get_largest_face(app, img_bgr)
    if face is None:
        print("ERROR: aucun visage détecté dans l'image source", file=sys.stderr)
        sys.exit(1)

    bbox = face.bbox.astype(int)
    print(f"  Visage détecté : bbox {bbox}")

    # Construire le masque
    mask = _build_face_mask(h, w, bbox, expand=0.12)
    face_pixels = int(np.sum(mask > 0))
    total_pixels = h * w
    print(f"  Masque visage : {face_pixels} px ({100*face_pixels/total_pixels:.1f}% de l'image)")

    if dry_run:
        # Sauvegarder le masque pour vérification visuelle
        debug_path = OUT_DIR / "debug_face_mask.png"
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        overlay = img_bgr.copy()
        overlay[mask > 0] = (overlay[mask > 0] * 0.5 + np.array([0, 0, 128]) * 0.5).astype(np.uint8)
        cv2.imwrite(str(debug_path), overlay)
        print(f"\n[DRY-RUN] Masque sauvegardé : {debug_path}")
        print(f"  Prompt ({len(FACE_PROMPT)} chars) : {FACE_PROMPT[:120]}...")
        return

    token = os.environ.get("REPLICATE_API_TOKEN", "")
    if not token:
        print("ERROR: REPLICATE_API_TOKEN non défini", file=sys.stderr)
        sys.exit(1)

    import replicate
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    img_b64  = _img_to_b64(img_bgr)
    mask_b64 = _img_to_b64(cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR))

    print(f"\n  Appel Flux Fill Pro (inpaint visage)...")
    t0 = time.monotonic()

    output = replicate.run(
        MODEL,
        input={
            "prompt":           FACE_PROMPT,
            "image":            img_b64,
            "mask":             mask_b64,
            "output_format":    "png",
            "output_quality":   100,
            "safety_tolerance": 6,
        },
    )
    elapsed = time.monotonic() - t0

    url = getattr(output, "url", None)
    if callable(url):
        url = url()
    else:
        url = str(output)
    with urllib.request.urlopen(url, timeout=60) as resp:
        img_bytes = resp.read()

    out_path = OUT_DIR / "nara_face_inpaint.png"
    out_path.write_bytes(img_bytes)

    # Vérifier le visage dans le résultat
    result_bgr = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    face_result = _get_largest_face(app, result_bgr) if result_bgr is not None else None
    face_status = "✓ visage détecté" if face_result is not None else "✗ pas de visage"

    print(f"  Sauvegardé : {out_path.name} — {elapsed:.1f}s — ${COST:.2f} — {face_status}")

    import shutil
    shutil.copy2(str(out_path), str(OUT_PORTRAIT))
    print(f"\n  nara_ref.png ← face inpaint sur seed920")
    print("  ETAPE SUIVANTE : valider visuellement")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Visualise le masque sans appel API")
    args = parser.parse_args()
    run(args.dry_run)
