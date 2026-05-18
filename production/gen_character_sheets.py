"""
production/gen_character_sheets.py
====================================
Génère les planches de référence multi-angles pour les 5 personnages.
Ces planches servent de source pour Tripo3D multiview_to_model (BLOC A — V4).

8 angles × 5 personnages = 40 images via Seedream 4.5 (Replicate)
Coût estimé : ~40 × $0.04 = ~$1.60

Outputs : production/character_sheets/{slug}/angle_{N:02d}_{label}.png

4 vues primaires Tripo3D (marquées [T]) :
  00_front [T], 02_profile_left [T], 04_back [T], 06_profile_right [T]

Usage :
    python production/gen_character_sheets.py --dry-run
    python production/gen_character_sheets.py --character nara --dry-run
    python production/gen_character_sheets.py --character nara --execute
    python production/gen_character_sheets.py --execute          # tous (5 × $1.60)
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

CHARACTERS_FILE = ROOT / "production/characters.json"
OUT_BASE = ROOT / "production/character_sheets"
MODEL = "bytedance/seedream-4.5"
COST_PER_IMAGE_USD = 0.04

# ------------------------------------------------------------------
# Angles de la planche de référence
# Flag [T] = vue primaire Tripo3D (front/left/back/right)
# ------------------------------------------------------------------
ANGLES: list[dict[str, str]] = [
    {
        "label": "front",
        "tripo3d_key": "front",
        "framing": (
            "Full-body front view, character facing camera directly. "
            "Head centred, body symmetrical. Arms slightly away from body (A-pose). "
            "Camera at eye level, aligned with character centre."
        ),
    },
    {
        "label": "front_three_quarter_left",
        "tripo3d_key": "",
        "framing": (
            "Full-body three-quarter view, character rotated 45 degrees to their right "
            "(camera's left). A-pose. Camera at eye level."
        ),
    },
    {
        "label": "profile_left",
        "tripo3d_key": "left",
        "framing": (
            "Full-body profile view from the left side. Character facing camera-right. "
            "A-pose. Camera at eye level, perfectly orthographic to the body axis."
        ),
    },
    {
        "label": "back_three_quarter_left",
        "tripo3d_key": "",
        "framing": (
            "Full-body three-quarter back-left view, character rotated 135 degrees "
            "(back mostly visible, slight left side). A-pose. Camera at eye level."
        ),
    },
    {
        "label": "back",
        "tripo3d_key": "back",
        "framing": (
            "Full-body back view, character facing away from camera. "
            "A-pose. Camera at eye level, aligned with character centre."
        ),
    },
    {
        "label": "back_three_quarter_right",
        "tripo3d_key": "",
        "framing": (
            "Full-body three-quarter back-right view, character rotated 225 degrees "
            "(back mostly visible, slight right side). A-pose. Camera at eye level."
        ),
    },
    {
        "label": "profile_right",
        "tripo3d_key": "right",
        "framing": (
            "Full-body profile view from the right side. Character facing camera-left. "
            "A-pose. Camera at eye level, perfectly orthographic to the body axis."
        ),
    },
    {
        "label": "front_three_quarter_right",
        "tripo3d_key": "",
        "framing": (
            "Full-body three-quarter view, character rotated 45 degrees to their left "
            "(camera's right). A-pose. Camera at eye level."
        ),
    },
]

# ------------------------------------------------------------------
# Prompt template
# ------------------------------------------------------------------

_STUDIO_SUFFIX = (
    "Clean studio reference lighting: soft box front-fill, rim separation from behind. "
    "Pure white seamless background. Full-body visible head to toe, "
    "no cropping, 10cm clearance around figure. "
    "Character reference sheet — turnaround view. "
    "Photorealistic, hyperdetailed textures, no motion blur, flat 3D-reference style. "
    "No cinematic grade. No background elements. No shadows on background. "
    "All surface details clearly readable for 3D reconstruction. "
    "2K resolution. No text, no labels, no annotations."
)


def _build_prompt(character: dict[str, Any], angle: dict[str, str]) -> str:
    return (
        f"{character['canonical']} "
        f"Standing in neutral A-pose — arms slightly spread, palms forward, legs hip-width apart. "
        f"{angle['framing']} "
        f"{_STUDIO_SUFFIX}"
    )


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


def _seed_for_character(character: dict[str, Any], angle_idx: int) -> int:
    """Dérive une graine par angle à partir du seed portrait validé."""
    base: int = character.get("validated_seed") or _parse_portrait_seed(character)
    return base * 100 + angle_idx


def _parse_portrait_seed(character: dict[str, Any]) -> int:
    note: str = character.get("note", "")
    for token in note.split():
        if token.isdigit():
            return int(token)
    return 42


def _generate_one(
    slug: str,
    character: dict[str, Any],
    angle_idx: int,
    angle: dict[str, str],
    execute: bool,
) -> str | None:
    """Génère une image pour un angle donné.

    Returns:
        Chemin absolu vers le PNG sauvegardé, ou None en dry-run.
    """
    out_dir = OUT_BASE / slug
    out_path = out_dir / f"angle_{angle_idx:02d}_{angle['label']}.png"

    tripo_marker = " [T]" if angle["tripo3d_key"] else ""
    print(f"  [{angle_idx:02d}] {angle['label']}{tripo_marker} → {out_path.name}")

    if not execute:
        print(f"       DRY-RUN : aucun appel API")
        return None

    if out_path.exists():
        print(f"       SKIP : fichier existe déjà")
        return str(out_path)

    import replicate

    seed = _seed_for_character(character, angle_idx)
    prompt = _build_prompt(character, angle)

    print(f"       Appel Seedream 4.5 (seed={seed})…")
    t0 = time.monotonic()
    last_exc: Exception | None = None
    for attempt in range(1, 6):
        try:
            output = replicate.run(
                MODEL,
                input={
                    "prompt": prompt,
                    "size": "2K",
                    "aspect_ratio": "2:3",
                    "sequential_image_generation": "disabled",
                },
            )
            break
        except Exception as exc:
            last_exc = exc
            wait = 20 * attempt
            print(f"       [WARN] tentative {attempt}/5 echouee : {exc}")
            print(f"       Attente {wait}s avant retry...")
            import time as _time; _time.sleep(wait)
    else:
        raise RuntimeError(f"Seedream echec apres 5 tentatives") from last_exc
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
    parser = argparse.ArgumentParser(description="Génère les planches multi-angles des personnages.")
    parser.add_argument("--character", help="Clé personnage (ex: nara). Tous si omis.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Déclenche les appels API (payants). Sans ce flag : dry-run.",
    )
    args = parser.parse_args()

    _load_env()

    characters: dict[str, Any] = json.loads(CHARACTERS_FILE.read_text(encoding="utf-8"))
    if args.character:
        if args.character not in characters:
            print(f"ERROR: personnage '{args.character}' inconnu. Valides : {list(characters)}", file=sys.stderr)
            return 1
        selection = {args.character: characters[args.character]}
    else:
        selection = characters

    total_images = len(selection) * len(ANGLES)
    total_cost = total_images * COST_PER_IMAGE_USD

    print("=" * 60)
    print("gen_character_sheets.py — Planches multi-angles V4")
    print("=" * 60)
    print(f"  Personnages   : {list(selection.keys())}")
    print(f"  Angles/perso  : {len(ANGLES)}")
    print(f"  Total images  : {total_images}")
    print(f"  Coût estimé   : ${total_cost:.2f}")
    print(f"  Mode          : {'EXECUTE' if args.execute else 'DRY-RUN'}")
    print()

    if args.execute and not os.environ.get("REPLICATE_API_TOKEN"):
        print("ERROR: REPLICATE_API_TOKEN manquant dans .env", file=sys.stderr)
        return 1

    generated = 0
    for slug, character in selection.items():
        print(f"── {slug} ({character['full_name']}) ──")
        for idx, angle in enumerate(ANGLES):
            result = _generate_one(slug, character, idx, angle, execute=args.execute)
            if result:
                generated += 1
        print()

    print("=" * 60)
    if args.execute:
        print(f"  Terminé : {generated}/{total_images} images générées")
        print(f"  Coût réel estimé : ${generated * COST_PER_IMAGE_USD:.2f}")
    else:
        print(f"  DRY-RUN terminé. Passer --execute pour générer.")
        tripo_views = sum(1 for a in ANGLES if a["tripo3d_key"])
        print(f"  Vues Tripo3D (4 par perso) : {tripo_views * len(selection)} images marquées [T]")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
