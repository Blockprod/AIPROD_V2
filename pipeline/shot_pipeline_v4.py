"""
pipeline/shot_pipeline_v4.py
=============================
Pipeline de stylisation frame-par-frame V4 — BLOC C.

NE PAS MODIFIER pipeline/shot_pipeline.py (v2 verrouillé 2026-04-30).

Architecture :
    ENTRÉE : frames PNG (EEVEE) + depth EXR + character_ref PNG
    TRAITEMENT : ControlNet (depth) + IP-Adapter (char ref) + FLUX/Seedream
    SORTIE : frames PNG stylisées

Deux backends :
    ComfyUIBackend   — local, RTX 5080 requis (VRAM ≥ 12GB)
    ReplicateBackend — API Replicate, fonctionne sur toute machine

Usage :
    python pipeline/shot_pipeline_v4.py \\
        --shot SCN_002_SHOT_001 \\
        --renders-dir production/renders \\
        --char-refs production/character_refs \\
        --out-dir production/stylized \\
        --backend replicate \\
        --dry-run

Coûts :
    ComfyUI local   : ~$0.00/frame
    Replicate       : ~$0.04/frame (4200 frames EP01 = ~$168)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STORYBOARD_FILE = ROOT / "production/storyboard.json"
ANIMATIONS_FILE = ROOT / "production/shot_animations.json"
LOCATIONS_FILE = ROOT / "production/locations.json"
CHAR_REFS_DIR = ROOT / "production/character_refs"
CHAR_FACES_DIR = ROOT / "production/character_faces"
LOCATION_REFS_DIR = ROOT / "production/location_refs"
RENDERS_DIR = ROOT / "production/renders"
STYLIZED_DIR = ROOT / "production/stylized"

_DEFAULT_FPS = 24
_COST_PER_FRAME_REPLICATE = 0.04
_REPLICATE_CONTROLNET_MODEL = "jagilley/controlnet-normal:cc8067cf-c4a9-4e28-b088-3d3741f7e1e0"


# ------------------------------------------------------------------
# Backend abstraction
# ------------------------------------------------------------------

class StylizationBackend(ABC):
    @abstractmethod
    def stylize_frame(
        self,
        frame_png: Path,
        depth_exr: Path,
        char_ref_png: Path,
        prompt: str,
        seed: int,
        shot_type: str,
    ) -> bytes:
        """Stylise une frame PNG. Retourne les bytes PNG stylisés."""
        ...

    @property
    @abstractmethod
    def cost_per_frame(self) -> float:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class ReplicateBackend(StylizationBackend):
    """Backend Replicate — ControlNet depth + IP-Adapter + FLUX/Seedream."""

    def __init__(self) -> None:
        token = os.environ.get("REPLICATE_API_TOKEN", "")
        if not token:
            raise RuntimeError("REPLICATE_API_TOKEN manquant dans .env")

    @property
    def name(self) -> str:
        return "replicate"

    @property
    def cost_per_frame(self) -> float:
        return _COST_PER_FRAME_REPLICATE

    def stylize_frame(
        self,
        frame_png: Path,
        depth_exr: Path,
        char_ref_png: Path,
        prompt: str,
        seed: int,
        shot_type: str,
    ) -> bytes:
        import replicate

        # Convertir depth EXR → PNG 8-bit pour ControlNet
        depth_png_bytes = _exr_depth_to_png(depth_exr)
        char_ref_b64 = _img_to_b64(char_ref_png)

        output = replicate.run(
            _REPLICATE_CONTROLNET_MODEL,
            input={
                "prompt": prompt,
                "image": char_ref_b64,
                "control_image": _bytes_to_b64(depth_png_bytes, "image/png"),
                "seed": seed,
                "num_inference_steps": 28,
                "guidance_scale": 7.5,
                "controlnet_conditioning_scale": 0.8,
            },
        )
        url = str(output[0]) if isinstance(output, list) else str(output)
        import urllib.request
        with urllib.request.urlopen(url, timeout=120) as resp:
            return resp.read()


class ComfyUIBackend(StylizationBackend):
    """Backend ComfyUI local — RTX 5080 requis (VRAM ≥ 12GB).

    Requiert ComfyUI en cours d'exécution sur localhost:8188.
    """

    def __init__(self, comfyui_url: str = "http://localhost:8188") -> None:
        self._url = comfyui_url

    @property
    def name(self) -> str:
        return "comfyui"

    @property
    def cost_per_frame(self) -> float:
        return 0.0

    def stylize_frame(
        self,
        frame_png: Path,
        depth_exr: Path,
        char_ref_png: Path,
        prompt: str,
        seed: int,
        shot_type: str,
    ) -> bytes:
        """Stylise une frame via ComfyUI local.

        Protocole :
          1. Résout le normals EXR si disponible (meilleur guidage ControlNet Normal)
             sinon utilise depth EXR converti en PNG 8-bit.
          2. Upload control image + char ref via /upload/image.
          3. Soumet le workflow et attend le résultat via polling /history.
        """
        import urllib.request
        import uuid

        client_id = str(uuid.uuid4())
        uid = client_id[:8]

        # Résoudre normals EXR (produit par blender_render.py)
        frame_num = depth_exr.stem.split("_")[-1]
        normals_exr = depth_exr.parent.parent / "normals" / f"normals_{frame_num}.exr"
        if normals_exr.exists():
            control_bytes = _exr_normals_to_png(normals_exr)
            control_name = f"normals_{uid}.png"
        else:
            control_bytes = _exr_depth_to_png(depth_exr)
            control_name = f"depth_{uid}.png"

        char_bytes = char_ref_png.read_bytes()
        char_name = f"charref_{uid}.png"

        # Upload vers ComfyUI input store
        uploaded_control = _upload_to_comfyui(self._url, control_bytes, control_name)
        uploaded_char = _upload_to_comfyui(self._url, char_bytes, char_name)

        workflow = _build_comfyui_workflow(
            control_image_filename=uploaded_control,
            char_ref_filename=uploaded_char,
            prompt=prompt,
            seed=seed,
        )
        payload = json.dumps({"prompt": workflow, "client_id": client_id}).encode()

        req = urllib.request.Request(
            f"{self._url}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            prompt_data = json.loads(resp.read())

        prompt_id: str = prompt_data["prompt_id"]
        return self._poll_result(prompt_id)

    def _poll_result(self, prompt_id: str) -> bytes:
        import urllib.request

        deadline = time.monotonic() + 300  # 5 minutes max par frame
        while time.monotonic() < deadline:
            with urllib.request.urlopen(f"{self._url}/history/{prompt_id}", timeout=10) as resp:
                history = json.loads(resp.read())
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_outputs in outputs.values():
                    images = node_outputs.get("images", [])
                    if images:
                        img_info = images[0]
                        img_url = f"{self._url}/view?filename={img_info['filename']}&subfolder={img_info.get('subfolder','')}&type={img_info.get('type','output')}"
                        with urllib.request.urlopen(img_url, timeout=60) as img_resp:
                            return img_resp.read()
            time.sleep(1)
        raise RuntimeError(f"ComfyUI prompt {prompt_id} timeout (5 min)")


class NullStylizationBackend(StylizationBackend):
    """Backend nul pour tests CI — retourne les bytes de la frame source inchangée."""

    @property
    def name(self) -> str:
        return "null"

    @property
    def cost_per_frame(self) -> float:
        return 0.0

    def stylize_frame(
        self,
        frame_png: Path,
        depth_exr: Path,
        char_ref_png: Path,
        prompt: str,
        seed: int,
        shot_type: str,
    ) -> bytes:
        return frame_png.read_bytes()


# ------------------------------------------------------------------
# Pipeline principal
# ------------------------------------------------------------------

def stylize_shot(
    shot_id: str,
    backend: StylizationBackend,
    renders_dir: Path = RENDERS_DIR,
    char_refs_dir: Path = CHAR_REFS_DIR,
    out_dir: Path = STYLIZED_DIR,
    fps: int = _DEFAULT_FPS,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Stylise tous les frames d'un shot via le backend donné.

    Args:
        shot_id:      Identifiant du shot.
        backend:      Instance de StylizationBackend.
        renders_dir:  Racine des rendus Blender (production/renders/).
        char_refs_dir: Racine des refs personnages (production/character_refs/).
        out_dir:      Répertoire de sortie pour les frames stylisées.
        fps:          Framerate.
        dry_run:      Si True, affiche les infos sans appeler l'API.

    Returns:
        dict {"shot_id", "frames_stylized", "cost_usd", "out_dir"}.
    """
    storyboard = _load_json(STORYBOARD_FILE)
    animations = _load_json(ANIMATIONS_FILE)

    shot = _find_shot(storyboard, shot_id)
    if shot is None:
        raise ValueError(f"Shot '{shot_id}' introuvable")

    anim_cfg = animations["shots"].get(shot_id, {})
    primary_char = shot.get("primary_character")

    # Frames sources (rendu Blender)
    shot_renders = renders_dir / shot_id / "frames"
    depth_dir = renders_dir / shot_id / "depth"
    frames = sorted(shot_renders.glob("frame_*.png")) if shot_renders.exists() else []

    duration_sec: int = shot.get("duration_sec", 5)
    expected_frames = duration_sec * fps

    # Référence personnage (ou master plate lieu pour env shots)
    char_ref = _resolve_char_ref(primary_char, char_refs_dir, shot) if primary_char else None
    if char_ref is None:
        char_ref = _resolve_location_ref(shot.get("location_key", ""))

    # Prompt cinématique
    prompt = _build_stylization_prompt(shot, storyboard)

    total_cost = len(frames) * backend.cost_per_frame

    print(f"[shot_pipeline_v4] {shot_id}")
    print(f"  Backend     : {backend.name}")
    print(f"  Frames      : {len(frames)}/{expected_frames}")
    print(f"  Char ref    : {char_ref.name if char_ref else 'aucune ref (pas de master plate lieu)'}")
    print(f"  Coût estimé : ${total_cost:.2f}")

    if dry_run:
        print("  DRY-RUN — aucun appel API")
        return {
            "shot_id": shot_id,
            "frames_stylized": 0,
            "cost_usd": 0.0,
            "out_dir": str(out_dir / shot_id),
        }

    if not frames:
        raise FileNotFoundError(
            f"Aucune frame trouvée dans {shot_renders}. "
            f"Lancer blender_render.py --shot {shot_id} d'abord."
        )

    shot_out = out_dir / shot_id / "frames"
    shot_out.mkdir(parents=True, exist_ok=True)

    stylized = 0
    for frame_path in frames:
        frame_num = frame_path.stem.split("_")[-1]
        depth_path = depth_dir / f"depth_{frame_num}.exr"
        out_path = shot_out / frame_path.name

        if out_path.exists():
            stylized += 1
            continue

        # Seed dérivée par frame pour reproductibilité
        base_seed = anim_cfg.get("camera", {}).get("fov_mm", 50)
        seed = int(base_seed) * 10000 + int(frame_num)

        result_bytes = backend.stylize_frame(
            frame_png=frame_path,
            depth_exr=depth_path if depth_path.exists() else frame_path,
            char_ref_png=char_ref if char_ref else frame_path,
            prompt=prompt,
            seed=seed,
            shot_type=shot.get("shot_type", "medium"),
        )
        out_path.write_bytes(result_bytes)
        stylized += 1

    actual_cost = stylized * backend.cost_per_frame
    print(f"  [OK] {stylized} frames stylisees -- cout reel : ${actual_cost:.2f}")

    return {
        "shot_id": shot_id,
        "frames_stylized": stylized,
        "cost_usd": actual_cost,
        "out_dir": str(shot_out),
    }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_stylization_prompt(shot: dict[str, Any], storyboard: dict[str, Any]) -> str:
    """Construit le prompt cinématique pour la stylisation ControlNet.

    Ordre des tokens (du plus fort au plus faible pour les modèles de diffusion) :
    1. reference_exact  — signal DOP (Deakins, Lubezki, titre du film)
    2. shot_type_label + camera_spec — signal technique
    3. location_canonical + colour_palette — ancrage spatial/chromatique du lieu
    4. composition — mise en scène
    5. eyeline — direction de regard
    6. scene_axis — contrainte 180°
    7. lighting_context
    8. material_state
    9. action_brief — signal narratif
    10. emotion_intent
    11. state_override — état physique personnage (si présent)
    12. off_frame_tension — tension hors-cadre (si présent)
    """
    shot_type = shot.get("shot_type", "medium")
    camera_spec = shot.get("camera_spec", "ARRI Alexa 35, anamorphic")
    composition = shot.get("composition", "")
    eyeline = shot.get("eyeline", "")
    lighting = shot.get("lighting_context", "")
    material = shot.get("material_state", "")
    action = shot.get("action_brief", "")
    emotion = shot.get("emotion_intent", "")
    state_override = shot.get("state_override")
    off_frame = shot.get("off_frame_tension")
    reference_exact = shot.get("reference_exact", "")
    scene_id = shot.get("scene_id", "")
    location_key = shot.get("location_key", "")

    # Données du lieu depuis locations.json
    loc_canonical = ""
    loc_palette = ""
    try:
        _locs = _load_json(LOCATIONS_FILE)
        if location_key in _locs:
            loc = _locs[location_key]
            loc_canonical = loc.get("canonical", "")[:220]  # tronquer si trop long
            colour = loc.get("colour", {})
            loc_dop = loc.get("dop_ref", "")
            palette_parts = []
            if colour.get("dominant"):
                palette_parts.append(f"dominant {colour['dominant']}")
            if colour.get("accent"):
                palette_parts.append(f"accent {colour['accent']}")
            if colour.get("blacks"):
                palette_parts.append(f"deep blacks {colour['blacks']}")
            if palette_parts:
                loc_palette = "Colour palette: " + ", ".join(palette_parts) + "."
            if loc_dop and loc_dop not in (reference_exact or ""):
                loc_palette += f" Location DOP reference: {loc_dop}."
    except Exception:
        pass  # locations.json absent ou mal formé — on continue sans
    off_frame = shot.get("off_frame_tension")
    reference_exact = shot.get("reference_exact", "")
    scene_id = shot.get("scene_id", "")

    shot_type_label = {
        "ultra_wide": "Ultra-wide establishing shot",
        "wide": "Wide shot",
        "wide_handheld": "Wide handheld shot",
        "medium_wide": "Medium-wide shot",
        "medium": "Medium shot",
        "medium_handheld": "Medium handheld shot",
        "close": "Close-up shot",
        "close_handheld": "Close-up handheld shot",
        "cu_handheld": "Close-up handheld shot",
        "ecu": "Extreme close-up",
        "ots": "Over-the-shoulder shot",
        "ots_over_shoulder": "Over-the-shoulder shot",
        "insert": "Insert shot",
        "follow_handheld": "Follow handheld shot",
        "follow_handheld_fast": "Fast follow handheld shot",
    }.get(shot_type, "Shot")

    # Scene axis — injection contrainte 180°
    scene_axis = ""
    scenes_axis = storyboard.get("scenes_axis", {})
    if scene_id in scenes_axis:
        axis_data = scenes_axis[scene_id]
        if isinstance(axis_data, dict):
            axis = axis_data.get("axis", "")
            note = axis_data.get("note", "")
            if axis and axis.lower() not in ("n/a", "n/a — no characters"):
                scene_axis = axis
                if note:
                    scene_axis += f" — {note}"
        elif isinstance(axis_data, str):
            scene_axis = axis_data

    parts: list[str] = []

    # 1. Référence DOP — signal le plus fort, premiers tokens
    if reference_exact:
        parts.append(f"Visual reference: {reference_exact}.")

    # 2. Type de shot + spec caméra
    parts.append(f"{shot_type_label}. {camera_spec}.")

    # 3. Lieu : canonical + palette couleur (ancrage spatial et chromatique)
    if loc_canonical:
        parts.append(loc_canonical)
    if loc_palette:
        parts.append(loc_palette)

    # 4. Composition — mise en scène
    if composition:
        parts.append(composition)

    # 5. Eyeline
    _eyeline_lower = (eyeline or "").strip().lower()
    if eyeline and _eyeline_lower not in ("n/a", "n/a — object shot, no character present"):
        parts.append(f"Eyeline: {eyeline}.")

    # 6. Axe de scène — contrainte 180°
    if scene_axis:
        parts.append(f"Camera axis: {scene_axis}.")

    # 7. Éclairage
    if lighting:
        parts.append(lighting)

    # 8. État matières
    if material:
        parts.append(material)

    # 9. Action — narratif (signal faible, placé après le technique)
    if action:
        parts.append(action)

    # 10. Intention émotionnelle
    if emotion:
        parts.append(emotion)

    # 11. État physique personnage — critique pour SCN_011 (wet states)
    if state_override:
        parts.append(f"Character physical state: {state_override}.")

    # 12. Tension hors-cadre (optionnel)
    if off_frame:
        parts.append(f"Off-frame tension: {off_frame}.")
    # Fin cinématographique — remplace les formules génériques IA
    parts.append(
        "Anamorphic 2.39:1. Practical light sources dominant. "
        "Motivated shadows. Optical lens aberrations retained. Film grain at ISO push."
    )

    return " ".join(parts)


