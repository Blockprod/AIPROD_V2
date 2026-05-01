"""
AssetRegistry — Construit et valide le GlobalAssetRegistry depuis un AIPRODOutput.

Responsabilités:
    - Extraire tous les personnages, lieux, props depuis l'IR
    - Enrichir avec les attributs du VisualBible si disponible
    - Charger les images de référence depuis un reference_pack.json
    - Détecter les assets dont le canon_locked est violé entre épisodes
    - Exporter vers GlobalAsset (schema v5.0)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aiprod_adaptation.models.schema import AIPRODOutput, GlobalAsset


class AssetRegistry:
    """Builds and validates GlobalAsset entries from an AIPRODOutput."""

    def build(self, output: AIPRODOutput) -> list[GlobalAsset]:
        """
        Extracts GlobalAsset entries from all episodes in the output.
        Characters and locations are discovered from scene metadata.
        First occurrence is the first shot_id that references the asset.
        """
        assets: dict[str, GlobalAsset] = {}

        for episode in output.episodes:
            # Build shot_id index: scene_id → first shot_id
            scene_first_shot: dict[str, str] = {}
            for shot in episode.shots:
                scn = shot.scene_id
                if scn not in scene_first_shot:
                    scene_first_shot[scn] = shot.shot_id

            for scene in episode.scenes:
                first_shot = scene_first_shot.get(scene.scene_id, scene.scene_id)

                # Characters
                for char_id in scene.character_ids:
                    char_id = char_id.strip().lower()
                    if not char_id or char_id in assets:
                        continue
                    assets[char_id] = GlobalAsset(
                        asset_id=char_id,
                        asset_type="character",
                        attributes={"display_name": char_id.replace("_", " ").title()},
                        first_occurrence=first_shot,
                    )

                # Location
                loc_id = scene.location_id or scene.location.lower().replace(" ", "_")
                if loc_id and loc_id not in assets:
                    assets[loc_id] = GlobalAsset(
                        asset_id=loc_id,
                        asset_type="location",
                        attributes={
                            "display_name": scene.location,
                            "lighting_condition": f"{scene.time_of_day or 'day'} lighting",
                        },
                        first_occurrence=first_shot,
                    )

        return list(assets.values())

    def enrich_from_reference_pack(
        self,
        assets: list[GlobalAsset],
        reference_pack_path: str | Path,
    ) -> list[GlobalAsset]:
        """
        Injects reference_image_id into character and location assets from a
        reference_pack.json file.

        The reference_pack.json structure (District Zero convention):
            {
                "characters": {
                    "Nara": { "reference_image_urls": ["path/to/nara.png"], ... },
                    ...
                },
                "locations": {
                    "district_zero_outer_wall_night": {
                        "reference_image_urls": ["path/to/seawall_ref.png"], ... },
                    ...
                }
            }

        Matching is done case-insensitively between asset_id and the key in the
        reference_pack (characters are matched by display_name or asset_id,
        locations by their exact key).
        """
        pack_path = Path(reference_pack_path)
        with pack_path.open(encoding="utf-8") as f:
            pack: dict[str, Any] = json.load(f)

        index = {a.asset_id: a for a in assets}

        # --- Characters ---
        for char_key, char_data in pack.get("characters", {}).items():
            urls: list[str] = char_data.get("reference_image_urls", [])
            if not urls:
                continue
            # Match by display_name OR by asset_id containing the key (case-insensitive)
            char_key_lower = char_key.lower()
            matched = next(
                (
                    a for a in assets
                    if a.asset_type == "character"
                    and (
                        a.asset_id == char_key_lower
                        or a.attributes.get("display_name", "").lower() == char_key_lower
                        or a.asset_id.startswith(char_key_lower)
                        or char_key_lower in a.asset_id
                    )
                ),
                None,
            )
            if matched:
                matched.attributes["reference_image_id"] = urls[0]
                if len(urls) > 1:
                    matched.attributes["reference_image_ids"] = urls

        # --- Locations ---
        for loc_key, loc_data in pack.get("locations", {}).items():
            urls = loc_data.get("reference_image_urls", [])
            if not urls:
                continue
            asset = index.get(loc_key)
            if asset and asset.asset_type == "location":
                asset.attributes["reference_image_id"] = urls[0]
                if len(urls) > 1:
                    asset.attributes["reference_image_ids"] = urls

        return list(index.values())

    def enrich(
        self,
        assets: list[GlobalAsset],
        overrides: dict[str, dict[str, Any]],
    ) -> list[GlobalAsset]:
        """
        Merges attribute overrides into existing assets.
        overrides: { asset_id: { attribute_key: value, ... } }
        """
        index = {a.asset_id: a for a in assets}
        for asset_id, attrs in overrides.items():
            if asset_id in index:
                index[asset_id].attributes.update(attrs)
        return list(index.values())

    def validate_canon(
        self,
        assets: list[GlobalAsset],
        previous_assets: list[GlobalAsset],
    ) -> list[str]:
        """
        Compares current asset list against a previous episode's assets.
        Returns list of violation messages for canon_locked assets whose
        attributes changed.
        """
        prev_index = {a.asset_id: a for a in previous_assets}
        violations: list[str] = []

        for asset in assets:
            prev = prev_index.get(asset.asset_id)
            if prev is None or not prev.canon_locked:
                continue
            changed = {
                k for k, v in asset.attributes.items()
                if prev.attributes.get(k) != v
            }
            if changed:
                violations.append(
                    f"CANON_VIOLATION: {asset.asset_id} changed locked attrs {changed}"
                )

        return violations
