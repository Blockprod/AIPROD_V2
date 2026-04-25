"""
core/postproduction — Post-production manifest generation.

Public API
----------
  build_manifest_for_episode(output, fps) -> PostProductionManifest
  AudioDirectivesBuilder
  ContinuityBuilder
  TimelineBuilder
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from aiprod_adaptation.core.postproduction.audio_directives import AudioDirectivesBuilder
from aiprod_adaptation.core.postproduction.continuity import ContinuityBuilder
from aiprod_adaptation.core.postproduction.models import (
    AudioCue,
    ContinuityNote,
    PostProductionManifest,
    TimelineClip,
)
from aiprod_adaptation.core.postproduction.timeline import TimelineBuilder
from aiprod_adaptation.models.schema import AIPRODOutput

__all__ = [
    "AudioCue",
    "AudioDirectivesBuilder",
    "ContinuityBuilder",
    "ContinuityNote",
    "PostProductionManifest",
    "TimelineBuilder",
    "TimelineClip",
    "build_manifest_for_episode",
]


def build_manifest_for_episode(
    output: AIPRODOutput,
    fps: float = 24.0,
) -> PostProductionManifest:
    """
    Build a complete PostProductionManifest from the first episode in *output*.

    Steps
    -----
      1. AudioDirectivesBuilder → list[AudioCue]
      2. TimelineBuilder        → list[TimelineClip]
      3. ContinuityBuilder      → list[ContinuityNote]
      4. Assemble manifest
    """
    if not output.episodes:
        return PostProductionManifest(
            episode_id="UNKNOWN",
            fps=fps,
            total_duration_sec=0.0,
            total_frames=0,
            timeline_clips=[],
            audio_cues=[],
            continuity_notes=[],
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    ep = output.episodes[0]
    shots = ep.shots
    scenes = ep.scenes

    audio_cues = AudioDirectivesBuilder().build(shots, scenes, fps=fps)
    clips = TimelineBuilder().build(shots, audio_cues, episode_id=ep.episode_id, fps=fps)
    cont_notes = ContinuityBuilder().build(shots, scenes)

    total_frames = sum(c.duration_frames for c in clips)
    total_duration = total_frames / fps if fps > 0 else 0.0

    # Dominant color grade — most frequent non-None value
    grade_counts: dict[str, int] = {}
    for clip in clips:
        if clip.color_grade:
            grade_counts[clip.color_grade] = grade_counts.get(clip.color_grade, 0) + 1
    dominant_grade: str | None = (
        max(grade_counts, key=grade_counts.__getitem__) if grade_counts else None
    )

    return PostProductionManifest(
        episode_id=ep.episode_id,
        fps=fps,
        total_duration_sec=round(total_duration, 3),
        total_frames=total_frames,
        timeline_clips=[dataclasses.asdict(c) for c in clips],
        audio_cues=[dataclasses.asdict(c) for c in audio_cues],
        continuity_notes=[dataclasses.asdict(n) for n in cont_notes],
        dominant_color_grade=dominant_grade,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
