"""
production/gen_metahuman_rigs.py
=================================
Importe les FBX MetaHuman exportes depuis UE5 et les prepare pour Blender Cycles.

PREREQUIS :
  1. Epic Games Launcher + UE5 installe
  2. MetaHumans crees sur metahuman.unrealengine.com
  3. Exported depuis UE5 Quixel Bridge vers production/metahumans/{slug}.fbx

WORKFLOW :
  Pour chaque personnage :
    1. Import FBX MetaHuman dans Blender (via bpy ou subprocess headless)
    2. Nettoyage du rig (suppression des bones UE5 inutiles)
    3. Export FBX compatible Mixamo vers production/assets_3d/characters/{slug}_clean.fbx
    4. [Manuel] Upload sur mixamo.com → Auto-Rig → Download FBX with skin
    5. Import FBX Mixamo rigge → production/assets_3d/characters/{slug}_mixamo.fbx

USAGE :
    python production/gen_metahuman_rigs.py --character nara
    python production/gen_metahuman_rigs.py --all
    python production/gen_metahuman_rigs.py --character nara --dry-run

OUTPUTS :
    production/assets_3d/characters/{slug}_clean.fbx   -- rig nettoye pour Mixamo
    production/metahumans/{slug}_status.json            -- statut par perso

Structure attendue des inputs :
    production/metahumans/nara.fbx      -- export UE5 Quixel Bridge
    production/metahumans/mira.fbx
    production/metahumans/elian.fbx
    production/metahumans/vale.fbx
    production/metahumans/rook.fbx
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CHARACTERS_FILE = ROOT / "production/characters.json"
METAHUMANS_DIR = ROOT / "production/metahumans"
ASSETS_CHARS_DIR = ROOT / "production/assets_3d/characters"

_DEFAULT_BLENDER_EXE = (
    r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
    if sys.platform == "win32"
    else "blender"
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


def _load_characters() -> dict[str, Any]:
    return json.loads(CHARACTERS_FILE.read_text(encoding="utf-8"))


def _write_status(slug: str, status: dict[str, Any]) -> None:
    METAHUMANS_DIR.mkdir(parents=True, exist_ok=True)
    path = METAHUMANS_DIR / f"{slug}_status.json"
    path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------
# Etape 1 — Import FBX MetaHuman + export clean pour Mixamo
# ------------------------------------------------------------------

_BLENDER_CLEAN_SCRIPT = '''
import bpy
import sys
import json
from pathlib import Path

argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--fbx-in", required=True)
parser.add_argument("--fbx-out", required=True)
args = parser.parse_args(argv)

fbx_in = Path(args.fbx_in)
fbx_out = Path(args.fbx_out)
fbx_out.parent.mkdir(parents=True, exist_ok=True)

# Nettoyer la scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Importer le FBX MetaHuman
bpy.ops.import_scene.fbx(filepath=str(fbx_in))
print(f"[clean_rig] Importe : {fbx_in.name}")

# Supprimer les objets non-mesh et non-armature (cameras, lights UE5, etc.)
to_delete = []
for obj in bpy.data.objects:
    if obj.type not in ("MESH", "ARMATURE"):
        to_delete.append(obj)
for obj in to_delete:
    bpy.data.objects.remove(obj, do_unlink=True)

# Remettre a l\'echelle 1.0 (UE5 exporte a x=100)
for obj in bpy.data.objects:
    obj.scale = (1.0, 1.0, 1.0)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.transform_apply(scale=True)

# Exporter FBX clean pour Mixamo
bpy.ops.export_scene.fbx(
    filepath=str(fbx_out),
    use_selection=False,
    apply_unit_scale=True,
    apply_scale_options="FBX_SCALE_NONE",
    bake_space_transform=True,
    object_types={"ARMATURE", "MESH"},
    mesh_smooth_type="FACE",
    add_leaf_bones=False,
)
print(f"[clean_rig] Exporte clean : {fbx_out.name}")
'''


def _clean_metahuman_fbx(
    slug: str,
    fbx_in: Path,
    fbx_out: Path,
    blender_exe: str,
    dry_run: bool,
) -> bool:
    """Importe le FBX UE5 et exporte une version clean pour Mixamo."""
    if dry_run:
        print(f"    [DRY-RUN] blender --background --python <clean_script> -- --fbx-in {fbx_in.name} --fbx-out {fbx_out.name}")
        return True

    if fbx_out.exists():
        print(f"    [SKIP] {fbx_out.name} existe deja")
        return True

    # Ecrire le script inline dans un fichier temporaire
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(_BLENDER_CLEAN_SCRIPT)
        script_path = tmp.name

    cmd = [
        blender_exe,
        "--background",
        "--python", script_path,
        "--",
        "--fbx-in", str(fbx_in),
        "--fbx-out", str(fbx_out),
    ]
    print(f"    Nettoyage rig via Blender headless...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    Path(script_path).unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"    [FAIL] Blender clean_rig code={result.returncode}", file=sys.stderr)
        print(result.stderr[-2000:], file=sys.stderr)
        return False

    print(f"    [OK] {fbx_out.name} genere")
    return True


# ------------------------------------------------------------------
# Etape 2 — Import FBX Mixamo rigge (apres upload manuel sur mixamo.com)
# ------------------------------------------------------------------

def _check_mixamo_fbx(slug: str, assets_dir: Path) -> bool:
    """Verifie la presence du FBX Mixamo rigge."""
    mixamo_fbx = assets_dir / f"{slug}_mixamo.fbx"
    if mixamo_fbx.exists():
        print(f"    [OK] {mixamo_fbx.name} present")
        return True
    print(f"    [WAIT] {mixamo_fbx.name} absent")
    print(f"           -> Uploader production/assets_3d/characters/{slug}_clean.fbx sur mixamo.com")
    print(f"           -> Choisir une animation T-Pose (ou Without Skin)")
    print(f"           -> Telecharger FBX with skin vers production/assets_3d/characters/{slug}_mixamo.fbx")
    return False


# ------------------------------------------------------------------
# Orchestration principale
# ------------------------------------------------------------------

def process_character(
    slug: str,
    character: dict[str, Any],
    blender_exe: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Traite un personnage complet : FBX in → clean → check Mixamo."""
    status: dict[str, Any] = {
        "slug": slug,
        "full_name": character["full_name"],
        "metahuman_fbx": None,
        "clean_fbx": None,
        "mixamo_fbx": None,
        "ready_for_blender": False,
    }

    fbx_in = METAHUMANS_DIR / f"{slug}.fbx"
    fbx_out = ASSETS_CHARS_DIR / f"{slug}_clean.fbx"
    mixamo_fbx = ASSETS_CHARS_DIR / f"{slug}_mixamo.fbx"

    print(f"\n  [{slug}] {character['full_name']}")
    print(f"    Input FBX    : {fbx_in}")
    print(f"    Clean FBX    : {fbx_out}")
    print(f"    Mixamo FBX   : {mixamo_fbx}")

    # Verifier presence du FBX MetaHuman
    if not fbx_in.exists():
        print(f"    [WAIT] {fbx_in.name} absent")
        print(f"           -> Creer le MetaHuman sur metahuman.unrealengine.com")
        print(f"           -> Exporter depuis UE5 Quixel Bridge vers {fbx_in}")
        _write_status(slug, status)
        return status

    status["metahuman_fbx"] = str(fbx_in)

    # Etape 1 — Nettoyage pour Mixamo
    print(f"    [1/2] Nettoyage rig MetaHuman...")
    ok = _clean_metahuman_fbx(slug, fbx_in, fbx_out, blender_exe, dry_run)
    if not ok:
        _write_status(slug, status)
        return status
    status["clean_fbx"] = str(fbx_out)

    # Etape 2 — Verifier FBX Mixamo (etape manuelle)
    print(f"    [2/2] Verification FBX Mixamo rigge...")
    if _check_mixamo_fbx(slug, ASSETS_CHARS_DIR):
        status["mixamo_fbx"] = str(mixamo_fbx)
        status["ready_for_blender"] = True

    _write_status(slug, status)
    return status