def _emotion_matches(keyword: str, text: str) -> bool:
    """Vérifie qu'un keyword est présent comme début de mot et sans négation directe.

    Règle 'anger' : mot entier uniquement (évite le substring dans 'danger').
    Autres keywords : correspondance de début de mot (permet 'calcul' → 'calculates').
    Négation directe : 'not <keyword>' dans la même expression annule le match.
    """
    pattern = r"\b" + re.escape(keyword) + (r"\b" if keyword == "anger" else "")
    if not re.search(pattern, text):
        return False
    if re.search(r"\bnot\s+" + re.escape(keyword), text):
        return False
    return True


# ---------------------------------------------------------------------------
# Mapping émotion → expression corpus Phase B
# Clé : sous-chaîne cherchée dans emotion_intent (lowercase)
# Valeur : nom de fichier dans character_faces/{slug}/
# ---------------------------------------------------------------------------
_EMOTION_TO_EXPR: list[tuple[str, str]] = [
    # paires (fragment_emotion, fichier_expression)
    ("dread",          "expr_03_contained_fear.png"),
    ("fear",           "expr_03_contained_fear.png"),
    ("panic",          "expr_03_contained_fear.png"),
    ("pain",           "expr_04_pain_contained.png"),
    ("contempt",       "expr_05_contempt_cold.png"),
    ("cold",           "expr_05_contempt_cold.png"),
    ("calculation",    "expr_11_calculation_cold.png"),
    ("calcul",         "expr_11_calculation_cold.png"),
    ("distrust",       "expr_12_distrust_guarded.png"),
    ("guarded",        "expr_12_distrust_guarded.png"),
    ("grief",          "expr_07_grief_suppressed.png"),
    ("grief",          "expr_07_grief_suppressed.png"),
    ("realisation",    "expr_08_surprise_flash.png"),
    ("disbelief",      "expr_08_surprise_flash.png"),
    ("discovery",      "expr_08_surprise_flash.png"),
    ("surprise",       "expr_08_surprise_flash.png"),
    ("exhaustion",     "expr_09_exhaustion_deep.png"),
    ("fatigue",        "expr_09_exhaustion_deep.png"),
    ("anger",          "expr_10_anger_suppressed.png"),
    ("determination",  "expr_06_determination_jaw.png"),
    ("resolve",        "expr_06_determination_jaw.png"),
    ("relief",         "expr_13_relief_flash.png"),
    ("alert",          "expr_01_alert_watchful.png"),
    ("watchful",       "expr_01_alert_watchful.png"),
    ("focus",          "expr_02_intent_focus.png"),
    ("intent",         "expr_02_intent_focus.png"),
    ("competence",     "expr_02_intent_focus.png"),
    ("escape",         "expr_06_determination_jaw.png"),
    ("urgency",        "expr_06_determination_jaw.png"),
]

