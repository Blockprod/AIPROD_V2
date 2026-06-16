from __future__ import annotations

from aiprod_adaptation.core.cost_report import CostReport
from aiprod_adaptation.core.production_budget import ProductionBudget
from aiprod_adaptation.core.run_metrics import RunMetrics

_IO_EXPORTS = {
    "save_output",
    "load_output",
    "save_storyboard",
    "load_storyboard",
    "save_video",
    "load_video",
    "save_production",
    "load_production",
}

__all__ = [
    "CostReport",
    "ProductionBudget",
    "RunMetrics",
    *_IO_EXPORTS,
]


def __getattr__(name: str) -> object:
    if name in _IO_EXPORTS:
        from aiprod_adaptation.core import io

        return getattr(io, name)
    raise AttributeError(f"module 'aiprod_adaptation.core' has no attribute {name!r}")
