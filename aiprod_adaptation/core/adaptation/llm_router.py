from __future__ import annotations

import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, ClassVar

from aiprod_adaptation.core.adaptation.llm_adapter import (
    LLMAdapter,
    LLMFailureCategory,
    LLMProviderError,
)


@dataclass(frozen=True)
class RouterPolicy:
    short_preference: str
    cooldown_sec: float
    max_cooldown_sec: float
    auth_quarantine_sec: float
    quota_quarantine_sec: float
    rate_limit_cooldown_multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.short_preference not in {"claude", "gemini"}:
            raise ValueError("short_preference must be 'claude' or 'gemini'")
        if self.cooldown_sec < 0:
            raise ValueError("cooldown_sec must be >= 0")
        if self.max_cooldown_sec < self.cooldown_sec:
            raise ValueError("max_cooldown_sec must be >= cooldown_sec")
        if self.auth_quarantine_sec < self.max_cooldown_sec:
            raise ValueError("auth_quarantine_sec must be >= max_cooldown_sec")
        if self.quota_quarantine_sec < self.max_cooldown_sec:
            raise ValueError("quota_quarantine_sec must be >= max_cooldown_sec")
        if self.rate_limit_cooldown_multiplier < 1.0:
            raise ValueError("rate_limit_cooldown_multiplier must be >= 1.0")


