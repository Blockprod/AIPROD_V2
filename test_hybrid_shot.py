"""
test_hybrid_shot.py
===================
Pipeline hybride — FLUX.2 Pro + Flux Fill Pro v5 — SCN_002_SHOT_001

  PASS 1 — FLUX.2 Pro ($0.03)
    → Génère le master plate SCN_002 : décor corridor + Nara
    → JSON prompting structuré (caméra, lumière, palette hex)
    → Seed fixe par scène → répétable pour tous les shots de SCN_002
    → Résolution 16:9 à 1 MP (~1365×768)
    → Sauvegardé comme référence de scène

  PASS 2 — Flux Fill Pro v5 ($0.05)
    → Source : nara_hero_ref_01.png (ArcFace = 1.0)
    → Masque : BLANC = fond (régénérer) / NOIR = visage (préserver)
    → Même technique que v5 (record 0.925572)
    → Score ArcFace attendu : ~0.925

  TOTAL : $0.08 → 1 image finale 2560×1440 (après upscale)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

ROOT     = Path(__file__).resolve().parent
REF_IMG  = ROOT / "_archive/district_zero/ep01_2026-04-30/preproduction/district_zero/characters/nara_voss/nara_hero_ref_01.png"
OUT_DIR  = ROOT / "out/test_hybrid_scn002_shot001"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_P1 = "black-forest-labs/flux-2-pro"
MODEL_P2 = "black-forest-labs/flux-fill-pro"

COST_P1 = 0.03
COST_P2 = 0.05
COST_TOTAL = COST_P1 + COST_P2

TARGET_W = 1344
TARGET_H = 768

# Seed fixe par scène → même environnement pour tous les shots SCN_002
SCN002_SEED = 42


# ---------------------------------------------------------------------------
# Prompts structurés
# ---------------------------------------------------------------------------

# FLUX.2 Pro — JSON structuré pour contrôle précis
FLUX2PRO_PROMPT = json.dumps({
    "scene": (
        "INT. LOWER TRANSIT STACK — SERVICE CORRIDOR — NIGHT. "
        "Narrow maintenance corridor underground, low ceiling with heavy exposed pipes "
        "sweating condensation, walls of corroded dark metal panels with rust streaks "
        "and recessed junction boxes, wet concrete floor with a thin film of water "
        "reflecting ceiling light, amber emergency LED strips along the upper wall edge, "
        "single cage-shielded industrial work lamp 12 metres ahead as the only key light, "
        "broken pipe joint venting a thin jet of steam mid-corridor, "
        "corridor recedes into darkness, sealed underground, no windows, no daylight"
    ),
    "subjects": [{
        "name": "Nara Voss",
        "description": (
            "Female protagonist, late 20s, fine balanced features, elegant defined jawline, "
            "high cheekbones, intense intelligent eyes, dark hair loosely tied back. "
            "Dark tactical neck scarf, weathered utility jacket, tactical vest. "
            "All sleeve patches are plain woven black fabric — no text, no letters. "
            "Sprinting alone through the corridor, wrist display flashing amber, "
            "urgency and contained panic in her expression."
        ),
        "position": "full figure visible, wide shot, subject left of center, rule of thirds"
    }],
    "lighting": {
        "key": "cage work lamp ahead — hard industrial back-key, 200W equivalent",
        "fill": "amber emergency LED strips along upper wall — warm 2200K",
        "ambient": "cool steel-blue reflection from wet concrete floor",
        "ratio": "6:1 chiaroscuro, deep shadow zones, no soft boxes",
    },
    "camera": {
        "shot_type": "wide",
        "angle": "eye_level",
        "focal_length": "28mm anamorphic",
        "aperture": "f2.0",
        "movement": "locked-off tripod"
    },
    "color_palette": {
        "dominant": "#2B3A4A",
        "accent": "#C4750A",
        "shadow": "#0D1519",
        "description": "desaturated teal and steel-blue dominant; isolated amber-warm practicals"
    },
    "style": (
        "Photorealistic cinematic, ARRI Alexa 35, anamorphic lens, 4K hyperrealistic. "
        "Natural film grain. No oversaturation. No fantasy glow. No HDR clipping. "
        "No text, no letters, no symbols on any patch or badge. "
        "Solo figure only — no other people."
    )
})

# Flux Fill Pro v5 — identique à la version record
NARA_CANONICAL = (
    "Female protagonist of a dystopian survival thriller. "
    "Late 20s, fine balanced features, elegant defined jawline, high cheekbones. "
    "Intense intelligent eyes exhausted by hardship — determination and contained vulnerability. "
    "No excessive makeup. Natural skin texture, visible pores. "
    "Dark hair loosely tied back, stray wet strands at temples and forehead. "
    "Dark tactical neck scarf, weathered utility jacket, tactical vest. "
    "All sleeve patches are plain woven black fabric — "
    "absolutely no text, no letters, no numbers, no symbols on any patch or badge."
)

FLUX_FILL_PROMPT = (
    "INT. LOWER TRANSIT STACK — SERVICE CORRIDOR — NIGHT. "
    "Narrow maintenance corridor underground, low ceiling with heavy exposed pipes "
    "sweating condensation, walls of corroded dark metal panels with rust streaks, "
    "wet concrete floor reflecting amber emergency LED strips along the upper wall edge, "
    "single cage-shielded industrial work lamp 12 metres ahead as the only key light, "
    "broken pipe joint venting a thin jet of steam mid-corridor. "
    "Lighting: cage work lamp ahead as hard back-key; amber emergency strips as warm fill; "
    "cool steel-blue ambient reflected from wet floor; deep chiaroscuro 6:1. "
    "Color: desaturated teal #2B3A4A dominant; isolated amber #C4750A accents. "
    "Nara Voss sprints alone through the leaking maintenance corridor, "
    "her wrist display flashing urgent amber pressure alert. "
    f"{NARA_CANONICAL} "
    "On her left forearm: small rectangular matte-black polymer tactical OLED wrist display, "
    "amber OLED screen glowing with a pressure readout. "
    "Full figure visible, wide shot, subject left of center, rule of thirds. "
    "Camera locked-off, 28mm anamorphic. "
    "Solo figure only — absolutely no other people. "
    "Photorealistic cinematic, ARRI Alexa 35, anamorphic lens, 4K hyperrealistic. "
    "Natural film grain. No oversaturation. No AI artefacts, no distorted anatomy."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _img_to_b64(img_bgr: np.ndarray) -> str:
    import base64
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
    return sorted(faces, key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]), reverse=True)[0]


def _score(app, img_a: np.ndarray, img_b: np.ndarray) -> float:
    fa = app.get(img_a)
    fb = app.get(img_b)
    if not fa or not fb:
        return 0.0
    return float(np.dot(fa[0].normed_embedding, fb[0].normed_embedding))


def _sharpen(img_bgr: np.ndarray, bbox, strength=1.0, sigma=0.5) -> np.ndarray:
    x1, y1, x2, y2 = [int(c) for c in bbox]
    pad = 15
    x1s = max(0, x1-pad); y1s = max(0, y1-pad)
    x2s = min(img_bgr.shape[1], x2+pad); y2s = min(img_bgr.shape[0], y2+pad)
    roi  = img_bgr[y1s:y2s, x1s:x2s].astype(np.float32)
    blur = cv2.GaussianBlur(roi, (0, 0), sigma)
    sharp = np.clip(roi*(1+strength) - blur*strength, 0, 255).astype(np.uint8)
    out = img_bgr.copy()
    out[y1s:y2s, x1s:x2s] = sharp
    return out


def _fit_to_canvas(img_bgr, w, h):
    sh, sw = img_bgr.shape[:2]
    scale = min(w/sw, h/sh)
    nw, nh = int(sw*scale), int(sh*scale)
    resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    ox, oy = (w-nw)//2, (h-nh)//2
    canvas[oy:oy+nh, ox:ox+nw] = resized
    return canvas, ox, oy, scale


def _build_mask(h, w, face_bbox, scale, ox, oy, expand=1.15):
    bx1, by1, bx2, by2 = face_bbox
    x1 = int(bx1*scale)+ox; y1 = int(by1*scale)+oy
    x2 = int(bx2*scale)+ox; y2 = int(by2*scale)+oy
    cx, cy = (x1+x2)//2, (y1+y2)//2
    fw, fh = x2-x1, y2-y1
    ax = int(fw*expand*0.55); ay = int(fh*expand*0.65)
    mask = np.ones((h, w), dtype=np.uint8)*255
    cv2.ellipse(mask, (cx, cy), (ax, ay), 0, 0, 360, 0, -1)
    mask = cv2.GaussianBlur(mask, (9, 9), 0)
    _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    return mask


def _remove_watermark(img_bgr: np.ndarray) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    wm = np.zeros((h, w), dtype=np.uint8)
    wm[int(h*0.90):h, int(w*0.50):w] = 255
    return cv2.inpaint(img_bgr, wm, inpaintRadius=6, flags=cv2.INPAINT_TELEA)


def _upscale_2x(img_bgr: np.ndarray) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    up = cv2.resize(img_bgr, (w*2, h*2), interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(up.astype(np.float32), (0, 0), 1.0)
    return np.clip(up.astype(np.float32)*1.4 - blur*0.4, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    _load_env()
    if not os.environ.get("REPLICATE_API_TOKEN", ""):
        print("ERROR: REPLICATE_API_TOKEN manquant", file=sys.stderr)
        return 1

    import replicate
    from insightface.app import FaceAnalysis

    print("=" * 60)
    print("  PIPELINE HYBRIDE — FLUX.2 Pro + Flux Fill Pro v5")
    print(f"  Shot   : SCN_002_SHOT_001")
    print(f"  Coût   : ${COST_P1:.2f} (P1) + ${COST_P2:.2f} (P2) = ${COST_TOTAL:.2f}")
    print("=" * 60)

    ref_bgr = cv2.imread(str(REF_IMG))
    if ref_bgr is None:
        print(f"ERROR: {REF_IMG}", file=sys.stderr)
        return 1

    # -----------------------------------------------------------------------
    # PASS 1 — FLUX.2 Pro : master plate SCN_002
    # -----------------------------------------------------------------------
    print(f"\n[PASS 1] FLUX.2 Pro — Master plate SCN_002 (seed={SCN002_SEED})")
    print(f"  Modèle     : {MODEL_P1}")
    print(f"  Résolution : 16:9 @ 1 MP (~1365×768)")
    print(f"  Seed fixe  : {SCN002_SEED} (même pour tous les shots de SCN_002)")
    print(f"  Coût       : ${COST_P1:.2f}")

    t0 = time.monotonic()
    out_p1 = replicate.run(
        MODEL_P1,
        input={
            "prompt": FLUX2PRO_PROMPT,
            "aspect_ratio": "16:9",
            "resolution": "1 MP",
            "seed": SCN002_SEED,
            "output_format": "png",
            "output_quality": 100,
            "safety_tolerance": 5,
        },
    )
    elapsed_p1 = time.monotonic() - t0
    print(f"  Temps API  : {elapsed_p1:.1f}s")

    url_p1 = str(out_p1)
    print(f"  URL        : {url_p1[:80]}...")
    master_bgr = _download(url_p1)
    master_path = OUT_DIR / "p1_flux2pro_master_scn002.png"
    cv2.imwrite(str(master_path), master_bgr)
    print(f"  Sauvegardé : {master_path.name}  ({master_bgr.shape[1]}×{master_bgr.shape[0]})")

    # -----------------------------------------------------------------------
    # PASS 2 — Flux Fill Pro v5 : face inpainting
    # -----------------------------------------------------------------------
    print(f"\n[PASS 2] Flux Fill Pro v5 — Face inpainting")
    print(f"  Modèle  : {MODEL_P2}")
    print(f"  Source  : nara_hero_ref_01.png (ArcFace = 1.0)")
    print(f"  Masque  : BLANC=fond / NOIR=visage")
    print(f"  Coût    : ${COST_P2:.2f}")

    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))

    print("\n  [2.1] Détection visage dans la référence...")
    src_sharp = _sharpen(ref_bgr, app.get(ref_bgr)[0].bbox, strength=1.0, sigma=0.5)
    face = _get_largest_face(app, src_sharp)
    if face is None:
        print("ERROR: aucun visage détecté", file=sys.stderr)
        return 1
    bx1, by1, bx2, by2 = [int(c) for c in face.bbox]
    print(f"  Face bbox : ({bx1},{by1})→({bx2},{by2})")

    print(f"  [2.2] Fit canvas {TARGET_W}×{TARGET_H}...")
    canvas, ox, oy, scale = _fit_to_canvas(src_sharp, TARGET_W, TARGET_H)
    cv2.imwrite(str(OUT_DIR / "p2_debug_canvas.png"), canvas)

    print("  [2.3] Masque elliptique (fond blanc / visage noir)...")
    mask = _build_mask(TARGET_H, TARGET_W, face.bbox, scale, ox, oy, expand=1.15)
    cv2.imwrite(str(OUT_DIR / "p2_debug_mask.png"), mask)

    print("  [2.4] Appel Flux Fill Pro (guidance=30, steps=50)...")
    t0 = time.monotonic()
    out_p2 = replicate.run(
        MODEL_P2,
        input={
            "prompt": FLUX_FILL_PROMPT,
            "image":  _img_to_b64(canvas),
            "mask":   _img_to_b64(mask),
            "output_format": "png",
            "output_quality": 100,
            "safety_tolerance": 6,
            "num_inference_steps": 50,
            "guidance": 30,
            "prompt_upsampling": False,
        },
    )
    elapsed_p2 = time.monotonic() - t0
    print(f"  Temps API  : {elapsed_p2:.1f}s")

    url_p2 = str(out_p2)
    print(f"  URL        : {url_p2[:80]}...")
    result_bgr = _download(url_p2)
    print(f"  Résolution : {result_bgr.shape[1]}×{result_bgr.shape[0]}")

    result_clean = _remove_watermark(result_bgr)
    cv2.imwrite(str(OUT_DIR / "p2_result_1x.png"), result_clean)

    result_2x = _upscale_2x(result_clean)
    cv2.imwrite(str(OUT_DIR / "p2_result_2x.png"), result_2x)
    print(f"  Upscale 2x : {result_2x.shape[1]}×{result_2x.shape[0]}")

    # -----------------------------------------------------------------------
    # Scores ArcFace
    # -----------------------------------------------------------------------
    print("\n[SCORES ArcFace]")
    score_master = _score(app, master_bgr, ref_bgr)
    score_1x     = _score(app, result_clean, ref_bgr)
    score_2x     = _score(app, result_2x, ref_bgr)

    print(f"  FLUX.2 Pro master plate  : {score_master:.6f}")
    print(f"  Hybride final 1x         : {score_1x:.6f}")
    print(f"  Hybride final 2x         : {score_2x:.6f}")
    print(f"  Best v5 (référence)      : 0.925572")

    delta = score_1x - 0.925572
    if score_1x >= 0.925572:
        print(f"\n  >> NOUVEAU RECORD !! ({delta:+.6f})")
    elif score_1x >= 0.880:
        print(f"\n  >> Excellent  (delta : {delta:+.6f})")
    elif score_1x >= 0.800:
        print(f"\n  >> Acceptable (delta : {delta:+.6f})")
    else:
        print(f"\n  >> Insuffisant (delta : {delta:+.6f})")

    print(f"\n[RÉSUMÉ]")
    print(f"  Coût total réel : ${COST_TOTAL:.2f}")
    print(f"  Temps total     : {elapsed_p1+elapsed_p2:.0f}s")
    print(f"  Master plate    : {master_path.name}")
    print(f"  Image finale    : p2_result_1x.png / p2_result_2x.png")
    print(f"  Dossier         : {OUT_DIR}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
