"""
production/gen_character_refs.py
=================================
Génère les portraits de référence pour chaque personnage via FLUX.2 Pro.
Source: characters.json -> portrait_brief (DOP-grade, pas de "describe what you want")

COUT : 5 personnages × $0.03 = $0.15
Usage : python production/gen_character_refs.py [--char nara] [--dry-run]
"""
from __future__ import annotations
import argparse, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.shot_pipeline import LOCKED_MODEL_P1, LOCKED_PARAMS, LOCKED_COST_P1, _load_env, _download
from production.dashboard import load_all_characters, update_character_ref
import cv2


def build_portrait_prompt(char_id: str, char: dict) -> str:
    pb = char["portrait_brief"]
    canonical = char["canonical"]
    seed_note = char.get("note", "")
    return (
        f'{{"character_canonical": "{canonical}", '
        f'"camera": "{pb["camera"]}", '
        f'"framing": "{pb["framing"]}", '
        f'"lighting": "{pb["lighting"]}", '
        f'"background": "{pb["background"]}", '
        f'"dop_ref": "{pb["dop_ref"]}", '
        f'"production_note": "Photorealistic, no illustration, no painting. Natural skin texture. '
        f'Exact canonical costume and appearance — zero deviation. {seed_note}"}}'
    )


def run(filter_chars: list[str], dry_run: bool) -> None:
    _load_env(ROOT)
    characters = load_all_characters()
    targets = filter_chars if filter_chars else list(characters.keys())
    targets = [c for c in targets if c in characters]

    cost = len(targets) * LOCKED_COST_P1
    print(f"\nPortraits à générer : {len(targets)} — coût estimé : ${cost:.2f}")

    if dry_run:
        for cid in targets:
            char = characters[cid]
            note = char.get("note", "")
            seed_str = note.split("seed: ")[1].split(".")[0] if "seed:" in note else "N/A"
            print(f"  {cid} | {char['full_name']} | seed={seed_str}")
        print("\n[DRY-RUN] Aucun appel API.")
        return

    import replicate
    out_dir = ROOT / "production/character_refs"
    out_dir.mkdir(parents=True, exist_ok=True)

    total_cost = 0.0
    for cid in targets:
        char = characters[cid]
        prompt = build_portrait_prompt(cid, char)
        note = char.get("note", "")
        seed = int(note.split("seed: ")[1].split(".")[0]) if "seed:" in note else 42
        print(f"\n[{cid}] {char['full_name']} — seed={seed} — appel FLUX.2 Pro...")
        t0 = time.monotonic()
        out = replicate.run(
            LOCKED_MODEL_P1,
            input={
                "prompt": prompt,
                "aspect_ratio": "1:1",
                "resolution": LOCKED_PARAMS["p1_resolution"],
                "seed": seed,
                "output_format": LOCKED_PARAMS["p1_output_format"],
                "output_quality": LOCKED_PARAMS["p1_output_quality"],
                "safety_tolerance": LOCKED_PARAMS["p1_safety_tolerance"],
            },
        )
        elapsed = time.monotonic() - t0
        img = _download(str(out))
        out_path = out_dir / f"{cid}_ref.png"
        cv2.imwrite(str(out_path), img)
        update_character_ref(cid, str(out_path))
        total_cost += LOCKED_COST_P1
        print(f"  Sauvegardé : {out_path.name} ({img.shape[1]}×{img.shape[0]}) — {elapsed:.1f}s — ${total_cost:.2f} cumulé")

    print(f"\nTerminé. {len(targets)} portraits. Coût : ${total_cost:.2f}")
    print("ETAPE SUIVANTE : python production/run.py benchmark --dry-run")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--char", nargs="*", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.char, args.dry_run)
