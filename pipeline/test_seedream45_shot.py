"""
test_seedream45_shot.py
=======================
Test Seedream 4.5 (ByteDance) — SCN_002_SHOT_001
  - Modèle  : bytedance/seedream-4.5
  - Résolution : 2K natif (16:9)
  - Référence  : nara_hero_ref_01.png
  - Coût       : $0.04
"""
from __future__ import annotations

import os
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

ROOT     = Path(__file__).resolve().parent.parent
REF_IMG  = ROOT / "_archive/district_zero/ep01_2026-04-30/preproduction/district_zero/characters/nara_voss/nara_hero_ref_01.png"
OUT_DIR  = ROOT / "out/test_seedream45_scn002_shot001"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL    = "bytedance/seedream-4.5"
COST_USD = 0.04


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


def _score(app, img_a: np.ndarray, img_b: np.ndarray) -> float:
    fa = app.get(img_a)
    fb = app.get(img_b)
    if not fa or not fb:
        return 0.0
    return float(np.dot(fa[0].normed_embedding, fb[0].normed_embedding))


def _img_to_b64(img_bgr: np.ndarray) -> str:
    import base64
    ok, buf = cv2.imencode(".png", img_bgr)
    if not ok:
        raise RuntimeError("imencode failed")
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


PROMPT = (
    "INT. LOWER TRANSIT STACK — SERVICE CORRIDOR — NIGHT. "
    "Narrow maintenance corridor underground, low ceiling with heavy exposed pipes "
    "sweating condensation, walls of corroded dark metal panels with rust streaks, "
    "wet concrete floor reflecting amber emergency LED strips along the upper wall edge, "
    "single cage-shielded industrial work lamp 12 metres ahead as the only key light, "
    "broken pipe joint venting a thin jet of steam mid-corridor. "
    "Lighting: cage work lamp ahead as hard back-key; amber emergency strips as warm fill; "
    "cool steel-blue ambient reflected from wet floor; deep chiaroscuro, 6:1 lighting ratio. "
    "Color: desaturated teal and steel-blue dominant; isolated amber-warm accents from practicals. "
    "Nara Voss sprints alone through the leaking maintenance corridor, "
    "her wrist display flashing urgent amber pressure alert, urgency and contained panic in her expression. "
    "Female protagonist, late 20s, fine balanced features, elegant defined jawline, high cheekbones, "
    "intense intelligent eyes exhausted by hardship. "
    "No excessive makeup. Natural skin texture, visible pores. "
    "Dark hair loosely tied back, stray wet strands at temples and forehead. "
    "Dark tactical neck scarf, weathered utility jacket, tactical vest. "
    "All sleeve patches are plain woven black fabric — "
    "absolutely no text, no letters, no numbers, no symbols on any patch or badge. "
    "On her left forearm: small rectangular matte-black polymer tactical OLED wrist display, "
    "clean machined aluminium bezel, secured with black nylon webbing straps, "
    "amber OLED screen glowing with a pressure readout. "
    "Full figure visible, wide shot, subject occupies 30% of frame height. "
    "Camera locked-off on tripod. Rule of thirds applied. "
    "Solo figure only — absolutely no other people. "
    "Photorealistic cinematic, ARRI Alexa 35, anamorphic lens, 2K hyperrealistic. "
    "Natural film grain. No oversaturation. No fantasy glow. No HDR clipping. "
    "No amateur work, no AI artefacts, no distorted anatomy."
)


def main() -> int:
    _load_env()
    if not os.environ.get("REPLICATE_API_TOKEN", ""):
        print("ERROR: REPLICATE_API_TOKEN manquant", file=sys.stderr)
        return 1

    import replicate
    from insightface.app import FaceAnalysis

    print("=== Seedream 4.5 — SCN_002_SHOT_001 ===")
    print(f"  Modèle   : {MODEL}")
    print(f"  Résolution: 2K (16:9)")
    print(f"  Coût     : ${COST_USD:.2f}")
    print(f"  Référence : {REF_IMG.name}")
    print(f"\n  PROMPT ({len(PROMPT)} chars) :\n  {PROMPT[:200]}...\n")

    ref_bgr = cv2.imread(str(REF_IMG))
    if ref_bgr is None:
        print(f"ERROR: {REF_IMG}", file=sys.stderr)
        return 1

    ref_b64 = _img_to_b64(ref_bgr)

    print("[1/3] Appel Seedream 4.5 (Replicate)...")
    print("  size=2K | aspect_ratio=16:9 | sequential_image_generation=disabled")
    t0 = time.monotonic()
    output = replicate.run(
        MODEL,
        input={
            "prompt": PROMPT,
            "image_input": [ref_b64],
            "size": "2K",
            "aspect_ratio": "16:9",
            "sequential_image_generation": "disabled",
        },
    )
    elapsed = time.monotonic() - t0
    print(f"  Temps API : {elapsed:.1f}s")

    # output peut être une URL ou une liste
    url = str(output[0]) if isinstance(output, list) else str(output)
    print(f"  URL : {url[:80]}...")

    with urllib.request.urlopen(url, timeout=120) as resp:
        img_bytes = resp.read()

    result_bgr = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    if result_bgr is None:
        print("ERROR: impossible de décoder le résultat", file=sys.stderr)
        return 1

    out_path = OUT_DIR / "seedream45_scn002_shot001.png"
    cv2.imwrite(str(out_path), result_bgr)
    print(f"\n[2/3] Image sauvegardée : {out_path}")
    print(f"  Résolution : {result_bgr.shape[1]}×{result_bgr.shape[0]}")

    print("[3/3] Score ArcFace vs référence...")
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    score = _score(app, result_bgr, ref_bgr)
    print(f"\n  Score ArcFace : {score:.6f}")
    print(f"  Best v5 (Flux Fill Pro) : 0.925572")
    delta = score - 0.925572
    if score >= 0.925572:
        print(f"  >> NOUVEAU RECORD !! ({delta:+.6f})")
    elif score >= 0.880:
        print(f"  >> Excellent  (delta vs best : {delta:+.6f})")
    elif score >= 0.800:
        print(f"  >> Acceptable (delta vs best : {delta:+.6f})")
    else:
        print(f"  >> Insuffisant (delta vs best : {delta:+.6f})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
