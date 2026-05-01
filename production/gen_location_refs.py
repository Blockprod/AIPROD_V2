"""
production/gen_location_refs.py
================================
Génère un master plate de référence pour chaque lieu via FLUX.2 Pro.
Source: locations.json -> canonical + lighting_brief + colour + dop_ref (DOP-grade)

COUT : 10 lieux × $0.03 = $0.30
Usage : python production/gen_location_refs.py [--loc int_transit_corridor_night] [--dry-run]
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.shot_pipeline import (
    LOCKED_MODEL_P1, LOCKED_PARAMS, LOCKED_COST_P1, _load_env, _download,
)
from production.dashboard import update_master_plate_path
import cv2


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


def run(filter_locs: list[str], dry_run: bool) -> None:
    _load_env(ROOT)
    locs_data = json.loads((ROOT / "production/locations.json").read_text(encoding="utf-8"))
    targets = filter_locs if filter_locs else list(locs_data.keys())
    targets = [loc for loc in targets if loc in locs_data]
    s2l = _scene_to_location_map(ROOT)

    grade = json.loads((ROOT / "production/grade.json").read_text(encoding="utf-8"))
    cost = len(targets) * LOCKED_COST_P1
    print(f"\nMaster plates à générer : {len(targets)} lieux — coût estimé : ${cost:.2f}")

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
        prompt = build_location_prompt(lk, loc, grade)
        print(f"\n[{lk}] seed={loc['seed']} — appel FLUX.2 Pro...")
        t0 = time.monotonic()
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

        # Update dashboard pour la première scène utilisant ce lieu
        if lk in s2l:
            update_master_plate_path(s2l[lk], str(out_path))

        # Update locations.json avec le ref_image généré
        locs_data[lk]["ref_image"] = str(out_path)
        (ROOT / "production/locations.json").write_text(
            json.dumps(locs_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        total_cost += LOCKED_COST_P1
        print(f"  Sauvegardé : {out_path.name} — {elapsed:.1f}s — ${total_cost:.2f} cumulé")

    print(f"\nTerminé. {len(targets)} master plates. Coût : ${total_cost:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--loc", nargs="*", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.loc, args.dry_run)
