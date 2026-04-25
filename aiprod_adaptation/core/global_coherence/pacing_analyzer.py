"""
pacing_analyzer.py — Episode pacing computation for Pass 4.

Receives the final list[Shot] after consistency enrichment and computes a
PacingProfile describing the episode's rhythm.

Rules applied (from pass4_coherence_rules.PACING_LABEL_RULES):
    mean_shot_duration <= 3.5 s  → "montage"
    mean_shot_duration <= 4.5 s  → "fast"
    mean_shot_duration <= 6.0 s  → "medium"
    mean_shot_duration  > 6.0 s  → "slow"

All computation is pure (no side effects).
"""

from __future__ import annotations

from aiprod_adaptation.core.rules.pass4_coherence_rules import PACING_LABEL_RULES
from aiprod_adaptation.models.schema import PacingProfile, Shot


def analyze(shots: list[Shot]) -> PacingProfile:
    """
    Compute a PacingProfile from the compiled shot list.

    Args:
        shots: List of validated Shot objects (Pydantic) for one episode.

    Returns:
        PacingProfile with total_duration_sec, mean_shot_duration,
        shot_count, and pacing_label.
    """
    if not shots:
        return PacingProfile(
            total_duration_sec=0,
            mean_shot_duration=0.0,
            shot_count=0,
            pacing_label="medium",
        )

    total = sum(s.duration_sec for s in shots)
    mean = total / len(shots)

    label = "slow"
    for max_mean, lbl in PACING_LABEL_RULES:
        if mean <= max_mean:
            label = lbl
            break

    return PacingProfile(
        total_duration_sec=total,
        mean_shot_duration=round(mean, 2),
        shot_count=len(shots),
        pacing_label=label,
    )
