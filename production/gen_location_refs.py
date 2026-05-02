"""
production/gen_location_refs.py
================================
Génère un master plate de référence pour chaque lieu via FLUX.2 Pro.
Source: locations.json -> canonical + lighting_brief + colour + dop_ref (DOP-grade)

COUT : 10 lieux × $0.03 = $0.30
Usage : python production/gen_location_refs.py [--loc int_transit_corridor_night] [--dry-run]
"""
from __future__ import annotations
import argparse, json, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.shot_pipeline import (
    LOCKED_MODEL_P1, LOCKED_PARAMS, LOCKED_COST_P1, _load_env, _download,
)
from production.dashboard import update_master_plate_path
import cv2

MODEL_ULTRA = "black-forest-labs/flux-1.1-pro-ultra"
COST_ULTRA  = 0.06

MODEL_GPT2  = "openai/gpt-image-2"
COST_GPT2   = 0.128   # quality=high


def _scene_to_location_map(root: Path) -> dict[str, str]:
    dash = json.loads((root / "production/dashboard.json").read_text(encoding="utf-8"))
    result: dict[str, str] = {}
    for sid, val in dash.items():
        lk = val["location_key"]
        if lk not in result:
            result[lk] = sid
    return result


def build_location_prompt(loc_key: str, loc: dict, grade: dict) -> str:
    colour = loc["colour"]
    show_look = grade["show_look"]["grade_intent"]
    forbidden = "; ".join(grade["show_look"]["forbidden"])
    return (
        f'{{"location_canonical": "{loc["canonical"]}", '
        f'"lighting_brief": "{loc["lighting_brief"]}", '
        f'"colour_grade": "Dominant {colour["dominant"]}, accent {colour["accent"]}, '
        f'deep blacks {colour["blacks"]}. '
        f'Grade reference: {loc["dop_ref"]}. Show look: {show_look}. Forbidden: {forbidden}.", '
        f'"camera": "{loc["camera"]}", '
        f'"production_note": "Photorealistic, ARRI film grain, anamorphic, no people, environment only. '
        f'Maximum cinematic quality. Inspired by {loc["dop_ref"]}. Zero digital-art aesthetics."}}'
    )


# ---------------------------------------------------------------------------
# Compositions master — purement spatiales/architecturales pour text-to-image pur.
# Les _creative_composition de gen_location_angles sont conçues pour Redux (image-to-image)
# et contiennent des références humaines (Vale, figures, "he") incompatibles avec les masters.
# ---------------------------------------------------------------------------

_MASTER_COMPOSITIONS: dict[str, str] = {
    "ext_outer_wall_night": (
        "Camera 15cm above black sea surface, tilted up 10 degrees — "
        "the concrete wall dominates the upper two-thirds of frame, towers dissolving into salt haze at the top edge. "
        "A single searchbeam slashes diagonally upper-right to upper-left at mid-frame. "
        "Tide-stain horizontal stripe at 8-metre height bisects the wall surface."
    ),
    "int_transit_corridor_night": (
        "Perfect bilateral symmetry — camera axis locked on corridor centreline at hip height. "
        "Walls mirror exactly. The single cage lamp at the vanishing point is the only subject. "
        "Steam jet at mid-corridor catches backlight as a horizontal white plume."
    ),
    "int_pressure_valve_chamber_night": (
        "Extreme low angle — lens at floor level, camera tilted 80 degrees upward. "
        "The valve manifold array ascends from floor to ceiling as a dense vertical architecture. "
        "Alarm strobe from overhead: hard white flash across every manifold edge, "
        "hard shadows slamming downward across iron surfaces."
    ),
    "int_voss_apartment_night": (
        "Camera wedged into far corner — geometry compressed toward centre. "
        "Practical lamp at frame-right: tight amber cone on the central scarred-wood table, only lit zone. "
        "Window at frame-left: cold teal-blue neon seeping through condensation fog. "
        "65% of frame at 2-4% IRE — near-absolute darkness beyond the lamp radius."
    ),
    "int_civic_atrium_morning": (
        "Camera at floor level, lens at 15mm height — polished marble fills the bottom third, "
        "mirror-like surface reflecting the ceiling geometry above. "
        "A single giant monolithic portrait on the far wall fills the upper half of the view. "
        "80 metres of empty polished floor between camera and far wall."
    ),
    "int_black_market_sublevel_day": (
        "Camera below stall-table height, lens at 60cm elevation — "
        "amber neon tube crosses frame horizontally from the left, cyan neon from the right, "
        "colour clash at eye-level. Grey daylight shaft punches straight down from ventilation grille above. "
        "Dense cables, crates, and server racks above camera height form a canopy."
    ),
    "int_security_ops_center_day": (
        "Camera at the back of the room, lens at standing height — "
        "twelve monitor screens in three rows cover the far wall, cold cyan 6500K wash on all surfaces. "
        "Screen glow reflects in every dark glass panel and in the polished floor. "
        "Cold window backlight from above-left provides rim separation on structural edges."
    ),
    "int_service_spine_night": (
        "Perfect symmetry — camera locked on corridor centreline at knee height. "
        "Emergency floor strips recede into green-tinted fog at the vanishing point. "
        "Track rails converge toward infinity. The relay panel at mid-distance: only asymmetric element, "
        "amber OLED gauges as the sole warm source breaking the green symmetry."
    ),
    "int_observation_chamber": (
        "Camera behind hydraulic machinery — lens peers through steel pipe framework. "
        "Steel shutters: 30cm slats partially open, cold grey-blue exterior light growing at centre gap. "
        "Red interior wash on machinery foreground. Two colour temperatures separated by 30cm of steel."
    ),
    "int_voss_apartment_predawn": (
        "Camera at floor level — a thin horizontal bar of cold pre-dawn blue across the floor "
        "is the entire composition. Door at frame-right: hairline of warm corridor light under the gap. "
        "All surfaces above the bar: absolute forms in darkness, zero fill, zero surface detail."
    ),
}


