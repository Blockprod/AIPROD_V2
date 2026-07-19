"""
production/gen_location_coverage.py
=====================================
Génère les planches de référence multi-angles pour les 10 lieux.
Ces planches servent de source pour Meshy image_to_model (BLOC A — V4).

5 angles × 10 lieux = 50 images via Seedream 4.5 (Replicate)
Coût estimé : ~50 × $0.04 = ~$2.00

Outputs : production/location_sheets/{location_key}/angle_{N:02d}_{label}.png

Usage :
    python production/gen_location_coverage.py --dry-run
    python production/gen_location_coverage.py --location ext_outer_wall_night --dry-run
    python production/gen_location_coverage.py --location ext_outer_wall_night --execute
    python production/gen_location_coverage.py --execute          # tous ($2.00)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LOCATIONS_FILE = ROOT / "production/locations.json"
OUT_BASE = ROOT / "production/location_sheets"
MODEL = "bytedance/seedream-4.5"
COST_PER_IMAGE_USD = 0.04

# ------------------------------------------------------------------
# Angle templates
# Chaque angle produit un cadragePrefix + suffixe technique commun
# ------------------------------------------------------------------

ANGLE_DEFS: list[dict[str, str]] = [
    {
        "label": "wide",
        "prefix": (
            "Wide establishing shot. Empty scene, no people. "
            "Camera at ground level. Horizon at lower third. "
            "Architecture fills upper two-thirds. "
            "Strong vanishing point receding to infinity. "
        ),
    },
    {
        "label": "medium",
        "prefix": (
            "Medium environmental shot. Empty scene, no people. "
            "Camera at chest height 1.5 metres. "
            "Dominant architectural element at left third. "
            "Open negative space right. "
            "Surface textures and material detail clearly readable. "
        ),
    },
    {
        "label": "detail",
        "prefix": (
            "Extreme close-up macro. "
            "Single texture element fills 80 percent of frame, subject bleeds off all edges. "
            "Empty scene, no people. "
            "Raking light 10 degrees to surface — micro-relief fully revealed. "
        ),
    },
    {
        "label": "birds_eye",
        "prefix": (
            "Bird's-eye overhead view. Camera directly above, looking straight down. "
            "Empty scene, no people. "
            "Floor plane and full spatial layout fully visible. "
            "All architectural elements in top-down projection. "
            "Useful as 3D layout reference. "
        ),
    },
    {
        "label": "corner_perspective",
        "prefix": (
            "Corner perspective view. Camera in room corner at mid-height, "
            "two walls and ceiling visible simultaneously. Empty scene, no people. "
            "Full spatial depth visible from corner. "
            "Architecture fills full frame. Useful as 3D volume reference. "
        ),
    },
]


# ------------------------------------------------------------------
# Prompt builder
# ------------------------------------------------------------------

_TECHNICAL_SUFFIX = (
    "Photorealistic cinematic, hyperdetailed textures. "
    "Natural film grain. No oversaturation. No HDR clipping. "
    "No people, no characters, no figures. "
    "2K resolution."
)


def _build_prompt(location: dict[str, Any], angle: dict[str, str], angle_idx: int) -> str:
    """Construit le prompt complet pour un angle et un lieu.

    Utilise refs_angles_prompts si disponible pour les 3 premiers angles.
    """
    label = angle["label"]
    existing_prompts: dict[str, str] = location.get("refs_angles_prompts", {})

    # Utiliser le prompt existant s'il est disponible
    if label in existing_prompts:
        return existing_prompts[label]

    # Construire depuis les champs canoniques
    slug = location["slug"]
    canonical = location["canonical"]
    lighting = location.get("lighting_brief", "")
    camera = location.get("camera", "ARRI Alexa 35")
    dop_ref = location.get("dop_ref", "")
    colour = location.get("colour", {})

    colour_str = ""
    if colour:
        colour_str = (
            f"Colour palette: dominant {colour.get('dominant', '')}. "
            f"Accent {colour.get('accent', '')}. "
            f"Blacks {colour.get('blacks', '')}. "
        )

    prompt = (
        f"{angle['prefix']}"
        f"{slug}. "
        f"{canonical} "
        f"{lighting} "
        f"{colour_str}"
        f"{camera}. "
        f"{dop_ref}. "
        f"{_TECHNICAL_SUFFIX}"
    )
    return prompt


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

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


def _generate_one(
    loc_key: str,
    location: dict[str, Any],
    angle_idx: int,
    angle: dict[str, str],
    execute: bool,
) -> str | None:
    out_dir = OUT_BASE / loc_key
    out_path = out_dir / f"angle_{angle_idx:02d}_{angle['label']}.png"

    meshy_marker = " [M]" if angle["label"] == "wide" else ""
    print(f"  [{angle_idx:02d}] {angle['label']}{meshy_marker} → {out_path.name}")

    if not execute:
        print(f"       DRY-RUN : aucun appel API")
        return None

    if out_path.exists():
        print(f"       SKIP : fichier existe déjà")
        return str(out_path)

    import replicate

    base_seed: int = location.get("seed", 42)
    seed = base_seed * 100 + angle_idx

    prompt = _build_prompt(location, angle, angle_idx)

    print(f"       Appel Seedream 4.5 (seed={seed})…")
    t0 = time.monotonic()
    output = replicate.run(
        MODEL,
        input={
            "prompt": prompt,
            "size": "2K",
            "aspect_ratio": "16:9",
            "seed": seed,
            "sequential_image_generation": "disabled",
        },
    )
    elapsed = time.monotonic() - t0

    url = str(output[0]) if isinstance(output, list) else str(output)
    print(f"       {elapsed:.1f}s — URL: {url[:60]}…")

    out_dir.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as resp:
        out_path.write_bytes(resp.read())
    print(f"       Sauvegardé : {out_path}")
    return str(out_path)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Génère les planches multi-angles des lieux.")
    parser.add_argument("--location", help="Clé lieu (ex: ext_outer_wall_night). Tous si omis.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Déclenche les appels API (payants). Sans ce flag : dry-run.",
    )
    parser.add_argument("--allow-cloud", action="store_true", help="Allow legacy paid cloud generation.")
    args = parser.parse_args()

    _load_env()

    locations: dict[str, Any] = json.loads(LOCATIONS_FILE.read_text(encoding="utf-8"))
    if args.location:
        if args.location not in locations:
            print(
                f"ERROR: lieu '{args.location}' inconnu. "
                f"Valides : {list(locations.keys())}",
                file=sys.stderr,
            )
            return 1
        selection = {args.location: locations[args.location]}
    else:
        selection = locations

    total_images = len(selection) * len(ANGLE_DEFS)
    total_cost = total_images * COST_PER_IMAGE_USD

    print("=" * 60)
    print("gen_location_coverage.py — Planches multi-angles V4")
    print("=" * 60)
    print(f"  Lieux         : {list(selection.keys())}")
    print(f"  Angles/lieu   : {len(ANGLE_DEFS)}")
    print(f"  Total images  : {total_images}")
    print(f"  Coût estimé   : ${total_cost:.2f}")
    print(f"  Mode          : {'EXECUTE' if args.execute else 'DRY-RUN'}")
    print(f"  [M] = vue source Meshy (wide)")
    print()

    if args.execute and not args.allow_cloud:
        print("Cloud generation blocked. Add --allow-cloud to acknowledge Replicate spend.", file=sys.stderr)
        return 1

    if args.execute and not os.environ.get("REPLICATE_API_TOKEN"):
        print("ERROR: REPLICATE_API_TOKEN manquant dans .env", file=sys.stderr)
        return 1

    generated = 0
    for loc_key, location in selection.items():
        slug = location.get("slug", loc_key)
        print(f"── {loc_key}")
        print(f"   {slug}")
        for idx, angle in enumerate(ANGLE_DEFS):
            result = _generate_one(loc_key, location, idx, angle, execute=args.execute)
            if result:
                generated += 1
        print()

    print("=" * 60)
    if args.execute:
        print(f"  Terminé : {generated}/{total_images} images générées")
        print(f"  Coût réel estimé : ${generated * COST_PER_IMAGE_USD:.2f}")
    else:
        print(f"  DRY-RUN terminé. Passer --execute pour générer.")
        print(f"  Vues source Meshy : 1 par lieu × {len(selection)} lieux (label: wide [M])")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
