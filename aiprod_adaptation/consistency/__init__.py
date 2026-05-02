"""
aiprod_adaptation.consistency — Services de cohérence transverse (v5.0)

Modules:
    asset_registry      — Construit et valide le GlobalAssetRegistry
    continuity_checker  — Valide la cohérence narrative/visuelle/structurelle
    color_manager       — Vérifie la cohérence des LUTs et color grades
    audio_normalizer    — Normalisation audio et SFX alignment
    timeline_engine     — Calcule et valide les timestamps absolus
"""
from aiprod_adaptation.consistency.asset_registry import AssetRegistry
from aiprod_adaptation.consistency.audio_normalizer import AudioNormalizer
from aiprod_adaptation.consistency.color_manager import ColorManager
from aiprod_adaptation.consistency.continuity_checker import ContinuityChecker
from aiprod_adaptation.consistency.timeline_engine import TimelineEngine

__all__ = [
    "AssetRegistry",
    "TimelineEngine",
    "ColorManager",
    "ContinuityChecker",
    "AudioNormalizer",
]
