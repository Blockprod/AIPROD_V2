"""
Post-production data models.

All dataclasses are serialisable via dataclasses.asdict().
PostProductionManifest is a Pydantic v2 model for JSON I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


@dataclass
class AudioCue:
    """Single audio event tied to a specific shot."""

    shot_id: str
    scene_id: str
    cue_index: int
    timecode_in: str          # "HH:MM:SS:FF"
    timecode_out: str         # "HH:MM:SS:FF"
    duration_sec: float
    cue_type: str             # "dialogue" | "ambiance" | "music" | "sfx" | "silence"
    mood_tag: str             # "tense" | "melancholic" | "uplifting" | "ambient" | "suspense"
    music_bpm_hint: int | None = None
    sfx_description: str | None = None
    voice_over_text: str | None = None
    voice_char_id: str | None = None
    fade_in_frames: int = 0
    fade_out_frames: int = 0


@dataclass
class ContinuityNote:
    """A detected continuity risk or violation between shots."""

    note_id: str
    shot_id: str
    scene_id: str
    continuity_type: str      # "spatial" | "color" | "props" | "lighting" | "establishing"
    note: str
    severity: str             # "info" | "warning" | "error"
    ref_shot_id: str | None = None


@dataclass
class TimelineClip:
    """A single clip entry in the NLE timeline."""

    clip_id: str
    shot_id: str
    scene_id: str
    episode_id: str
    track: int                # 0 = V1 primary video track
    timecode_in: str          # "HH:MM:SS:FF"
    timecode_out: str         # "HH:MM:SS:FF"
    duration_frames: int
    fps: float
    prompt: str
    shot_type: str
    camera_movement: str
    transition_in: str        # "cut" | "dissolve" | "fade_in"
    transition_out: str       # "cut" | "dissolve" | "fade_out"
    color_grade: str | None = None
    audio_cue_ids: list[str] = field(default_factory=list)


class PostProductionManifest(BaseModel):
    """
    Complete post-production manifest for one episode.

    Aggregates timeline, audio cues, and continuity notes
    ready for NLE import (DaVinci Resolve, Premiere, etc.).
    """

    episode_id: str
    fps: float = 24.0
    total_duration_sec: float
    total_frames: int
    timeline_clips: list[dict[str, Any]]     # serialized TimelineClip (dataclasses.asdict)
    audio_cues: list[dict[str, Any]]          # serialized AudioCue
    continuity_notes: list[dict[str, Any]]    # serialized ContinuityNote
    dominant_color_grade: str | None = None
    created_at: str                 # ISO 8601 datetime (UTC)
