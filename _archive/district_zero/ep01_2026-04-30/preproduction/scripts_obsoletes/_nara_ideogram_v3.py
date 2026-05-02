"""
_nara_ideogram_v3.py
====================
Génère le portrait de référence Nara via Ideogram v3 Turbo (Replicate).
Modèle : ideogram-ai/ideogram-v3-turbo
Format : 2:3 portrait (832x1248)
Style : REALISTIC — anti-AI, photoréaliste

Prompt calqué sur reference_pack.json + esthétique nara_hero_ref_01.png.

Usage : python _nara_ideogram_v3.py [--dry-run] [--seeds 1 22 33]
Coût  : ~$0.025/image (Turbo)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MODEL = "ideogram-ai/ideogram-v3-turbo"
OUT_DIR = ROOT / "production/character_refs/ideogram_v3"
OUT_PORTRAIT = ROOT / "production/character_refs/nara_ref.png"
COST_PER_IMAGE = 0.025

# Prompt fidèle au reference_pack.json original + éclairage du hero ref
PROMPT = (
    "Female protagonist of a dystopian survival thriller TV series. "
    "Late 20s, facial appearance close to a top model: fine balanced features, "
    "elegant defined jawline, high cheekbones. "
    "Intense intelligent dark eyes exhausted by hardship — determination and contained vulnerability in every feature. "
    "No excessive makeup. Natural skin, no airbrushing, visible pores, wet with condensation. "
    "Dark brown hair loosely tied back, stray wet strands falling at temples and cheeks. "
    "Dark tactical neck scarf wrapped close, weathered charcoal utility jacket, dark tactical vest, lean runner's build. "
    "Tight portrait framing shoulders to crown. "
    "Cold blue-white industrial corridor light from behind — backlit silhouette edge, cool teal-steel ambient fill. "
    "Leaking industrial service corridor background, dense pipes, wet corroded metal walls, deep shadow. "
    "Photorealistic cinematic quality, ARRI Alexa 35, anamorphic lens, 4K. "
    "Desaturated teal and steel-blue color grade. Natural grain, no fantasy glow, no HDR."
)

NEGATIVE = (
    "cartoon, anime, illustration, painting, 3D render, CGI, digital art, "
    "plastic skin, airbrushed, overly smooth, uncanny valley, "
    "deformed face, asymmetric eyes, bad anatomy, watermark, text, logo, "
    "warm lighting, amber, orange, fashion studio, white background"
)

DEFAULT_SEEDS = [11, 22, 33, 44, 55]


def _load_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def run(seeds: list[int], dry_run: bool, pick: int | None) -> None:
    _load_env()

    print("\n" + "=" * 60)
    print("  NARA PORTRAIT — Ideogram v3 Turbo (Replicate)")
    print(f"  Seeds : {seeds}")
    print(f"  Coût estimé : ${len(seeds) * COST_PER_IMAGE:.3f}")
    print("=" * 60)
    print(f"\nPrompt ({len(PROMPT)} chars):\n  {PROMPT[:160]}...")

    if dry_run:
        print("\n[DRY-RUN] Aucun appel API.")
        return

    token = os.environ.get("REPLICATE_API_TOKEN", "")
    if not token:
        print("ERROR: REPLICATE_API_TOKEN non défini", file=sys.stderr)
        sys.exit(1)

    import replicate
    import cv2
    import urllib.request

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []
    total_cost = 0.0

    for seed in seeds:
        print(f"\n[seed={seed}] Appel Ideogram v3 Turbo...")
        t0 = time.monotonic()
        output = replicate.run(
            MODEL,
            input={
                "prompt": PROMPT,
                "negative_prompt": NEGATIVE,
                "resolution": "832x1248",
                "magic_prompt_option": "Off",
                "style_type": "Realistic",
                "seed": seed,
            },
        )
        elapsed = time.monotonic() - t0
        total_cost += COST_PER_IMAGE

        # Télécharger l'image
        if hasattr(output, "read"):
            img_bytes = output.read()
        else:
            url = getattr(output, "url", None)
            if callable(url):
                url = url()
            else:
                url = str(output)
            with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
                img_bytes = resp.read()

        out_path = OUT_DIR / f"nara_ideogram_seed{seed}.png"
        out_path.write_bytes(img_bytes)
        generated.append(out_path)
        print(f"  Sauvegardé : {out_path.name} — {elapsed:.1f}s — ${total_cost:.3f} cumulé")

    print(f"\nTerminé. {len(generated)} images. Coût total : ${total_cost:.3f}")
    print(f"Images dans : {OUT_DIR}")

    # Copier le meilleur seed vers nara_ref.png
    chosen_seed = pick if pick is not None else seeds[0]
    chosen_path = OUT_DIR / f"nara_ideogram_seed{chosen_seed}.png"
    if chosen_path.exists():
        import shutil
        shutil.copy2(str(chosen_path), str(OUT_PORTRAIT))
        print(f"\nnara_ref.png <- seed {chosen_seed}")
        print("ETAPE SUIVANTE : python production/run.py benchmark --char nara")
    else:
        print(f"\nWARN: seed {chosen_seed} non trouvé, nara_ref.png non mis à jour.")
        print(f"Relancer avec --pick <seed> pour choisir.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--pick", type=int, default=None,
                        help="Seed à copier vers nara_ref.png (défaut: premier seed)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.seeds, args.dry_run, args.pick)
