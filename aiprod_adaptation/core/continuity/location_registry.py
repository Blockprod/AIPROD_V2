"""
LocationRegistry — tracks location descriptions and lighting hints for continuity prompt injection.
"""

from __future__ import annotations

from dataclasses import dataclass

from aiprod_adaptation.models.schema import AIPRODOutput


@dataclass
class LocationProfile:
    location_id: str
    description: str
    lighting_hint: str
    first_seen_scene: str


def _normalize(location: str) -> str:
    return location.lower().strip()


class LocationRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, LocationProfile] = {}

    def build_from_output(self, output: AIPRODOutput) -> LocationRegistry:
        for ep in output.episodes:
            for scene in ep.scenes:
                key = _normalize(scene.location)
                if key not in self._profiles:
                    tod = scene.time_of_day or "day"
                    lighting = f"{tod} lighting"
                    self._profiles[key] = LocationProfile(
                        location_id=key,
                        description=scene.location,
                        lighting_hint=lighting,
                        first_seen_scene=scene.scene_id,
                    )
        return self

    def get_prompt_hint(self, location: str) -> str:
        profile = self._profiles.get(_normalize(location))
        if profile is None:
            return ""
        return f"LOCATION CONTEXT: {profile.description}. Lighting: {profile.lighting_hint}."
