from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any


class LLMFailureCategory(StrEnum):
    TRANSIENT = "transient"
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    QUOTA = "quota"
    SCHEMA = "schema"
    UNKNOWN = "unknown"


def classify_llm_failure(message: str) -> LLMFailureCategory:
    lowered = message.lower()
    if any(
        token in lowered
        for token in (
            "unauthorized",
            "authentication",
            "invalid api key",
            "api key not valid",
            "forbidden",
            "permission denied",
            "access denied",
            "auth",
        )
    ):
        return LLMFailureCategory.AUTH
    if any(
        token in lowered
        for token in (
            "rate limit",
            "too many requests",
            "429",
            "resource exhausted",
        )
    ):
        return LLMFailureCategory.RATE_LIMIT
    if any(
        token in lowered
        for token in (
            "quota",
            "billing",
            "credit",
            "insufficient funds",
        )
    ):
        return LLMFailureCategory.QUOTA
    if any(
        token in lowered
        for token in (
            "json",
            "decode",
            "schema",
            "malformed",
            "invalid response format",
        )
    ):
        return LLMFailureCategory.SCHEMA
    if any(
        token in lowered
        for token in (
            "503",
            "unavailable",
            "high demand",
            "try again later",
            "timeout",
            "temporarily",
            "connection reset",
        )
    ):
        return LLMFailureCategory.TRANSIENT
    return LLMFailureCategory.UNKNOWN


def is_retryable_failure(category: LLMFailureCategory) -> bool:
    return category in {
        LLMFailureCategory.TRANSIENT,
        LLMFailureCategory.RATE_LIMIT,
    }


class LLMProviderError(RuntimeError):
    """Raised when a real LLM provider request fails upstream."""

    def __init__(
        self,
        message: str,
        *,
        category: LLMFailureCategory = LLMFailureCategory.UNKNOWN,
        failures: tuple[LLMProviderError, ...] = (),
    ) -> None:
        super().__init__(message)
        self.category = category
        self.failures = failures


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
