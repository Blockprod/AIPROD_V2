from __future__ import annotations

from typing_extensions import TypedDict

from aiprod_adaptation.models.schema import AIPRODOutput


class CharacterProfile(TypedDict):
    name: str
    description: str
    first_scene: str
    scenes: list[str]


class CharacterRegistry:
    def build(self, output: AIPRODOutput) -> dict[str, CharacterProfile]:
        registry: dict[str, CharacterProfile] = {}
        for episode in output.episodes:
            for scene in episode.scenes:
                for character in scene.characters:
                    name = character.strip()
                    if not name:
                        continue
                    if name not in registry:
                        registry[name] = CharacterProfile(
                            name=name,
                            description="",
                            first_scene=scene.scene_id,
                            scenes=[scene.scene_id],
                        )
                    else:
                        if scene.scene_id not in registry[name]["scenes"]:
                            registry[name]["scenes"].append(scene.scene_id)
        return registry

    def enrich_from_text(
        self,
        registry: dict[str, CharacterProfile],
        descriptions: dict[str, str],
    ) -> dict[str, CharacterProfile]:
        for name, description in descriptions.items():
            if name in registry:
                registry[name]["description"] = description
            else:
                # Character not extracted automatically (e.g. rule-based pipeline)
                # — add it so PromptEnricher can still inject the description.
                registry[name] = CharacterProfile(
                    name=name,
                    description=description,
                    first_scene="",
                    scenes=[],
                )
        return registry
