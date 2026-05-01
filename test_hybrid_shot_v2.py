"""
test_hybrid_shot_v2.py
======================
Pipeline hybride v2 — FLUX.2 Pro + Flux Fill Pro v5 — SCN_002_SHOT_001

  Améliorations vs v1 :
  - Prompt P1 réécrit en format "document de production réel" (DOP brief)
  - Références cinématographiques directes nommées
  - Kelvin précis, T-stop, ISO, shutter angle
  - Lignes de composition explicites (vanishing point, leading lines)
  - Description costume positive (plus de "no text" → description exacte)
  - Notes gaffer détaillées
  - Patch badge décrit positivement au niveau du fil

  Coût : $0.03 (FLUX.2 Pro P1) + $0.05 (Flux Fill Pro P2) = $0.08
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
OUT_DIR  = ROOT / "out/test_hybrid_scn002_shot001_v2"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_P1 = "black-forest-labs/flux-2-pro"
MODEL_P2 = "black-forest-labs/flux-fill-pro"

COST_P1    = 0.03
COST_P2    = 0.05
COST_TOTAL = COST_P1 + COST_P2

TARGET_W   = 1344
TARGET_H   = 768
SCN002_SEED = 42


# ---------------------------------------------------------------------------
# PASS 1 — FLUX.2 Pro : prompt format "document de production réel"
# ---------------------------------------------------------------------------

FLUX2PRO_PROMPT = json.dumps({

    "production_note": (
        "DISTRICT ZERO — Episode 01 — Scene 002. "
        "Visual language: Roger Deakins on Sicario (2015) — "
        "wide anamorphic, deep shadow architecture, single motivated practical as key, "
        "clinical cold industrial palette with isolated warm practicals. "
        "Reference frame: Denis Villeneuve + Roger Deakins tunnel sequence aesthetic. "
        "Shoot on ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, "
        "1.4x squeeze, oval bokeh on background."
    ),

    "location": (
        "INT. LOWER TRANSIT STACK — UNDERGROUND MAINTENANCE SERVICE CORRIDOR — NIGHT. "
        "A narrow maintenance corridor 1.8m wide, 2.2m ceiling height, "
        "extending 30 metres into absolute darkness. "
        "Walls: riveted corroded dark steel panels, visible rust bloom and mineral deposits, "
        "recessed junction boxes with conduit bundles, "
        "surface moisture and salt crystallisation on all metal surfaces. "
        "Floor: wet poured concrete, 2mm standing water film, "
        "perfect mirror-like reflections of all light sources. "
        "Ceiling: dense parallel pipe runs, thermal insulation stripped in sections, "
        "exposed bare metal sweating condensation. "
        "Corridor geometry creates a strong natural vanishing point 30m ahead — "
        "the single cage work lamp sits precisely on that vanishing point axis."
    ),

    "lighting_design": {
        "dop_intent": (
            "Single-source motivated lighting. The cage work lamp IS the story. "
            "Everything else is ambient spill and reflection. "
            "Deep chiaroscuro — 80% of frame in shadow. "
            "No fill panels. No beauty light. Raw industrial authenticity."
        ),
        "key_light": {
            "fixture": "Cage-shielded industrial work lamp, bare tungsten bulb 200W",
            "position": "30 metres ahead on corridor axis, hanging from ceiling pipe bracket",
            "colour_temperature": "2850K tungsten — warm amber-orange core",
            "quality": "hard, directional, strong fall-off, no diffusion",
            "effect": "creates back-rim on subject from extreme distance — silhouette edge lighting"
        },
        "practical_strips": {
            "fixture": "Amber emergency LED strips, 8mm width, mounted along upper wall junction",
            "colour_temperature": "2200K deep amber",
            "coverage": "continuous both side walls, 10% brightness, emergency mode",
            "effect": "warm amber rim trace along wall top edges, reflected in floor water"
        },
        "ambient": {
            "source": "Cool blue-grey reflected from wet concrete floor and pipe condensation",
            "colour_temperature": "6500K cold blue",
            "intensity": "5% — barely perceptible, lifts deep shadow to visible detail",
            "effect": "steel-blue undertone in all shadow zones"
        },
        "steam_interaction": (
            "Broken pipe joint mid-corridor at 15m — thin pressurised steam jet, "
            "illuminated by cage lamp backlight, "
            "creates volumetric haze catching amber light — "
            "thin god-ray in mid-ground separating subject from background."
        ),
        "lighting_ratio": "8:1 — extreme chiaroscuro, shadow zones at 0.5 stops above pure black",
        "exposure": "T2.3 | ISO 1600 | 180 degree shutter | 24fps"
    },

    "colour_grade_intent": {
        "dominant_palette": "Desaturated steel-blue #1C2B35 — walls, shadows, atmosphere",
        "accent_warm": "Isolated amber #B8600A — LED strips, cage lamp glow, floor reflection",
        "skin_zone": "Neutral desaturated — no warm push on face, preserve natural skin tone",
        "blacks": "Lifted slightly — #0A0F12 — not crushed, retain shadow texture",
        "grade_reference": "Sicario (2015) tunnel sequence — Denis Villeneuve / Roger Deakins"
    },

    "composition": {
        "shot_type": "wide — subject occupies 25-35% of frame height",
        "subject_position": (
            "Nara positioned at lower-left third intersection. "
            "Her head at 60% frame height. "
            "She occupies the left vertical third. "
            "Right two-thirds: corridor receding to vanishing point with cage lamp."
        ),
        "leading_lines": (
            "Ceiling pipe runs create parallel diagonal convergence lines "
            "leading from both upper corners to vanishing point (cage lamp). "
            "Floor water reflection mirrors the lines below. "
            "Subject body axis perpendicular to these lines — creates visual tension."
        ),
        "depth_layers": (
            "Foreground: subject in slight ambient underexposure — silhouette-adjacent. "
            "Midground: steam haze at 15m catching amber backlight. "
            "Background: cage lamp as point source, corridor fades to pure black."
        ),
        "negative_space": "Right two-thirds deliberately empty — corridor is the antagonist"
    },

    "subject": {
        "identity": (
            "Nara Voss — female protagonist, late 20s. "
            "Fine balanced features, elegant defined jawline, high cheekbones. "
            "Intense intelligent eyes — exhaustion and contained urgency. "
            "Natural skin texture — visible pores, no makeup, authentic."
        ),
        "action": (
            "Mid-sprint — left leg extended forward, right arm swinging forward, "
            "motion blur on hands and feet indicating speed. "
            "Body slightly forward-leaning at 10 degrees — urgency, not panic. "
            "Head turned 3/4 toward camera — expression: controlled fear, absolute determination."
        ),
        "costume": {
            "jacket": (
                "Weathered dark olive utility jacket, waxed cotton exterior, "
                "visible wear at elbows and collar, zip half-open at chest. "
                "Left sleeve: single plain raw-edge woven black nylon rectangle "
                "sewn directly to fabric — no embroidery, no print, no logo, "
                "visible weave texture of the nylon only, matte black. "
                "Right sleeve: identical plain black nylon rectangle, same construction."
            ),
            "vest": (
                "Tactical vest over jacket — dark charcoal grey, "
                "molle webbing panels empty, two front zip pockets, "
                "no markings, no text, no patches of any kind."
            ),
            "neck": "Dark grey tubular neck gaiter pulled to chin",
            "hair": (
                "Dark hair pulled back tightly, "
                "3-4 wet loose strands escaped at temples and forehead, "
                "pressed to skin by perspiration — cinematic detail."
            ),
            "wrist_display": (
                "Left forearm: rectangular matte-black polymer OLED tactical display, "
                "25mm x 40mm, 2mm thin, machined aluminium micro-bezel, "
                "secured by two black nylon webbing straps with aluminium buckles. "
                "Screen: amber OLED active — pressure gauge readout, flickering urgency."
            )
        }
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
    )
})

# Flux Fill Pro v5 — même prompt record mais amélioré sur costume
NARA_CANONICAL = (
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

FLUX_FILL_PROMPT = (
    "INT. LOWER TRANSIT STACK — UNDERGROUND SERVICE CORRIDOR — NIGHT. "
    "Narrow 1.8m wide corridor, riveted corroded steel walls with rust and mineral deposits, "
    "wet concrete floor with standing water mirror-reflecting amber emergency LED strips, "
    "dense ceiling pipe runs sweating condensation, "
    "single cage-shielded tungsten work lamp 30 metres ahead on vanishing point axis, "
    "broken pipe joint at 15m emitting thin pressurised steam jet catching backlight. "
    "Lighting: 2850K cage tungsten lamp as hard back-key at extreme distance — "
    "silhouette edge rim on subject; "
    "2200K deep amber emergency LED strips as practical fill on walls; "
    "6500K cool blue-grey ambient from wet floor reflection; "
    "8:1 chiaroscuro ratio, 80% of frame in deep shadow. "
    "Color grade: desaturated steel-blue #1C2B35 dominant, "
    "isolated amber #B8600A accents, lifted blacks #0A0F12. "
    "Roger Deakins Sicario (2015) tunnel sequence visual language. "
    "Nara Voss mid-sprint, left leg extended, forward lean 10 degrees, "
    "head 3/4 to camera — controlled fear and determination. "
    f"{NARA_CANONICAL} "
    "Left forearm: matte-black polymer OLED wrist display 25x40mm, "
    "machined aluminium micro-bezel, two black nylon strap buckles, "
    "amber OLED screen active with pressure gauge readout. "
    "Subject at lower-left third, head at 60% frame height, "
    "corridor vanishing point fills right two-thirds of frame. "
    "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 1600, "
    "oval bokeh, subtle horizontal lens flare from cage lamp, organic film grain. "
    "Tack-sharp face and upper body. Motion blur on hands and feet. "
    "Solo — one person only, no other figures. "
    "No HDR clipping, no oversaturation, no AI artefact, no distorted anatomy. "
    "Feature film production quality."
)


# ---------------------------------------------------------------------------
# Helpers (identiques v1)
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
    print("  PIPELINE HYBRIDE v2 — FLUX.2 Pro + Flux Fill Pro v5")
    print("  Prompt DOP-grade — Références cinéma nommées")
    print(f"  Shot   : SCN_002_SHOT_001")
    print(f"  Coût   : ${COST_P1:.2f} (P1) + ${COST_P2:.2f} (P2) = ${COST_TOTAL:.2f}")
    print("=" * 60)

    ref_bgr = cv2.imread(str(REF_IMG))
    if ref_bgr is None:
        print(f"ERROR: {REF_IMG}", file=sys.stderr)
        return 1

    # -----------------------------------------------------------------------
    # PASS 1 — FLUX.2 Pro : master plate SCN_002 v2
    # -----------------------------------------------------------------------
    print(f"\n[PASS 1] FLUX.2 Pro — Master plate SCN_002 v2 (seed={SCN002_SEED})")
    print(f"  Référence DOP : Roger Deakins / Sicario (2015)")
    print(f"  Caméra        : ARRI Alexa 35 | Cooke Anamorphic /i 32mm T2.3 | ISO 1600")
    print(f"  Lumière       : 2850K tungsten cage key | 2200K amber LED fill | 6500K blue ambient")
    print(f"  Coût          : ${COST_P1:.2f}")

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
    print(f"  Temps API     : {elapsed_p1:.1f}s")

    url_p1 = str(out_p1)
    print(f"  URL           : {url_p1[:80]}...")
    master_bgr = _download(url_p1)
    master_path = OUT_DIR / "p1_flux2pro_master_scn002_v2.png"
    cv2.imwrite(str(master_path), master_bgr)
    print(f"  Sauvegardé    : {master_path.name}  ({master_bgr.shape[1]}×{master_bgr.shape[0]})")

    # -----------------------------------------------------------------------
    # PASS 2 — Flux Fill Pro v5 : face inpainting
    # -----------------------------------------------------------------------
    print(f"\n[PASS 2] Flux Fill Pro v5 — Face inpainting")
    print(f"  Source  : nara_hero_ref_01.png (ArcFace = 1.0)")
    print(f"  Coût    : ${COST_P2:.2f}")

    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))

    print("\n  [2.1] Détection visage...")
    src_sharp = _sharpen(ref_bgr, app.get(ref_bgr)[0].bbox, strength=1.0, sigma=0.5)
    face = _get_largest_face(app, src_sharp)
    if face is None:
        print("ERROR: aucun visage détecté", file=sys.stderr)
        return 1
    print(f"  Face bbox : ({int(face.bbox[0])},{int(face.bbox[1])})→({int(face.bbox[2])},{int(face.bbox[3])})")

    canvas, ox, oy, scale = _fit_to_canvas(src_sharp, TARGET_W, TARGET_H)
    cv2.imwrite(str(OUT_DIR / "p2_debug_canvas.png"), canvas)

    mask = _build_mask(TARGET_H, TARGET_W, face.bbox, scale, ox, oy, expand=1.15)
    cv2.imwrite(str(OUT_DIR / "p2_debug_mask.png"), mask)

    print(f"  [2.2] Appel Flux Fill Pro (guidance=30, steps=50)...")
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
    result_bgr   = _download(url_p2)
    result_clean = _remove_watermark(result_bgr)
    result_2x    = _upscale_2x(result_clean)

    cv2.imwrite(str(OUT_DIR / "p2_result_1x.png"), result_clean)
    cv2.imwrite(str(OUT_DIR / "p2_result_2x.png"), result_2x)
    print(f"  Résolution : {result_bgr.shape[1]}×{result_bgr.shape[0]} → 2x : {result_2x.shape[1]}×{result_2x.shape[0]}")

    # -----------------------------------------------------------------------
    # Scores
    # -----------------------------------------------------------------------
    print("\n[SCORES ArcFace]")
    score_master = _score(app, master_bgr, ref_bgr)
    score_1x     = _score(app, result_clean, ref_bgr)
    score_2x     = _score(app, result_2x, ref_bgr)

    print(f"  FLUX.2 Pro master plate  : {score_master:.6f}")
    print(f"  Hybride final 1x         : {score_1x:.6f}")
    print(f"  Hybride final 2x         : {score_2x:.6f}")
    print(f"  Best v5 (référence)      : 0.925572")
    print(f"  Best hybride v1          : 0.899987")

    delta_best = score_1x - 0.925572
    delta_v1   = score_1x - 0.899987
    if score_1x >= 0.925572:
        print(f"\n  >> NOUVEAU RECORD ABSOLU !! ({delta_best:+.6f})")
    elif score_1x >= 0.900:
        print(f"\n  >> Excellent — égale ou dépasse hybride v1 ({delta_v1:+.6f} vs v1)")
    elif score_1x >= 0.880:
        print(f"\n  >> Très bon  (delta vs best : {delta_best:+.6f})")
    elif score_1x >= 0.800:
        print(f"\n  >> Acceptable (delta vs best : {delta_best:+.6f})")
    else:
        print(f"\n  >> Insuffisant (delta vs best : {delta_best:+.6f})")

    print(f"\n[RÉSUMÉ]")
    print(f"  Coût total   : ${COST_TOTAL:.2f}")
    print(f"  Temps total  : {elapsed_p1+elapsed_p2:.0f}s")
    print(f"  Master plate : {master_path.name}")
    print(f"  Finale 1x    : p2_result_1x.png")
    print(f"  Finale 2x    : p2_result_2x.png")
    print(f"  Dossier      : {OUT_DIR}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
