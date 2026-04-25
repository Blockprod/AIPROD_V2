"""
Visual Bible — deterministic source of truth for series-wide visual invariants.

A VisualBible is loaded from a JSON file at pipeline startup and injected into
Pass 3 (DoP shot construction) and Pass 4 (quality gate + prompt enrichment).

Priority hierarchy (hard-coded, not configurable):
  1. Character identity & wardrobe signature
  2. Location lighting condition (key direction, temperature, quality)
  3. Spatial coherence (camera axis continuity)
  4. Composition (rule of thirds, headroom, lead room)
  5. Narrative intent (emotion, pacing, dramatic tension)

All structures are TypedDicts for zero-overhead runtime validation.
The `load()` class method deserialises and validates the JSON contract.

JSON schema example (stories/visual_bible_template.json):
{
  "series_title": "District Zero",
  "series_style": {
    "aspect_ratio": "2.39:1",
    "primary_lens_kit_mm": [24, 35, 50, 85],
    "default_color_grade": "orange_teal",
    "default_scene_tone": "tense",
    "grain_level": "medium",
    "default_shot_ratio": {"wide": 0.25, "medium": 0.50, "close_up": 0.20, "other": 0.05}
  },
  "characters": {
    "Kael": {
      "wardrobe_fingerprint": "worn leather jacket, dark tactical trousers, no insignia",
      "physical_signature": "tall, lean, scar across left brow, moves with controlled economy",
      "color_anchor": "#1a1a2e",
      "lighting_affinity": "hard side-light, high contrast"
    }
  },
  "locations": {
    "district_zero_central": {
      "description": "Industrial district, brutalist concrete, neon signage",
      "lighting_condition": "sodium-vapor key, orange-teal split, motivated from street level",
      "palette": ["#ff6b35", "#004e89", "#1a1a2e"],
      "architecture_style": "brutalist",
      "default_camera_height": "eye_level",
      "ref_image_id": "loc_dz_central_001"
    }
  }
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# TypedDicts — serialisable contract
# ---------------------------------------------------------------------------

class SeriesStyle(TypedDict):
    aspect_ratio: str                              # e.g. "2.39:1", "1.78:1"
    primary_lens_kit_mm: list[int]                 # available focal lengths
    default_color_grade: str                       # one of _VALID_COLOR_GRADES
    default_scene_tone: str                        # one of _VALID_SCENE_TONES
    grain_level: str                               # "none" | "light" | "medium" | "heavy"
    default_shot_ratio: dict[str, float]           # target ratio per shot category


class CharacterInvariant(TypedDict):
    wardrobe_fingerprint: str      # single prose description of distinctive wardrobe
    physical_signature: str        # distinctive physical traits (height, build, marks)
    color_anchor: str              # hex color dominant in character's palette
    lighting_affinity: str         # preferred lighting treatment (narrative anchor)


class LocationInvariant(TypedDict):
    description: str               # brief environment description
    lighting_condition: str        # key light direction, temperature, quality
    palette: list[str]             # up to 3 hex colors defining the location palette
    architecture_style: str        # "brutalist" | "domestic" | "industrial" | "natural" | etc.
    default_camera_height: str     # "eye_level" | "low_angle" | "high_angle" | "overhead"
    ref_image_id: str              # ID linking to reference image pack


class VisualBibleData(TypedDict):
    series_title: str
    series_style: SeriesStyle
    characters: dict[str, CharacterInvariant]
    locations: dict[str, LocationInvariant]


# ---------------------------------------------------------------------------
# _DEFAULTS: fallback for optional keys in incoming JSON
# ---------------------------------------------------------------------------

_DEFAULT_SERIES_STYLE: SeriesStyle = SeriesStyle(
    aspect_ratio="1.78:1",
    primary_lens_kit_mm=[24, 35, 50, 85],
    default_color_grade="neutral",
    default_scene_tone="neutral",
    grain_level="none",
    default_shot_ratio={"wide": 0.25, "medium": 0.50, "close_up": 0.20, "other": 0.05},
)

_VALID_GRAIN_LEVELS: frozenset[str] = frozenset({"none", "light", "medium", "heavy"})
_VALID_CAMERA_HEIGHTS: frozenset[str] = frozenset({
    "eye_level", "low_angle", "high_angle", "overhead",
})


# ---------------------------------------------------------------------------
# VisualBible — main object
# ---------------------------------------------------------------------------

class VisualBible:
    """
    Immutable Visual Bible for one series.

    Attributes
    ----------
    data : VisualBibleData
        Full deserialised content.
    series_style : SeriesStyle
        Series-wide visual grammar.
    characters : dict[str, CharacterInvariant]
        Keyed by canonical character name (exact match, case-sensitive).
    locations : dict[str, LocationInvariant]
        Keyed by location slug (lower-case, underscores).
    """

    def __init__(self, data: VisualBibleData) -> None:
        self._data = data

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def data(self) -> VisualBibleData:
        return self._data

    @property
    def series_style(self) -> SeriesStyle:
        return self._data["series_style"]

    @property
    def characters(self) -> dict[str, CharacterInvariant]:
        return self._data["characters"]

    @property
    def locations(self) -> dict[str, LocationInvariant]:
        return self._data["locations"]

    def get_character(self, name: str) -> CharacterInvariant | None:
        return self._data["characters"].get(name)

    def get_location(self, slug: str) -> LocationInvariant | None:
        return self._data["locations"].get(slug.lower().replace(" ", "_"))

    def get_character_prompt_fragment(self, name: str) -> str:
        """Return a prompt fragment describing a character's visual invariants."""
        inv = self.get_character(name)
        if inv is None:
            return ""
        parts = [
            inv["physical_signature"],
            inv["wardrobe_fingerprint"],
            f"Lighting: {inv['lighting_affinity']}.",
        ]
        return " ".join(p for p in parts if p)

    def get_location_prompt_fragment(self, slug: str) -> str:
        """Return a prompt fragment describing a location's visual invariants."""
        inv = self.get_location(slug)
        if inv is None:
            return ""
        palette_str = ", ".join(inv["palette"]) if inv["palette"] else ""
        parts = [
            inv["description"],
            f"Lighting: {inv['lighting_condition']}.",
        ]
        if palette_str:
            parts.append(f"Palette: {palette_str}.")
        return " ".join(p for p in parts if p)

    def nearest_focal_length(self, target_mm: int) -> int:
        """Return the focal length from the series lens kit closest to target_mm."""
        kit = self._data["series_style"]["primary_lens_kit_mm"]
        if not kit:
            return target_mm
        return min(kit, key=lambda f: abs(f - target_mm))

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> "VisualBible":
        """
        Deserialise a Visual Bible from a JSON file.

        Raises
        ------
        ValueError
            On schema violations (missing required keys, invalid values).
        FileNotFoundError
            If the path does not exist.
        """
        raw: Any = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, raw: Any) -> "VisualBible":
        if not isinstance(raw, dict):
            raise ValueError("Visual Bible JSON root must be an object.")

        series_title: str = raw.get("series_title", "")
        if not series_title:
            raise ValueError("Visual Bible must contain a non-empty 'series_title'.")

        # Series style — merge with defaults so optional keys are tolerated
        raw_style: dict[str, Any] = raw.get("series_style", {})
        style = SeriesStyle(
            aspect_ratio=raw_style.get("aspect_ratio", _DEFAULT_SERIES_STYLE["aspect_ratio"]),
            primary_lens_kit_mm=raw_style.get(
                "primary_lens_kit_mm", _DEFAULT_SERIES_STYLE["primary_lens_kit_mm"]
            ),
            default_color_grade=raw_style.get(
                "default_color_grade", _DEFAULT_SERIES_STYLE["default_color_grade"]
            ),
            default_scene_tone=raw_style.get(
                "default_scene_tone", _DEFAULT_SERIES_STYLE["default_scene_tone"]
            ),
            grain_level=raw_style.get("grain_level", _DEFAULT_SERIES_STYLE["grain_level"]),
            default_shot_ratio=raw_style.get(
                "default_shot_ratio", _DEFAULT_SERIES_STYLE["default_shot_ratio"]
            ),
        )
        if style["grain_level"] not in _VALID_GRAIN_LEVELS:
            raise ValueError(
                f"Invalid series_style.grain_level: {style['grain_level']!r}. "
                f"Must be one of {sorted(_VALID_GRAIN_LEVELS)}."
            )

        # Characters
        raw_chars: dict[str, Any] = raw.get("characters", {})
        characters: dict[str, CharacterInvariant] = {}
        for name, char_data in raw_chars.items():
            characters[name] = CharacterInvariant(
                wardrobe_fingerprint=char_data.get("wardrobe_fingerprint", ""),
                physical_signature=char_data.get("physical_signature", ""),
                color_anchor=char_data.get("color_anchor", ""),
                lighting_affinity=char_data.get("lighting_affinity", ""),
            )

        # Locations
        raw_locs: dict[str, Any] = raw.get("locations", {})
        locations: dict[str, LocationInvariant] = {}
        for slug, loc_data in raw_locs.items():
            camera_height = loc_data.get("default_camera_height", "eye_level")
            if camera_height not in _VALID_CAMERA_HEIGHTS:
                raise ValueError(
                    f"Invalid location '{slug}' default_camera_height: {camera_height!r}. "
                    f"Must be one of {sorted(_VALID_CAMERA_HEIGHTS)}."
                )
            locations[slug.lower().replace(" ", "_")] = LocationInvariant(
                description=loc_data.get("description", ""),
                lighting_condition=loc_data.get("lighting_condition", ""),
                palette=loc_data.get("palette", []),
                architecture_style=loc_data.get("architecture_style", ""),
                default_camera_height=camera_height,
                ref_image_id=loc_data.get("ref_image_id", ""),
            )

        data = VisualBibleData(
            series_title=series_title,
            series_style=style,
            characters=characters,
            locations=locations,
        )
        return cls(data)

    @classmethod
    def empty(cls) -> "VisualBible":
        """Return a no-op Visual Bible (all invariants absent → pipeline runs in v2 compat mode)."""
        return cls(VisualBibleData(
            series_title="",
            series_style=_DEFAULT_SERIES_STYLE,
            characters={},
            locations={},
        ))
