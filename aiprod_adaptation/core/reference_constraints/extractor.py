"""
reference_constraints/extractor.py — Deterministic constraint extraction.

ReferenceConstraintsExtractor.extract() converts a VisualInvariants object
(from core/reference_image/models.py) plus an optional LocationInvariant dict
(from core/visual_bible.py) into a ReferenceConstraints object.

All lookups are table-driven.  No heuristics, no randomness, no LLM.

Priority hierarchy reflected
-----------------------------
  P1  Subject identity          — not in ReferenceConstraints (identity anchor, never overridden)
  P2  Lighting (key direction)  → lighting_direction_h, lighting_direction_v
  P3  Camera height             → camera_height, forbidden_movements, suggested_movements
  P4  Depth layer               → dominant_depth_layer
  P5  Palette                   → palette_anchor_hex (invariant + semi-variable)
  +   Location architecture     → architecture_style (from LocationInvariant)
"""

from __future__ import annotations

from typing import Any

from aiprod_adaptation.core.reference_constraints.models import ReferenceConstraints

# ---------------------------------------------------------------------------
# P3 — Camera height → forbidden camera movements
# Same mapping as ConflictResolutionEngine._HEIGHT_INCOMPATIBLE_MOVEMENTS,
# defined independently here to avoid coupling with rule_engine internals.
# ---------------------------------------------------------------------------

_HEIGHT_FORBIDDEN: dict[str, frozenset[str]] = {
    "overhead":   frozenset({"crane_up", "tilt_up", "dolly_in", "dolly_out"}),
    "high_angle": frozenset({"crane_up", "tilt_up"}),
    "low_angle":  frozenset({"crane_down", "tilt_down"}),
    "eye_level":  frozenset(),
}

# ---------------------------------------------------------------------------
# P3 — Camera height → suggested (compatible) movements
# Ordered from most to least characteristic of the height class.
# ---------------------------------------------------------------------------

_HEIGHT_SUGGESTED: dict[str, list[str]] = {
    "overhead":   ["tilt_down", "static", "pan"],
    "high_angle": ["tilt_down", "pan", "static", "tracking"],
    "low_angle":  ["tilt_up", "pan", "static", "tracking"],
    "eye_level":  ["static", "pan", "follow", "tracking", "dolly_in", "dolly_out"],
}

# Variability classifications for palette filtering
_INVARIANT_VARIABILITIES: frozenset[str] = frozenset({"invariant", "semi_variable"})


class ReferenceConstraintsExtractor:
    """
    Deterministic extraction of ReferenceConstraints from a VisualInvariants object.

    Usage
    -----
        extractor = ReferenceConstraintsExtractor()
        constraints = extractor.extract(visual_invariants, location_invariant=loc_dict)

    Parameters
    ----------
    visual_invariants : VisualInvariants | Any
        The Pydantic object produced by VisualInvariantsExtractor.
        If None, an empty ReferenceConstraints is returned (safe no-op).
    location_invariant : dict | None
        A LocationInvariant TypedDict from VisualBible.locations.
        If provided, `architecture_style` and `location_id` are populated.
    """

    def extract(
        self,
        visual_invariants: Any,
        location_invariant: Any | None = None,
    ) -> ReferenceConstraints:
        """Return a ReferenceConstraints populated from visual_invariants."""
        if visual_invariants is None:
            return ReferenceConstraints()

        camera_height = self._extract_camera_height(visual_invariants)
        lighting_h, lighting_v = self._extract_lighting(visual_invariants)
        depth_layer = self._extract_depth_layer(visual_invariants)
        palette_hex = self._extract_palette(visual_invariants)
        forbidden = list(_HEIGHT_FORBIDDEN.get(camera_height or "", frozenset()))
        suggested = list(_HEIGHT_SUGGESTED.get(camera_height or "", []))
        architecture_style: str | None = None
        location_id: str | None = None

        if location_invariant is not None:
            architecture_style = _safe_str(location_invariant, "architecture_style")
            location_id = _safe_str(location_invariant, "ref_image_id") or _safe_str(
                location_invariant, "location_id"
            )
            # Merge camera height from location default if ref image didn't specify
            if camera_height is None:
                loc_height = _safe_str(location_invariant, "default_camera_height")
                if loc_height:
                    camera_height = loc_height
                    forbidden = list(_HEIGHT_FORBIDDEN.get(loc_height, frozenset()))
                    suggested = list(_HEIGHT_SUGGESTED.get(loc_height, []))

        return ReferenceConstraints(
            camera_height=camera_height,
            lighting_direction_h=lighting_h,
            lighting_direction_v=lighting_v,
            dominant_depth_layer=depth_layer,
            forbidden_movements=sorted(forbidden),
            suggested_movements=suggested,
            palette_anchor_hex=palette_hex,
            location_id=location_id,
            architecture_style=architecture_style,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_camera_height(inv: Any) -> str | None:
        raw = getattr(inv, "camera_height_class", None)
        if raw is None:
            return None
        # CameraHeightClass(str, Enum) → .value returns the string
        return raw.value if hasattr(raw, "value") else str(raw)

    @staticmethod
    def _extract_lighting(inv: Any) -> tuple[str | None, str | None]:
        lighting = getattr(inv, "lighting", None)
        if lighting is None:
            return None, None
        h = getattr(lighting, "key_direction_h", None)
        v = getattr(lighting, "key_direction_v", None)
        h_val = h.value if hasattr(h, "value") else (str(h) if h is not None else None)
        v_val = v.value if hasattr(v, "value") else (str(v) if v is not None else None)
        return h_val, v_val

    @staticmethod
    def _extract_depth_layer(inv: Any) -> str | None:
        depth = getattr(inv, "depth_layers", None)
        if depth is None:
            return None
        return getattr(depth, "dominant_layer", None)

    @staticmethod
    def _extract_palette(inv: Any) -> list[str]:
        palette = getattr(inv, "palette", None)
        if palette is None:
            return []
        result: list[str] = []
        for swatch in palette:
            variability = getattr(swatch, "variability", "variable")
            if variability in _INVARIANT_VARIABILITIES:
                hex_code = getattr(swatch, "hex_code", None)
                if hex_code:
                    result.append(hex_code)
        return result


def _safe_str(obj: Any, key: str) -> str | None:
    """Safely get a string value from a dict or object attribute."""
    if isinstance(obj, dict):
        val = obj.get(key)
    else:
        val = getattr(obj, key, None)
    return str(val) if val is not None else None
