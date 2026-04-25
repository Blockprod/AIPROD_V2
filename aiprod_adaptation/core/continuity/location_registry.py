"""
LocationRegistry — tracks location descriptions and lighting hints for continuity prompt injection.

v3.0: enriched with palette, architecture_style, and Visual Bible integration.
When a VisualBible is provided, its LocationInvariant entries take priority over
values inferred from the narrative text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from aiprod_adaptation.models.schema import AIPRODOutput

if TYPE_CHECKING:
    from aiprod_adaptation.core.visual_bible import VisualBible


@dataclass
class LocationProfile:
    location_id: str
    description: str
    lighting_hint: str
    first_seen_scene: str
    # v3.0 extensions
    palette: list[str] = field(default_factory=list)        # up to 3 hex colors
    architecture_style: str = ""
    default_camera_height: str = "eye_level"
    ref_image_id: str = ""


def _normalize(location: str) -> str:
    return location.lower().strip().replace(" ", "_")


class LocationRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, LocationProfile] = {}

    def build_from_output(
        self,
        output: AIPRODOutput,
        visual_bible: "VisualBible | None" = None,
    ) -> "LocationRegistry":
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

        # Visual Bible override — invariants take priority over text-inferred values
        if visual_bible is not None:
            for slug, inv in visual_bible.locations.items():
                key = _normalize(slug)
                if key in self._profiles:
                    profile = self._profiles[key]
                    if inv["lighting_condition"]:
                        profile.lighting_hint = inv["lighting_condition"]
                    if inv["description"]:
                        profile.description = inv["description"]
                    profile.palette = list(inv["palette"])
                    profile.architecture_style = inv["architecture_style"]
                    profile.default_camera_height = inv["default_camera_height"]
                    profile.ref_image_id = inv["ref_image_id"]
                else:
                    # Location exists in Visual Bible but not yet seen in the IR
                    self._profiles[key] = LocationProfile(
                        location_id=key,
                        description=inv["description"],
                        lighting_hint=inv["lighting_condition"],
                        first_seen_scene="",
                        palette=list(inv["palette"]),
                        architecture_style=inv["architecture_style"],
                        default_camera_height=inv["default_camera_height"],
                        ref_image_id=inv["ref_image_id"],
                    )
        return self

    def get_prompt_hint(self, location: str) -> str:
        profile = self._profiles.get(_normalize(location))
        if profile is None:
            return ""
        parts = [f"LOCATION CONTEXT: {profile.description}.", f"Lighting: {profile.lighting_hint}."]
        if profile.palette:
            parts.append(f"Palette: {', '.join(profile.palette)}.")
        if profile.architecture_style:
            parts.append(f"Style: {profile.architecture_style}.")
        if profile.ref_image_id:
            parts.append(f"REF: {profile.ref_image_id}.")
        return " ".join(parts)
