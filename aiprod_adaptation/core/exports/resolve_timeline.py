"""
DaVinci Resolve-compatible timeline JSON export.

Produces an OTIO-inspired JSON format ingestible by custom DaVinci Resolve
importers or the OpenTimelineIO Python library.

Track structure
---------------
  V1 — primary video track (all shots, ordered)
  A1 — audio track (cues derived from AudioDirectivesBuilder)
"""

from __future__ import annotations

import json
from typing import Any

from aiprod_adaptation.core.postproduction import build_manifest_for_episode
from aiprod_adaptation.models.schema import AIPRODOutput


def export_resolve_timeline(
    output: AIPRODOutput,
    fps: float = 24.0,
) -> str:
    """Export AIPRODOutput as a DaVinci Resolve-compatible timeline JSON."""
    manifest = build_manifest_for_episode(output, fps=fps)

    # V1 — video track
    v1_clips: list[dict[str, Any]] = []
    for clip in manifest.timeline_clips:
        v1_clips.append(
            {
                "name": clip["shot_id"],
                "source_range": {
                    "start_time": {"value": 0, "rate": fps},
                    "duration": {"value": clip["duration_frames"], "rate": fps},
                },
                "metadata": {
                    "shot_id": clip["shot_id"],
                    "scene_id": clip["scene_id"],
                    "shot_type": clip["shot_type"],
                    "camera_movement": clip["camera_movement"],
                    "transition_in": clip["transition_in"],
                    "transition_out": clip["transition_out"],
                    "color_grade": clip.get("color_grade"),
                    "prompt": clip["prompt"],
                    "timecode_in": clip["timecode_in"],
                    "timecode_out": clip["timecode_out"],
                },
            }
        )

    # A1 — audio track
    a1_clips: list[dict[str, Any]] = []
    for cue in manifest.audio_cues:
        duration_frames = int(cue["duration_sec"] * fps)
        a1_clips.append(
            {
                "name": f"CUE-{cue['cue_index']:03d}",
                "cue_type": cue["cue_type"],
                "mood": cue["mood_tag"],
                "bpm": cue.get("music_bpm_hint"),
                "source_range": {
                    "start_time": {"value": 0, "rate": fps},
                    "duration": {"value": duration_frames, "rate": fps},
                },
                "metadata": {
                    "shot_id": cue["shot_id"],
                    "timecode_in": cue["timecode_in"],
                    "timecode_out": cue["timecode_out"],
                    "sfx_description": cue.get("sfx_description"),
                    "voice_char_id": cue.get("voice_char_id"),
                },
            }
        )

    timeline: dict[str, Any] = {
        "schema": "aiprod_resolve_timeline",
        "schema_version": "1.0",
        "name": output.title,
        "global_start_time": {"value": 0, "rate": fps},
        "fps": fps,
        "total_duration_sec": manifest.total_duration_sec,
        "total_frames": manifest.total_frames,
        "dominant_color_grade": manifest.dominant_color_grade,
        "tracks": [
            {"name": "V1", "kind": "Video", "clips": v1_clips},
            {"name": "A1", "kind": "Audio", "clips": a1_clips},
        ],
        "continuity_notes": manifest.continuity_notes,
        "created_at": manifest.created_at,
    }
    return json.dumps(timeline, indent=2, ensure_ascii=False)
