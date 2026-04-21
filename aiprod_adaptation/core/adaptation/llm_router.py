from __future__ import annotations

from typing import Any

from aiprod_adaptation.core.adaptation.llm_adapter import LLMAdapter


class LLMRouter(LLMAdapter):
    """
    Routes LLM calls based on estimated input token count.

    - input <= token_threshold  →  claude (default: fast, 200K context)
    - input >  token_threshold  →  gemini (1M context, for long novels)

    Token estimation: len(prompt) // 4  (4 chars ≈ 1 token).
    Default threshold: 80_000 tokens ≈ 320_000 chars ≈ 240_000 words.
    """

    def __init__(
        self,
        claude: LLMAdapter,
        gemini: LLMAdapter,
        token_threshold: int = 80_000,
    ) -> None:
        self._claude = claude
        self._gemini = gemini
        self._threshold = token_threshold

    def generate_json(self, prompt: str) -> dict[str, Any]:
        token_estimate = len(prompt) // 4
        if token_estimate <= self._threshold:
            return self._claude.generate_json(prompt)
        return self._gemini.generate_json(prompt)
