from __future__ import annotations

from typing import Any

from aiprod_adaptation.models.intermediate import VisualScene


class Normalizer:
    def normalize(self, scenes: list[dict[str, Any]]) -> list[VisualScene]:
        normalized: list[VisualScene] = []
        for i, s in enumerate(scenes, start=1):
            visual_actions_raw = s.get("actions") or s.get("visual_actions", [])
            visual_actions: list[str] = (
                visual_actions_raw if isinstance(visual_actions_raw, list) else []
            )
            dialogues_raw = s.get("dialogues", [])
            dialogues: list[str] = dialogues_raw if isinstance(dialogues_raw, list) else []
            characters_raw = s.get("characters", [])
            characters: list[str] = (
                characters_raw[:2] if isinstance(characters_raw, list) else []
            )
            normalized.append(
                VisualScene(
                    scene_id=str(s.get("scene_id") or f"SCN_{i:03d}"),
                    characters=characters,
                    location=str(s.get("location") or "Unknown"),
                    time_of_day=s.get("time_of_day"),
                    visual_actions=visual_actions,
                    dialogues=dialogues,
                    emotion=str(s.get("emotion") or "neutral"),
                )
            )
        return normalized