# Mapping shot_type → pose corps (character_bodies/{slug}/)
_SHOT_TYPE_TO_POSE: dict[str, str] = {
    "wide":                  "turn_00_front.png",
    "ultra_wide":            "turn_00_front.png",
    "wide_handheld":         "pose_03_walking_mid_stride.png",
    "medium_wide":           "turn_00_front.png",
    "follow_handheld":       "pose_03_walking_mid_stride.png",
    "follow_handheld_fast":  "pose_03_walking_mid_stride.png",
}

# Mapping shot_type → angle visage (character_faces/{slug}/)
_SHOT_TYPE_TO_FACE_ANGLE: dict[str, str] = {
    "profile":               "angle_02_profile_left.png",
    "ots":                   "angle_01_three_quarter_left.png",
    "ots_over_shoulder":     "angle_01_three_quarter_left.png",
    "three_quarter":         "angle_01_three_quarter_left.png",
    "over_shoulder":         "angle_01_three_quarter_left.png",
    "medium":                "angle_00_front_neutral.png",
    "medium_handheld":       "angle_00_front_neutral.png",
    "medium_wide":           "angle_00_front_neutral.png",
    "close":                 "angle_00_front_neutral.png",  # overridden by emotion
    "close_handheld":        "angle_00_front_neutral.png",
    "cu_handheld":           "angle_00_front_neutral.png",
    "ecu":                   "angle_00_front_neutral.png",  # overridden by emotion
    "insert":                "angle_00_front_neutral.png",
}


