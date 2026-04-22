from __future__ import annotations

from typing import NotRequired

from typing_extensions import TypedDict

from aiprod_adaptation.models.schema import AIPRODOutput

_ABRUPT_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("fear",    "joy"),
    ("joy",     "fear"),
    ("terror",  "neutral"),
    ("neutral", "terror"),
    ("grief",   "joy"),
    ("joy",     "grief"),
})


class EmotionState(TypedDict):
    shot_id: str
    scene_id: str
    emotion: str
    previous: NotRequired[str]
    transition_ok: bool


class EmotionArcTracker:
    def track(self, output: AIPRODOutput) -> list[EmotionState]:
        states: list[EmotionState] = []
        previous_emotion: str | None = None
        for episode in output.episodes:
            for shot in episode.shots:
                transition_ok = True
                if previous_emotion is not None:
                    transition_ok = (
                        previous_emotion, shot.emotion
                    ) not in _ABRUPT_TRANSITIONS
                state = EmotionState(
                    shot_id=shot.shot_id,
                    scene_id=shot.scene_id,
                    emotion=shot.emotion,
                    transition_ok=transition_ok,
                )
                if previous_emotion is not None:
                    state["previous"] = previous_emotion
                states.append(state)
                previous_emotion = shot.emotion
        return states

    def get_warnings(self, states: list[EmotionState]) -> list[str]:
        return [
            f"Abrupt emotion transition at shot {s['shot_id']}: "
            f"{s.get('previous', '?')} \u2192 {s['emotion']}"
            for s in states
            if not s["transition_ok"]
        ]
