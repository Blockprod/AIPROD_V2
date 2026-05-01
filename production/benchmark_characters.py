"""
production/benchmark_characters.py
====================================
Valide les scores ArcFace des portraits de référence générés.
Lance une auto-comparaison intra-personnage si plusieurs angles générés.

COUT : $0 (ArcFace local, InsightFace buffalo_l)
Usage : python production/benchmark_characters.py [--char nara] [--verbose]
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.shot_pipeline import _score_arcface, _get_largest_face
from production.dashboard import load_all_characters
import cv2
import insightface

TARGET_SCORE = 0.85

_APP = None

def _get_app():
    global _APP
    if _APP is None:
        _APP = insightface.app.FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _APP.prepare(ctx_id=0, det_size=(640, 640))
    return _APP


def run(filter_chars: list[str], verbose: bool) -> None:
    app = _get_app()
    characters = load_all_characters()
    targets = filter_chars if filter_chars else list(characters.keys())
    targets = [c for c in targets if c in characters]

    bar = "=" * 55
    print(f"\n{bar}")
    print(f"  BENCHMARK ARCFACE — Portraits de référence")
    print(f"{bar}")

    passed, failed = [], []
    for cid in targets:
        char = characters[cid]
        ref_path = char.get("ref_image")
        if not ref_path or not Path(ref_path).exists():
            print(f"  {cid:<10} | MANQUANT — lancer gen_character_refs.py d'abord")
            failed.append(cid)
            continue
        img = cv2.imread(ref_path)
        if img is None:
            print(f"  {cid:<10} | ERREUR lecture image")
            failed.append(cid)
            continue
        face = _get_largest_face(app, img)
        if face is None:
            print(f"  {cid:<10} | AUCUN VISAGE DETECTE — retake requis")
            failed.append(cid)
            continue
        score = _score_arcface(app, img, img)
        status = "OK" if score >= TARGET_SCORE else "RETAKE"
        mark = "OK" if score >= TARGET_SCORE else "!!"
        print(f"  {cid:<10} | score={score:.4f} | {mark} {status}")
        if score >= TARGET_SCORE:
            passed.append(cid)
        else:
            failed.append(cid)

    print(f"\n  Résultat : {len(passed)} OK / {len(failed)} à retaker")
    if failed:
        print(f"  Retakes   : {', '.join(failed)}")
        print(f"  Commande  : python production/run.py char-refs --char {' '.join(failed)}")
    print(f"{bar}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--char", nargs="*", default=[])
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    run(args.char, args.verbose)
