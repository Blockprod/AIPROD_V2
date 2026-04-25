"""
AudioDirectivesBuilder — derives audio cues from Shot/Scene metadata.

Mapping logic
-------------
  1. scene_tone    → cue_type  (ambiance/music/sfx/silence/dialogue)
  2. dominant_sound override → dialogue or silence takes priority
  3. shot.emotion  → mood_tag (tense/melancholic/uplifting/ambient/suspense)
  4. mood_tag      → music_bpm_hint (only when cue_type == "music")
"""

from __future__ import annotations

from aiprod_adaptation.core.postproduction._timecode import frames_to_timecode
from aiprod_adaptation.core.postproduction.models import AudioCue
from aiprod_adaptation.models.schema import Scene, Shot

# ---------------------------------------------------------------------------
# Mapping tables
# ---------------------------------------------------------------------------

_EMOTION_TO_MOOD: dict[str, str] = {
    "tense": "tense",
    "fear": "tense",
    "anger": "tense",
    "disgust": "tense",
    "sad": "melancholic",
    "grief": "melancholic",
    "lonely": "melancholic",
    "sorrow": "melancholic",
    "melancholic": "melancholic",
    "joy": "uplifting",
    "excitement": "uplifting",
    "happy": "uplifting",
    "triumph": "uplifting",
    "hopeful": "uplifting",
    "surprise": "suspense",
    "anticipation": "suspense",
    "dread": "suspense",
    "neutral": "ambient",
    "contemplative": "ambient",
    "calm": "ambient",
}

_MOOD_TO_BPM: dict[str, int] = {
    "tense": 120,
    "melancholic": 60,
    "uplifting": 96,
    "ambient": 0,      # no BPM for ambient pads
    "suspense": 80,
}

_SCENE_TONE_TO_CUE: dict[str, str] = {
    "noir": "ambiance",
    "tense": "ambiance",
    "surreal": "sfx",
    "intimate": "dialogue",
    "epic": "music",
    "golden_hour": "music",
    "clinical": "silence",
    "neutral": "ambiance",
}


class AudioDirectivesBuilder:
    """Build a list of AudioCues from a shot list and scene list."""

    def build(
        self,
        shots: list[Shot],
        scenes: list[Scene],
        fps: float = 24.0,
    ) -> list[AudioCue]:
        scene_by_id = {sc.scene_id: sc for sc in scenes}
        cues: list[AudioCue] = []
        current_frame = 0

        for idx, shot in enumerate(shots):
            duration_frames = int(shot.duration_sec * fps)
            tc_in = frames_to_timecode(current_frame, fps)
            tc_out = frames_to_timecode(current_frame + duration_frames, fps)

            scene = scene_by_id.get(shot.scene_id)
            scene_tone: str = (
                (scene.scene_tone if scene else None)
                or shot.metadata.get("scene_tone", "neutral")
                or "neutral"
            )
            dominant_sound: str = shot.metadata.get("dominant_sound", "ambient") or "ambient"

            # Resolve cue_type: dominant_sound takes priority over scene_tone
            cue_type = _SCENE_TONE_TO_CUE.get(scene_tone, "ambiance")
            if dominant_sound == "dialogue":
                cue_type = "dialogue"
            elif dominant_sound == "silence":
                cue_type = "silence"

            mood = _EMOTION_TO_MOOD.get(shot.emotion, "ambient")
            raw_bpm = _MOOD_TO_BPM.get(mood, 0) if cue_type == "music" else 0
            bpm: int | None = raw_bpm if raw_bpm > 0 else None

            voice_char: str | None = (
                shot.action.subject_id if (cue_type == "dialogue" and shot.action) else None
            )
            sfx_desc: str | None = (
                f"{scene_tone} / {shot.emotion}" if cue_type == "sfx" else None
            )

            cues.append(
                AudioCue(
                    shot_id=shot.shot_id,
                    scene_id=shot.scene_id,
                    cue_index=idx,
                    timecode_in=tc_in,
                    timecode_out=tc_out,
                    duration_sec=float(shot.duration_sec),
                    cue_type=cue_type,
                    mood_tag=mood,
                    music_bpm_hint=bpm,
                    sfx_description=sfx_desc,
                    voice_over_text=None,
                    voice_char_id=voice_char,
                )
            )
            current_frame += duration_frames

        return cues
