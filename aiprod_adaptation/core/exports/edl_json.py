"""
EDL-like JSON export — Edit Decision List in JSON format.

Based on CMX 3600 EDL concepts translated to JSON for AI generation tools.
Record timecodes start at 01:00:00:00 (broadcast convention, offset 86 400 frames at 24 fps).

Output structure
----------------
{
  "edl_version": "1.0",
  "title": "...",
  "fps": 24.0,
  "total_duration_sec": ...,
  "clip_count": ...,
  "clips": [
    {
      "clip_id": "V001",
      "shot_id": "...",
      "scene_id": "...",
      "reel": "EP01",
      "record_tc_in": "01:00:00:00",
      "record_tc_out": "01:00:05:00",
      "source_tc_in": "00:00:00:00",
      "source_tc_out": "00:00:05:00",
      "transition": "cut",
      "prompt": "...",
      "shot_type": "medium",
      "camera_movement": "static",
      "emotion": "neutral",
      "duration_sec": 5
    }
  ]
}
"""

from __future__ import annotations

import json
from typing import Any

from aiprod_adaptation.core.postproduction._timecode import frames_to_timecode
from aiprod_adaptation.models.schema import AIPRODOutput

_RECORD_OFFSET_FRAMES = 86_400  # 01:00:00:00 at 24 fps


def export_edl_json(
    output: AIPRODOutput,
    fps: float = 24.0,
    start_timecode_offset_frames: int = _RECORD_OFFSET_FRAMES,
) -> str:
    """Export AIPRODOutput as an EDL-like JSON string."""
    clips: list[dict[str, Any]] = []
    record_frame = start_timecode_offset_frames
    source_frame = 0

    for ep in output.episodes:
        for idx, shot in enumerate(ep.shots):
            duration_frames = int(shot.duration_sec * fps)
            rec_tc_in = frames_to_timecode(record_frame, fps)
            rec_tc_out = frames_to_timecode(record_frame + duration_frames, fps)
            src_tc_in = frames_to_timecode(source_frame, fps)
            src_tc_out = frames_to_timecode(source_frame + duration_frames, fps)

            prev_scene = ep.shots[idx - 1].scene_id if idx > 0 else None
            if idx == 0:
                transition = "fade_in"
            elif prev_scene != shot.scene_id:
                transition = "dissolve"
            else:
                transition = "cut"

            clips.append(
                {
                    "clip_id": f"V{len(clips) + 1:03d}",
                    "shot_id": shot.shot_id,
                    "scene_id": shot.scene_id,
                    "reel": ep.episode_id,
                    "record_tc_in": rec_tc_in,
                    "record_tc_out": rec_tc_out,
                    "source_tc_in": src_tc_in,
                    "source_tc_out": src_tc_out,
                    "transition": transition,
                    "prompt": shot.prompt,
                    "shot_type": shot.shot_type,
                    "camera_movement": shot.camera_movement,
                    "emotion": shot.emotion,
                    "duration_sec": shot.duration_sec,
                }
            )
            record_frame += duration_frames
            source_frame += duration_frames

    total_duration = sum(c["duration_sec"] for c in clips)
    edl: dict[str, Any] = {
        "edl_version": "1.0",
        "title": output.title,
        "fps": fps,
        "total_duration_sec": round(total_duration, 3),
        "clip_count": len(clips),
        "clips": clips,
    }
    return json.dumps(edl, indent=2, ensure_ascii=False)