def main() -> int:
    _load_env()

    parser = argparse.ArgumentParser(
        description="gen_metahuman_rigs.py — Preparation rigs MetaHuman pour Blender Cycles"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--character", metavar="SLUG", help="Traiter un seul personnage")
    group.add_argument("--all", action="store_true", help="Traiter tous les personnages")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Afficher sans executer (defaut)")
    parser.add_argument("--execute", action="store_true",
                        help="Executer reellement")
    args = parser.parse_args()

    execute = args.execute
    dry_run = not execute

    blender_exe = os.environ.get("BLENDER_EXECUTABLE", _DEFAULT_BLENDER_EXE)
    characters = _load_characters()

    if args.character:
        slugs = [args.character]
    else:
        slugs = list(characters.keys())

    print("=" * 60)
    print("gen_metahuman_rigs.py — Rigs MetaHuman V4")
    print("=" * 60)
    print(f"  Personnages : {slugs}")
    print(f"  Blender     : {blender_exe}")
    print(f"  Mode        : {'DRY-RUN' if dry_run else 'EXECUTE'}")
    print()
    print("WORKFLOW REQUIS :")
    print("  1. Creer chaque perso sur metahuman.unrealengine.com")
    print("  2. UE5 Quixel Bridge -> Export FBX -> production/metahumans/{slug}.fbx")
    print("  3. Ce script nettoie le rig et exporte pour Mixamo")
    print("  4. Uploader {slug}_clean.fbx sur mixamo.com -> FBX with skin")
    print("  5. Sauvegarder sous production/assets_3d/characters/{slug}_mixamo.fbx")
    print()

    ASSETS_CHARS_DIR.mkdir(parents=True, exist_ok=True)
    METAHUMANS_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for slug in slugs:
        if slug not in characters:
            print(f"[WARN] Personnage '{slug}' inconnu dans characters.json", file=sys.stderr)
            continue
        result = process_character(
            slug=slug,
            character=characters[slug],
            blender_exe=blender_exe,
            dry_run=dry_run,
        )
        results.append(result)

    # Rapport final
    ready = [r for r in results if r["ready_for_blender"]]
    waiting_mh = [r for r in results if not r["metahuman_fbx"]]
    waiting_mx = [r for r in results if r["clean_fbx"] and not r["mixamo_fbx"]]

    print()
    print("=" * 60)
    print(f"  Prets pour Blender Cycles : {len(ready)}/{len(results)}")
    if waiting_mh:
        print(f"  En attente FBX MetaHuman  : {[r['slug'] for r in waiting_mh]}")
    if waiting_mx:
        print(f"  En attente Mixamo upload  : {[r['slug'] for r in waiting_mx]}")
        print()
        print("  -> Uploader les FBX clean sur https://www.mixamo.com")
        print("     Choisir T-Pose > Download > FBX with skin")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
