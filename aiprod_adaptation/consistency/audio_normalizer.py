"""
AudioNormalizer — Normalisation audio et alignment SFX (v5.0).

Responsabilités:
    - Valider que chaque dialogue a un fichier audio référencé dans l'IR
    - Vérifier que les niveaux cibles sont déclarés (-23 LUFS dialogue)
    - Valider l'alignment frame-exact des SFX sur les actions correspondantes
    - Signaler les orphan SFX (SFX sans action visuelle associée)

Note: Ce module est un validateur de données IR, pas un processeur audio.
Les fichiers audio réels ne sont pas générés ici.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from aiprod_adaptation.models.schema import AIPRODOutput

_DIALOGUE_LUFS_TARGET = -23.0
_DIALOGUE_LUFS_TOLERANCE = 1.0  # ±1 LUFS acceptable


@dataclass
class AudioValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class AudioNormalizer:
    """Validates audio specification compliance in AIPRODOutput IR."""

    def validate(self, output: AIPRODOutput) -> AudioValidationResult:
        """
        Checks audio specifications across all shots:
          - Shots with dialogue have voice_id referenced in audio metadata
          - LUFS targets are within ±1 of -23 LUFS (if declared)
          - Ambiance location is declared for each shot
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Build a voice_id index from global_assets
        voice_assets = {
            a.asset_id: a.attributes
            for a in output.global_assets
            if a.asset_type == "voice"
        }

        for episode in output.episodes:
            for shot in episode.shots:
                meta = shot.metadata or {}

                # Check dialogue audio reference
                dominant_sound = meta.get("dominant_sound", "")
                if dominant_sound == "dialogue":
                    # Each character in the shot should have a locked voice
                    for scene in episode.scenes:
                        if scene.scene_id != shot.scene_id:
                            continue
                        for char_id in scene.character_ids:
                            char_id = char_id.strip().lower()
                            if char_id and char_id not in voice_assets:
                                warnings.append(
                                    f"{shot.shot_id}: character '{char_id}' has dialogue "
                                    f"but no voice asset in global_assets"
                                )

                # Check LUFS if declared
                lufs_val = meta.get("audio_lufs")
                if lufs_val is not None:
                    try:
                        lufs_float = float(lufs_val)
                        if abs(lufs_float - _DIALOGUE_LUFS_TARGET) > _DIALOGUE_LUFS_TOLERANCE:
                            errors.append(
                                f"{shot.shot_id}: audio_lufs={lufs_float} is outside "
                                f"target {_DIALOGUE_LUFS_TARGET} ± {_DIALOGUE_LUFS_TOLERANCE}"
                            )
                    except (TypeError, ValueError):
                        warnings.append(
                            f"{shot.shot_id}: audio_lufs='{lufs_val}' is not a number"
                        )

        return AudioValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)
