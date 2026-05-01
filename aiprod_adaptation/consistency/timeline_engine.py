"""
TimelineEngine — Calcule et valide les timestamps absolus d'un épisode.

Responsabilités:
    - Calculer offset_in_episode pour chaque shot (somme cumulée des durées)
    - Calculer offset_in_season à partir de episode_offsets
    - Valider la monotonie et l'absence de gaps/chevauchements
    - Exporter vers Timeline (schema v5.0)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aiprod_adaptation.models.schema import AIPRODOutput, Timeline


@dataclass
class TimelineValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


class TimelineEngine:
    """Builds and validates a master Timeline from an AIPRODOutput."""

    def build(self, output: AIPRODOutput, episode_offsets: dict[str, int] | None = None) -> Timeline:
        """
        Computes absolute timestamps for all shots in all episodes.
        episode_offsets: optional dict mapping episode_id → season-level offset in seconds.
        If not provided, offsets are computed cumulatively from episode durations.
        """
        if episode_offsets is None:
            episode_offsets = self._compute_episode_offsets(output)

        absolute_timestamps: list[dict[str, Any]] = []

        for episode in output.episodes:
            ep_offset = episode_offsets.get(episode.episode_id, 0)
            cursor = 0
            for shot in episode.shots:
                duration = shot.duration_sec
                entry: dict[str, Any] = {
                    "shot_id": shot.shot_id,
                    "episode_id": episode.episode_id,
                    "offset_in_episode": cursor,
                    "offset_in_season": ep_offset + cursor,
                    "duration_sec": duration,
                    "end_offset": cursor + duration,
                }
                absolute_timestamps.append(entry)
                cursor += duration

        return Timeline(
            episode_offsets=episode_offsets,
            absolute_timestamps=absolute_timestamps,
        )

    def validate(self, timeline: Timeline) -> TimelineValidationResult:
        """
        Validates a Timeline against consistency rules:
          - First shot of each episode starts at offset 0
          - No gaps or overlaps between consecutive shots in an episode
          - All duration_sec values are in [3, 8]
        """
        errors: list[str] = []
        ts = timeline.absolute_timestamps
        if not ts:
            return TimelineValidationResult(valid=True)

        # Group by episode
        episodes: dict[str, list[dict[str, Any]]] = {}
        for entry in ts:
            episodes.setdefault(entry["episode_id"], []).append(entry)

        for ep_id, shots in episodes.items():
            # Check first shot starts at 0
            if shots[0]["offset_in_episode"] != 0:
                errors.append(
                    f"EP {ep_id}: first shot '{shots[0]['shot_id']}' offset_in_episode "
                    f"should be 0, got {shots[0]['offset_in_episode']}"
                )

            # Check consecutive shots are contiguous
            for i in range(1, len(shots)):
                prev = shots[i - 1]
                curr = shots[i]
                expected_start = prev["offset_in_episode"] + prev["duration_sec"]
                actual_start = curr["offset_in_episode"]
                if expected_start != actual_start:
                    errors.append(
                        f"EP {ep_id}: gap/overlap between '{prev['shot_id']}' "
                        f"(end={expected_start}) and '{curr['shot_id']}' "
                        f"(start={actual_start})"
                    )

            # Check durations in [3, 8]
            for shot in shots:
                d = shot["duration_sec"]
                if not 3 <= d <= 8:
                    errors.append(
                        f"EP {ep_id}: shot '{shot['shot_id']}' duration_sec={d} "
                        f"out of range [3, 8]"
                    )

        return TimelineValidationResult(valid=len(errors) == 0, errors=errors)

    def _compute_episode_offsets(self, output: AIPRODOutput) -> dict[str, int]:
        offsets: dict[str, int] = {}
        cursor = 0
        for episode in output.episodes:
            offsets[episode.episode_id] = cursor
            cursor += sum(s.duration_sec for s in episode.shots)
        return offsets
