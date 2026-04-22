from __future__ import annotations

from dataclasses import dataclass, field

from aiprod_adaptation.models.intermediate import VisualScene


@dataclass
class SceneValidationResult:
    scene_id: str
    is_valid: bool
    score: float
    issues: list[str] = field(default_factory=list)


class StoryValidator:
    """
    Validates each VisualScene for filmability before Pass 3.
    Fully deterministic — zero LLM dependency.
    """

    INTERNAL_THOUGHT_WORDS: list[str] = [
        "thought", "wondered", "realized", "remembered",
        "imagined", "believed", "felt that", "knew", "hoped",
    ]

    IMPOSSIBLE_ACTION_PATTERNS: list[str] = [
        "dreamed", "dreamt", "fantasized", "hallucinated", "envisioned",
    ]

    _VALID_EMOTIONS: frozenset[str] = frozenset(
        {"angry", "scared", "sad", "happy", "nervous", "neutral"}
    )

    def validate(self, scene: VisualScene) -> SceneValidationResult:
        issues: list[str] = []

        location = scene.get("location", "")
        if not location or location.lower() == "unknown":
            issues.append("location_missing")

        actions = scene.get("visual_actions", [])
        if not actions:
            issues.append("no_filmable_actions")

        for action in actions:
            lower = action.lower()
            for w in self.INTERNAL_THOUGHT_WORDS:
                if w in lower:
                    issues.append(f"internal_thought: {action[:60]}")
                    break
            for p in self.IMPOSSIBLE_ACTION_PATTERNS:
                if p in lower:
                    issues.append(f"impossible_action: {action[:60]}")
                    break

        if len(scene.get("characters", [])) > 2:
            issues.append(f"too_many_characters: {len(scene['characters'])}")

        emotion = scene.get("emotion", "")
        if emotion not in self._VALID_EMOTIONS:
            issues.append(f"invalid_emotion: {emotion}")

        score = max(0.0, 1.0 - len(issues) * 0.25)
        return SceneValidationResult(
            scene_id=scene["scene_id"],
            is_valid=len(issues) == 0,
            score=score,
            issues=issues,
        )

    def validate_all(
        self,
        scenes: list[VisualScene],
        threshold: float = 0.5,
    ) -> list[VisualScene]:
        return [s for s in scenes if self.validate(s).score >= threshold]
