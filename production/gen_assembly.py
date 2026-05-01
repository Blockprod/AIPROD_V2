"""
production/gen_assembly.py
===========================
Assemble les shots de EP01 en rough cut via ffmpeg.
Source: storyboard.json (duration_sec), production/shots/ (images générées)

COUT : $0 — ffmpeg local
Usage : python production/run.py assembly [--fps 24]
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(fps: int = 24) -> None:
    storyboard = json.loads((ROOT / "production/storyboard.json").read_text(encoding="utf-8"))["shots"]
    out_dir = ROOT / "production/assembly"
    out_dir.mkdir(parents=True, exist_ok=True)

    filelist_path = out_dir / "filelist.txt"
    lines: list[str] = []
    missing: list[str] = []

    for shot in storyboard:
        # Priorité : shot_2x > shot_1x > master plate lieu (env-only)
        candidates = [
            ROOT / f"production/shots/{shot['scene_id']}/{shot['shot_id']}/shot_2x.png",
            ROOT / f"production/shots/{shot['scene_id']}/{shot['shot_id']}/shot_1x.png",
        ]
        found = next((p for p in candidates if p.exists()), None)
        if not found:
            missing.append(shot["shot_id"])
            continue
        lines.append(f"file '{found.as_posix()}'")
        lines.append(f"duration {shot['duration_sec']}")

    if missing:
        print(f"\n  !! {len(missing)} shots manquants :")
        for sid in missing[:10]:
            print(f"     - {sid}")
        if len(missing) > 10:
            print(f"     ... et {len(missing) - 10} autres")

    if not lines:
        print("Aucun shot disponible — lancer Phase C d'abord.")
        return

    filelist_path.write_text("\n".join(lines), encoding="utf-8")
    out_path = out_dir / "DZ_EP01_rough_cut_v001.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(filelist_path),
        "-vf", (
            f"fps={fps},"
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        str(out_path),
    ]
    print(f"\nAssemblage — {len(lines) // 2} shots — fps={fps} — sortie : {out_path.name}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Rough cut généré : {out_path}")
    else:
        print(f"Erreur ffmpeg :\n{result.stderr[-500:]}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fps", type=int, default=24)
    run(fps=parser.parse_args().fps)
