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

    def register(self, character: str, image_url: str) -> None:
        """Store image_url for character only if not already registered."""
        if character not in self._registry:
            self._registry[character] = image_url

    def get_reference(self, character: str) -> str:
        """Return image_url for character, or empty string if unknown."""
        return self._registry.get(character, "")

    def register_prompt(self, character: str, canonical_prompt: str) -> None:
        """Store canonical_prompt for character only if not already registered."""
        if character not in self._prompts:
            self._prompts[character] = canonical_prompt

    def get_canonical_prompt(self, character: str) -> str:
        """Return canonical_prompt for character, or empty string if unknown."""
        return self._prompts.get(character, "")

    def known_characters(self) -> list[str]:
        return list(self._registry.keys())
