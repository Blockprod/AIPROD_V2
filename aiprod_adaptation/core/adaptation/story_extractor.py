from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from aiprod_adaptation.core.adaptation.llm_adapter import LLMAdapter
from aiprod_adaptation.core.adaptation.normalizer import Normalizer
from aiprod_adaptation.models.intermediate import VisualScene

if TYPE_CHECKING:
    from aiprod_adaptation.core.production_budget import ProductionBudget


class StoryExtractor:
    """
    Single-call LLM scene extractor with JSON schema enforcement via prompt.

    Replaces the 3-call novel_pipe.run_novel_pipe().
    extract_chunk() is the P6-compatible interface (prior_summary enables inter-chunk context).
    """

    PRODUCTION_SCHEMA: dict[str, Any] = {
        "type": "object",
        "required": ["scenes"],
        "properties": {
            "scenes": {
                "type": "array",
                "maxItems": 150,
                "items": {
                    "type": "object",
                    "required": ["location", "characters", "actions", "emotion"],
                    "properties": {
                        "location": {"type": "string", "minLength": 3},
                        "characters": {
                            "type": "array",
                            "maxItems": 2,
                            "items": {"type": "string"},
                        },
                        "actions": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 6,
                            "items": {"type": "string", "maxLength": 120},
                        },
                        "dialogues": {"type": "array", "items": {"type": "string"}},
                        "emotion": {
                            "enum": ["angry", "scared", "sad", "happy", "nervous", "neutral"]
                        },
                        "pacing": {"enum": ["fast", "medium", "slow"]},
                        "time_of_day_visual": {
                            "enum": ["dawn", "day", "dusk", "night", "interior"]
                        },
                        "dominant_sound": {
                            "enum": ["dialogue", "ambient", "silence"]
                        },
                    },
                },
            }
        },
    }

    def extract(
        self,
        llm: LLMAdapter,
        text: str,
        budget: "ProductionBudget",
        prior_summary: str = "",
    ) -> list[VisualScene]:
        """
        Single LLM call → list[VisualScene].

        prior_summary: résumé des scènes précédentes.
        Vide pour usage normal (P1/P2); renseigné par P6 pour le chunking.
        """
        context_block = (
            f"\nCONTEXT FROM PREVIOUS SCENES:\n{prior_summary}\n"
            if prior_summary
            else ""
        )
        schema_str = json.dumps(self.PRODUCTION_SCHEMA, ensure_ascii=False)
        prompt = (
            "You are a professional screenwriter adapting text into a filmable screenplay.\n\n"
            "ABSOLUTE CONSTRAINTS:\n"
            f"- Maximum {budget.max_scenes} scenes for this sequence\n"
            "- Each action = 1 shot = 3 to 8 seconds of video\n"
            "- Maximum 2 visible characters per scene\n"
            "- Zero internal thoughts, zero narration — only observable actions\n"
            "- Each action must be filmable with a camera\n"
            "- Maximum 6 actions per scene\n"
            "- Location = 1 concrete identifiable set (e.g. 'wooden cabin interior')\n"
            "- emotion: angry | scared | sad | happy | nervous | neutral\n"
            "- pacing: fast (action/chase) | slow (drama/tension) | medium (default)\n"
            "- time_of_day_visual: dawn | day | dusk | night | interior\n"
            "- dominant_sound: dialogue | ambient | silence\n"
            f"{context_block}\n"
            f"Return ONLY valid JSON matching this schema:\n{schema_str}\n\n"
            f"TEXT:\n{text}"
        )
        result = llm.generate_json(prompt)
        raw_scenes: list[dict[str, Any]] = result.get("scenes", [])
        if not isinstance(raw_scenes, list):
            raw_scenes = []
        return Normalizer().normalize(raw_scenes)

    def extract_chunk(
        self,
        llm: LLMAdapter,
        text: str,
        budget: "ProductionBudget",
        prior_summary: str = "",
    ) -> list[VisualScene]:
        """P6-compatible alias for extract(). Identical behaviour when prior_summary=''."""
        return self.extract(llm, text, budget, prior_summary)
