"""
season — Multi-episode coherence tracking for AIPROD_Cinematic.

Public API
----------
    SeasonCoherenceTracker  — accumulates episode outputs, computes SeasonCoherenceMetrics
    EpisodeCoherenceSummary — per-episode summary added to the tracker
    SeasonState             — full accumulated season state
"""

from aiprod_adaptation.core.season.models import EpisodeCoherenceSummary, SeasonState
from aiprod_adaptation.core.season.tracker import SeasonCoherenceTracker

__all__ = [
    "EpisodeCoherenceSummary",
    "SeasonCoherenceTracker",
    "SeasonState",
]
