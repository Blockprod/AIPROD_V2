"""
_retake_vale_portrait.py
========================
Retake portrait Commander Sarin Vale — FLUX.1.1 Pro Ultra (raw=True)
Méthode : identique à _retake_mira_portrait.py — 6 blocs ordonnés, sujet en premier, zéro formulation négative

Coût : ~$0.06/image (FLUX 1.1 Pro Ultra)

Usage : python production/_retake_vale_portrait.py [--seed N] [--dry-run]
"""
from __future__ import annotations

import argparse
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
    _score_arcface,
)

MODEL        = "black-forest-labs/flux-1.1-pro-ultra"
COST_PER_IMG = 0.06
OUT_DIR      = ROOT / "production/character_refs/vale_retake"
OUT_PORTRAIT = ROOT / "production/character_refs/vale_ref.png"
PORTRAIT_SIZE = 1008

# ---------------------------------------------------------------------------
# PROMPT — méthode 6 blocs
# Ordre : SUJET → EXPRESSION → PEAU → ÉCLAIRAGE → CAMÉRA → AMBIANCE
# Règles : sujet en premier token, zéro formulation négative, Hasselblad H6D-100c
# ---------------------------------------------------------------------------

PROMPT = (
    # BLOC 1 — SUJET + IDENTITÉ
    "Photorealistic cinematic portrait of Commander Vale, a late-40s military officer, "
    "dark hair silver-white at both temples, slicked back with visible product, immaculately maintained, "
    "cold grey-blue irises carrying genuine absence of empathy, zero sentiment, "
    "clean angular geometry, strong cheekbones, jaw with precisely maintained dark stubble at 1mm, "
    "slightly sallow skin under cold overhead light, "
    "wearing a black tactical command uniform, high collar, impeccable fit, "
    "single slim horizontal silver bar on left chest, no other insignia. "

    # BLOC 2 — EXPRESSION + REGARD
    "Direct gaze into camera, slight upward angle — looking down at viewer, "
    "parade-ground rigid posture, weight centred, absolute institutional stillness. "
    "Catchlights visible in both eyes. "

    # BLOC 3 — PHYSIQUE PRÉCIS — texture peau
    "Natural skin texture with visible pores, controlled institutional complexion, "
    "subtle age lines at eye corners, slightly sallow skin tone under cold light, "
    "precise stubble texture at 1mm, real human asymmetry, angular bone structure. "

    # BLOC 4 — ÉCLAIRAGE CINÉMATOGRAPHIQUE
    "Cold overhead institutional fluorescent 6500K, hard and flat on upper face, "
    "window behind right shoulder creating cold backlight silhouette edge, "
    "no warmth anywhere, 9:1 ratio. Pure cold light dominance. "

    # BLOC 5 — CAMÉRA + OPTIQUE
    "Shot on Hasselblad H6D-100c, 85mm f/2.8 lens, shallow depth of field, "
    "face sharp from hairline to chin, background soft shallow-focus security operations centre, "
    "wall of monitors in cold blue glow, analysts as blurred texture behind. "
    "Kodak Portra 400 pushed one stop — visible silver grain structure on skin, natural halation at light edges. "

    # BLOC 6 — AMBIANCE + FINITION
    "Fincher / The Social Network cold corporate interior framing, Denis Villeneuve character study. "
    "Photojournalistic realism, ultra-high resolution, no digital retouching, "
    "no beauty filter, no AI skin texture, production character reference quality."
)

DEFAULT_SEED = 500


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


def run(seed: int, dry_run: bool) -> None:
    _load_env_local()

    print("\n" + "=" * 60)
    print("  RETAKE VALE PORTRAIT — FLUX.1.1 Pro Ultra (raw=True)")
    print(f"  Seed : {seed}  |  Coût : ${COST_PER_IMG:.2f}")
    print("=" * 60)
    print(f"\nPrompt ({len(PROMPT)} chars) :\n  {PROMPT[:160]}...")

    if dry_run:
        print("\n[DRY-RUN] Aucun appel API.")
        print(f"  Modèle : {MODEL}")
        print(f"  Seed   : {seed}")
        print(f"  Output : {OUT_DIR}")
        return

    token = os.environ.get("REPLICATE_API_TOKEN", "")
    if not token:
        print("ERROR: REPLICATE_API_TOKEN non défini", file=sys.stderr)
        sys.exit(1)

    import replicate

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    import insightface
    app = insightface.app.FaceAnalysis(
        name=LOCKED_PARAMS["face_model"],
        providers=["CPUExecutionProvider"],
    )
    app.prepare(ctx_id=0, det_size=LOCKED_PARAMS["face_det_size"])

    print(f"\n[seed={seed}] Appel FLUX.1.1 Pro Ultra...")
    t0 = time.monotonic()

    output = replicate.run(
        MODEL,
        input={
            "prompt":           PROMPT,
            "aspect_ratio":     "2:3",
            "output_format":    "png",
            "output_quality":   100,
            "safety_tolerance": 6,
            "raw":              True,
            "seed":             seed,
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

    out_path = OUT_DIR / f"vale_flux_ultra_seed{seed}.png"
    out_path.write_bytes(img_bytes)

    img_bgr = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    face = _get_largest_face(app, img_bgr) if img_bgr is not None else None
    face_status = "✓ visage détecté" if face is not None else "✗ pas de visage"

    print(f"  Sauvegardé : {out_path.name} — {elapsed:.1f}s — ${COST_PER_IMG:.2f} — {face_status}")

    import shutil
    shutil.copy2(str(out_path), str(OUT_PORTRAIT))
    print(f"\n  vale_ref.png ← seed {seed}")
    print("  ETAPE SUIVANTE : valider visuellement, puis relancer avec --seed N si insatisfaisant")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help=f"Seed unique à générer (défaut: {DEFAULT_SEED})")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.seed, args.dry_run)
