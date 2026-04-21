"""
AudioSynchronizer — syncs AudioAdapter output with VideoOutput to produce
a fully ordered ProductionOutput (timeline with cumulative start_sec).
"""

from __future__ import annotations

from typing import Dict, List

from aiprod_adaptation.models.schema import AIPRODOutput, Scene, Shot
from aiprod_adaptation.post_prod.audio_adapter import AudioAdapter
from aiprod_adaptation.post_prod.audio_request import (
    AudioRequest,
    AudioResult,
    ProductionOutput,
    TimelineClip,
)
from aiprod_adaptation.video_gen.video_request import VideoClipResult, VideoOutput


def _shot_map(output: AIPRODOutput) -> Dict[str, Shot]:
    return {shot.shot_id: shot for ep in output.episodes for shot in ep.shots}


def _scene_map(output: AIPRODOutput) -> Dict[str, Scene]:
    return {scene.scene_id: scene for ep in output.episodes for scene in ep.scenes}


def _text_for_shot(shot: Shot, scene: Scene | None) -> str:
    """Return dialogue if available, else the visual prompt."""
    if scene is not None and scene.dialogues:
        return scene.dialogues[0]
    return shot.prompt


class AudioSynchronizer:
    """Orchestrate audio generation and timeline assembly."""

    def __init__(self, adapter: AudioAdapter) -> None:
        self._adapter = adapter

    def build_requests(
        self,
        video: VideoOutput,
        output: AIPRODOutput,
    ) -> List[AudioRequest]:
        shots = _shot_map(output)
        scenes = _scene_map(output)
        requests: List[AudioRequest] = []
        for clip in video.clips:
            shot = shots.get(clip.shot_id)
            scene = scenes.get(shot.scene_id) if shot is not None else None
            text = _text_for_shot(shot, scene) if shot is not None else clip.video_url
            requests.append(
                AudioRequest(
                    shot_id=clip.shot_id,
                    scene_id=shot.scene_id if shot is not None else "",
                    text=text,
                    duration_hint_sec=clip.duration_sec,
                )
            )
        return requests

    def generate(
        self,
        video: VideoOutput,
        output: AIPRODOutput,
    ) -> tuple[List[AudioResult], ProductionOutput]:
        requests = self.build_requests(video, output)
        audio_results: List[AudioResult] = []

        for request in requests:
            try:
                result = self._adapter.generate(request)
            except Exception:
                result = AudioResult(
                    shot_id=request.shot_id,
                    audio_url="error://generation-failed",
                    duration_sec=request.duration_hint_sec,
                    model_used="error",
                    latency_ms=0,
                )
            audio_results.append(result)

        # Build ordered timeline with cumulative start_sec
        timeline: List[TimelineClip] = []
        start_sec = 0
        clip_by_shot: Dict[str, VideoClipResult] = {c.shot_id: c for c in video.clips}
        shots_map = _shot_map(output)

        for audio in audio_results:
            video_clip = clip_by_shot.get(audio.shot_id)
            video_url = video_clip.video_url if video_clip is not None else ""
            duration = audio.duration_sec
            shot = shots_map.get(audio.shot_id)
            scene_id = shot.scene_id if shot is not None else ""
            timeline.append(
                TimelineClip(
                    shot_id=audio.shot_id,
                    scene_id=scene_id,
                    video_url=video_url,
                    audio_url=audio.audio_url,
                    duration_sec=duration,
                    start_sec=start_sec,
                )
            )
            start_sec += duration

        production = ProductionOutput(
            title=video.title,
            timeline=timeline,
            total_duration_sec=start_sec,
        )
        return audio_results, production
