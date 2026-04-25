"""
Audio Cue Sheet export — music and sound design cue list.

Standard broadcast format (JSON) containing shot-by-shot cue index,
timecodes, cue type, mood, BPM hint, voice character and fade instructions.
"""

from __future__ import annotations

import json
from typing import Any

from aiprod_adaptation.core.postproduction import build_manifest_for_episode
from aiprod_adaptation.models.schema import AIPRODOutput


def export_audio_cue_sheet(
    output: AIPRODOutput,
    fps: float = 24.0,
) -> str:
    """Export audio cue sheet as JSON."""
    manifest = build_manifest_for_episode(output, fps=fps)

    cues: list[dict[str, Any]] = []
    for cue in manifest.audio_cues:
        cues.append(
            {
                "cue_number": f"Q{cue['cue_index'] + 1:03d}",
                "shot_id": cue["shot_id"],
                "scene_id": cue["scene_id"],
                "timecode_in": cue["timecode_in"],
                "timecode_out": cue["timecode_out"],
                "duration_sec": cue["duration_sec"],
                "cue_type": cue["cue_type"],
                "mood": cue["mood_tag"],
                "bpm_hint": cue.get("music_bpm_hint"),
                "sfx_description": cue.get("sfx_description"),
                "voice_char": cue.get("voice_char_id"),
                "fade_in_frames": cue.get("fade_in_frames", 0),
                "fade_out_frames": cue.get("fade_out_frames", 0),
            }
        )

    sheet: dict[str, Any] = {
        "title": output.title,
        "episode_id": manifest.episode_id,
        "fps": fps,
        "total_duration_sec": manifest.total_duration_sec,
        "cue_count": len(cues),
        "cues": cues,
    }
    return json.dumps(sheet, indent=2, ensure_ascii=False)
