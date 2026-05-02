"""
production/run.py
==================
CLI unifié de production District Zero EP01 — méthode professionnelle v3.0

PHASES DE PRODUCTION :
  Phase A : python production/run.py char-refs [--char nara] [--dry-run]    $0.15
  Phase B : python production/run.py location-refs [--dry-run]              $0.30
  Phase B2: python production/run.py benchmark [--char nara]                $0
  Phase B3: python production/run.py location-angles [--loc X] [--angle Y]  $1.98
  Phase C : python production/run.py shots [--scene SCN_002] [--dry-run]    ~$2.80
  Phase D : python production/run.py retakes [--dry-run]                    variable
  Phase E : python production/run.py assembly [--fps 24]                    $0
  Rapport : python production/run.py report
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def cmd_char_refs(args):
    from production.gen_character_refs import run
    run(filter_chars=args.char or [], dry_run=args.dry_run)


def cmd_location_refs(args):
    from production.gen_location_refs import run
    run(filter_locs=args.loc or [], dry_run=args.dry_run)


def cmd_location_angles(args):
    from production.gen_location_angles import run
    run(filter_locs=args.loc or [], filter_angles=args.angle or [], dry_run=args.dry_run)


def cmd_benchmark(args):
    from production.benchmark_characters import run
    run(filter_chars=args.char or [], verbose=args.verbose)


def cmd_shots(args):
    from production.gen_shots import run
    run(filter_scene=args.scene, filter_shot=args.shot, dry_run=args.dry_run)


def cmd_report(args):
    metrics_path = ROOT / "production/shots/metrics.jsonl"
    if not metrics_path.exists():
        print("Aucune métrique — aucun shot généré pour l'instant.")
        return
    rows = [json.loads(l) for l in metrics_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    total_cost = sum(r.get("cost", 0) for r in rows)
    flagged = [r for r in rows if r.get("flag_retake")]
    scores = [r["arcface_score"] for r in rows if r.get("arcface_score")]
    bar = "=" * 55
    print(f"\n{bar}")
    print(f"  RAPPORT DE PRODUCTION EP01")
    print(f"{bar}")
    print(f"  Shots générés  : {len(rows)}")
    if scores:
        print(f"  Score ArcFace  : min={min(scores):.4f}  max={max(scores):.4f}  moy={sum(scores)/len(scores):.4f}")
    print(f"  A retaker      : {len(flagged)}")
    print(f"  Coût total     : ${total_cost:.2f}")
    print(f"{bar}\n")
    for r in flagged:
        score_val = r.get("arcface_score")
        score_str = f"{score_val:.4f}" if isinstance(score_val, float) else "n/a"
        print(f"  !! RETAKE : {r['shot_id']} — score={score_str}")


def cmd_retakes(args):
    metrics_path = ROOT / "production/shots/metrics.jsonl"
    if not metrics_path.exists():
        print("Aucune métrique.")
        return
    rows = [json.loads(l) for l in metrics_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    flagged = [r["shot_id"] for r in rows if r.get("flag_retake")]
    if not flagged:
        print("Aucun shot à retaker.")
        return
    from production.gen_shots import run
    for shot_id in flagged:
        scene_id = shot_id.rsplit("_SHOT_", 1)[0]
        run(filter_scene=scene_id, filter_shot=shot_id, dry_run=args.dry_run)


def cmd_assembly(args):
    from production.gen_assembly import run
    run(fps=args.fps)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="production/run.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cr = sub.add_parser("char-refs", help="Phase A — génère portraits référence personnages")
    p_cr.add_argument("--char", nargs="*")
    p_cr.add_argument("--dry-run", action="store_true")

    p_lr = sub.add_parser("location-refs", help="Phase B — génère master plates lieux")
    p_lr.add_argument("--loc", nargs="*")
    p_lr.add_argument("--dry-run", action="store_true")

    p_la = sub.add_parser("location-angles", help="Phase B3 — génère 3 angles visual bible par lieu")
    p_la.add_argument("--loc", nargs="*")
    p_la.add_argument("--angle", nargs="*", choices=["wide", "medium", "detail"])
    p_la.add_argument("--dry-run", action="store_true")

    p_bm = sub.add_parser("benchmark", help="Phase B2 — valide ArcFace des refs")
    p_bm.add_argument("--char", nargs="*")
    p_bm.add_argument("--verbose", action="store_true")

    p_sh = sub.add_parser("shots", help="Phase C — génère les shots EP01")
    p_sh.add_argument("--scene", default=None)
    p_sh.add_argument("--shot", default=None)
    p_sh.add_argument("--dry-run", action="store_true")

    sub.add_parser("report", help="Rapport de production")

    p_rt = sub.add_parser("retakes", help="Phase D — régénère les shots flaggés")
    p_rt.add_argument("--dry-run", action="store_true")

    p_asm = sub.add_parser("assembly", help="Phase E — assemble rough cut EP01")
    p_asm.add_argument("--fps", type=int, default=24)

    args = parser.parse_args()
    dispatch = {
        "char-refs": cmd_char_refs,
        "location-refs": cmd_location_refs,
        "location-angles": cmd_location_angles,
        "benchmark": cmd_benchmark,
        "shots": cmd_shots,
        "report": cmd_report,
        "retakes": cmd_retakes,
        "assembly": cmd_assembly,
    }
    dispatch[args.cmd](args)