def _resolve_char_ref(char_slug: str, char_refs_dir: Path, shot: dict[str, Any]) -> Path | None:
    """Résout la meilleure référence personnage Phase B pour ce shot.

    Logique de sélection (3 niveaux) :

    1. Plans LARGES (wide/ultra_wide/medium_wide/follow) :
       → Corps turnaround ou pose de marche (character_bodies/)
       Le personnage est visible en entier — la ref corps est plus utile qu'un visage.

    2. Plans SERRÉS (close/ecu) :
       → Expression matchée sur emotion_intent (character_faces/)
       Le visage remplit le cadre — matcher l'expression améliore la cohérence.

    3. Plans MOYENS et OTS :
       → Angle de visage selon direction (character_faces/)

    Fallback chain :
       Phase B corps → Phase B visage angle → Phase B front_neutral → Phase A.
    """
    shot_type = (shot.get("shot_type") or "medium").lower()
    emotion = (shot.get("emotion_intent") or "").lower()
    action = (shot.get("action_brief") or "").lower()
    emotion_full = emotion + " " + action  # combiner pour meilleure couverture

    FACES = CHAR_FACES_DIR / char_slug
    BODIES = ROOT / "production" / "character_bodies" / char_slug

    def _try(path: Path) -> Path | None:
        return path if path.exists() else None

    def _face(name: str) -> Path | None:
        return _try(FACES / name)

    def _body(name: str) -> Path | None:
        return _try(BODIES / name)

    # ------------------------------------------------------------------
    # 1. Plans larges → corps
    # ------------------------------------------------------------------
    if shot_type in _SHOT_TYPE_TO_POSE:
        pose_name = _SHOT_TYPE_TO_POSE[shot_type]
        # Action override : sprint/dive → crouch, seated → seated
        if any(w in action for w in ("sprint", "dive", "crouch", "running", "ducking")):
            pose_name = "pose_02_tactical_crouch.png"
        elif any(w in action for w in ("seated", "sitting", "sits")):
            pose_name = "pose_04_seated_contained.png"
        elif any(w in action for w in ("carrying", "holds", "drive", "drive in her")):
            pose_name = "pose_06_under_load_carrying.png"
        elif any(w in action for w in ("turning hard", "braced", "body weight", "weight forward")):
            pose_name = "pose_01_alert_forward_lean.png"
        elif any(w in action for w in ("detonates", "breach", "door opens with force")):
            pose_name = "pose_01_alert_forward_lean.png"
        ref = _body(pose_name)
        if ref:
            print(f"  [ref] {char_slug}: corps/{pose_name} (shot_type={shot_type})")
            return ref
        # Corps absent → tomber sur visage
        ref = _body("turn_00_front.png")
        if ref:
            print(f"  [ref] {char_slug}: corps/turn_00_front.png (fallback corps)")
            return ref

    # ------------------------------------------------------------------
    # 2. Plans serrés → expression matchée
    # ------------------------------------------------------------------
    if shot_type in ("close", "ecu", "close_handheld", "cu_handheld", "insert"):
        for keyword, expr_file in _EMOTION_TO_EXPR:
            if _emotion_matches(keyword, emotion_full):
                ref = _face(expr_file)
                if ref:
                    print(f"  [ref] {char_slug}: faces/{expr_file} (émotion='{keyword}')")
                    return ref
        # Aucune expression matchée → front_neutral
        ref = _face("angle_00_front_neutral.png")
        if ref:
            print(f"  [ref] {char_slug}: faces/angle_00_front_neutral.png (close, émotion non matchée)")
            return ref

    # ------------------------------------------------------------------
    # 3. Plans moyens et OTS → expression matchée, puis angle de visage
    # ------------------------------------------------------------------
    # 3a. Expression matchée sur émotion (medium/ots aussi)
    for keyword, expr_file in _EMOTION_TO_EXPR:
        if _emotion_matches(keyword, emotion_full):
            ref = _face(expr_file)
            if ref:
                print(f"  [ref] {char_slug}: faces/{expr_file} (émotion='{keyword}', medium)")
                return ref

    # 3b. Angle de visage selon shot_type
    angle_name = "angle_00_front_neutral.png"  # défaut
    for key, fname in _SHOT_TYPE_TO_FACE_ANGLE.items():
        if key in shot_type:
            angle_name = fname
            break

    ref = _face(angle_name)
    if ref:
        print(f"  [ref] {char_slug}: faces/{angle_name} (shot_type={shot_type})")
        return ref

    # ------------------------------------------------------------------
    # Fallback Phase B front_neutral
    # ------------------------------------------------------------------
    ref = _face("angle_00_front_neutral.png")
    if ref:
        print(f"  [ref] {char_slug}: faces/angle_00_front_neutral.png (fallback front_neutral)")
        return ref

    # ------------------------------------------------------------------
    # Fallback Phase A
    # ------------------------------------------------------------------
    for ext in (".png", ".jpg", ".jpeg"):
        p = char_refs_dir / f"{char_slug}_ref{ext}"
        if p.exists():
            print(f"  [WARN] {char_slug}: Phase A fallback (Phase B absent)")
            return p

    return None


