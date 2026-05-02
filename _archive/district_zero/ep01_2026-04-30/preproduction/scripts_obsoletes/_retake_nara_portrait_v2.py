"""
_retake_nara_portrait_v2.py
============================
Retake portrait Nara — FLUX.1.1 Pro Ultra (raw=True)
Méthode : methode_prompt.md — 6 blocs ordonnés, sujet en premier, zéro formulation négative

Différence vs v1 (_retake_nara_portrait.py) :
  v1 → Flux Fill Pro, inpainting du fond sur nara_hero_ref_01.png
  v2 → Flux Ultra, génération complète, prompt restructuré selon methode_prompt.md

Coût : ~$0.06/image (FLUX 1.1 Pro Ultra)

Usage : python production/_retake_nara_portrait_v2.py [--seed N] [--dry-run]
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
OUT_DIR      = ROOT / "production/character_refs/nara_retake"
OUT_PORTRAIT = ROOT / "production/character_refs/nara_ref.png"
PORTRAIT_SIZE = 1008

# ---------------------------------------------------------------------------
# PROMPT v2 — méthode 6 blocs (methode_prompt.md)
# Ordre : SUJET → EXPRESSION → PEAU → ÉCLAIRAGE → CAMÉRA → AMBIANCE
# Règles : sujet en premier, zéro formulation négative, Hasselblad H6D-100c
# ---------------------------------------------------------------------------

PROMPT = (
    # BLOC 1 — SUJET + IDENTITÉ
    "Photorealistic cinematic portrait of Nara, a 28-year-old Central European woman, "
    "dark brown hair pulled up in a tight bun, four loose wet strands falling across forehead and cheek, "
    "dark brown almond-shaped eyes, intense and watchful, "
    "warm olive complexion, well-defined cheekbones, angular jaw, full lips, real human asymmetry, "
    "dark circles from exhaustion, naturally weathered complexion, "
    "wearing a dark tubular neck gaiter pulled up to the chin and a weathered dark olive utility jacket with tactical vest harness over it. "

    # BLOC 2 — EXPRESSION + REGARD
    "Over-shoulder glance, survival alertness, jaw slightly set, body caught mid-movement. "
    "Catchlights visible in both eyes. "

    # BLOC 3 — PHYSIQUE PRÉCIS — texture peau
    "Natural skin texture with clearly visible pores, micro skin irregularities, "
    "stress lines under the eyes, fine moisture droplets on cheekbone and temple, "
    "real lip texture with slight dryness, uneven skin tone, real human asymmetry. "

    # BLOC 4 — ÉCLAIRAGE CINÉMATOGRAPHIQUE
    "Three-point lighting: hard cold blue-white industrial key light from upper-left at 45 degrees, "
    "cold blue emergency strip fill light from the right, hair rim light separating subject from background. "
    "60 percent deep shadow. Practical motivated light sources. "

    # BLOC 5 — CAMÉRA + OPTIQUE
    "Shot on Hasselblad H6D-100c, 85mm f/2.8 lens, shallow depth of field, "
    "face sharp from hairline to chin, background soft dark industrial corridor with pipes and wet concrete. "
    "Kodak Portra 400 pushed one stop — visible silver grain structure on skin, natural halation at light edges. "

    # BLOC 6 — AMBIANCE + FINITION
    "Steve McCurry documentary portrait realism, Anders Petersen candid film photography. "
    "Photojournalistic realism, ultra-high resolution, no digital retouching, "
    "no beauty filter, no AI skin texture, production character reference quality."
)

DEFAULT_SEED = 600


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
    print("  RETAKE NARA PORTRAIT v2 — FLUX.1.1 Pro Ultra (raw=True)")
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

    # InsightFace pour détection visage
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

    out_path = OUT_DIR / f"nara_flux_ultra_seed{seed}.png"
    out_path.write_bytes(img_bytes)

    img_bgr = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    face = _get_largest_face(app, img_bgr) if img_bgr is not None else None
    face_status = "✓ visage détecté" if face is not None else "✗ pas de visage"

    print(f"  Sauvegardé : {out_path.name} — {elapsed:.1f}s — ${COST_PER_IMG:.2f} — {face_status}")

    import shutil
    shutil.copy2(str(out_path), str(OUT_PORTRAIT))
    print(f"\n  nara_ref.png ← seed {seed}")
    print("  ETAPE SUIVANTE : valider visuellement, puis relancer avec --seed N si insatisfaisant")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help=f"Seed unique à générer (défaut: {DEFAULT_SEED})")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.seed, args.dry_run)