def build_master_prompt_dop(loc_key: str, loc: dict) -> str:
    """Prompt DOP-grade pour master plate — Ultra mode.
    Composition spatiale pure + précision photographique + grain.
    PAS de narrative_beat : les pronoms en début de phrase échappent à _sanitize_canonical.
    _creative_composition retiré : conçu pour Redux, contient des humains (Vale, figures...).
    _precision_master sanitisé pour supprimer les refs humaines résiduelles (vale, analyst faces...).
    """
    from production.gen_location_angles import (
        _sanitize_canonical, _precision_master,
    )
    dop    = loc["dop_ref"]
    camera = loc.get("camera", "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 1600")
    canonical_clean  = _sanitize_canonical(loc["canonical"])
    composition      = _MASTER_COMPOSITIONS.get(loc_key, "")
    precision_clean  = _sanitize_canonical(_precision_master(loc_key))
    return (
        f"Photorealistic 35mm anamorphic film still. "
        f"Master plate. {loc['slug']}. Empty location — no people, no silhouettes, no figures, no human presence. No text, no readable signage, no labels on any surface. "
        f"{canonical_clean} "
        f"{composition} "
        f"{precision_clean} "
        f"Cinematic shutter 1/48sec. "
        f"{camera}. Anamorphic horizontal flares. "
        f"Kodak Vision3 500T — silver halide grain, natural halation. {dop}."
    )


def _strip_black_bands(img: "cv2.Mat", threshold: float = 5.0) -> "cv2.Mat":
    """Supprime les bandes noires en haut et en bas de l'image (letterbox / watermark)."""
    import numpy as np
    row_means = img.mean(axis=(1, 2))
    top = next((i for i, v in enumerate(row_means) if v > threshold), 0)
    bottom = len(row_means) - next((i for i, v in enumerate(reversed(row_means)) if v > threshold), 0) - 1
    if top > 0 or bottom < len(row_means) - 1:
        img = img[top:bottom + 1, :]
    return img


