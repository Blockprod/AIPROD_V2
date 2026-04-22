from __future__ import annotations

import json
import os
from typing import Any

from aiprod_adaptation.core.adaptation.llm_adapter import LLMAdapter


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
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic package required: pip install anthropic"
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate_json(self, prompt: str) -> dict[str, Any]:
        message = self._client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        content: str = message.content[0].text
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == 0:
            return {"scenes": []}
        return dict(json.loads(content[start:end]))
