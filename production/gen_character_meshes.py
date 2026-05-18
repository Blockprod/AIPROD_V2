"""
production/gen_character_meshes.py
====================================
Genere les meshes 3D des personnages via Hyper3D Rodin (image-to-3D).

Ce script remplace le workflow MetaHuman (non-automatisable) par un pipeline
100% automatise :

  BLOC A -- Personnages (Scenario B) :
    character_sheets/{slug}/angle_00_front.png
    + angle_02_profile_left.png
    + angle_06_profile_right.png
            |
            v
    Hyper3D Rodin API  (image-to-3D, ~1 credit/perso)
            |
            v
    production/assets_3d/characters/{slug}_rodin.glb   -- mesh brut Rodin
            |
            v (Blender headless : nettoyage + export)
    production/assets_3d/characters/{slug}_clean.glb   -- mesh pret pour Blender

  Le mesh clean est ensuite charge par blender_render.py pour :
    - Render couleur Cycles (guide visuel)
    - Depth EXR (guide ControlNet depth)
    - Normal EXR (guide ControlNet normal)

  La passe finale photorealiste utilise :
    - ControlNet depth/normal depuis les maps Blender
    - IP-Adapter + character_sheets comme reference visuelle
    - Seedream pour la synthese finale

USAGE :
    python production/gen_character_meshes.py --character nara
    python production/gen_character_meshes.py --all
    python production/gen_character_meshes.py --character nara --dry-run
    python production/gen_character_meshes.py --character nara --execute

FLAGS :
    --dry-run   (defaut) Affiche le plan sans appel API
    --execute   Declenche les appels API payants

PREREQUIS :
    - character_sheets/{slug}/ generes par gen_character_sheets.py
    - RODIN_API_TOKEN dans .env

COUTS :
    Rodin Regular tier : ~1 credit/personnage (plan $24/mois = 30 credits/mois)
    5 personnages = 5 credits -- largement dans le plan mensuel

OUTPUTS :
    production/assets_3d/characters/{slug}_rodin.glb   -- brut Rodin
    production/assets_3d/characters/{slug}_clean.glb   -- nettoye Blender
    production/assets_3d/characters/{slug}_status.json -- statut JSON
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CHARACTERS_FILE = ROOT / "production/characters.json"
SHEETS_BASE = ROOT / "production/character_sheets"
ASSETS_CHARS_DIR = ROOT / "production/assets_3d/characters"

# Vue principale pour TripoSG (image unique, front recommande)
_TRIPOSG_PRIMARY_ANGLE = "angle_00_front"
# Fallback si le front est absent
_TRIPOSG_FALLBACK_ANGLES = ["angle_01_front_three_quarter_left", "angle_07_front_three_quarter_right"]

_DEFAULT_BLENDER_EXE = (
    r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
    if sys.platform == "win32"
    else "blender"
)

# ------------------------------------------------------------------
# Script Blender inline : nettoyage du GLB TripoSG
# ------------------------------------------------------------------
_BLENDER_CLEAN_SCRIPT = r"""
import bpy
import sys
from pathlib import Path

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--glb-in", required=True)
ap.add_argument("--glb-out", required=True)
args = ap.parse_args(argv)

# Nettoyer la scene par defaut
bpy.ops.wm.read_factory_settings(use_empty=True)

# Importer le GLB brut de TripoSG
bpy.ops.import_scene.gltf(filepath=args.glb_in)

# Supprimer cameras et lumieres parasites
for obj in list(bpy.data.objects):
    if obj.type not in ("MESH", "ARMATURE"):
        bpy.data.objects.remove(obj, do_unlink=True)

# Appliquer les transformations
for obj in bpy.data.objects:
    if obj.type in ("MESH", "ARMATURE"):
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        break

# Exporter GLB nettoye
bpy.ops.export_scene.gltf(
    filepath=args.glb_out,
    export_format="GLB",
    export_apply=True,
    use_selection=False,
)
print("[blender_clean] OK -- GLB exporte : " + args.glb_out)
"""


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _load_env() -> None:
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def _find_angle_image(sheets_dir: Path, angle_label: str) -> Path | None:
    """Cherche une image d'angle dans le dossier character sheets."""
    candidate = sheets_dir / f"{angle_label}.png"
    return candidate if candidate.exists() else None


def _find_triposg_image(slug: str) -> Path | None:
    """Retourne la meilleure image source pour TripoSG (front en priorite)."""
    sheets_dir = SHEETS_BASE / slug
    front = _find_angle_image(sheets_dir, _TRIPOSG_PRIMARY_ANGLE)
    if front is not None:
        return front
    for label in _TRIPOSG_FALLBACK_ANGLES:
        img = _find_angle_image(sheets_dir, label)
        if img is not None:
            return img
    return None


# ------------------------------------------------------------------
# Core -- generation TripoSG + nettoyage Blender
# ------------------------------------------------------------------

