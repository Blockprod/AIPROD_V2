from __future__ import annotations

from dataclasses import dataclass, field

from aiprod_adaptation.core.cost_report import CostReport


@dataclass
class RunMetrics:
    shots_requested: int = 0
    shots_generated: int = 0
    shots_failed: int = 0
    total_latency_ms: int = 0
    image_latency_ms: int = 0
    video_latency_ms: int = 0
    audio_latency_ms: int = 0
    cost: CostReport = field(default_factory=CostReport)

    @property
    def success_rate(self) -> float:
        if self.shots_requested == 0:
            return 1.0
        return self.shots_generated / self.shots_requested

    @property
    def average_latency_ms(self) -> float:
        if self.shots_generated == 0:
            return 0.0
        return self.total_latency_ms / self.shots_generated
