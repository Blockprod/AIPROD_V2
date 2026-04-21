from __future__ import annotations

from typing import List

from aiprod_adaptation.core.continuity.character_registry import CharacterProfile
from aiprod_adaptation.core.continuity.emotion_arc import EmotionState
from aiprod_adaptation.core.continuity.location_registry import LocationRegistry
from aiprod_adaptation.core.continuity.prop_registry import PropRegistry
from aiprod_adaptation.models.schema import AIPRODOutput, Episode, Shot  # Episode/Shot used in type hints below


class PromptEnricher:
    def enrich(
        self,
        output: AIPRODOutput,
        registry: dict[str, CharacterProfile],
        arc_states: List[EmotionState],
        location_registry: LocationRegistry | None = None,
        prop_registry: PropRegistry | None = None,
    ) -> AIPRODOutput:
        arc_by_shot = {s["shot_id"]: s for s in arc_states}
        scene_location: dict[str, str] = {
            scene.scene_id: scene.location
            for ep in output.episodes
            for scene in ep.scenes
        }
        enriched_episodes: List[Episode] = []

        for episode in output.episodes:
            enriched_shots: List[Shot] = []
            for shot in episode.shots:
                location = scene_location.get(shot.scene_id, "")
                enriched_prompt = self._enrich_prompt(
                    shot.prompt,
                    registry,
                    arc_by_shot.get(shot.shot_id),
                    location_hint=location_registry.get_prompt_hint(location) if location_registry else "",
                    prop_hint=prop_registry.get_prompt_hint(shot.shot_id) if prop_registry else "",
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
        location_hint: str = "",
        prop_hint: str = "",
    ) -> str:
        parts = [prompt]
        # Inject description for all registry characters with a non-empty description.
        # sorted() → byte-level determinism guaranteed.
        for char in sorted(registry.keys()):
            profile = registry[char]
            if profile["description"]:
                parts.append(f"{char}: {profile['description']}.")
        if location_hint:
            parts.append(location_hint)
        if prop_hint:
            parts.append(prop_hint)
        if arc_state is not None and not arc_state["transition_ok"]:
            parts.append("[CONTINUITY WARNING: abrupt emotion transition]")
        return " ".join(parts)