def _run_blender_clean(
    glb_in: Path,
    glb_out: Path,
    blender_exe: str,
    dry_run: bool,
) -> bool:
    """Nettoie le GLB TripoSG via Blender headless."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(_BLENDER_CLEAN_SCRIPT)
        script_path = tmp.name

    glb_out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        blender_exe,
        "--background",
        "--python", script_path,
        "--",
        "--glb-in", str(glb_in),
        "--glb-out", str(glb_out),
    ]

    if dry_run:
        print(f"    DRY-RUN Blender : {' '.join(cmd)}")
        return False

    print(f"    Blender nettoyage GLB...")
    result = subprocess.run(cmd, capture_output=False)
    try:
        Path(script_path).unlink()
    except OSError:
        pass

    if result.returncode != 0:
        print(
            f"    [WARN] Blender retourne code {result.returncode} -- verifier les logs",
            file=sys.stderr,
        )
        return False

    return glb_out.exists()


def process_character(
    slug: str,
    character: dict[str, Any],
    blender_exe: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Genere le mesh 3D d'un personnage via TripoSG + Blender.

    Returns:
        dict avec {"slug", "status", "triposg_glb", "clean_glb", "error"}.
    """
    triposg_glb = ASSETS_CHARS_DIR / f"{slug}_triposg.glb"
    clean_glb = ASSETS_CHARS_DIR / f"{slug}_clean.glb"
    status_file = ASSETS_CHARS_DIR / f"{slug}_status.json"

    result: dict[str, Any] = {
        "slug": slug,
        "status": "pending",
        "triposg_glb": str(triposg_glb),
        "clean_glb": str(clean_glb),
        "error": None,
    }

    print(f"\n  [{slug}] {character['full_name']}")
    print(f"    TripoSG GLB : {triposg_glb}")
    print(f"    Clean GLB   : {clean_glb}")

    # -- Trouver l'image source
    front_img = _find_triposg_image(slug)
    if front_img:
        print(f"    Image source : {front_img.name}")
    else:
        msg = (
            f"Aucune image trouvee dans {SHEETS_BASE / slug}. "
            f"Lancer : python production/gen_character_sheets.py --character {slug} --execute"
        )
        print(f"    [ERROR] {msg}")
        result["status"] = "missing_sheets"
        result["error"] = msg
        return result

    # -- Skip si clean GLB existe deja
    if clean_glb.exists():
        print(f"    SKIP : {clean_glb.name} existe deja")
        result["status"] = "done"
        return result

    if dry_run:
        from aiprod_adaptation.image_gen.triposg_adapter import TripoSGAdapter, TripoSGError
        print(f"    DRY-RUN : verification installation TripoSG...")
        try:
            TripoSGAdapter()
            print(f"    [OK] TripoSG installe et pret")
            print(f"    Cout : gratuit (inference locale)")
            print(f"    GPU  : 8 Go VRAM min requis")
        except TripoSGError as exc:
            print(f"    [WARN] TripoSG non installe :")
            for line in str(exc).splitlines():
                print(f"           {line}")
        result["status"] = "dry-run"
        return result

    # -- Step 1 : TripoSG inference
    if not triposg_glb.exists():
        from aiprod_adaptation.image_gen.triposg_adapter import TripoSGAdapter

        adapter = TripoSGAdapter()
        print(f"    [1/2] TripoSG inference ({front_img.name})...")
        ASSETS_CHARS_DIR.mkdir(parents=True, exist_ok=True)
        adapter.generate(image_path=front_img, output_path=triposg_glb)
        print(f"    [OK] GLB TripoSG : {triposg_glb}")
    else:
        print(f"    SKIP TripoSG : {triposg_glb.name} existe deja")

    # -- Step 2 : Blender nettoyage
    print(f"    [2/2] Blender nettoyage + export clean GLB...")
    ok = _run_blender_clean(triposg_glb, clean_glb, blender_exe, dry_run=False)
    if ok:
        print(f"    [OK] Clean GLB : {clean_glb}")
        result["status"] = "done"
    else:
        print(f"    [WARN] Blender echoue -- utilisation du GLB TripoSG brut")
        import shutil
        clean_glb.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(triposg_glb, clean_glb)
        result["status"] = "done_no_clean"

    # -- Sauvegarder statut
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return result


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genere les meshes 3D personnages via TripoSG local + Blender."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--character", help="Cle personnage unique (ex: nara).")
    group.add_argument("--all", action="store_true", help="Traiter tous les personnages.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Lance l'inference TripoSG. Sans ce flag : dry-run.",
    )
    parser.add_argument(
        "--blender",
        default=None,
        help="Chemin vers blender.exe. Defaut : auto-detect.",
    )
    args = parser.parse_args()

    if not args.character and not args.all:
        parser.print_help()
        return 1

    _load_env()

    characters: dict[str, Any] = json.loads(
        CHARACTERS_FILE.read_text(encoding="utf-8")
    )
    blender_exe = args.blender or os.environ.get("BLENDER_EXECUTABLE", _DEFAULT_BLENDER_EXE)
    dry_run = not args.execute

    selection = (
        characters
        if args.all
        else {args.character: characters[args.character]}
        if args.character in characters
        else {}
    )

    if not selection:
        print(
            f"ERROR: personnage '{args.character}' inconnu. "
            f"Valides : {list(characters)}",
            file=sys.stderr,
        )
        return 1

    print("=" * 60)
    print("gen_character_meshes.py -- Meshes 3D TripoSG V4")
    print("=" * 60)
    print(f"  Personnages : {list(selection)}")
    print(f"  Blender     : {blender_exe}")
    print(f"  Mode        : {'DRY-RUN' if dry_run else 'EXECUTE'}")
    if dry_run:
        print()
        print("  NOTE : inference locale gratuite. Ajouter --execute pour lancer.")

    results: list[dict[str, Any]] = []
    for slug, char in selection.items():
        r = process_character(slug, char, blender_exe, dry_run)
        results.append(r)

    done = [r for r in results if r["status"] in ("done", "done_no_clean")]
    pending = [r for r in results if r["status"] not in ("done", "done_no_clean")]

    print()
    print("=" * 60)
    print(f"  Meshes prets      : {len(done)}/{len(results)}")
    if pending:
        print(f"  En attente        : {[r['slug'] for r in pending]}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
