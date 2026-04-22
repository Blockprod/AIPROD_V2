"""
CSV export backend.

Produces one row per shot with fixed columns:
    episode_id, scene_id, shot_id, shot_type, camera_movement, prompt, duration_sec, emotion

metadata is intentionally excluded — it is reserved for renderer-specific backends.
"""

from __future__ import annotations

import csv
import io

from aiprod_adaptation.backends.base import BackendBase
from aiprod_adaptation.models.schema import AIPRODOutput

_COLUMNS = (
    "episode_id", "scene_id", "shot_id", "shot_type",
    "camera_movement", "prompt", "duration_sec", "emotion",
)


class CsvExport(BackendBase):
    def export(self, output: AIPRODOutput) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(_COLUMNS)
        for episode in output.episodes:
            for shot in episode.shots:
                writer.writerow([
                    episode.episode_id,
                    shot.scene_id,
                    shot.shot_id,
                    shot.shot_type,
                    shot.camera_movement,
                    shot.prompt,
                    shot.duration_sec,
                    shot.emotion,
                ])
        return buf.getvalue()
