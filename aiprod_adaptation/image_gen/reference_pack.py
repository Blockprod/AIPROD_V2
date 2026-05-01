from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from aiprod_adaptation.image_gen.character_sheet import CharacterSheet, CharacterSheetRegistry


class ReferenceSubject(BaseModel):
    prompt: str = ""
    reference_image_urls: list[str] = Field(default_factory=list)
    seed: int | None = None

    def primary_reference_url(self) -> str:
        return self.reference_image_urls[0] if self.reference_image_urls else ""


class ReferencePack(BaseModel):
    style_block: str = ""
    characters: dict[str, ReferenceSubject] = Field(default_factory=dict)
    locations: dict[str, ReferenceSubject] = Field(default_factory=dict)
    scene_locations: dict[str, str] = Field(default_factory=dict)
    scene_adapters: dict[str, str] = Field(default_factory=dict)  # scene_id → adapter name

    @staticmethod
    def _normalize_key(value: str) -> str:
        return " ".join(value.lower().replace("_", " ").split())

    def _character_subject(self, character: str) -> ReferenceSubject | None:
        if not character:
            return None
        exact = self.characters.get(character)
        if exact is not None:
            return exact

        normalized = self._normalize_key(character)
        for key, subject in self.characters.items():
            if self._normalize_key(key) == normalized:
                return subject

        short_name = normalized.split(" ", maxsplit=1)[0]
        for key, subject in self.characters.items():
            if self._normalize_key(key) == short_name:
                return subject

        return None

    def character_prompt(self, character: str) -> str:
        subject = self._character_subject(character)
        prompt = subject.prompt if subject is not None else ""
        if prompt and self.style_block:
            return prompt.rstrip(" .") + ". " + self.style_block
        return prompt

    def character_reference_url(self, character: str) -> str:
        subject = self._character_subject(character)
        return subject.primary_reference_url() if subject is not None else ""

    def location_prompt(self, location_key: str) -> str:
        subject = self.locations.get(location_key)
        prompt = subject.prompt if subject is not None else ""
        if prompt and self.style_block:
            return prompt.rstrip(" .") + ". " + self.style_block
        return prompt

    def location_reference_url(self, location_key: str) -> str:
        subject = self.locations.get(location_key)
        return subject.primary_reference_url() if subject is not None else ""

    def to_character_sheet_registry(self, base_seed: int = 42) -> CharacterSheetRegistry:
        registry = CharacterSheetRegistry()
        for index, (name, subject) in enumerate(self.characters.items()):
            if not subject.prompt:
                continue
            registry.register(
                CharacterSheet(
                    name=name,
                    canonical_prompt=subject.prompt,
                    seed=subject.seed if subject.seed is not None else base_seed + index,
                    image_url=subject.primary_reference_url(),
                )
            )
        return registry


def load_reference_pack(path: str | Path) -> ReferencePack:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ReferencePack.model_validate(payload)
