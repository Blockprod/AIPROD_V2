from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CharacterSheet:
    name: str
    canonical_prompt: str
    seed: int = 42
    image_url: str = ""


class CharacterSheetRegistry:
    def __init__(self) -> None:
        self._sheets: dict[str, CharacterSheet] = {}

    def register(self, sheet: CharacterSheet) -> None:
        """Store sheet only if character name not already registered."""
        if sheet.name not in self._sheets:
            self._sheets[sheet.name] = sheet

    def get(self, name: str) -> CharacterSheet | None:
        return self._sheets.get(name)

    def all_sheets(self) -> list[CharacterSheet]:
        return list(self._sheets.values())
