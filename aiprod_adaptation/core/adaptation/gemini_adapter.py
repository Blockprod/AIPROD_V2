from __future__ import annotations

import json
import os
import time
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
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
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
        self._client = genai.Client(api_key=api_key)
        self._max_attempts = self.DEFAULT_MAX_ATTEMPTS
        self._retry_delay_sec = self.DEFAULT_RETRY_DELAY_SEC
        self._generation_config = types.GenerateContentConfig(
            temperature=self.DEFAULT_TEMPERATURE,
            candidate_count=1,
            seed=self.DEFAULT_SEED,
            response_mime_type="application/json",
        )

    def _generate_with_model(self, model: str, prompt: str) -> dict[str, Any]:
        last_error: Exception | None = None
        last_category = LLMFailureCategory.UNKNOWN
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.models.generate_content(
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
