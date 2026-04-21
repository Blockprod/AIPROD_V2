from __future__ import annotations

import json
import os
from typing import Any

from aiprod_adaptation.core.adaptation.llm_adapter import LLMAdapter


class GeminiAdapter(LLMAdapter):
    """
    Google Gemini 2.5 Pro via google-generativeai SDK.

    Selected automatically by LLMRouter when input > 80K tokens.
    Excluded from mypy (prod adapter — external dependency).
    """

    MODEL = "gemini-2.5-pro"

    def __init__(self) -> None:
        import google.generativeai as genai

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(self.MODEL)

    def generate_json(self, prompt: str) -> dict[str, Any]:
        try:
            response = self._model.generate_content(prompt)
            content: str = response.text
            start = content.find("{")
            end = content.rfind("}") + 1
            if start == -1 or end == 0:
                return {"scenes": []}
            return dict(json.loads(content[start:end]))
        except Exception:
            return {"scenes": []}
