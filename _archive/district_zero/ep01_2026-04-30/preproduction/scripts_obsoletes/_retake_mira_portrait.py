"""
_retake_mira_portrait.py
========================
Retake portrait Mira Sol — FLUX.1.1 Pro Ultra (raw=True)

Problèmes du portrait précédent :
  - Cicatrice trop dessinée / CGI → redéfinie comme marque naturelle et discrète
  - Visage trop "stock photo militaire" → reformulation cinématographique
  - Éclairage neon trop plat → brief DOP précis

Stratégie :
  - FLUX.1.1 Pro Ultra avec raw=True : mode "moins stylisé, plus cinéma"
    → évite spécifiquement le rendu "AI stock photo" sur-traité
  - Plusieurs seeds → sélection manuelle du meilleur
  - ArcFace scoring automatique vs seed retenu

Coût : ~$0.06/image (FLUX 1.1 Pro Ultra)

Usage : python production/_retake_mira_portrait.py [--dry-run] [--seeds 1 2 3] [--pick SEED]
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
OUT_DIR      = ROOT / "production/character_refs/mira_retake"
OUT_PORTRAIT = ROOT / "production/character_refs/mira_ref.png"
PORTRAIT_SIZE = 1008

# ---------------------------------------------------------------------------
# PROMPT REFORMULÉ — clés du réalisme cinématographique
#
# Changements vs canonical original :
#   - Cicatrice : "healed hairline fracture scar" → "3cm old healed scar, barely visible,
#     thin pale line at skin level, no raised tissue, fades into skin tone" → Discret, réel
#   - Beauté : ajout "striking natural beauty, angular features of a stage actress"
#     → garde le caractère fort mais évite le visage trop dur/générique
#   - Anti-AI : "no digital smoothing, no AI skin texture, no stock photo lighting"
#   - Référence film précise : Blade Runner 2049, Sicario — cinéastes nommés
#   - Skin : "visible real pores, stress lines under eyes, no retouching"
# ---------------------------------------------------------------------------

PROMPT = (
    # BLOC 1 — SUJET + IDENTITÉ (en premier, priorité maximale pour T5-XXL)
    "Photorealistic cinematic portrait of Mira, a 30-year-old Puerto Rican woman, "
    "undercut hair with shaved sides and flat top pushed back, unwashed and slightly matted, "
    "almond-shaped green eyes, lean angular face with natural asymmetry, "
    "olive-caramel skin with uneven complexion, dark under-eye circles, no makeup, "
    "wearing a worn dark grey transit worker coverall unzipped to waist, "
    "black thermal long-sleeve underneath, a signal-relay device clipped to the chest strap. "

    # BLOC 2 — EXPRESSION + REGARD
    "Over-shoulder glance, suspicious and calculating, jaw slightly set, composed stillness. "
    "Catchlights visible in both eyes. "

    # BLOC 3 — PHYSIQUE PRÉCIS — texture peau (jamais de formulations négatives)
    "Natural skin texture with clearly visible pores, micro skin irregularities, "
    "stress lines under the eyes, real lip texture with natural chapping, "
    "faint dust settled in skin creases, slight redness at nostrils, "
    "uneven skin tone, naturally weathered complexion, real human asymmetry. "

    # BLOC 4 — ÉCLAIRAGE CINÉMATOGRAPHIQUE
    "Three-point lighting: hard cold blue-green industrial key light from upper-left at 45 degrees, "
    "warm amber CRT fill light from the right, hair rim light separating subject from background. "
    "60 percent deep shadow. Practical motivated light sources. "

    # BLOC 5 — CAMÉRA + OPTIQUE
    "Shot on Hasselblad H6D-100c, 85mm f/2.8 lens, shallow depth of field, "
    "face sharp from hairline to chin, background soft dark concrete charcoal. "
    "Kodak Portra 400 pushed one stop — visible silver grain structure on skin, natural halation at light edges. "

    # BLOC 6 — AMBIANCE + FINITION
    "Steve McCurry documentary portrait realism, Anders Petersen candid film photography. "
    "Photojournalistic realism, ultra-high resolution, no digital retouching, "
    "no beauty filter, no AI skin texture, production character reference quality."
)

DEFAULT_SEED = 750   # seed frais — 500 donnait rendu trop clean


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
    print("  RETAKE MIRA PORTRAIT — FLUX.1.1 Pro Ultra (raw=True)")
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

    # InsightFace pour ArcFace scoring
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

    out_path = OUT_DIR / f"mira_flux_ultra_seed{seed}.png"
    out_path.write_bytes(img_bytes)

    img_bgr = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    face = _get_largest_face(app, img_bgr) if img_bgr is not None else None
    face_status = "✓ visage détecté" if face is not None else "✗ pas de visage"

    print(f"  Sauvegardé : {out_path.name} — {elapsed:.1f}s — ${COST_PER_IMG:.2f} — {face_status}")

    import shutil
    shutil.copy2(str(out_path), str(OUT_PORTRAIT))
    print(f"\n  mira_ref.png ← seed {seed}")
    print("  ETAPE SUIVANTE : valider visuellement, puis relancer avec --seed N si insatisfaisant")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help="Seed unique à générer (défaut: 11)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.seed, args.dry_run)
