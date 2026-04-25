"""
CostReport — tracks API usage and estimated costs per run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_DEFAULT_NOTES = (
    "llm_tokens_input, llm_tokens_output, and llm_cost_usd are not populated by scheduler runtime.",
    (
        "image_cost_usd, video_cost_usd, and audio_cost_usd stay at 0.0 unless adapters "
        "return cost_usd."
    ),
)


@dataclass
class CostReport:
    llm_tokens_input: int = 0
    llm_tokens_output: int = 0
    image_api_calls: int = 0
    video_api_calls: int = 0
    audio_api_calls: int = 0

    # Estimated costs in USD
    llm_cost_usd: float = 0.0
    image_cost_usd: float = 0.0
    video_cost_usd: float = 0.0
    audio_cost_usd: float = 0.0
    notes: list[str] = field(default_factory=lambda: list(_DEFAULT_NOTES))

    @property
    def total_cost_usd(self) -> float:
        return self.llm_cost_usd + self.image_cost_usd + self.video_cost_usd + self.audio_cost_usd

    def merge(self, other: CostReport) -> CostReport:
        merged_notes = list(dict.fromkeys([*self.notes, *other.notes]))
        return CostReport(
            llm_tokens_input=self.llm_tokens_input + other.llm_tokens_input,
            llm_tokens_output=self.llm_tokens_output + other.llm_tokens_output,
            image_api_calls=self.image_api_calls + other.image_api_calls,
            video_api_calls=self.video_api_calls + other.video_api_calls,
            audio_api_calls=self.audio_api_calls + other.audio_api_calls,
            llm_cost_usd=self.llm_cost_usd + other.llm_cost_usd,
            image_cost_usd=self.image_cost_usd + other.image_cost_usd,
            video_cost_usd=self.video_cost_usd + other.video_cost_usd,
            audio_cost_usd=self.audio_cost_usd + other.audio_cost_usd,
            notes=merged_notes,
        )

    def to_summary_str(self) -> str:
        return (
            f"LLM: {self.llm_tokens_input}in/{self.llm_tokens_output}out tokens, "
            f"Image: {self.image_api_calls} calls, "
            f"Video: {self.video_api_calls} calls, "
            f"Audio: {self.audio_api_calls} calls, "
            f"Total: ${self.total_cost_usd:.4f}"
        )