def _resolve_location_ref(location_key: str) -> Path | None:
    """Retourne le master plate du lieu si généré (Phase B-bis).

    Utilisé comme image ref pour les env shots (pas de personnage principal).
    Le fichier est généré par gen_location_refs.py dans production/location_refs/.
    Nommage : {location_key}_master.png
    """
    if not location_key:
        return None
    p = LOCATION_REFS_DIR / f"{location_key}_master.png"
    if p.exists():
        print(f"  [ref] lieu: location_refs/{p.name}")
        return p
    return None


def _exr_depth_to_png(depth_exr: Path) -> bytes:
    """Convertit un fichier EXR depth en PNG 8-bit pour ControlNet."""
    try:
        import cv2
        import numpy as np

        img = cv2.imread(str(depth_exr), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"Impossible de lire {depth_exr}")
        # Normaliser entre 0 et 255
        img_norm = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)
        img_uint8 = img_norm.astype(np.uint8)
        ok, buf = cv2.imencode(".png", img_uint8)
        if not ok:
            raise ValueError("imencode failed")
        return buf.tobytes()
    except ImportError:
        # Fallback sans cv2
        depth_exr_bytes = depth_exr.read_bytes()
        return depth_exr_bytes


def _exr_normals_to_png(normals_exr: Path) -> bytes:
    """Convertit un EXR normals RGB (Blender Normal Pass) en PNG 8-bit pour ControlNet Normal.

    Blender exporte les normales en camera space, range [-1, 1] par canal (float32).
    La convention ControlNet Normal (normalbae) attend une image RGB [0, 255] où
    R=X, G=Y, B=Z, chaque composante mappée de [-1, 1] → [0, 255].
    """
    try:
        import cv2
        import numpy as np

        img = cv2.imread(str(normals_exr), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"Impossible de lire {normals_exr}")
        # Float32 [-1, 1] → uint8 [0, 255]
        img_mapped = ((img.astype(np.float32) * 0.5 + 0.5) * 255.0).clip(0, 255).astype(np.uint8)
        ok, buf = cv2.imencode(".png", img_mapped)
        if not ok:
            raise ValueError("imencode failed")
        return buf.tobytes()
    except ImportError:
        return normals_exr.read_bytes()