class LLMRouter(LLMAdapter):
    """
    Routes LLM calls based on estimated input token count.

    - input <= token_threshold  →  claude (default: fast, 200K context)
    - input >  token_threshold  →  gemini (1M context, for long novels)

    Token estimation: len(prompt) // 4  (4 chars ≈ 1 token).
    Default threshold: 80_000 tokens ≈ 320_000 chars ≈ 240_000 words.
    """

    CONTEXT_MARKER = "CONTEXT FROM PREVIOUS SCENES:"
    PROVIDERS = ("claude", "gemini")
    SHORT_PROFILE = "short"
    CONTEXTUAL_SHORT_PROFILE = "contextual_short"
    LONG_PROFILE = "long"
    PROFILES = (SHORT_PROFILE, CONTEXTUAL_SHORT_PROFILE, LONG_PROFILE)
    RATE_LIMIT_COOLDOWN_MULTIPLIER: ClassVar[float] = 2.0
    AUTH_QUARANTINE_MULTIPLIER: ClassVar[float] = 16.0
    QUOTA_QUARANTINE_MULTIPLIER: ClassVar[float] = 8.0

    def __init__(
        self,
        claude: LLMAdapter,
        gemini: LLMAdapter,
        token_threshold: int = 80_000,
        short_preference: str = "claude",
        cooldown_sec: float = 300.0,
        max_cooldown_sec: float | None = None,
        auth_quarantine_sec: float | None = None,
        quota_quarantine_sec: float | None = None,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        resolved_max_cooldown_sec = max_cooldown_sec or max(cooldown_sec, cooldown_sec * 8.0)
        resolved_auth_quarantine_sec = auth_quarantine_sec or max(
            resolved_max_cooldown_sec,
            cooldown_sec * self.AUTH_QUARANTINE_MULTIPLIER,
        )
        resolved_quota_quarantine_sec = quota_quarantine_sec or max(
            resolved_max_cooldown_sec,
            cooldown_sec * self.QUOTA_QUARANTINE_MULTIPLIER,
        )
        self._policy = RouterPolicy(
            short_preference=short_preference,
            cooldown_sec=cooldown_sec,
            max_cooldown_sec=resolved_max_cooldown_sec,
            auth_quarantine_sec=resolved_auth_quarantine_sec,
            quota_quarantine_sec=resolved_quota_quarantine_sec,
            rate_limit_cooldown_multiplier=self.RATE_LIMIT_COOLDOWN_MULTIPLIER,
        )
        self._claude = claude
        self._gemini = gemini
        self._threshold = token_threshold
        self._short_preference = self._policy.short_preference
        self._cooldown_sec: float = self._policy.cooldown_sec
        self._max_cooldown_sec: float = self._policy.max_cooldown_sec
        self._auth_quarantine_sec: float = self._policy.auth_quarantine_sec
        self._quota_quarantine_sec: float = self._policy.quota_quarantine_sec
        self._rate_limit_cooldown_multiplier: float = self._policy.rate_limit_cooldown_multiplier
        self._time_fn = time_fn or time.monotonic
        self._provider_unavailable_until: dict[str, float] = {
            "claude": 0.0,
            "gemini": 0.0,
        }
        self._provider_cooldown_streak: dict[str, int] = {
            provider: 0 for provider in self.PROVIDERS
        }
        self._provider_profile_failure_streak: dict[str, dict[str, int]] = {
            provider: {profile: 0 for profile in self.PROFILES}
            for provider in self.PROVIDERS
        }
        self._provider_profile_last_failure_at: dict[str, dict[str, float]] = {
            provider: {profile: 0.0 for profile in self.PROFILES}
            for provider in self.PROVIDERS
        }
        self._trace_history: list[dict[str, Any]] = []
        self._last_trace: dict[str, Any] | None = None

    @classmethod
    def _is_contextual_prompt(cls, prompt: str) -> bool:
        return cls.CONTEXT_MARKER in prompt

    def _base_provider_order(self, token_estimate: int, prompt: str) -> tuple[str, str]:
        if token_estimate <= self._threshold and self._is_contextual_prompt(prompt):
            return ("gemini", "claude")
        if token_estimate <= self._threshold:
            if self._short_preference == "gemini":
                return ("gemini", "claude")
            return ("claude", "gemini")
        return ("gemini", "claude")

    def _prompt_profile(self, token_estimate: int, prompt: str) -> str:
        if token_estimate <= self._threshold and self._is_contextual_prompt(prompt):
            return self.CONTEXTUAL_SHORT_PROFILE
        if token_estimate <= self._threshold:
            return self.SHORT_PROFILE
        return self.LONG_PROFILE

    def _provider_for_name(self, name: str) -> LLMAdapter:
        if name == "claude":
            return self._claude
        return self._gemini

    def _is_provider_available(self, name: str) -> bool:
        return self._time_fn() >= self._provider_unavailable_until[name]

    def _provider_health_penalty(self, name: str, profile: str) -> float:
        streak = self._provider_profile_failure_streak[name][profile]
        if streak == 0:
            return 0.0
        elapsed = max(
            0.0,
            self._time_fn() - self._provider_profile_last_failure_at[name][profile],
        )
        recovered = elapsed / max(self._cooldown_sec, 1.0)
        return max(0.0, streak - recovered)

    def get_last_trace(self) -> dict[str, Any] | None:
        if self._last_trace is None:
            return None
        return deepcopy(self._last_trace)

    def get_trace_history(self) -> list[dict[str, Any]]:
        return deepcopy(self._trace_history)

    def _decision_reason(
        self,
        token_estimate: int,
        prompt: str,
        base_order: tuple[str, str],
        final_order: tuple[str, str],
        availability: dict[str, bool],
        penalties: dict[str, float],
    ) -> str:
        if final_order != base_order and not availability[base_order[0]]:
            return f"{base_order[0]} unavailable"
        if final_order != base_order and penalties[final_order[0]] < penalties[base_order[0]]:
            return f"{final_order[0]} healthier for {self._prompt_profile(token_estimate, prompt)}"
        if token_estimate <= self._threshold and self._is_contextual_prompt(prompt):
            return "contextual short prompt prefers gemini"
        if token_estimate <= self._threshold:
            return f"short prompt prefers {self._short_preference}"
        return "long prompt prefers gemini"

    def _retry_cooldown_window(self, name: str, category: LLMFailureCategory) -> float:
        base_window: float = self._cooldown_sec
        if category == LLMFailureCategory.RATE_LIMIT:
            base_window *= self._rate_limit_cooldown_multiplier
        cooldown_multiplier: int = 2 ** (self._provider_cooldown_streak[name] - 1)
        cooldown_window: float = base_window * cooldown_multiplier
        if cooldown_window > self._max_cooldown_sec:
            return self._max_cooldown_sec
        return cooldown_window

    def _quarantine_window(self, category: LLMFailureCategory) -> float:
        if category == LLMFailureCategory.AUTH:
            return self._auth_quarantine_sec
        return self._quota_quarantine_sec

    def _mark_provider_failed(
        self,
        name: str,
        profile: str,
        category: LLMFailureCategory,
    ) -> None:
        self._provider_profile_failure_streak[name][profile] += 1
        self._provider_profile_last_failure_at[name][profile] = self._time_fn()
        if category == LLMFailureCategory.SCHEMA:
            return
        self._provider_cooldown_streak[name] += 1
        if category in {LLMFailureCategory.AUTH, LLMFailureCategory.QUOTA}:
            self._provider_unavailable_until[name] = (
                self._time_fn() + self._quarantine_window(category)
            )
            return
        self._provider_unavailable_until[name] = (
            self._time_fn() + self._retry_cooldown_window(name, category)
        )

    def _mark_provider_healthy(self, name: str, profile: str) -> None:
        self._provider_unavailable_until[name] = 0.0
        if self._provider_cooldown_streak[name] > 0:
            self._provider_cooldown_streak[name] -= 1
        if self._provider_profile_failure_streak[name][profile] == 0:
            return
        self._provider_profile_failure_streak[name][profile] = max(
            0,
            self._provider_profile_failure_streak[name][profile] - 1,
        )
        if self._provider_profile_failure_streak[name][profile] == 0:
            self._provider_profile_last_failure_at[name][profile] = 0.0
        else:
            self._provider_profile_last_failure_at[name][profile] = self._time_fn()

    def _provider_order(self, token_estimate: int, prompt: str) -> tuple[str, str]:
        primary_name, secondary_name = self._base_provider_order(token_estimate, prompt)
        profile = self._prompt_profile(token_estimate, prompt)
        primary_available = self._is_provider_available(primary_name)
        secondary_available = self._is_provider_available(secondary_name)
        if primary_available and secondary_available:
            primary_penalty = self._provider_health_penalty(primary_name, profile)
            secondary_penalty = self._provider_health_penalty(secondary_name, profile)
            if secondary_penalty < primary_penalty:
                return (secondary_name, primary_name)
            return (primary_name, secondary_name)
        if primary_available:
            return (primary_name, secondary_name)
        if secondary_available:
            return (secondary_name, primary_name)
        return (primary_name, secondary_name)

    def generate_json(self, prompt: str) -> dict[str, Any]:
        token_estimate = len(prompt) // 4
        profile = self._prompt_profile(token_estimate, prompt)
        base_order = self._base_provider_order(token_estimate, prompt)
        primary_name, secondary_name = self._provider_order(token_estimate, prompt)
        availability = {
            provider: self._is_provider_available(provider)
            for provider in self.PROVIDERS
        }
        penalties = {
            provider: self._provider_health_penalty(provider, profile)
            for provider in self.PROVIDERS
        }
        current_trace = {
            "token_estimate": token_estimate,
            "prompt_profile": profile,
            "base_order": list(base_order),
            "final_order": [primary_name, secondary_name],
            "provider_availability": availability,
            "health_penalties": penalties,
            "selected_provider": None,
            "fallback_provider": secondary_name,
            "failure_category": None,
            "decision_reason": self._decision_reason(
                token_estimate,
                prompt,
                base_order,
                (primary_name, secondary_name),
                availability,
                penalties,
            ),
            "result": "pending",
        }
        self._last_trace = current_trace
        primary = self._provider_for_name(primary_name)
        secondary = self._provider_for_name(secondary_name)
        try:
            result = primary.generate_json(prompt)
            self._mark_provider_healthy(primary_name, profile)
            current_trace["selected_provider"] = primary_name
            current_trace["result"] = "success"
            self._trace_history.append(deepcopy(current_trace))
            return result
        except LLMProviderError as primary_exc:
            self._mark_provider_failed(primary_name, profile, primary_exc.category)
            current_trace["failure_category"] = primary_exc.category.value
            try:
                result = secondary.generate_json(prompt)
                self._mark_provider_healthy(secondary_name, profile)
                current_trace["selected_provider"] = secondary_name
                current_trace["result"] = "fallback_success"
                self._trace_history.append(deepcopy(current_trace))
                return result
            except LLMProviderError as secondary_exc:
                self._mark_provider_failed(secondary_name, profile, secondary_exc.category)
                current_trace["result"] = "failed"
                self._trace_history.append(deepcopy(current_trace))
                raise LLMProviderError(
                    "LLMRouter failed on both providers: "
                    f"primary={primary_name}[{primary_exc.category.value}]={primary_exc}; "
                    f"secondary={secondary_name}[{secondary_exc.category.value}]={secondary_exc}",
                    category=secondary_exc.category,
                    failures=(primary_exc, secondary_exc),
                ) from secondary_exc
