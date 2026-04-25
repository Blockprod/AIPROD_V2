from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from aiprod_adaptation.core.adaptation.llm_adapter import LLMAdapter
from aiprod_adaptation.core.adaptation.normalizer import Normalizer
from aiprod_adaptation.models.intermediate import VisualScene

if TYPE_CHECKING:
    from aiprod_adaptation.core.production_budget import ProductionBudget


def _append_unique(values: list[str], candidate: str) -> None:
    cleaned = candidate.strip()
    if cleaned and cleaned not in values:
        values.append(cleaned)


def _build_continuity_snapshot(scenes: list[VisualScene]) -> dict[str, object]:
    recent_scenes = scenes[-3:]
    active_characters: list[str] = []
    active_locations: list[str] = []
    snapshot_scenes: list[dict[str, object]] = []

    for scene in recent_scenes:
        location = scene.get("location", "Unknown")
        if location != "Unknown":
            _append_unique(active_locations, location)
        for character in scene.get("characters", []):
            _append_unique(active_characters, character)
        snapshot_scenes.append(
            {
                "scene_id": scene["scene_id"],
                "location": location,
                "characters": list(scene.get("characters", [])),
                "emotion": scene.get("emotion", "neutral"),
                "actions": list(scene.get("visual_actions", []))[:2],
            }
        )

    return {
        "recent_scenes": snapshot_scenes,
        "active_characters": active_characters,
        "active_locations": active_locations,
    }


def _serialize_continuity_snapshot(snapshot: dict[str, object]) -> str:
    return "CONTINUITY_SNAPSHOT_JSON:\n" + json.dumps(snapshot, ensure_ascii=False)


def _parse_prior_summary_snapshot(prior_summary: str) -> dict[str, Any] | None:
    prefix = "CONTINUITY_SNAPSHOT_JSON:\n"
    if not prior_summary.startswith(prefix):
        return None
    payload = prior_summary[len(prefix):].strip()
    if not payload:
        return None
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def split_into_chunks(text: str, max_chars: int = 8_000) -> list[str]:
    """
    Découpe text aux frontières de paragraphes (double newline).
    Garantit: len(chunk) <= max_chars.
    Si un paragraphe seul dépasse max_chars, il est tronqué à la dernière phrase.
    Retourne une liste de chunks non-vides.
    """
    if not text.strip():
        return []
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0
    for para in paragraphs:
        para_len = len(para)
        if para_len > max_chars:
            # flush current accumulator first
            if current_parts:
                chunks.append("\n\n".join(current_parts))
                current_parts = []
                current_len = 0
            # truncate oversized paragraph at last sentence boundary
            truncated = para[:max_chars]
            last_dot = max(truncated.rfind(". "), truncated.rfind(".\n"))
            if last_dot > 0:
                truncated = truncated[: last_dot + 1]
            chunks.append(truncated.strip())
            continue
        separator_len = 2 if current_parts else 0
        if current_len + separator_len + para_len > max_chars:
            chunks.append("\n\n".join(current_parts))
            current_parts = [para]
            current_len = para_len
        else:
            current_parts.append(para)
            current_len += separator_len + para_len
    if current_parts:
        chunks.append("\n\n".join(current_parts))
    return [c for c in chunks if c.strip()]


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
        budget: ProductionBudget,
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
        continuity_snapshot = _parse_prior_summary_snapshot(prior_summary)
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
        return Normalizer().normalize(
            raw_scenes,
            continuity_snapshot=continuity_snapshot,
        )

    def extract_chunk(
        self,
        llm: LLMAdapter,
        text: str,
        budget: ProductionBudget,
        prior_summary: str = "",
    ) -> list[VisualScene]:
        """P6-compatible alias for extract(). Identical behaviour when prior_summary=''."""
        return self.extract(llm, text, budget, prior_summary)

    def extract_all(
        self,
        llm: LLMAdapter,
        text: str,
        budget: ProductionBudget,
    ) -> list[VisualScene]:
        """
        Découpe text en chunks via split_into_chunks(budget.max_chars_per_chunk),
        appelle extract_chunk() sur chacun avec prior_summary cumulatif.
        """
        chunks = split_into_chunks(text, budget.max_chars_per_chunk)
        if not chunks:
            return []
        if len(chunks) == 1:
            return self.extract_chunk(llm, chunks[0], budget, prior_summary="")
        all_scenes: list[VisualScene] = []
        prior_summary = ""
        for chunk in chunks:
            scenes = self.extract_chunk(llm, chunk, budget, prior_summary)
            all_scenes.extend(scenes)
            if scenes:
                prior_summary = _serialize_continuity_snapshot(
                    _build_continuity_snapshot(all_scenes)
                )
        return all_scenes