def run(filter_locs: list[str], dry_run: bool, ultra: bool = False, gpt2: bool = False) -> None:
    _load_env(ROOT)
    locs_data = json.loads((ROOT / "production/locations.json").read_text(encoding="utf-8"))
    targets = filter_locs if filter_locs else list(locs_data.keys())
    targets = [loc for loc in targets if loc in locs_data]
    s2l = _scene_to_location_map(ROOT)

    grade = json.loads((ROOT / "production/grade.json").read_text(encoding="utf-8"))
    model      = MODEL_GPT2  if gpt2  else (MODEL_ULTRA if ultra else LOCKED_MODEL_P1)
    cost_per   = COST_GPT2   if gpt2  else (COST_ULTRA  if ultra else LOCKED_COST_P1)
    cost = len(targets) * cost_per
    mode_label = "GPT Image 2 [high]" if gpt2 else ("Ultra DOP-grade 4K" if ultra else "FLUX.2 Pro")
    print(f"\nMaster plates à générer : {len(targets)} lieux [{mode_label}] — coût estimé : ${cost:.2f}")

    if dry_run:
        for lk in targets:
            loc = locs_data[lk]
            print(f"  {lk} | seed={loc['seed']} | scènes={loc['scene_ids']}")
        print("\n[DRY-RUN] Aucun appel API.")
        return

    import replicate
    out_dir = ROOT / "production/location_refs"
    out_dir.mkdir(parents=True, exist_ok=True)
    total_cost = 0.0

    for lk in targets:
        loc = locs_data[lk]
        if gpt2:
            prompt = build_master_prompt_dop(lk, loc)   # GPT-4o lit tout, pas de limite T5
        elif ultra:
            prompt = build_master_prompt_dop(lk, loc)
        else:
            prompt = build_location_prompt(lk, loc, grade)
        print(f"\n[{lk}] — appel {model}...")
        t0 = time.monotonic()

        if gpt2:
            out = replicate.run(
                MODEL_GPT2,
                input={
                    "prompt":         prompt,
                    "aspect_ratio":   "3:2",
                    "quality":        "high",
                    "output_format":  "png",
                    "moderation":     "low",
                },
            )
            elapsed = time.monotonic() - t0
            item = out[0]
            url = item.url() if callable(getattr(item, "url", None)) else str(item)
            with urllib.request.urlopen(url, timeout=120) as resp:
                img_bytes = resp.read()
            import numpy as np
            arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            img = _strip_black_bands(img)
            h, w = img.shape[:2]
            target_h = int(w * 9 / 16)
            y0 = (h - target_h) // 2
            img_crop = img[y0:y0 + target_h, :]
            img_4k = cv2.resize(img_crop, (3840, 2160), interpolation=cv2.INTER_LANCZOS4)
            blur = cv2.GaussianBlur(img_4k, (0, 0), 1.0)
            img_4k = cv2.addWeighted(img_4k, 2.4, blur, -1.4, 0)
            out_path = out_dir / f"{lk}_master_gpt2.png"
            cv2.imwrite(str(out_path), img_4k, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            total_cost += cost_per
            print(f"  Sauvegardé : {out_path.name} (3840×2160, crop 3:2→16:9) — {elapsed:.1f}s — ${total_cost:.2f} cumulé")

        elif ultra:
            out = replicate.run(
                MODEL_ULTRA,
                input={
                    "prompt":           prompt,
                    "aspect_ratio":     "16:9",
                    "output_format":    "png",
                    "output_quality":   100,
                    "safety_tolerance": 5,
                    "raw":              True,
                    "seed":             loc["seed"],
                },
            )
            elapsed = time.monotonic() - t0
            url = getattr(out, "url", None)
            url = url() if callable(url) else str(out)
            with urllib.request.urlopen(url, timeout=60) as resp:
                img_bytes = resp.read()
            import numpy as np
            arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            img = _strip_black_bands(img)
            img_4k = cv2.resize(img, (3840, 2160), interpolation=cv2.INTER_LANCZOS4)
            blur = cv2.GaussianBlur(img_4k, (0, 0), 1.0)
            img_4k = cv2.addWeighted(img_4k, 2.4, blur, -1.4, 0)
            out_path = out_dir / f"{lk}_master.png"
            cv2.imwrite(str(out_path), img_4k, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            total_cost += cost_per
            if lk in s2l:
                update_master_plate_path(s2l[lk], str(out_path))
            locs_data[lk]["ref_image"] = str(out_path)
            (ROOT / "production/locations.json").write_text(
                json.dumps(locs_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"  Sauvegardé : {out_path.name} (3840×2160) — {elapsed:.1f}s — ${total_cost:.2f} cumulé")

        else:
            out = replicate.run(
                LOCKED_MODEL_P1,
                input={
                    "prompt": prompt,
                    "aspect_ratio": LOCKED_PARAMS["p1_aspect_ratio"],
                    "resolution": LOCKED_PARAMS["p1_resolution"],
                    "seed": loc["seed"],
                    "output_format": LOCKED_PARAMS["p1_output_format"],
                    "output_quality": LOCKED_PARAMS["p1_output_quality"],
                    "safety_tolerance": LOCKED_PARAMS["p1_safety_tolerance"],
                },
            )
            elapsed = time.monotonic() - t0
            img = _download(str(out))
            out_path = out_dir / f"{lk}_master.png"
            cv2.imwrite(str(out_path), img)
            total_cost += cost_per
            if lk in s2l:
                update_master_plate_path(s2l[lk], str(out_path))
            locs_data[lk]["ref_image"] = str(out_path)
            (ROOT / "production/locations.json").write_text(
                json.dumps(locs_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"  Sauvegardé : {out_path.name} — {elapsed:.1f}s — ${total_cost:.2f} cumulé")

    print(f"\nTerminé. {len(targets)} master plates. Coût : ${total_cost:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--loc",      nargs="*", default=[])
    parser.add_argument("--ultra",    action="store_true", help="FLUX Ultra + DOP-grade + 4K")
    parser.add_argument("--gpt2",     action="store_true", help="GPT Image 2 high quality (test, $0.128)")
    parser.add_argument("--dry-run",  action="store_true")
    args = parser.parse_args()
    run(args.loc, args.dry_run, args.ultra, args.gpt2)
