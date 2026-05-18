"""
production/gen_3d_assets.py
============================
Orchestre la generation des assets 3D.

  PERSONNAGES : workflow MetaHuman (Epic)
      -> Voir gen_metahuman_rigs.py pour le detail
      -> Ce script ne traite PLUS les personnages via Tripo3D
         (qualite insuffisante pour un thriller photorealistic)

  DECORS (LOCATIONS) : Meshy image-to-3D
      Entrees : location_sheets/ generes par gen_location_coverage.py

Outputs :
    production/assets_3d/locations/{key}.glb    -- 10 decors

Couts :
    Meshy decors : ~$0.20 x 10 = ~$2.00  (requiert subscription Meshy)

Usage :
    python production/gen_3d_assets.py --type locations --dry-run
    python production/gen_3d_assets.py --type locations --execute

Note : --type characters et --character sont conserves pour compatibilite
       mais affichent un message de redirection vers gen_metahuman_rigs.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHARACTERS_FILE = ROOT / "production/characters.json"
LOCATIONS_FILE = ROOT / "production/locations.json"
SHEETS_BASE = ROOT / "production/character_sheets"
LOC_SHEETS_BASE = ROOT / "production/location_sheets"
ASSETS_BASE = ROOT / "production/assets_3d"

COST_MESHY_USD = 0.20


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


def _find_angle_image(sheets_dir: Path, angle_label: str) -> Path | None:
    """Cherche un fichier angle_{angle_label}.png dans sheets_dir."""
    candidate = sheets_dir / f"angle_{angle_label}.png"
    if candidate.exists():
        return candidate
    return None


# ------------------------------------------------------------------
# Characters -- REDIRIGE vers gen_metahuman_rigs.py
# ------------------------------------------------------------------

def _process_character(slug: str, character: dict[str, Any], execute: bool) -> bool:
    """Les personnages utilisent desormais MetaHuman (Epic) via gen_metahuman_rigs.py."""
    print(f"  [{slug}] {character['full_name']}")
    print(f"    [INFO] Les personnages ne sont plus generes via Tripo3D.")
    print(f"    [INFO] Workflow Rodin automatise disponible :")
    print(f"           python production/gen_character_meshes.py --character {slug} --execute")
    return False


# ------------------------------------------------------------------
# Locations — Meshy image_to_model
# ------------------------------------------------------------------

def _process_location(loc_key: str, location: dict[str, Any], execute: bool) -> bool:
    """Génère le GLB d'un décor via Meshy.

    Returns True si le GLB a été généré (ou existait déjà).
    """
    out_path = ASSETS_BASE / "locations" / f"{loc_key}.glb"
    sheets_dir = LOC_SHEETS_BASE / loc_key
    wide_img = _find_angle_image(sheets_dir, "wide")

    slug = location.get("slug", loc_key)
    print(f"  [{loc_key}]")
    print(f"    Slug       : {slug}")
    print(f"    Source img : {wide_img}")
    print(f"    Output     : {out_path}")

    if not execute:
        print(f"    DRY-RUN : aucun appel API")
        if wide_img is None:
            print(f"    ⚠️  Image wide manquante")
            print(f"       → Lancer d'abord gen_location_coverage.py --location {loc_key} --execute")
        else:
            print(f"    ✅ Image wide présente — prêt pour Meshy")
        if not os.environ.get("MESHY_API_TOKEN"):
            print(f"    ⚠️  MESHY_API_TOKEN manquant (subscription requise)")
        return False

    if out_path.exists():
        print(f"    SKIP : {out_path.name} existe déjà")
        return True

    if wide_img is None:
        print(f"    ERROR : image wide introuvable dans {sheets_dir}", file=sys.stderr)
        print(f"    → Lancer gen_location_coverage.py --location {loc_key} --execute", file=sys.stderr)
        return False

    from aiprod_adaptation.image_gen.meshy_adapter import MeshyAdapter

    adapter = MeshyAdapter()
    print(f"    Envoi task Meshy image-to-3D…")
    task_id = adapter.image_to_model(
        image_path=wide_img,
        seed=location.get("seed", 42),
    )
    print(f"    task_id : {task_id}")
    print(f"    Attente complétion (max 10 min)…")
    result = adapter.poll_task(task_id)
    print(f"    Statut : {result['status']} — téléchargement GLB…")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    adapter.download_glb(result["model_url"], out_path)
    print(f"    ✅ GLB sauvegardé : {out_path}")
    return True


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Genere les assets 3D GLB (locations via Meshy, persos via MetaHuman).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--type",
        choices=["characters", "locations"],
        help="Limiter à un type d'asset.",
    )
    group.add_argument("--character", help="Clé personnage unique (ex: nara).")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Déclenche les appels API (payants). Sans ce flag : dry-run.",
    )
    args = parser.parse_args()

    _load_env()

    characters: dict[str, Any] = json.loads(CHARACTERS_FILE.read_text(encoding="utf-8"))
    locations: dict[str, Any] = json.loads(LOCATIONS_FILE.read_text(encoding="utf-8"))

    do_characters = args.type in (None, "characters") and args.character is None
    do_locations = args.type in (None, "locations") and args.character is None
    if args.character:
        do_characters = True
        do_locations = False

    if args.character and args.character not in characters:
        print(
            f"ERROR: personnage '{args.character}' inconnu. "
            f"Valides : {list(characters)}",
            file=sys.stderr,
        )
        return 1

    char_selection = (
        {args.character: characters[args.character]} if args.character else characters
    ) if do_characters else {}
    loc_selection = locations if do_locations else {}

    total_char = len(char_selection)
    total_loc = len(loc_selection)
    total_cost = total_loc * COST_MESHY_USD

    print("=" * 60)
    print("gen_3d_assets.py — Génération assets 3D V4")
    print("=" * 60)
    print(f"  Personnages (Tripo3D) : {list(char_selection.keys())}")
    print(f"  Décors    (Meshy)     : {list(loc_selection.keys())}")
    print(f"  Coût estimé           : ${total_cost:.2f}")
    print(f"  Mode                  : {'EXECUTE' if args.execute else 'DRY-RUN'}")
    print()

    generated_chars = 0
    generated_locs = 0

    if char_selection:
        print("─── PERSONNAGES (Tripo3D) ───")
        for slug, char in char_selection.items():
            ok = _process_character(slug, char, execute=args.execute)
            if ok:
                generated_chars += 1
            print()

    if loc_selection:
        print("─── DÉCORS (Meshy) ───")
        for loc_key, loc in loc_selection.items():
            ok = _process_location(loc_key, loc, execute=args.execute)
            if ok:
                generated_locs += 1
            print()

    print("=" * 60)
    if args.execute:
        print(f"  Personnages : {generated_chars}/{total_char} GLB générés")
        print(f"  Décors      : {generated_locs}/{total_loc} GLB générés")
        print(f"  Coût réel   : ${generated_chars * COST_TRIPO3D_USD + generated_locs * COST_MESHY_USD:.2f}")
    else:
        print(f"  DRY-RUN terminé. Passer --execute pour générer.")
        print(f"  Outputs attendus :")
        for slug in char_selection:
            print(f"    production/assets_3d/characters/{slug}.glb")
        for loc_key in loc_selection:
            print(f"    production/assets_3d/locations/{loc_key}.glb")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
