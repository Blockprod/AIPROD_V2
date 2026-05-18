"""
pipeline/video_pipeline.py
===========================
Conversion frames PNG → clips MP4 par shot + ajout audio.
Utilise FFmpeg (doit être installé et accessible dans PATH ou FFMPEG_EXECUTABLE dans .env).

Fonctions :
    frames_to_clip(frames_dir, fps, out_path)  → clip MP4 muet
    add_audio(clip_path, audio_path, out_path) → clip MP4 avec audio
    concat_clips(clip_paths, out_path)         → assemblage séquentiel

Usage :
    python pipeline/video_pipeline.py \\
        --shot SCN_002_SHOT_001 \\
        --stylized-dir production/stylized \\
        --out-dir production/clips \\
        --fps 24

Coût : gratuit (traitement local FFmpeg).
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

STYLIZED_DIR = ROOT / "production/stylized"
CLIPS_DIR = ROOT / "production/clips"
AUDIO_DIR = ROOT / "production/audio"

_DEFAULT_FPS = 24
_DEFAULT_CRF = 18  # qualité H.264 (0=lossless, 23=default, 18=high quality)
_DEFAULT_FFMPEG = "ffmpeg"


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def frames_to_clip(
    frames_dir: Path,
    fps: int = _DEFAULT_FPS,
    out_path: Path | None = None,
    crf: int = _DEFAULT_CRF,
    ffmpeg_exe: str | None = None,
) -> Path:
    """Convertit une séquence de frames PNG en clip MP4.

    Les frames doivent respecter le pattern : frame_NNNN.png (zéro-padded).

    Args:
        frames_dir: Répertoire contenant les frames PNG.
        fps:        Framerate.
        out_path:   Chemin du clip de sortie. Défaut: {frames_dir.parent}/clip.mp4
        crf:        Qualité H.264 (18 = haute qualité, 28 = compression forte).
        ffmpeg_exe: Chemin vers ffmpeg.

    Returns:
        Path vers le clip MP4 généré.

    Raises:
        FileNotFoundError: si aucune frame n'est trouvée dans frames_dir.
        RuntimeError:      si FFmpeg échoue.
    """
    frames = sorted(frames_dir.glob("frame_*.png"))
    if not frames:
        raise FileNotFoundError(f"Aucune frame PNG dans {frames_dir}")

    if out_path is None:
        out_path = frames_dir.parent / "clip.mp4"

    exe = ffmpeg_exe or _get_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Pattern FFmpeg : frame_%04d.png
    input_pattern = str(frames_dir / "frame_%04d.png")

    cmd = [
        exe, "-y",
        "-framerate", str(fps),
        "-i", input_pattern,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", str(crf),
        "-preset", "slow",
        "-movflags", "+faststart",
        str(out_path),
    ]
    _run(cmd, f"frames_to_clip → {out_path.name}")
    return out_path


def add_audio(
    clip_path: Path,
    audio_path: Path,
    out_path: Path | None = None,
    ffmpeg_exe: str | None = None,
) -> Path:
    """Ajoute une piste audio à un clip MP4 muet.

    La durée audio est tronquée/padded à la durée vidéo.

    Args:
        clip_path:   Clip MP4 muet.
        audio_path:  Fichier audio (MP3, WAV, AAC...).
        out_path:    Clip de sortie. Défaut: {clip_path.stem}_audio.mp4
        ffmpeg_exe:  Chemin vers ffmpeg.

    Returns:
        Path vers le clip MP4 avec audio.
    """
    if out_path is None:
        out_path = clip_path.parent / f"{clip_path.stem}_audio.mp4"

    exe = ffmpeg_exe or _get_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        exe, "-y",
        "-i", str(clip_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",  # tronque à la durée la plus courte
        "-map", "0:v:0",
        "-map", "1:a:0",
        str(out_path),
    ]
    _run(cmd, f"add_audio → {out_path.name}")
    return out_path


def concat_clips(
    clip_paths: list[Path],
    out_path: Path,
    ffmpeg_exe: str | None = None,
) -> Path:
    """Concatène une liste de clips MP4 en un seul fichier.

    Tous les clips doivent avoir le même codec, résolution et framerate.

    Args:
        clip_paths: Liste ordonnée des clips à assembler.
        out_path:   Fichier de sortie.
        ffmpeg_exe: Chemin vers ffmpeg.

    Returns:
        Path vers le clip assemblé.
    """
    if not clip_paths:
        raise ValueError("clip_paths est vide")

    exe = ffmpeg_exe or _get_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Écrire le fichier de liste FFmpeg concat
    concat_list = out_path.parent / "_concat_list.txt"
    lines = [f"file '{str(p.resolve())}'" for p in clip_paths]
    concat_list.write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        exe, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(out_path),
    ]
    _run(cmd, f"concat_clips → {out_path.name}")
    concat_list.unlink(missing_ok=True)
    return out_path


# ------------------------------------------------------------------
# Shot-level helper
# ------------------------------------------------------------------

def process_shot(
    shot_id: str,
    stylized_dir: Path = STYLIZED_DIR,
    clips_dir: Path = CLIPS_DIR,
    audio_dir: Path | None = None,
    fps: int = _DEFAULT_FPS,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Pipeline complet pour un shot : frames → clip (+audio si disponible).

    Returns:
        dict {"shot_id", "clip_path", "has_audio"}.
    """
    frames_dir = stylized_dir / shot_id / "frames"
    clip_path = clips_dir / f"{shot_id}.mp4"

    frames = sorted(frames_dir.glob("frame_*.png")) if frames_dir.exists() else []
    print(f"[video_pipeline] {shot_id}")
    print(f"  Frames     : {len(frames)}")
    print(f"  Clip out   : {clip_path}")

    if dry_run:
        print("  DRY-RUN — aucun appel FFmpeg")
        return {"shot_id": shot_id, "clip_path": str(clip_path), "has_audio": False}

    if not frames:
        raise FileNotFoundError(
            f"Aucune frame stylisée pour {shot_id} dans {frames_dir}. "
            f"Lancer shot_pipeline_v4.py --shot {shot_id} d'abord."
        )

    clip_path = frames_to_clip(frames_dir=frames_dir, fps=fps, out_path=clip_path)

    has_audio = False
    if audio_dir:
        audio_path = audio_dir / f"{shot_id}.mp3"
        if not audio_path.exists():
            audio_path = audio_dir / f"{shot_id}.wav"
        if audio_path.exists():
            audio_clip = clips_dir / f"{shot_id}_final.mp4"
            clip_path = add_audio(clip_path, audio_path, audio_clip)
            has_audio = True

    print(f"  [OK] Clip genere : {clip_path.name} (audio: {has_audio})")
    return {"shot_id": shot_id, "clip_path": str(clip_path), "has_audio": has_audio}


# ------------------------------------------------------------------
# Helpers internes
# ------------------------------------------------------------------

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
    parser = argparse.ArgumentParser(description="Convertit les frames stylisées en clips MP4.")
    parser.add_argument("--shot", required=True, help="Shot ID (ex: SCN_002_SHOT_001)")
    parser.add_argument("--stylized-dir", default=str(STYLIZED_DIR))
    parser.add_argument("--out-dir", default=str(CLIPS_DIR))
    parser.add_argument("--audio-dir", default=None)
    parser.add_argument("--fps", type=int, default=_DEFAULT_FPS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _load_env()
    result = process_shot(
        shot_id=args.shot,
        stylized_dir=Path(args.stylized_dir),
        clips_dir=Path(args.out_dir),
        audio_dir=Path(args.audio_dir) if args.audio_dir else None,
        fps=args.fps,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    _load_env()
    sys.exit(main())
