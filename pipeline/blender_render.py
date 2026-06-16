"""
pipeline/blender_render.py
===========================
Script Blender headless — rendu 3D par shot pour le pipeline V4.

USAGE (deux modes) :

  Mode 1 — exécution directe via Blender headless :
    blender --background --python pipeline/blender_render.py -- \\
        --shot SCN_002_SHOT_001 \\
        --assets-dir production/assets_3d \\
        --animations production/shot_animations.json \\
        --storyboard production/storyboard.json \\
        --out-dir production/renders/SCN_002_SHOT_001 \\
        --fps 24 --duration 5

  Mode 2 — appel depuis Python (via subprocess) :
    from pipeline.blender_render import render_shot
    render_shot("SCN_002_SHOT_001", out_dir=Path("production/renders/SCN_002_SHOT_001"))

Outputs par shot :
    frames/frame_{NNNN:04d}.png         — rendu couleur Cycles
    depth/depth_{NNNN:04d}.exr          — Z-depth (utilisé par ControlNet)
    normals/normals_{NNNN:04d}.exr      — Normal pass (complément ControlNet)
    metadata.json                       — paramètres de rendu

Dépendances :
    Blender 4.5+ installé, accessible via BLENDER_EXECUTABLE dans .env
    Assets GLB/FBX dans production/assets_3d/
    shot_animations.json pour le mapping camera + animations

Coût : gratuit (rendu local).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

STORYBOARD_FILE = ROOT / "production/storyboard.json"
ANIMATIONS_FILE = ROOT / "production/shot_animations.json"
ASSETS_DIR = ROOT / "production/assets_3d"
RENDERS_DIR = ROOT / "production/renders"

_DEFAULT_FPS = 24
_DEFAULT_BLENDER_EXE = "blender"


# ------------------------------------------------------------------
# Public API — appelé depuis Python
# ------------------------------------------------------------------

def render_shot(
    shot_id: str,
    out_dir: Path | None = None,
    fps: int = _DEFAULT_FPS,
    blender_exe: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Lance le rendu Blender headless pour un shot.

    Args:
        shot_id:     Identifiant du shot (ex: 'SCN_002_SHOT_001').
        out_dir:     Répertoire de sortie. Défaut: production/renders/{shot_id}/
        fps:         Framerate. Défaut: 24.
        blender_exe: Chemin vers l'exécutable Blender.
        dry_run:     Si True, affiche la commande sans l'exécuter.

    Returns:
        dict avec {"out_dir", "frame_count", "metadata_path"}.
    """
    _load_env()
    exe = blender_exe or os.environ.get("BLENDER_EXECUTABLE", _DEFAULT_BLENDER_EXE)
    out = out_dir or (RENDERS_DIR / shot_id)

    storyboard = _load_json(STORYBOARD_FILE)
    animations = _load_json(ANIMATIONS_FILE)
    shot = _find_shot(storyboard, shot_id)
    if shot is None:
        raise ValueError(f"Shot '{shot_id}' introuvable dans storyboard.json")

    anim_cfg = animations["shots"].get(shot_id, {})
    duration_sec: int = shot.get("duration_sec", 5)
    frame_count = duration_sec * fps

    cmd = _build_blender_cmd(
        exe=exe,
        shot_id=shot_id,
        shot=shot,
        anim_cfg=anim_cfg,
        out_dir=out,
        fps=fps,
        frame_count=frame_count,
    )

    if dry_run:
        print("DRY-RUN — commande Blender :")
        print("  " + " ".join(str(c) for c in cmd))
        return {"out_dir": str(out), "frame_count": frame_count, "metadata_path": None}

    out.mkdir(parents=True, exist_ok=True)
    print(f"[blender_render] Rendu {shot_id} → {out} ({frame_count} frames @ {fps}fps)")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        raise RuntimeError(f"Blender a terminé avec code {result.returncode} pour {shot_id}")

    metadata_path = out / "metadata.json"
    return {"out_dir": str(out), "frame_count": frame_count, "metadata_path": str(metadata_path)}


