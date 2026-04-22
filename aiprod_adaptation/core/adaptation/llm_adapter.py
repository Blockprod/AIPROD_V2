from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMAdapter(ABC):
    @abstractmethod
    def generate_json(self, prompt: str) -> dict[str, Any]: ...


class NullLLMAdapter(LLMAdapter):
    """Deterministic adapter for tests and CI.

    Returns a valid empty structure — LLM passes are no-ops.
    The rule-based fallback in engine.py activates when scenes are empty.
    """

    def generate_json(self, _prompt: str) -> dict[str, Any]:
        return {"scenes": []}