def _upload_to_comfyui(url: str, img_bytes: bytes, filename: str) -> str:
    """Upload une image vers ComfyUI via POST /upload/image (multipart/form-data).

    Returns:
        Nom de fichier tel qu'enregistré dans le store ComfyUI (à utiliser dans les workflows).
    Raises:
        RuntimeError: si l'upload échoue.
    """
    import urllib.request

    boundary = "----AIPRODFormBoundary" + filename[:8]
    CRLF = b"\r\n"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("ascii") + img_bytes + CRLF
    body += (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="overwrite"\r\n\r\n'
        f"true\r\n"
        f"--{boundary}--\r\n"
    ).encode("ascii")

    req = urllib.request.Request(
        f"{url}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        return result["name"]
    except Exception as exc:
        raise RuntimeError(f"ComfyUI upload échoué pour {filename}: {exc}") from exc


def _img_to_b64(path: Path) -> str:
    import base64
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def _bytes_to_b64(data: bytes, mime: str) -> str:
    import base64
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_shot(storyboard: dict[str, Any], shot_id: str) -> dict[str, Any] | None:
    for shot in storyboard.get("shots", []):
        if shot["shot_id"] == shot_id:
            return shot
    return None


def _build_comfyui_workflow(
    control_image_filename: str,
    char_ref_filename: str,
    prompt: str,
    seed: int,
) -> dict[str, Any]:
    """Workflow ComfyUI production : SD1.5 + ControlNet Normal + IP-Adapter.

    Reproduit fidèlement le pipeline Replicate jagilley/controlnet-normal (SD1.5 base).

    Modèles requis dans ComfyUI/models/ :
      checkpoints/ : v1-5-pruned-emaonly.safetensors
      controlnet/  : control_v11p_sd15_normalbae.safetensors
      ipadapter/   : ip-adapter-plus_sd15.safetensors
      clip_vision/ : CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors

    Extensions ComfyUI requises :
      ComfyUI-IPAdapter-plus (https://github.com/cubiq/ComfyUI_IPAdapter_plus)
    """
    negative_prompt = (
        "worst quality, low quality, blurry, jpeg artifacts, watermark, text, "
        "signature, extra fingers, fused limbs, malformed hands, deformed anatomy, "
        "cartoon, anime, painting, illustration, digital art, nsfw"
    )
    return {
        # --- Checkpoint SD1.5 ---
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"},
        },
        # --- Prompts ---
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["1", 1]},
        },
        # --- Images d'entrée ---
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": control_image_filename},
        },
        "5": {
            "class_type": "LoadImage",
            "inputs": {"image": char_ref_filename},
        },
        # --- ControlNet Normal ---
        "6": {
            "class_type": "ControlNetLoader",
            "inputs": {"control_net_name": "control_v11p_sd15_normalbae.safetensors"},
        },
        "7": {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": ["2", 0],
                "negative": ["3", 0],
                "control_net": ["6", 0],
                "image": ["4", 0],
                "strength": 0.85,
                "start_percent": 0.0,
                "end_percent": 1.0,
            },
        },
        # --- IP-Adapter (cohérence personnage) ---
        "8": {
            "class_type": "CLIPVisionLoader",
            "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"},
        },
        "9": {
            "class_type": "IPAdapterModelLoader",
            "inputs": {"ipadapter_file": "ip-adapter-plus_sd15.safetensors"},
        },
        "10": {
            "class_type": "IPAdapter",
            "inputs": {
                "model": ["1", 0],
                "ipadapter": ["9", 0],
                "image": ["5", 0],
                "clip_vision": ["8", 0],
                "weight": 0.6,
                "start_at": 0.0,
                "end_at": 1.0,
            },
        },
        # --- Latent + sampling ---
        "11": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 1920, "height": 1080, "batch_size": 1},
        },
        "12": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["10", 0],
                "positive": ["7", 0],
                "negative": ["7", 1],
                "latent_image": ["11", 0],
                "seed": seed,
                "steps": 28,
                "cfg": 7.5,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 0.75,
            },
        },
        # --- Decode + save ---
        "13": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["12", 0], "vae": ["1", 2]},
        },
        "14": {
            "class_type": "SaveImage",
            "inputs": {"images": ["13", 0], "filename_prefix": "stylized"},
        },
    }


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


