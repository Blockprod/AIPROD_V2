"""
CharacterImageRegistry — conserve la première image générée par personnage.
Utilisé par StoryboardGenerator pour passer une référence visuelle aux shots suivants.
"""

from __future__ import annotations


class CharacterImageRegistry:
    """Maps character name → first generated image_url."""

    def __init__(self) -> None:
        self._registry: dict[str, str] = {}

    def register(self, character: str, image_url: str) -> None:
        """Store image_url for character only if not already registered."""
        if character not in self._registry:
            self._registry[character] = image_url

    def get_reference(self, character: str) -> str:
        """Return image_url for character, or empty string if unknown."""
        return self._registry.get(character, "")

    def known_characters(self) -> list[str]:
        return list(self._registry.keys())
