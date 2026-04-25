"""
TimelineBuilder — assembles NLE timeline clips with SMPTE timecodes.

Transition logic
----------------
  • First clip              : fade_in
  • Last clip               : fade_out
  • Shot at scene boundary  : dissolve (both in and out)
  • Shot within same scene  : cut
"""

from __future__ import annotations

from aiprod_adaptation.core.postproduction._timecode import frames_to_timecode
from aiprod_adaptation.core.postproduction.models import AudioCue, TimelineClip
from aiprod_adaptation.models.schema import Shot


class TimelineBuilder:
    """Build a timeline clip list from a compiled shot list + audio cues."""

    def build(
        self,
        shots: list[Shot],
        audio_cues: list[AudioCue],
        episode_id: str = "EP01",
        fps: float = 24.0,
    ) -> list[TimelineClip]:
        # Map shot_id → first matching cue label
        cue_map: dict[str, str] = {}
        for cue in audio_cues:
            if cue.shot_id not in cue_map:
                cue_map[cue.shot_id] = f"CUE-{cue.cue_index:03d}"

        clips: list[TimelineClip] = []
        current_frame = 0
        n = len(shots)

        for idx, shot in enumerate(shots):
            duration_frames = int(shot.duration_sec * fps)
            tc_in = frames_to_timecode(current_frame, fps)
            tc_out = frames_to_timecode(current_frame + duration_frames, fps)

            # Transition IN
            if idx == 0:
                trans_in = "fade_in"
            elif shots[idx - 1].scene_id != shot.scene_id:
                trans_in = "dissolve"
            else:
                trans_in = "cut"

            # Transition OUT
            if idx == n - 1:
                trans_out = "fade_out"
            elif shot.scene_id != shots[idx + 1].scene_id:
                trans_out = "dissolve"
            else:
                trans_out = "cut"

            color_grade: str | None = shot.metadata.get("color_grade_hint")

            clips.append(
                TimelineClip(
                    clip_id=f"V{idx + 1:03d}",
                    shot_id=shot.shot_id,
                    scene_id=shot.scene_id,
                    episode_id=episode_id,
                    track=0,
                    timecode_in=tc_in,
                    timecode_out=tc_out,
                    duration_frames=duration_frames,
                    fps=fps,
                    prompt=shot.prompt,
                    shot_type=shot.shot_type,
                    camera_movement=shot.camera_movement,
                    transition_in=trans_in,
                    transition_out=trans_out,
                    color_grade=color_grade,
                    audio_cue_ids=[cue_map[shot.shot_id]] if shot.shot_id in cue_map else [],
                )
            )
            current_frame += duration_frames

        return clips
