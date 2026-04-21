"""
JSON flat export backend.

Produces a flat list of shots (no episodes/scenes hierarchy).
Each item is enriched with episode_id at root level.
metadata is included only when non-empty.
"""

from __future__ import annotations

import json
from typing import Any

from aiprod_adaptation.backends.base import BackendBase
from aiprod_adaptation.models.schema import AIPRODOutput


class JsonFlatExport(BackendBase):
    def export(self, output: AIPRODOutput) -> str:
        rows: list[dict[str, Any]] = []
        for episode in output.episodes:
            for shot in episode.shots:
                row: dict[str, Any] = {
                    "episode_id":   episode.episode_id,
                    "scene_id":     shot.scene_id,
                    "shot_id":      shot.shot_id,
                    "prompt":       shot.prompt,
                    "duration_sec": shot.duration_sec,
                    "emotion":      shot.emotion,
                }
                if shot.metadata:
                    row["metadata"] = shot.metadata
                rows.append(row)
        return json.dumps(rows, indent=2, ensure_ascii=False)
