from __future__ import annotations

from typing import Any

from aiprod_adaptation.models.intermediate import VisualScene


class Normalizer:
    _VALID_PACING = frozenset({"fast", "medium", "slow"})
    _VALID_TOD_VISUAL = frozenset({"dawn", "day", "dusk", "night", "interior"})
    _VALID_DOMINANT_SOUND = frozenset({"dialogue", "ambient", "silence"})

    def _continuity_characters(
        self,
        continuity_snapshot: dict[str, Any] | None,
    ) -> list[str]:
        if continuity_snapshot is None:
            return []
        characters_raw = continuity_snapshot.get("active_characters", [])
        if not isinstance(characters_raw, list):
            return []
        return [str(character) for character in characters_raw if str(character).strip()]

    def _continuity_location(
        self,
        continuity_snapshot: dict[str, Any] | None,
    ) -> str | None:
        if continuity_snapshot is None:
            return None
        locations_raw = continuity_snapshot.get("active_locations", [])
        if not isinstance(locations_raw, list):
            return None
        for location in locations_raw:
            text = str(location).strip()
            if text:
                return text
        return None

    def normalize(
        self,
        scenes: list[dict[str, Any]],
        continuity_snapshot: dict[str, Any] | None = None,
    ) -> list[VisualScene]:
        normalized: list[VisualScene] = []
        continuity_characters = self._continuity_characters(continuity_snapshot)
        continuity_location = self._continuity_location(continuity_snapshot)
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
            if not characters and continuity_characters:
                characters = continuity_characters[:2]
            location = str(s.get("location") or "Unknown")
            if location == "Unknown" and continuity_location is not None:
                location = continuity_location
            scene_out: VisualScene = VisualScene(
                scene_id=str(s.get("scene_id") or f"SCN_{i:03d}"),
                characters=characters,
                location=location,
                time_of_day=s.get("time_of_day"),
                visual_actions=visual_actions,
                dialogues=dialogues,
                emotion=str(s.get("emotion") or "neutral"),
            )
            pacing = s.get("pacing")
            if pacing in self._VALID_PACING:
                scene_out["pacing"] = pacing
            tod_visual = s.get("time_of_day_visual")
            if tod_visual in self._VALID_TOD_VISUAL:
                scene_out["time_of_day_visual"] = tod_visual
            dominant_sound = s.get("dominant_sound")
            if dominant_sound in self._VALID_DOMINANT_SOUND:
                scene_out["dominant_sound"] = dominant_sound
            normalized.append(scene_out)
        return normalized
