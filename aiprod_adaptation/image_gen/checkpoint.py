from __future__ import annotations

import json
from pathlib import Path

import structlog

from aiprod_adaptation.image_gen.image_request import ShotStoryboardFrame

logger = structlog.get_logger(__name__)


class CheckpointStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._cache: dict[str, ShotStoryboardFrame] = {}
        if path is not None and Path(path).exists():
            try:
                raw = Path(path).read_text(encoding="utf-8")
                data: dict[str, object] = json.loads(raw)
                for shot_id, frame_dict in data.items():
                    self._cache[shot_id] = ShotStoryboardFrame.model_validate(frame_dict)
            except Exception as exc:
                logger.warning(
                    "checkpoint_load_failed",
                    checkpoint_path=str(path),
                    error=str(exc),
                )

    def has(self, shot_id: str) -> bool:
        return shot_id in self._cache

    def get(self, shot_id: str) -> ShotStoryboardFrame | None:
        return self._cache.get(shot_id)

    def save(self, frame: ShotStoryboardFrame) -> None:
        self._cache[frame.shot_id] = frame
        if self._path is not None:
            serialized = {k: v.model_dump() for k, v in self._cache.items()}
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            Path(self._path).write_text(
                json.dumps(serialized, indent=2), encoding="utf-8"
            )

    def all_cached(self) -> list[ShotStoryboardFrame]:
        return list(self._cache.values())
