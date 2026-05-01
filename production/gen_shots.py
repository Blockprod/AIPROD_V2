"""
production/gen_shots.py
========================
Génère les 35 shots de EP01 via le pipeline hybride v2.
Source de vérité : storyboard.json (DOP-grade shot briefs)
                   characters.json (canoniques personnages)
                   locations.json  (DOP-grade lieux)

COUT EP01 complet : ~$2.80 (35 shots avec personnages, ~$0.08 chacun)
Usage : python production/gen_shots.py [--scene SCN_002] [--shot SCN_002_SHOT_001] [--dry-run]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.shot_pipeline import run_shot, SceneP1Params, _load_env
from production.dashboard import load_scene, load_character, load_location, load_shot_brief

METRICS = ROOT / "production/shots/metrics.jsonl"


def build_scene_params(shot: dict, scene_cfg: dict, location: dict, grade: dict) -> SceneP1Params:
    colour = location["colour"]
    state = shot.get("state_override") or "canonical appearance"
    scene_grade = grade["per_scene_grade"].get(shot["scene_id"], "")
    return SceneP1Params(
        scene_id=shot["scene_id"],
        episode="Episode 01",
        location_slug=location["slug"],
        location_desc=location["canonical"],
        lighting_desc=location["lighting_brief"],
        colour_desc=(
            f"Dominant: {colour['dominant']}. Accent: {colour['accent']}. "
            f"Blacks: {colour['blacks']}. Grade reference: {location['dop_ref']}. "
            f"Show look: {grade['show_look']['grade_intent']} Scene grade: {scene_grade}."
        ),
        composition=shot["composition"],
        subject_action=shot["action_brief"],
        seed=scene_cfg["seed"],
        extra_notes=(
            f"Camera spec: {shot['camera_spec']}. Emotion: {shot['emotion_intent']}. "
            f"Character state: {state}."
        ),
    )


def run(filter_scene: str | None, filter_shot: str | None, dry_run: bool) -> None:
    _load_env(ROOT)
    storyboard = json.loads((ROOT / "production/storyboard.json").read_text(encoding="utf-8"))["shots"]
    grade = json.loads((ROOT / "production/grade.json").read_text(encoding="utf-8"))

    shots_to_run = []
    for shot in storyboard:
        if filter_scene and shot["scene_id"] != filter_scene:
            continue
        if filter_shot and shot["shot_id"] != filter_shot:
            continue
        shots_to_run.append(shot)

    cost = sum(0.08 if s["primary_character"] else 0.03 for s in shots_to_run)
    print(f"\nShots à générer : {len(shots_to_run)} — coût estimé : ${cost:.2f}")

    if dry_run:
        for shot in shots_to_run:
            char = shot.get("primary_character") or "env-only"
            print(f"  {shot['shot_id']} | {char:<12} | {shot['shot_type']:<18} | {shot['action_brief'][:60]}")
        print(f"\n  Total estimé : ${cost:.2f}")
        print("\n[DRY-RUN] Aucun appel API.")
        return

    METRICS.parent.mkdir(parents=True, exist_ok=True)
    import time
    total_cost = 0.0

    for shot in shots_to_run:
        scene_cfg = load_scene(shot["scene_id"])
        location = load_location(shot["location_key"])
        out_dir = ROOT / f"production/shots/{shot['scene_id']}/{shot['shot_id']}"
        char_id = shot.get("primary_character")

        if char_id:
            char = load_character(char_id)
            ref_path = char.get("ref_image")
            if not ref_path or not Path(ref_path).exists():
                print(f"  !! {shot['shot_id']} — ref manquante pour '{char_id}'. Lancer gen_character_refs.py.")
                continue
            params = build_scene_params(shot, scene_cfg, location, grade)
            result = run_shot(
                scene_params=params,
                shot_id=shot["shot_id"],
                ref_img=Path(ref_path),
                out_dir=out_dir,
                p2_scene_env=location["lighting_brief"][:200],
                p2_subject_action=shot["action_brief"],
                root=ROOT,
            )
            entry = {
                "shot_id": shot["shot_id"],
                "scene_id": shot["scene_id"],
                "character": char_id,
                "arcface_score": result.score_1x,
                "cost": result.cost_total,
                "elapsed": result.elapsed_total,
                "result_1x": str(result.result_1x),
                "result_2x": str(result.result_2x),
                "flag_retake": result.score_1x < 0.85,
            }
            total_cost += result.cost_total
            score_str = f"score={result.score_1x:.4f}"
        else:
            # Shot environnement seulement — copie du master plate lieu (déjà généré en Phase B)
            import shutil
            location_ref = ROOT / f"production/location_refs/{shot['location_key']}_master.png"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / "shot_1x.png"
            if location_ref.exists():
                shutil.copy2(str(location_ref), str(out_path))
                score_str = "env-only (master plate copié)"
                flag = False
            else:
                score_str = "env-only (master plate MANQUANT — lancer location-refs d'abord)"
                flag = True
            entry = {
                "shot_id": shot["shot_id"],
                "scene_id": shot["scene_id"],
                "character": None,
                "result_1x": str(out_path) if location_ref.exists() else None,
                "flag_retake": flag,
                "note": score_str,
            }

        with open(METRICS, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"  {shot['shot_id']} | {score_str} | ${total_cost:.2f} cumulé")

    print(f"\nTerminé. Coût total : ${total_cost:.2f}")
    print("Rapport : python production/run.py report")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", default=None)
    parser.add_argument("--shot", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.scene, args.shot, args.dry_run)
