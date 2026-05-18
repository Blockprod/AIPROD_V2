"""
pipeline/assembly.py
=====================
Assemblage final EP01 — concatène les 35 clips dans l'ordre storyboard.

Pipeline :
    1. Lit storyboard.json → ordre canonique des 35 shots
    2. Résout le clip MP4 de chaque shot (clips_dir/{shot_id}.mp4 ou _final.mp4)
    3. Génère production/ep01_assembly.mp4 via FFmpeg concat

Options :
    --add-music     : ajoute la piste musicale sous les dialogues
    --add-credits   : ajoute un clip de générique final (s'il existe)
    --out           : chemin de sortie (défaut: production/ep01_assembly.mp4)
    --dry-run       : affiche le plan sans exécuter FFmpeg

Usage :
    python pipeline/assembly.py --dry-run
    python pipeline/assembly.py --out production/ep01_assembly.mp4 --execute
    python pipeline/assembly.py --out production/ep01_assembly.mp4 --add-music production/audio/music.mp3 --execute
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STORYBOARD_FILE = ROOT / "production/storyboard.json"
CLIPS_DIR = ROOT / "production/clips"
ASSEMBLY_OUT = ROOT / "production/ep01_assembly.mp4"
CREDITS_CLIP = ROOT / "production/clips/credits.mp4"

_DEFAULT_FFMPEG = "ffmpeg"


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def assemble_episode(
    clips_dir: Path = CLIPS_DIR,
    out_path: Path = ASSEMBLY_OUT,
    music_path: Path | None = None,
    credits_clip: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Assemble les clips de l'EP01 dans l'ordre storyboard.

    Args:
        clips_dir:    Répertoire contenant les clips MP4 par shot.
        out_path:     Chemin du fichier assemblé final.
        music_path:   Piste musicale à mixer sous les dialogues (optionnel).
        credits_clip: Clip de générique à ajouter à la fin (optionnel).
        dry_run:      Si True, affiche le plan sans exécuter FFmpeg.

    Returns:
        dict {"out_path", "shots_assembled", "missing_clips", "duration_s_estimate"}.
    """
    storyboard = _load_json(STORYBOARD_FILE)
    shots = storyboard.get("shots", [])
    ordered_ids = [s["shot_id"] for s in shots]

    # Résolution des clips — priorité au clip _final (avec audio)
    clip_paths: list[Path] = []
    missing: list[str] = []

    for shot_id in ordered_ids:
        clip = _resolve_clip(clips_dir, shot_id)
        if clip is None:
            missing.append(shot_id)
        else:
            clip_paths.append(clip)

    # Ajouter générique si disponible
    if credits_clip and credits_clip.exists():
        clip_paths.append(credits_clip)

    # Durée estimée (d'après storyboard)
    total_sec = sum(s.get("duration_sec", 5) for s in shots)

    print(f"[assembly] EP01 — {len(clip_paths)} clips / {len(ordered_ids)} shots")
    if missing:
        print(f"  [WARN] Clips manquants ({len(missing)}) : {missing[:5]}{'...' if len(missing) > 5 else ''}")
    print(f"  Durée estimée  : {total_sec // 60}min {total_sec % 60}s")
    print(f"  Sortie         : {out_path}")

    if dry_run:
        print("  DRY-RUN — aucun appel FFmpeg")
        return {
            "out_path": str(out_path),
            "shots_assembled": len(clip_paths),
            "missing_clips": missing,
            "duration_s_estimate": total_sec,
        }

    if not clip_paths:
        raise FileNotFoundError(
            f"Aucun clip disponible dans {clips_dir}. "
            f"Lancer gen_shots_v4.py --all --execute d'abord."
        )

    if missing:
        print(
            f"  [WARN] {len(missing)} shots manquants — assemblage partiel ({len(clip_paths)}/{len(ordered_ids)} shots)"
        )

    # Concatène les clips
    out_path.parent.mkdir(parents=True, exist_ok=True)
    concat_tmp = out_path.parent / "_concat_list.txt"
    lines = [f"file '{str(p.resolve())}'" for p in clip_paths]
    concat_tmp.write_text("\n".join(lines), encoding="utf-8")

    ffmpeg = _get_ffmpeg()
    cmd_concat = [
        ffmpeg, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_tmp),
        "-c", "copy",
        str(out_path),
    ]
    _run(cmd_concat, "concat 35 clips")
    concat_tmp.unlink(missing_ok=True)

    # Mixage musique (optionnel) — musique en fond, dialogue prioritaire
    if music_path and music_path.exists():
        out_with_music = out_path.with_stem(out_path.stem + "_music")
        cmd_mix = [
            ffmpeg, "-y",
            "-i", str(out_path),
            "-i", str(music_path),
            "-filter_complex",
            "[0:a]volume=1.0[a1];[1:a]volume=0.15[a2];[a1][a2]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "256k",
            str(out_with_music),
        ]
        _run(cmd_mix, "mixage musique + dialogue")
        out_path = out_with_music

    print(f"  [OK] Assemblage termine : {out_path.name}")
    return {
        "out_path": str(out_path),
        "shots_assembled": len(clip_paths),
        "missing_clips": missing,
        "duration_s_estimate": total_sec,
    }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _resolve_clip(clips_dir: Path, shot_id: str) -> Path | None:
    """Cherche le clip d'un shot (priorité: _final > standard)."""
    candidates = [
        clips_dir / f"{shot_id}_final.mp4",
        clips_dir / f"{shot_id}.mp4",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _get_ffmpeg() -> str:
    _load_env()
    return os.environ.get("FFMPEG_EXECUTABLE", _DEFAULT_FFMPEG)


def _run(cmd: list[str], label: str) -> None:
    print(f"  FFmpeg : {label}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg a échoué ({label}):\n{result.stderr[-2000:]}"
        )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
    parser = argparse.ArgumentParser(description="Assemble les clips EP01 dans l'ordre storyboard.")
    parser.add_argument("--clips-dir", default=str(CLIPS_DIR))
    parser.add_argument("--out", default=str(ASSEMBLY_OUT))
    parser.add_argument("--add-music", default=None, help="Chemin piste musicale (MP3/WAV)")
    parser.add_argument("--add-credits", default=None, help="Chemin clip générique (MP4)")

    exec_group = parser.add_mutually_exclusive_group(required=True)
    exec_group.add_argument("--dry-run", action="store_true")
    exec_group.add_argument("--execute", action="store_true")

    args = parser.parse_args()
    _load_env()

    result = assemble_episode(
        clips_dir=Path(args.clips_dir),
        out_path=Path(args.out),
        music_path=Path(args.add_music) if args.add_music else None,
        credits_clip=Path(args.add_credits) if args.add_credits else None,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    _load_env()
    sys.exit(main())
