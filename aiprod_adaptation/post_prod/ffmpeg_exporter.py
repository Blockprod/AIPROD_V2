"""
FFmpegExporter — assembles VideoOutput + AudioSynchronizer timeline into a final MP4.

Requires ffmpeg in PATH. Export steps:
  1. Per-clip: mux video + audio → clip_N.mp4 (using -shortest)
  2. Concat all clips → final output (resolution + fps from ProductionOutput)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from aiprod_adaptation.post_prod.audio_request import ProductionOutput


class FFmpegExporter:
    """Assembles a ProductionOutput timeline into a single MP4 file."""

    @staticmethod
    def is_available(ffmpeg_bin: str = "ffmpeg") -> bool:
        """Return True if ffmpeg binary is found on PATH."""
        return shutil.which(ffmpeg_bin) is not None

    def __init__(
        self,
        output_path: str,
        ffmpeg_bin: str = "ffmpeg",
        loglevel: str = "error",
    ) -> None:
        self._output_path = output_path
        self._ffmpeg_bin = ffmpeg_bin
        self._loglevel = loglevel

    def _run(self, args: list[str]) -> None:
        cmd = [self._ffmpeg_bin, "-loglevel", self._loglevel, "-y"] + args
        try:
            subprocess.run(cmd, check=True)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"ffmpeg binary not found: {self._ffmpeg_bin!r}. "
                "Install ffmpeg and ensure it is in PATH."
            )

    def export(self, production: ProductionOutput) -> str:
        """
        Mux and concatenate all clips.
        Returns the absolute path of the produced MP4 file.
        """
        with tempfile.TemporaryDirectory() as tmp:
            clip_paths: list[str] = []

            for i, clip in enumerate(production.timeline):
                clip_out = os.path.join(tmp, f"clip_{i:04d}.mp4")
                self._run([
                    "-i", clip.video_url,
                    "-i", clip.audio_url,
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-shortest",
                    clip_out,
                ])
                clip_paths.append(clip_out)

            filelist = os.path.join(tmp, "filelist.txt")
            with open(filelist, "w", encoding="utf-8") as f:
                for p in clip_paths:
                    f.write(f"file '{p}'\n")

            self._run([
                "-f", "concat",
                "-safe", "0",
                "-i", filelist,
                "-c:v", "libx264",
                "-s", production.resolution,
                "-r", str(production.fps),
                "-c:a", "aac",
                "-b:a", "320k",
                self._output_path,
            ])

        return str(Path(self._output_path).resolve())