# ------------------------------------------------------------------
# Blender internal — exécuté DANS le contexte bpy quand lancé via
# `blender --background --python blender_render.py -- [args]`
# ------------------------------------------------------------------

def _blender_main() -> None:
    """Point d'entrée quand ce script est exécuté directement par Blender."""
    import argparse

    # Les arguments passés après -- sont pour notre script
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser()
    parser.add_argument("--shot", required=True)
    parser.add_argument("--assets-dir", default=str(ASSETS_DIR))
    parser.add_argument("--animations", default=str(ANIMATIONS_FILE))
    parser.add_argument("--storyboard", default=str(STORYBOARD_FILE))
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--fps", type=int, default=_DEFAULT_FPS)
    parser.add_argument("--duration", type=int, default=5)
    args = parser.parse_args(argv)

    try:
        import bpy
    except ImportError:
        print("ERROR: ce script doit être lancé via Blender headless.", file=sys.stderr)
        sys.exit(1)

    _blender_setup_scene(
        bpy=bpy,
        shot_id=args.shot,
        assets_dir=Path(args.assets_dir),
        animations_file=Path(args.animations),
        storyboard_file=Path(args.storyboard),
        out_dir=Path(args.out_dir),
        fps=args.fps,
        duration=args.duration,
    )


def _blender_setup_scene(
    bpy: Any,
    shot_id: str,
    assets_dir: Path,
    animations_file: Path,
    storyboard_file: Path,
    out_dir: Path,
    fps: int,
    duration: int,
) -> None:
    """Configure et lance le rendu depuis l'API bpy."""
    scene = bpy.context.scene
    storyboard = _load_json(storyboard_file)
    animations = _load_json(animations_file)
    shot = _find_shot(storyboard, shot_id)
    if shot is None:
        raise ValueError(f"Shot '{shot_id}' introuvable")

    anim_cfg = animations["shots"].get(shot_id, {})
    frame_count = duration * fps

    # ── Nettoyer la scène par défaut
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # ── Paramètres de rendu — Cycles (photorealistic)
    scene.render.engine = "CYCLES"
    cycles = scene.cycles
    cycles.samples = 128          # qualité production (augmenter pour final)
    cycles.use_denoising = True
    cycles.denoiser = "OPENIMAGEDENOISE"
    # Utiliser GPU si disponible
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "CUDA"  # RTX 5080 — fallback CPU si absent
    try:
        prefs.get_devices()
        for device in prefs.devices:
            device.use = True
        scene.cycles.device = "GPU"
    except Exception:
        scene.cycles.device = "CPU"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.fps = fps
    scene.frame_start = 1
    scene.frame_end = frame_count
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"

    # ── Output passes
    scene.use_nodes = True
    _setup_render_passes(bpy, scene, out_dir)

    # ── Charger décor GLB
    location_key = shot.get("location_key", "")
    decor_glb = assets_dir / "locations" / f"{location_key}.glb"
    if decor_glb.exists():
        bpy.ops.import_scene.gltf(filepath=str(decor_glb))
        print(f"[blender_render] Décor chargé : {decor_glb.name}")
    else:
        print(f"[blender_render] [WARN] GLB decor absent : {decor_glb}")

    # ── Charger personnages (Rodin GLB clean > fallback Mixamo FBX)
    char_animations = anim_cfg.get("animations", {})
    char_layout = anim_cfg.get("characters_layout", {})
    for char_slug, char_anim in char_animations.items():
        # Priorite 1 : GLB Rodin nettoye par Blender
        glb_path = assets_dir / "characters" / f"{char_slug}_clean.glb"
        # Priorite 2 : FBX Mixamo (workflow precedent)
        fbx_path = assets_dir / "characters" / f"{char_slug}_mixamo.fbx"
        layout = char_layout.get(char_slug, {})
        if glb_path.exists():
            bpy.ops.import_scene.gltf(filepath=str(glb_path))
            print(f"[blender_render] Personnage charge (Rodin) : {glb_path.name}")
            _position_character(bpy, char_slug, layout, char_anim)
        elif fbx_path.exists():
            bpy.ops.import_scene.fbx(filepath=str(fbx_path))
            print(f"[blender_render] Personnage charge (Mixamo) : {fbx_path.name}")
            _position_character(bpy, char_slug, layout, char_anim)
        else:
            print(f"[blender_render] [WARN] Mesh absent pour {char_slug} "
                  f"(cherche {glb_path.name} ou {fbx_path.name})")

    # ── Configurer caméra
    cam_cfg = anim_cfg.get("camera", {})
    _setup_camera(bpy, scene, cam_cfg)

    # ── Configurer éclairage de base
    _setup_lighting(bpy, scene, shot)

    # ── Lancer le rendu
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(frames_dir / "frame_")
    bpy.ops.render.render(animation=True)

    # ── Sauvegarder metadata
    metadata = {
        "shot_id": shot_id,
        "fps": fps,
        "frame_count": frame_count,
        "location_key": location_key,
        "characters": list(char_animations.keys()),
        "camera": cam_cfg,
        "render_engine": "CYCLES",
        "resolution": "1920x1080",
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[blender_render] [OK] {shot_id} rendu -- {frame_count} frames dans {out_dir}")


def _setup_render_passes(bpy: Any, scene: Any, out_dir: Path) -> None:
    """Configure les passes de rendu : couleur + depth EXR + normals EXR."""
    view_layer = scene.view_layers[0]
    view_layer.use_pass_z = True
    view_layer.use_pass_normal = True

    tree = scene.node_tree
    tree.nodes.clear()

    render_layers = tree.nodes.new("CompositorNodeRLayers")
    composite = tree.nodes.new("CompositorNodeComposite")
    file_output_depth = tree.nodes.new("CompositorNodeOutputFile")
    file_output_normals = tree.nodes.new("CompositorNodeOutputFile")

    # Depth output
    depth_dir = out_dir / "depth"
    depth_dir.mkdir(parents=True, exist_ok=True)
    file_output_depth.base_path = str(depth_dir)
    file_output_depth.file_slots[0].path = "depth_"
    file_output_depth.format.file_format = "OPEN_EXR"
    file_output_depth.format.color_depth = "32"

    # Normals output
    normals_dir = out_dir / "normals"
    normals_dir.mkdir(parents=True, exist_ok=True)
    file_output_normals.base_path = str(normals_dir)
    file_output_normals.file_slots[0].path = "normals_"
    file_output_normals.format.file_format = "OPEN_EXR"
    file_output_normals.format.color_depth = "32"

    # Connexions
    links = tree.links
    links.new(render_layers.outputs["Image"], composite.inputs["Image"])
    links.new(render_layers.outputs["Depth"], file_output_depth.inputs[0])
    links.new(render_layers.outputs["Normal"], file_output_normals.inputs[0])


def _setup_camera(bpy: Any, scene: Any, cam_cfg: dict[str, Any]) -> None:
    """Crée et positionne la caméra selon la config du shot."""
    bpy.ops.object.camera_add()
    cam_obj = bpy.context.active_object
    cam = cam_obj.data
    scene.camera = cam_obj

    fov_mm: float = cam_cfg.get("fov_mm", 50)
    cam.lens = fov_mm
    cam.sensor_width = 36.0  # 35mm équivalent

    height_m: float = cam_cfg.get("height_m", 1.5)
    distance_m: float = cam_cfg.get("distance_m") or 3.0
    dutch_deg: float = cam_cfg.get("dutch_tilt_deg", 0)

    import mathutils
    cam_obj.location = mathutils.Vector((0.0, -distance_m, height_m))
    cam_obj.rotation_euler = mathutils.Euler(
        (1.1781, 0.0, 0.0 + (dutch_deg * 3.14159 / 180)),
        "XYZ",
    )


def _setup_lighting(bpy: Any, scene: Any, shot: dict[str, Any]) -> None:
    """Ajoute un éclairage de base selon le context du shot.

    L'éclairage est volontairement simple (EEVEE) — la stylisation IA le remplace.
    """
    bpy.ops.object.light_add(type="AREA")
    light = bpy.context.active_object
    light.data.energy = 800
    light.data.size = 3.0

    import mathutils
    light.location = mathutils.Vector((2.0, -2.0, 4.0))
    light.rotation_euler = mathutils.Euler((0.785, 0.0, 0.785), "XYZ")


def _position_character(
    bpy: Any, char_slug: str, layout: dict[str, str], anim_cfg: dict[str, Any]
) -> None:
    """Positionne le personnage importé selon le layout du shot."""
    import mathutils

    position_key = layout.get("position", "centre")
    facing = layout.get("facing", "screen_right")

    position_map: dict[str, tuple[float, float, float]] = {
        "centre": (0.0, 0.0, 0.0),
        "centre_left": (-0.8, 0.0, 0.0),
        "centre_right": (0.8, 0.0, 0.0),
        "right_of_table": (0.6, 0.0, 0.0),
        "left_of_table": (-0.6, 0.0, 0.0),
        "right_side": (0.9, 0.0, 0.0),
        "left_side": (-0.9, 0.0, 0.0),
        "right": (0.7, 0.0, 0.0),
        "left": (-0.7, 0.0, 0.0),
        "foreground": (0.0, -0.5, 0.0),
        "foreground_left": (-0.5, -0.5, 0.0),
        "midground_left": (-0.5, 1.0, 0.0),
        "behind_nara": (0.3, 1.5, 0.0),
        "left_of_display": (-0.5, 0.2, 0.0),
        "right_of_display": (0.5, 0.2, 0.0),
    }
    facing_map: dict[str, float] = {
        "screen_right": 0.0,
        "screen_left": 3.14159,
        "depth": 1.5708,
    }

    pos = position_map.get(position_key, (0.0, 0.0, 0.0))
    rot_z = facing_map.get(facing, 0.0)

    # L'armature importée par FBX est l'objet actif
    obj = bpy.context.active_object
    if obj is not None:
        obj.location = mathutils.Vector(pos)
        obj.rotation_euler = mathutils.Euler((0.0, 0.0, rot_z), "XYZ")


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


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_shot(storyboard: dict[str, Any], shot_id: str) -> dict[str, Any] | None:
    for shot in storyboard.get("shots", []):
        if shot["shot_id"] == shot_id:
            return shot
    return None


def _build_blender_cmd(
    exe: str,
    shot_id: str,
    shot: dict[str, Any],
    anim_cfg: dict[str, Any],
    out_dir: Path,
    fps: int,
    frame_count: int,
) -> list[str]:
    """Construit la commande Blender headless."""
    script_path = Path(__file__).resolve()
    duration = shot.get("duration_sec", frame_count // fps)
    return [
        exe,
        "--background",
        "--python", str(script_path),
        "--",
        "--shot", shot_id,
        "--assets-dir", str(ASSETS_DIR),
        "--animations", str(ANIMATIONS_FILE),
        "--storyboard", str(STORYBOARD_FILE),
        "--out-dir", str(out_dir),
        "--fps", str(fps),
        "--duration", str(duration),
    ]


# ------------------------------------------------------------------
# CLI — invocation depuis Python directement (hors Blender)
# ------------------------------------------------------------------

def _cli_main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Lance le rendu Blender headless pour un shot.")
    parser.add_argument("--shot", required=True, help="Shot ID (ex: SCN_002_SHOT_001)")
    parser.add_argument("--out-dir", help="Répertoire de sortie")
    parser.add_argument("--fps", type=int, default=_DEFAULT_FPS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--blender", default=None, help="Chemin vers l'exécutable Blender")
    args = parser.parse_args()

    out = Path(args.out_dir) if args.out_dir else None
    result = render_shot(
        shot_id=args.shot,
        out_dir=out,
        fps=args.fps,
        blender_exe=args.blender,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))
    return 0


# Point d'entrée : détecter si on est dans Blender ou hors Blender
if __name__ == "__main__":
    try:
        import bpy  # noqa: F401
        _blender_main()
    except ImportError:
        sys.exit(_cli_main())
