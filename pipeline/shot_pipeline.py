"""
pipeline/shot_pipeline.py
=========================
MÉTHODE VERROUILLÉE — Pipeline de production hybride v2
Validé le 2026-04-30 | Score ArcFace record : 0.9378

Architecture :
  PASS 1 — FLUX.2 Pro     : master plate décor (seed fixe par scène)
  PASS 2 — Flux Fill Pro  : face inpainting (source = ref personnage)

Coût standard : $0.03 (P1) + $0.05 (P2) = $0.08/shot

═══════════════════════════════════════════════════════════════════
  NE PAS MODIFIER ce fichier sans révision ArcFace complète.
  Tout changement de prompt, paramètre ou modèle nécessite
  un benchmark sur nara_hero_ref_01.png (baseline 0.9378).
═══════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# MODÈLES VERROUILLÉS
# ---------------------------------------------------------------------------

LOCKED_MODEL_P1 = "black-forest-labs/flux-2-pro"
LOCKED_MODEL_P2 = "black-forest-labs/flux-fill-pro"

LOCKED_COST_P1 = 0.03
LOCKED_COST_P2 = 0.05
LOCKED_COST_TOTAL = LOCKED_COST_P1 + LOCKED_COST_P2

# ---------------------------------------------------------------------------
# PARAMÈTRES VERROUILLÉS — NE PAS MODIFIER
# ---------------------------------------------------------------------------

LOCKED_PARAMS = {
    # PASS 1 — FLUX.2 Pro
    "p1_aspect_ratio":    "16:9",
    "p1_resolution":      "1 MP",
    "p1_output_format":   "png",
    "p1_output_quality":  100,
    "p1_safety_tolerance": 5,
    # PASS 2 — Flux Fill Pro v5
    "p2_guidance":         30,
    "p2_steps":            50,
    "p2_prompt_upsampling": False,
    "p2_output_format":    "png",
    "p2_output_quality":   100,
    "p2_safety_tolerance": 6,
    # Canvas
    "canvas_w":            1344,
    "canvas_h":            768,
    # Upscale
    "upscale_factor":      2,
    "upscale_sharp_gain":  1.4,
    "upscale_blur_sigma":  1.0,
    # Face mask
    "mask_expand":         1.15,
    "face_det_size":       (640, 640),
    "face_model":          "buffalo_l",
}

# ---------------------------------------------------------------------------
# PROMPT P2 — NARA CANONICAL (verrouillé)
# ---------------------------------------------------------------------------
# Description pixel-parfaite du personnage pour Flux Fill Pro.
# Toute modification DOIT être rebenchmarkée.

LOCKED_NARA_CANONICAL = (
    "Female protagonist of a dystopian survival thriller. "
    "Late 20s, fine balanced features, elegant defined jawline, high cheekbones. "
    "Intense intelligent eyes — exhaustion and absolute determination. "
    "Natural skin texture, visible pores, no makeup, sweat on skin. "
    "Dark hair pulled back tightly, 3-4 wet loose strands at temples pressed to skin. "
    "Dark grey tubular neck gaiter. "
    "Weathered dark olive utility jacket — "
    "left and right sleeves each have ONE plain raw-edge woven black nylon rectangle "
    "sewn directly to fabric, matte black, visible weave texture only, "
    "zero embroidery, zero print, zero text, zero logo, zero symbol. "
    "Dark charcoal tactical vest over jacket, no markings of any kind."
)


# ---------------------------------------------------------------------------
# CONSTRUCTEURS DE PROMPTS — DOP-GRADE
# ---------------------------------------------------------------------------

@dataclass
class SceneP1Params:
    """Paramètres variables par scène pour le prompt FLUX.2 Pro.

    Tous les champs 'locked_*' sont des constantes de production
    — ne pas les remplacer, les enrichir dans 'extra_notes' si besoin.
    """
    scene_id:       str                    # ex: "SCN_002"
    episode:        str                    # ex: "Episode 01"
    location_slug:  str                    # ex: "INT. LOWER TRANSIT STACK — NIGHT"
    location_desc:  str                    # description architecturale détaillée
    lighting_desc:  str                    # brief DOP : key, fill, ambient, ratio
    colour_desc:    str                    # palette hex + grade intent
    composition:    str                    # position sujet, vanishing point, leading lines
    subject_action: str                    # action précise du personnage dans ce shot
    seed:           int         = 42       # seed fixe par scène pour cohérence décor
    extra_notes:    str         = ""       # notes additionnelles (optionnel)

    # Constantes verrouillées
    locked_dop_ref:  str = field(default="Roger Deakins / Sicario (2015)", init=False)
    locked_camera:   str = field(default=(
        "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, 1.4x squeeze, "
        "oval bokeh on background, T2.3 | ISO 1600 | 180° shutter | 24fps"
    ), init=False)


def build_p1_prompt(p: SceneP1Params) -> str:
    """Construit le prompt JSON DOP-grade pour FLUX.2 Pro (Pass 1)."""
    doc = {
        "production_note": (
            f"DISTRICT ZERO — {p.episode} — {p.scene_id}. "
            f"Visual language: {p.locked_dop_ref} — "
            "wide anamorphic, deep shadow architecture, single motivated practical as key, "
            "clinical cold industrial palette with isolated warm practicals. "
            "Shoot on " + p.locked_camera + "."
            + (f" {p.extra_notes}" if p.extra_notes else "")
        ),
        "location": f"{p.location_slug}. {p.location_desc}",
        "lighting_design": p.lighting_desc,
        "colour_grade_intent": p.colour_desc,
        "composition": p.composition,
        "subject": {
            "action": p.subject_action,
            "costume": LOCKED_NARA_CANONICAL,
        },
        "technical_quality": (
            "ARRI Alexa 35 RAW capture aesthetic. "
            "Cooke Anamorphic /i lens character: subtle barrel distortion at edges, "
            "oval out-of-focus highlights, horizontal lens flare streak from cage lamp. "
            "Natural 35mm film grain structure — visible in shadow zones, "
            "not digital noise — organic texture. "
            "Tack-sharp focus plane on subject face and upper body. "
            "Controlled motion blur on moving extremities. "
            "No HDR clipping. No oversaturation. No AI artefact. "
            "No extra fingers. No floating limbs. No duplicated subjects. "
            "Solo figure — absolutely one person only in frame. "
            "Feature film production quality — 2026 state of the art."
        ),
    }
    return json.dumps(doc)


def build_p2_prompt(scene_env: str, subject_action: str) -> str:
    """Construit le prompt Flux Fill Pro (Pass 2) pour un shot donné.

    Args:
        scene_env:      Description courte décor + lumière de la scène (1-3 phrases).
        subject_action: Action précise du personnage dans ce shot.
    """
    return (
        f"{scene_env} "
        f"Nara Voss {subject_action}. "
        f"{LOCKED_NARA_CANONICAL} "
        "Left forearm: matte-black polymer OLED wrist display 25x40mm, "
        "machined aluminium micro-bezel, two black nylon strap buckles, "
        "amber OLED screen active with pressure gauge readout. "
        "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 1600, "
        "oval bokeh, organic film grain. "
        "Tack-sharp face and upper body. "
        "Solo — one person only, no other figures. "
        "No HDR clipping, no oversaturation, no AI artefact, no distorted anatomy. "
        "Feature film production quality."
    )


# ---------------------------------------------------------------------------
# PIPELINE HELPERS (identiques v2 validé)
# ---------------------------------------------------------------------------

def _load_env(root: Path) -> None:
    env_file = root / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _img_to_b64(img_bgr: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", img_bgr)
    if not ok:
        raise RuntimeError("imencode failed")
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def _download(url: str) -> np.ndarray:
    with urllib.request.urlopen(url, timeout=120) as resp:
        data = resp.read()
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"Impossible de décoder : {url}")
    return img


def _get_largest_face(app, img_bgr):
    faces = app.get(img_bgr)
    if not faces:
        return None
    return sorted(
        faces,
        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        reverse=True,
    )[0]


def _score_arcface(app, img_a: np.ndarray, img_b: np.ndarray) -> float:
    fa = app.get(img_a)
    fb = app.get(img_b)
    if not fa or not fb:
        return 0.0
    return float(np.dot(fa[0].normed_embedding, fb[0].normed_embedding))


def _sharpen_region(img_bgr: np.ndarray, bbox, strength: float = 1.0, sigma: float = 0.5) -> np.ndarray:
    x1, y1, x2, y2 = [int(c) for c in bbox]
    pad = 15
    x1s = max(0, x1 - pad); y1s = max(0, y1 - pad)
    x2s = min(img_bgr.shape[1], x2 + pad); y2s = min(img_bgr.shape[0], y2 + pad)
    roi = img_bgr[y1s:y2s, x1s:x2s].astype(np.float32)
    blur = cv2.GaussianBlur(roi, (0, 0), sigma)
    sharp = np.clip(roi * (1 + strength) - blur * strength, 0, 255).astype(np.uint8)
    out = img_bgr.copy()
    out[y1s:y2s, x1s:x2s] = sharp
    return out


def _fit_to_canvas(img_bgr: np.ndarray, w: int, h: int):
    sh, sw = img_bgr.shape[:2]
    scale = min(w / sw, h / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    ox, oy = (w - nw) // 2, (h - nh) // 2
    canvas[oy:oy + nh, ox:ox + nw] = resized
    return canvas, ox, oy, scale


def _build_face_mask(h: int, w: int, face_bbox, scale: float, ox: int, oy: int, expand: float = 1.15) -> np.ndarray:
    bx1, by1, bx2, by2 = face_bbox
    x1 = int(bx1 * scale) + ox; y1 = int(by1 * scale) + oy
    x2 = int(bx2 * scale) + ox; y2 = int(by2 * scale) + oy
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    fw, fh = x2 - x1, y2 - y1
    ax = int(fw * expand * 0.55); ay = int(fh * expand * 0.65)
    mask = np.ones((h, w), dtype=np.uint8) * 255
    cv2.ellipse(mask, (cx, cy), (ax, ay), 0, 0, 360, 0, -1)
    mask = cv2.GaussianBlur(mask, (9, 9), 0)
    _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    return mask


def _remove_watermark(img_bgr: np.ndarray) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    wm = np.zeros((h, w), dtype=np.uint8)
    wm[int(h * 0.90):h, int(w * 0.50):w] = 255
    return cv2.inpaint(img_bgr, wm, inpaintRadius=6, flags=cv2.INPAINT_TELEA)


def _upscale_2x(img_bgr: np.ndarray) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    up = cv2.resize(img_bgr, (w * 2, h * 2), interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(up.astype(np.float32), (0, 0), LOCKED_PARAMS["upscale_blur_sigma"])
    gain = LOCKED_PARAMS["upscale_sharp_gain"]
    return np.clip(up.astype(np.float32) * gain - blur * (gain - 1), 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# POINT D'ENTRÉE PRINCIPAL
# ---------------------------------------------------------------------------

@dataclass
class ShotResult:
    scene_id:      str
    shot_id:       str
    master_path:   Path
    result_1x:     Path
    result_2x:     Path
    score_1x:      float
    score_2x:      float
    cost_total:    float
    elapsed_total: float
    master_url:    str
    result_url:    str


def run_shot(
    scene_params:  SceneP1Params,
    shot_id:       str,
    ref_img:       Path,
    out_dir:       Path,
    p2_scene_env:  str,
    p2_subject_action: str,
    root:          Optional[Path] = None,
    verbose:       bool = True,
) -> ShotResult:
    """Lance le pipeline hybride v2 pour un shot.

    Args:
        scene_params:       Paramètres visuels de la scène (P1 — FLUX.2 Pro).
        shot_id:            Identifiant du shot (ex: "SHOT_001").
        ref_img:            Chemin vers l'image de référence du personnage (ArcFace = 1.0).
        out_dir:            Dossier de sortie pour ce shot.
        p2_scene_env:       Décor + lumière résumé pour le prompt P2 (1-3 phrases).
        p2_subject_action:  Action du personnage pour le prompt P2.
        root:               Racine du projet (pour charger .env). Défaut = CWD.
        verbose:            Afficher le log de progression.

    Returns:
        ShotResult avec chemins, scores ArcFace et métriques de coût/temps.
    """
    _root = root or Path.cwd()
    _load_env(_root)

    token = os.environ.get("REPLICATE_API_TOKEN", "")
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN manquant dans .env")

    import replicate
    from insightface.app import FaceAnalysis

    out_dir.mkdir(parents=True, exist_ok=True)

    cw = LOCKED_PARAMS["canvas_w"]
    ch = LOCKED_PARAMS["canvas_h"]
    shot_label = f"{scene_params.scene_id}_{shot_id}"

    if verbose:
        print(f"\n{'='*60}")
        print(f"  PIPELINE HYBRIDE v2 — {shot_label}")
        print(f"  Coût : ${LOCKED_COST_TOTAL:.2f}  |  Seed P1 : {scene_params.seed}")
        print(f"{'='*60}")

    ref_bgr = cv2.imread(str(ref_img))
    if ref_bgr is None:
        raise FileNotFoundError(f"Image de référence introuvable : {ref_img}")

    # ------------------------------------------------------------------
    # PASS 1 — FLUX.2 Pro : master plate décor
    # ------------------------------------------------------------------
    if verbose:
        print(f"\n[P1] FLUX.2 Pro — master plate {scene_params.scene_id} (seed={scene_params.seed})")
    t_start = time.monotonic()

    p1_prompt = build_p1_prompt(scene_params)
    out_p1 = replicate.run(
        LOCKED_MODEL_P1,
        input={
            "prompt":           p1_prompt,
            "aspect_ratio":     LOCKED_PARAMS["p1_aspect_ratio"],
            "resolution":       LOCKED_PARAMS["p1_resolution"],
            "seed":             scene_params.seed,
            "output_format":    LOCKED_PARAMS["p1_output_format"],
            "output_quality":   LOCKED_PARAMS["p1_output_quality"],
            "safety_tolerance": LOCKED_PARAMS["p1_safety_tolerance"],
        },
    )
    t_p1 = time.monotonic() - t_start
    master_url = str(out_p1)
    master_bgr = _download(master_url)
    master_path = out_dir / f"p1_master_{shot_label}.png"
    cv2.imwrite(str(master_path), master_bgr)
    if verbose:
        print(f"  Temps : {t_p1:.1f}s  |  {master_bgr.shape[1]}×{master_bgr.shape[0]}  →  {master_path.name}")

    # ------------------------------------------------------------------
    # PASS 2 — Flux Fill Pro v5 : face inpainting
    # ------------------------------------------------------------------
    if verbose:
        print(f"\n[P2] Flux Fill Pro v5 — face inpainting")

    app = FaceAnalysis(name=LOCKED_PARAMS["face_model"], providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=LOCKED_PARAMS["face_det_size"])

    faces = app.get(ref_bgr)
    if not faces:
        raise RuntimeError("Aucun visage détecté dans l'image de référence")
    src_sharp = _sharpen_region(ref_bgr, faces[0].bbox)
    face = _get_largest_face(app, src_sharp)

    canvas, ox, oy, scale = _fit_to_canvas(src_sharp, cw, ch)
    mask = _build_face_mask(ch, cw, face.bbox, scale, ox, oy, LOCKED_PARAMS["mask_expand"])

    p2_prompt = build_p2_prompt(p2_scene_env, p2_subject_action)
    t2 = time.monotonic()
    out_p2 = replicate.run(
        LOCKED_MODEL_P2,
        input={
            "prompt":               p2_prompt,
            "image":                _img_to_b64(canvas),
            "mask":                 _img_to_b64(mask),
            "output_format":        LOCKED_PARAMS["p2_output_format"],
            "output_quality":       LOCKED_PARAMS["p2_output_quality"],
            "safety_tolerance":     LOCKED_PARAMS["p2_safety_tolerance"],
            "num_inference_steps":  LOCKED_PARAMS["p2_steps"],
            "guidance":             LOCKED_PARAMS["p2_guidance"],
            "prompt_upsampling":    LOCKED_PARAMS["p2_prompt_upsampling"],
        },
    )
    t_p2 = time.monotonic() - t2
    result_url = str(out_p2)
    result_bgr   = _download(result_url)
    result_clean = _remove_watermark(result_bgr)
    result_2x    = _upscale_2x(result_clean)

    result_1x_path = out_dir / "result_1x.png"
    result_2x_path = out_dir / "result_2x.png"
    cv2.imwrite(str(result_1x_path), result_clean)
    cv2.imwrite(str(result_2x_path), result_2x)
    if verbose:
        print(f"  Temps : {t_p2:.1f}s  |  {result_clean.shape[1]}×{result_clean.shape[0]}")

    # ------------------------------------------------------------------
    # ArcFace scores
    # ------------------------------------------------------------------
    score_1x = _score_arcface(app, ref_bgr, result_clean)
    score_2x = _score_arcface(app, ref_bgr, result_2x)
    elapsed_total = time.monotonic() - t_start

    if verbose:
        print(f"\n[SCORES]")
        print(f"  ArcFace 1x : {score_1x:.6f}")
        print(f"  ArcFace 2x : {score_2x:.6f}")
        print(f"  Temps total : {elapsed_total:.1f}s  |  Coût : ${LOCKED_COST_TOTAL:.2f}")

    return ShotResult(
        scene_id=scene_params.scene_id,
        shot_id=shot_id,
        master_path=master_path,
        result_1x=result_1x_path,
        result_2x=result_2x_path,
        score_1x=score_1x,
        score_2x=score_2x,
        cost_total=LOCKED_COST_TOTAL,
        elapsed_total=elapsed_total,
        master_url=master_url,
        result_url=result_url,
    )
