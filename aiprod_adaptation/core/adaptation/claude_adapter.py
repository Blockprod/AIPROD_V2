from __future__ import annotations

import json
import os
from typing import Any, Protocol, cast

from aiprod_adaptation.core.adaptation.llm_adapter import (
    LLMAdapter,
    LLMFailureCategory,
    LLMProviderError,
    classify_llm_failure,
)


class _TextBlockLike(Protocol):
    text: str


def _extract_message_text(message: Any) -> str:
    parts: list[str] = []
    for block in message.content:
        if getattr(block, "type", None) == "text":
            parts.append(cast(_TextBlockLike, block).text)
    return "".join(parts)


class ClaudeAdapter(LLMAdapter):
    """LLM adapter backed by Claude via the Anthropic API.

    Requires ANTHROPIC_API_KEY environment variable.
    NOT used in CI — tests use NullLLMAdapter.
    """

    MODEL = "claude-sonnet-4-5"
    MAX_TOKENS = 4096

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set.")
        self._api_key = api_key
        self._client: Any | None = None
        self._input_tokens: int = 0
        self._output_tokens: int = 0

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                self._client = _build_anthropic_client(self._api_key)
            except ImportError as exc:
                raise ImportError(
                    "anthropic package required: pip install anthropic"
                ) from exc
        return self._client

    def generate_json(self, prompt: str) -> dict[str, Any]:
        client = self._ensure_client()
        try:
            message = client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise LLMProviderError(
                f"Claude request failed: {exc}",
                category=classify_llm_failure(str(exc)),
            ) from exc

        if hasattr(message, "usage"):
            self._input_tokens += getattr(message.usage, "input_tokens", 0)
            self._output_tokens += getattr(message.usage, "output_tokens", 0)
        content = _extract_message_text(message)
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == 0:
            return {"scenes": []}
        try:
            return dict(json.loads(content[start:end]))
        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                f"Claude response JSON decode failed: {exc}",
                category=LLMFailureCategory.SCHEMA,
            ) from exc

    def get_token_usage(self) -> tuple[int, int]:
        return self._input_tokens, self._output_tokens


def _build_anthropic_client(api_key: str) -> Any:
    import anthropic

    return anthropic.Anthropic(api_key=api_key)


def _get_claude_token_usage(adapter: ClaudeAdapter) -> tuple[int, int]:
    return adapter._input_tokens, adapter._output_tokens
