from __future__ import annotations

from typing import List

from aiprod_adaptation.core.continuity.character_registry import CharacterProfile
from aiprod_adaptation.core.continuity.emotion_arc import EmotionState
from aiprod_adaptation.models.schema import AIPRODOutput, Episode, Shot  # Episode/Shot used in type hints below


class PromptEnricher:
    def enrich(
        self,
        output: AIPRODOutput,
        registry: dict[str, CharacterProfile],
        arc_states: List[EmotionState],
    ) -> AIPRODOutput:
        arc_by_shot = {s["shot_id"]: s for s in arc_states}
        enriched_episodes: List[Episode] = []

        for episode in output.episodes:
            enriched_shots: List[Shot] = []
            for shot in episode.shots:
                enriched_prompt = self._enrich_prompt(
                    shot.prompt,
                    registry,
                    arc_by_shot.get(shot.shot_id),
                )
                enriched_shots.append(shot.model_copy(update={"prompt": enriched_prompt}))
            enriched_episodes.append(
                episode.model_copy(update={"shots": enriched_shots})
            )

        return output.model_copy(update={"episodes": enriched_episodes})

    def _enrich_prompt(
        self,
        prompt: str,
        registry: dict[str, CharacterProfile],
        arc_state: EmotionState | None,
    ) -> str:
        parts = [prompt]
        # Inject description for all registry characters with a non-empty description.
        # sorted() → byte-level determinism guaranteed.
        for char in sorted(registry.keys()):
            profile = registry[char]
            if profile["description"]:
                parts.append(f"{char}: {profile['description']}.")
        if arc_state is not None and not arc_state["transition_ok"]:
            parts.append("[CONTINUITY WARNING: abrupt emotion transition]")
        return " ".join(parts)
