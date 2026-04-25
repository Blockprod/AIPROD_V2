from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from aiprod_adaptation.core.adaptation.llm_adapter import (
    LLMAdapter,
    LLMFailureCategory,
    LLMProviderError,
    classify_llm_failure,
    is_retryable_failure,
)


class GeminiAdapter(LLMAdapter):
    """
    Google Gemini via google-genai SDK.

    Selected automatically by LLMRouter when input > 80K tokens.
    Excluded from mypy (prod adapter — external dependency).
    """

    DEFAULT_MODEL = "gemini-2.5-flash"
    DEFAULT_FALLBACK_MODELS = (
        "gemini-2.5-flash-lite",
        "gemini-flash-lite-latest",
    )
    DEFAULT_TEMPERATURE = 0.0
    DEFAULT_SEED = 0
    DEFAULT_MAX_ATTEMPTS = 3
    DEFAULT_RETRY_DELAY_SEC = 1.0

    def __init__(self) -> None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        self._api_key = api_key
        self._model = os.environ.get("GEMINI_MODEL", self.DEFAULT_MODEL)
        fallback_models_raw = os.environ.get("GEMINI_FALLBACK_MODELS", "")
        if fallback_models_raw.strip():
            self._fallback_models = tuple(
                model.strip()
                for model in fallback_models_raw.split(",")
                if model.strip() and model.strip() != self._model
            )
        else:
            self._fallback_models = tuple(
                model for model in self.DEFAULT_FALLBACK_MODELS if model != self._model
            )
        self._client: Any | None = None
        self._max_attempts = self.DEFAULT_MAX_ATTEMPTS
        self._retry_delay_sec = self.DEFAULT_RETRY_DELAY_SEC
        self._generation_config = _build_generation_config()

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                self._client = _build_gemini_client(self._api_key)
            except ImportError as exc:
                raise ImportError(
                    "google-genai package required: pip install google-genai"
                ) from exc
        return self._client

    def _generate_with_model(self, model: str, prompt: str) -> dict[str, Any]:
        last_error: Exception | None = None
        last_category = LLMFailureCategory.UNKNOWN
        client = self._ensure_client()
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=self._generation_config,
                )
                content = response.text or ""
                start = content.find("{")
                end = content.rfind("}") + 1
                if start == -1 or end == 0:
                    return {"scenes": []}
                return dict(json.loads(content[start:end]))
            except json.JSONDecodeError as exc:
                last_error = exc
                last_category = LLMFailureCategory.SCHEMA
                break
            except LLMProviderError as exc:
                last_error = exc
                last_category = exc.category
                if attempt == self._max_attempts or not is_retryable_failure(exc.category):
                    break
                time.sleep(self._retry_delay_sec)
            except Exception as exc:
                last_error = exc
                last_category = classify_llm_failure(str(exc))
                if attempt == self._max_attempts or not is_retryable_failure(last_category):
                    break
                time.sleep(self._retry_delay_sec)
        if (
            last_category == LLMFailureCategory.SCHEMA
            and isinstance(last_error, json.JSONDecodeError)
        ):
            raise LLMProviderError(
                f"Gemini response JSON decode failed ({model}): {last_error}",
                category=LLMFailureCategory.SCHEMA,
            ) from last_error
        raise LLMProviderError(
            f"Gemini request failed ({model}): {last_error}",
            category=last_category,
        )

    def generate_json(self, prompt: str) -> dict[str, Any]:
        failures: list[LLMProviderError] = []
        for model in (self._model, *self._fallback_models):
            try:
                return self._generate_with_model(model, prompt)
            except LLMProviderError as exc:
                failures.append(exc)
        raise LLMProviderError(
            "Gemini request failed across all configured models: "
            + " | ".join(str(exc) for exc in failures),
            category=failures[-1].category if failures else LLMFailureCategory.UNKNOWN,
            failures=tuple(failures),
        )


@dataclass(frozen=True)
class _FallbackGenerateContentConfig:
    temperature: float
    candidate_count: int
    seed: int
    response_mime_type: str


def _build_generation_config() -> object:
    try:
        from google.genai import types
    except ImportError:
        return _FallbackGenerateContentConfig(
            temperature=GeminiAdapter.DEFAULT_TEMPERATURE,
            candidate_count=1,
            seed=GeminiAdapter.DEFAULT_SEED,
            response_mime_type="application/json",
        )

    return types.GenerateContentConfig(
        temperature=GeminiAdapter.DEFAULT_TEMPERATURE,
        candidate_count=1,
        seed=GeminiAdapter.DEFAULT_SEED,
        response_mime_type="application/json",
    )


def _build_gemini_client(api_key: str) -> Any:
    from google import genai

    return genai.Client(api_key=api_key)
