from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductionBudget:
    """
    Production constraints injected into LLM prompts and used by P6 for chunking.

    Defaults: short film (~3 minutes).
    Use factory methods for common configurations.
    """

    target_duration_sec: int = 180
    max_scenes: int = 12
    max_shots_per_scene: int = 6
    max_characters: int = 4
    chunk_size: int = 20
    max_chars_per_chunk: int = 8_000

    @property
    def shots_estimate(self) -> int:
        return self.max_scenes * self.max_shots_per_scene

    @classmethod
    def for_short(cls) -> "ProductionBudget":
        return cls(target_duration_sec=180, max_scenes=12, max_characters=4)

    @classmethod
    def for_episode_45(cls) -> "ProductionBudget":
        return cls(
            target_duration_sec=2700,
            max_scenes=135,
            max_characters=6,
            chunk_size=20,
            max_chars_per_chunk=12_000,
        )
