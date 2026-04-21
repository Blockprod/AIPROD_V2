"""
PropRegistry — tracks props held by characters for continuity prompt injection.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PropEntry:
    name: str
    held_by: str | None
    last_seen_shot: str
    description: str


class PropRegistry:
    def __init__(self) -> None:
        self._props: list[PropEntry] = []

    def register(
        self,
        prop: str,
        shot_id: str,
        held_by: str | None = None,
        description: str = "",
    ) -> None:
        self._props.append(
            PropEntry(
                name=prop,
                held_by=held_by,
                last_seen_shot=shot_id,
                description=description or prop,
            )
        )

    def get_active_props_for_character(self, character: str) -> list[PropEntry]:
        return [p for p in self._props if p.held_by == character]

    def get_prompt_hint(self, shot_id: str) -> str:
        relevant = [p for p in self._props if p.last_seen_shot == shot_id]
        if not relevant:
            return ""
        parts = []
        for prop in sorted(relevant, key=lambda p: p.name):
            holder = f" held by {prop.held_by}" if prop.held_by else ""
            parts.append(f"{prop.description}{holder}")
        return "PROPS IN SCENE: " + ", ".join(parts) + "."
