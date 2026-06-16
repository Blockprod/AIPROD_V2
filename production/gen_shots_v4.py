"""
production/gen_shots_v4.py
===========================
Orchestrateur EP01 V4 — Blender render + stylisation des 35 shots.

Pipeline complet par shot :
    1. blender_render.py --shot {shot_id}    → frames PNG + depth EXR
    2. shot_pipeline_v4.py --shot {shot_id}  → frames stylisées
    3. video_pipeline.py --shot {shot_id}    → clip MP4
    4. quality_gate_v4.py --shot {shot_id}   → validation qualité

Fonctionnalités :
    - Checkpoint auto : reprend depuis le dernier shot terminé
    - Budget tracking : alerte si dépassement estimé (seuil $250)
    - Log production/metrics_v4.jsonl
    - Option --shot pour traiter un seul shot
    - Option --from-shot pour reprendre depuis un shot donné
    - Option --skip-blender / --skip-stylize pour les passes partielles

Usage :
    python production/gen_shots_v4.py --dry-run
    python production/gen_shots_v4.py --shot SCN_002_SHOT_001 --backend replicate --dry-run
    python production/gen_shots_v4.py --from-shot SCN_005_SHOT_001 --backend replicate --execute
    python production/gen_shots_v4.py --all --backend replicate --execute
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aiprod_adaptation.production.receipt import ExecutionAuthorization

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STORYBOARD_FILE = ROOT / "production/storyboard.json"
RENDERS_DIR = ROOT / "production/renders"
STYLIZED_DIR = ROOT / "production/stylized"
CLIPS_DIR = ROOT / "production/clips"
METRICS_FILE = ROOT / "production/metrics_v4.jsonl"
CHECKPOINT_FILE = ROOT / "production/checkpoint_v4.json"

# Read from environment so dev and prod can have different caps.
# Default 0.0 ensures any run without explicit configuration is blocked
# before spending API budget. Set AIPROD_BUDGET_CAP_USD=250 in production.
_BUDGET_ALERT_USD: float = float(os.environ.get("AIPROD_BUDGET_CAP_USD", "0.0"))
_DEFAULT_FPS = 24
_COST_PER_FRAME_REPLICATE = 0.04


# ------------------------------------------------------------------
# Orchestrateur principal
# ------------------------------------------------------------------

def run_all(
    shot_ids: list[str],
    backend: str = "replicate",
    skip_blender: bool = False,
    skip_stylize: bool = False,
    skip_video: bool = False,
    skip_qg: bool = False,
    fps: int = _DEFAULT_FPS,
    dry_run: bool = False,
    budget_cap: float = _BUDGET_ALERT_USD,
    authorization: ExecutionAuthorization | None = None,
) -> dict[str, Any]:
    """Traite une liste de shots en séquence avec checkpoint et suivi budget.

    Args:
        shot_ids:      Liste ordonnée des shots à traiter.
        backend:       Backend de stylisation (replicate/comfyui/null).
        skip_blender:  Passer le render Blender (frames déjà rendues).
        skip_stylize:  Passer la stylisation (frames déjà stylisées).
        skip_video:    Passer la conversion en clip.
        skip_qg:       Passer le quality gate.
        fps:           Framerate.
        dry_run:       Si True, ne déclenche aucun appel API/Blender/FFmpeg.

    Returns:
        dict {"processed", "passed_qg", "failed_qg", "total_cost_usd", "budget_ok"}.
    """
    if backend == "replicate" and not dry_run and authorization is None:
        raise RuntimeError("Paid backend blocked: a validated production receipt is required.")
    if skip_qg and not dry_run:
        raise RuntimeError("Quality gate cannot be skipped during production execution.")

    checkpoint = _load_checkpoint()
    total_cost = checkpoint.get("total_cost_usd", 0.0)
    processed = checkpoint.get("processed", [])
    states: dict[str, str] = dict(checkpoint.get("states", {}))

    # Pre-execution budget guard: estimate total remaining cost upfront
    if backend == "replicate" and not dry_run and not skip_stylize:
        remaining_ids = [s for s in shot_ids if s not in processed]
        total_estimated = sum(
            _count_frames(RENDERS_DIR / sid / "frames") * _COST_PER_FRAME_REPLICATE
            for sid in remaining_ids
        ) + total_cost
        if total_estimated > budget_cap:
            print(
                f"[gen_shots_v4] BUDGET CAP ATTEINT : coût estimé total "
                f"${total_estimated:.2f} > cap ${budget_cap:.2f}.\n"
                f"  Relancer avec --budget-cap {total_estimated:.0f} pour dépasser ce seuil.\n"
                f"  Aucun appel API n'a été lancé.",
                file=sys.stderr,
            )
            sys.exit(1)

    summary: list[dict[str, Any]] = []
    python_exe = sys.executable

    for shot_id in shot_ids:
        if shot_id in processed and not dry_run:
            print(f"[gen_shots_v4] [SKIP] {shot_id} -- deja traite (checkpoint)")
            continue

        print(f"\n{'='*60}")
        print(f"[gen_shots_v4] >> {shot_id}")
        print(f"{'='*60}")

        shot_result: dict[str, Any] = {"shot_id": shot_id, "steps": {}}
        shot_cost = 0.0

        # ─── Étape 1 : Blender render
        if not skip_blender:
            blender_ok, blender_info = _run_step(
                python_exe,
                ["pipeline/blender_render.py", "--shot", shot_id, "--fps", str(fps)]
                + (["--dry-run"] if dry_run else []),
                label="blender_render",
            )
            shot_result["steps"]["blender"] = {"ok": blender_ok, "info": blender_info}
            if not blender_ok and not dry_run:
                print("  [FAIL] Blender render echoue -- shot ignore")
                shot_result["passed_qg"] = False
                states[shot_id] = "retryable"
                _save_checkpoint({"processed": processed, "states": states, "total_cost_usd": total_cost})
                summary.append(shot_result)
                continue

        # ─── Étape 2 : Stylisation
        if not skip_stylize:
            frame_count = _count_frames(RENDERS_DIR / shot_id / "frames")
            estimated_cost = frame_count * _COST_PER_FRAME_REPLICATE if backend == "replicate" else 0.0

            if not dry_run and total_cost + estimated_cost > budget_cap:
                print(
                    f"  [STOP] BUDGET CAP : {total_cost + estimated_cost:.2f}$ > {budget_cap:.2f}$. "
                    f"Arrêt automatique. Relancer avec --budget-cap {total_cost + estimated_cost:.0f} pour continuer."
                )
                break

            stylize_ok, stylize_info = _run_step(
                python_exe,
                [
                    "pipeline/shot_pipeline_v4.py",
                    "--shot", shot_id,
                    "--backend", backend,
                    "--fps", str(fps),
                ]
                + (["--dry-run"] if dry_run else []),
                label="stylize",
            )
            shot_result["steps"]["stylize"] = {"ok": stylize_ok, "info": stylize_info}
            if stylize_ok and not dry_run:
                shot_cost += estimated_cost
                total_cost += estimated_cost
                states[shot_id] = "generated"

        # ─── Étape 3 : Clip vidéo
        if not skip_video:
            video_ok, video_info = _run_step(
                python_exe,
                ["pipeline/video_pipeline.py", "--shot", shot_id, "--fps", str(fps)]
                + (["--dry-run"] if dry_run else []),
                label="video",
            )
            shot_result["steps"]["video"] = {"ok": video_ok, "info": video_info}

        # ─── Étape 4 : Quality gate
        qg_passed = True
        if not skip_qg:
            qg_ok, qg_info = _run_step(
                python_exe,
                ["production/quality_gate_v4.py", "--shot", shot_id]
                + (["--no-write"] if dry_run else []),
                label="quality_gate",
            )
            qg_passed = qg_ok
            shot_result["steps"]["quality_gate"] = {"ok": qg_ok, "info": qg_info}

        shot_result["passed_qg"] = qg_passed
        shot_result["cost_usd"] = shot_cost
        summary.append(shot_result)

        if not dry_run:
            if qg_passed:
                states[shot_id] = "approved"
                if shot_id not in processed:
                    processed.append(shot_id)
            else:
                states[shot_id] = "quality_failed"
            _save_checkpoint({
                "processed": processed,
                "states": states,
                "total_cost_usd": total_cost,
            })

        _append_run_metrics(shot_result)

    passed_qg = sum(1 for r in summary if r.get("passed_qg", False))
    failed_qg = len(summary) - passed_qg

    final = {
        "processed": len(summary),
        "passed_qg": passed_qg,
        "failed_qg": failed_qg,
        "total_cost_usd": round(total_cost, 2),
        "budget_ok": total_cost <= budget_cap,
    }

    print(f"\n{'='*60}")
    print("[gen_shots_v4] RÉSUMÉ")
    print(f"  Shots traités    : {final['processed']}")
    print(f"  Quality gate [OK] : {final['passed_qg']}")
    print(f"  Quality gate [KO] : {final['failed_qg']}")
    print(f"  Coût total       : ${final['total_cost_usd']:.2f}")
    print(f"{'='*60}")

    return final


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _run_step(
    python_exe: str,
    args: list[str],
    label: str,
) -> tuple[bool, str]:
    """Exécute un sous-script Python et retourne (success, output_snippet)."""
    cmd = [python_exe] + args
    print(f"  → {label} : {' '.join(args[-4:])}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    ok = result.returncode == 0
    output = (result.stdout + result.stderr)[-800:]
    if not ok:
        print(f"  [FAIL] {label} a echoue :\n{output}")
    return ok, output


def _count_frames(frames_dir: Path) -> int:
    if not frames_dir.exists():
        return 0
    return len(list(frames_dir.glob("frame_*.png")))


def _load_checkpoint() -> dict[str, Any]:
    if CHECKPOINT_FILE.exists():
        try:
            data: dict[str, Any] = json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"processed": [], "total_cost_usd": 0.0}


def _save_checkpoint(data: dict[str, Any]) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_run_metrics(result: dict[str, Any]) -> None:
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    import datetime
    result_with_ts = {**result, "timestamp": datetime.datetime.now().isoformat()}
    with open(METRICS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(result_with_ts, ensure_ascii=False) + "\n")


def _load_shot_ids() -> list[str]:
    storyboard = json.loads(STORYBOARD_FILE.read_text(encoding="utf-8"))
    return [s["shot_id"] for s in storyboard.get("shots", [])]


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


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Orchestrateur V4 — génère les 35 shots EP01.")

    # Sélection des shots
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--shot", help="Traiter un seul shot (ex: SCN_002_SHOT_001)")
    group.add_argument("--from-shot", help="Reprendre depuis ce shot (inclus)")
    group.add_argument("--all", action="store_true", help="Tous les shots (35)")

    # Options passes
    parser.add_argument(
        "--backend",
        choices=["replicate", "comfyui", "null"],
        default="replicate",
    )
    parser.add_argument("--skip-blender", action="store_true")
    parser.add_argument("--skip-stylize", action="store_true")
    parser.add_argument("--skip-video", action="store_true")
    parser.add_argument("--skip-qg", action="store_true")
    parser.add_argument("--fps", type=int, default=_DEFAULT_FPS)

    # Mode exécution
    exec_group = parser.add_mutually_exclusive_group(required=True)
    exec_group.add_argument("--dry-run", action="store_true")
    exec_group.add_argument("--execute", action="store_true")

    # Checkpoint
    parser.add_argument(
        "--reset-checkpoint",
        action="store_true",
        help="Supprimer le checkpoint et recommencer depuis le début",
    )
    parser.add_argument(
        "--budget-cap",
        type=float,
        default=_BUDGET_ALERT_USD,
        metavar="USD",
        help=f"Seuil de coût USD au-delà duquel l'exécution est bloquée (défaut: {_BUDGET_ALERT_USD}$)",
    )

    parser.add_argument("--receipt", help="Preflight receipt required for paid execution")
    parser.add_argument("--ir", help="Strict IR v6 bound to the receipt")
    parser.add_argument("--storyboard", default=str(STORYBOARD_FILE))

    args = parser.parse_args()
    _load_env()

    if args.reset_checkpoint and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        print("[gen_shots_v4] Checkpoint supprimé.")

    all_shot_ids = _load_shot_ids()

    if args.shot:
        shot_ids = [args.shot]
    elif args.from_shot:
        try:
            idx = all_shot_ids.index(args.from_shot)
        except ValueError:
            print(f"Shot '{args.from_shot}' introuvable", file=sys.stderr)
            return 1
        shot_ids = all_shot_ids[idx:]
    else:
        shot_ids = all_shot_ids  # --all ou défaut

    authorization = None
    if args.execute and args.backend == "replicate":
        if not args.receipt or not args.ir:
            print("Paid execution requires --receipt and --ir.", file=sys.stderr)
            return 1
        from aiprod_adaptation.production.receipt import ReceiptValidationError, validate_receipt
        try:
            authorization = validate_receipt(
                Path(args.receipt),
                root=ROOT,
                ir_path=Path(args.ir),
                storyboard_path=Path(args.storyboard),
                shot_ids=shot_ids,
                backend=args.backend,
                budget_cap_usd=args.budget_cap,
            )
        except ReceiptValidationError as exc:
            print(f"Paid execution blocked: {exc}", file=sys.stderr)
            return 1

    result = run_all(
        shot_ids=shot_ids,
        backend=args.backend,
        skip_blender=args.skip_blender,
        skip_stylize=args.skip_stylize,
        skip_video=args.skip_video,
        skip_qg=args.skip_qg,
        fps=args.fps,
        dry_run=args.dry_run,
        budget_cap=args.budget_cap,
        authorization=authorization,
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("budget_ok", True) else 1


if __name__ == "__main__":
    _load_env()
    sys.exit(main())
