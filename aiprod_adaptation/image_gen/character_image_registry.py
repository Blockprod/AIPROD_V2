"""
CharacterImageRegistry — conserve la première image générée par personnage.
Utilisé par StoryboardGenerator pour passer une référence visuelle aux shots suivants.
"""

from __future__ import annotations


class CharacterImageRegistry:
    """Maps character name → first generated image_url and optional canonical_prompt."""

    def __init__(self) -> None:
        self._registry: dict[str, str] = {}
        self._prompts: dict[str, str] = {}

    @staticmethod
    def _key(character: str) -> str:
        return " ".join(character.lower().replace("_", " ").split())

    def register(self, character: str, image_url: str, overwrite: bool = False) -> None:
        """Store image_url for character only if not already registered."""
        key = self._key(character)
        if overwrite or key not in self._registry:
            self._registry[key] = image_url

    def get_reference(self, character: str) -> str:
        """Return image_url for character, or empty string if unknown."""
        return self._registry.get(self._key(character), "")

    def register_prompt(
        self,
        character: str,
        canonical_prompt: str,
        overwrite: bool = False,
    ) -> None:
        """Store canonical_prompt for character only if not already registered."""
        key = self._key(character)
        if overwrite or key not in self._prompts:
            self._prompts[key] = canonical_prompt

    def get_canonical_prompt(self, character: str) -> str:
        """Return canonical_prompt for character, or empty string if unknown."""
        return self._prompts.get(self._key(character), "")

    def known_characters(self) -> list[str]:
        return list(self._registry.keys())