def _make_backend(name: str) -> StylizationBackend:
    if name == "replicate":
        return ReplicateBackend()
    if name == "comfyui":
        return ComfyUIBackend()
    if name == "null":
        return NullStylizationBackend()
    raise ValueError(f"Backend inconnu : '{name}'. Valides : replicate, comfyui, null")


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Stylise un shot via ControlNet + FLUX (V4).")
    parser.add_argument("--shot", required=True, help="Shot ID (ex: SCN_002_SHOT_001)")
    parser.add_argument(
        "--backend",
        choices=["replicate", "comfyui", "null"],
        default="replicate",
        help="Backend de stylisation.",
    )
    parser.add_argument("--renders-dir", default=str(RENDERS_DIR))
    parser.add_argument("--char-refs", default=str(CHAR_REFS_DIR))
    parser.add_argument("--out-dir", default=str(STYLIZED_DIR))
    parser.add_argument("--fps", type=int, default=_DEFAULT_FPS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _load_env()

    backend = _make_backend(args.backend)
    result = stylize_shot(
        shot_id=args.shot,
        backend=backend,
        renders_dir=Path(args.renders_dir),
        char_refs_dir=Path(args.char_refs),
        out_dir=Path(args.out_dir),
        fps=args.fps,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    _load_env()
    sys.exit(main())
