"""
ContinuityChecker — Valide la cohérence narrative/visuelle/structurelle (v5.0).

Checklist couverte (cf. tasks/corrections/plans/06_continuity_checklist.md):
  A1  — Chaque shot a un prompt non vide
  A2  — Chaque shot_id est unique dans l'épisode
  A3  — L'ordre des shot_id dans chaque scène est monotone
  B1  — reference_anchor_strength >= 0.8 pour les personnages
  B6  — feasibility_score >= 70 pour tous les shots
  C1-C4 — Validation temporelle (voir TimelineEngine)
  E1  — character_ids référencés dans GlobalAssetRegistry
  E2  — location_id référencés dans GlobalAssetRegistry
  E5  — global_assets non vide
"""
from __future__ import annotations

from dataclasses import dataclass, field

from aiprod_adaptation.models.schema import AIPRODOutput

_MIN_FEASIBILITY = 70
_MIN_ANCHOR_STRENGTH = 0.8


@dataclass
class ContinuityReport:
    valid: bool
    blocking_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    passed_checks: list[str] = field(default_factory=list)
    score: float = 0.0  # 0.0–1.0


class ContinuityChecker:
    """Runs the continuity checklist against an AIPRODOutput."""

    def check(self, output: AIPRODOutput) -> ContinuityReport:
        errors: list[str] = []
        warnings: list[str] = []
        passed: list[str] = []

        # --- Build asset lookup sets ---
        asset_chars = {
            a.asset_id
            for a in output.global_assets
            if a.asset_type == "character"
        }
        asset_locs = {
            a.asset_id
            for a in output.global_assets
            if a.asset_type == "location"
        }

        # E5 — global_assets non vide
        if output.global_assets:
            passed.append("E5: global_assets non vide")
        else:
            warnings.append("E5: global_assets est vide (aucun asset enregistré)")

        for episode in output.episodes:
            ep_id = episode.episode_id

            # --- A2: shot_id unicité ---
            seen_shot_ids: set[str] = set()
            for shot in episode.shots:
                if shot.shot_id in seen_shot_ids:
                    errors.append(f"A2 [{ep_id}]: shot_id dupliqué '{shot.shot_id}'")
                seen_shot_ids.add(shot.shot_id)
            if not any(e.startswith(f"A2 [{ep_id}]") for e in errors):
                passed.append(f"A2 [{ep_id}]: tous les shot_id sont uniques")

            # --- A1, B1, B6 per shot ---
            a1_ok = True
            b1_ok = True
            b6_ok = True

            for shot in episode.shots:
                # A1 — prompt non vide
                if not shot.prompt or not shot.prompt.strip():
                    errors.append(f"A1 [{ep_id}]: prompt vide sur '{shot.shot_id}'")
                    a1_ok = False

                # B1 — reference_anchor_strength >= 0.8
                if shot.reference_anchor_strength < _MIN_ANCHOR_STRENGTH:
                    warnings.append(
                        f"B1 [{ep_id}]: '{shot.shot_id}' reference_anchor_strength="
                        f"{shot.reference_anchor_strength:.2f} < {_MIN_ANCHOR_STRENGTH}"
                    )
                    b1_ok = False

                # B6 — feasibility_score >= 70
                if shot.feasibility_score < _MIN_FEASIBILITY:
                    errors.append(
                        f"B6 [{ep_id}]: '{shot.shot_id}' feasibility_score="
                        f"{shot.feasibility_score} < {_MIN_FEASIBILITY}"
                    )
                    b6_ok = False

            if a1_ok:
                passed.append(f"A1 [{ep_id}]: tous les prompts sont non vides")
            if b1_ok:
                passed.append(f"B1 [{ep_id}]: tous les reference_anchor_strength >= {_MIN_ANCHOR_STRENGTH}")
            if b6_ok:
                passed.append(f"B6 [{ep_id}]: tous les feasibility_score >= {_MIN_FEASIBILITY}")

            # --- A3: shot order in each scene is monotone ---
            scene_shots: dict[str, list[str]] = {}
            for shot in episode.shots:
                scene_shots.setdefault(shot.scene_id, []).append(shot.shot_id)

            a3_ok = True
            for scene_id, shot_ids in scene_shots.items():
                for i in range(1, len(shot_ids)):
                    if shot_ids[i] <= shot_ids[i - 1]:
                        errors.append(
                            f"A3 [{ep_id}]: scene '{scene_id}' shot_id non-monotone: "
                            f"'{shot_ids[i - 1]}' → '{shot_ids[i]}'"
                        )
                        a3_ok = False
            if a3_ok:
                passed.append(f"A3 [{ep_id}]: ordre des shot_id monotone dans toutes les scènes")

            # --- E1: character_ids référencés dans global_assets ---
            e1_ok = True
            for scene in episode.scenes:
                for char_id in scene.character_ids:
                    char_id_clean = char_id.strip().lower()
                    if char_id_clean and asset_chars and char_id_clean not in asset_chars:
                        warnings.append(
                            f"E1 [{ep_id}]: character '{char_id_clean}' dans scène "
                            f"'{scene.scene_id}' absent du GlobalAssetRegistry"
                        )
                        e1_ok = False
            if e1_ok:
                passed.append(f"E1 [{ep_id}]: tous les character_ids référencés dans global_assets")

            # --- E2: location_id référencés dans global_assets ---
            e2_ok = True
            for scene in episode.scenes:
                loc_id = scene.location_id
                if loc_id and asset_locs and loc_id not in asset_locs:
                    warnings.append(
                        f"E2 [{ep_id}]: location '{loc_id}' dans scène "
                        f"'{scene.scene_id}' absente du GlobalAssetRegistry"
                    )
                    e2_ok = False
            if e2_ok:
                passed.append(f"E2 [{ep_id}]: tous les location_id référencés dans global_assets")

        total = len(errors) + len(warnings) + len(passed)
        score = len(passed) / total if total > 0 else 1.0

        return ContinuityReport(
            valid=len(errors) == 0,
            blocking_errors=errors,
            warnings=warnings,
            passed_checks=passed,
            score=score,
        )
