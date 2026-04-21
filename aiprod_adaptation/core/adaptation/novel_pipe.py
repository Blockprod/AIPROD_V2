from __future__ import annotations

import json
from typing import Any

from aiprod_adaptation.core.adaptation.llm_adapter import LLMAdapter

_SCENE_SCHEMA = (
    '{"scenes": [{"location": "", "characters": [], '
    '"actions": [], "dialogues": [], "emotion": "neutral"}]}'
)


def extract_scenes(llm: LLMAdapter, text: str) -> list[dict[str, Any]]:
    prompt = (
        "Split this novel into cinematic scenes.\n\n"
        "Rules:\n"
        "- One location per scene\n"
        "- Max 2 main characters\n"
        f"- Output JSON only: {_SCENE_SCHEMA}\n\n"
        f"TEXT:\n{text}"
    )
    result = llm.generate_json(prompt)
    scenes = result.get("scenes", [])
    return scenes if isinstance(scenes, list) else []


def make_cinematic(llm: LLMAdapter, scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prompt = (
        "Convert narrative scenes into filmable actions.\n\n"
        "Rules:\n"
        "- Remove internal thoughts\n"
        "- Keep only visible actions\n"
        "- Convert abstraction into physical behavior\n"
        "- Output JSON only: same structure as input\n\n"
        f"INPUT:\n{json.dumps(scenes, ensure_ascii=False)}"
    )
    result = llm.generate_json(prompt)
    scenes_out = result.get("scenes", scenes)
    return scenes_out if isinstance(scenes_out, list) else scenes


def to_screenplay(llm: LLMAdapter, scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prompt = (
        "Convert into structured screenplay JSON.\n\n"
        f"Output format:\n{_SCENE_SCHEMA}\n\n"
        f"INPUT:\n{json.dumps(scenes, ensure_ascii=False)}"
    )
    result = llm.generate_json(prompt)
    scenes_out = result.get("scenes", scenes)
    return scenes_out if isinstance(scenes_out, list) else scenes


def run_novel_pipe(llm: LLMAdapter, text: str) -> list[dict[str, Any]]:
    scenes = extract_scenes(llm, text)
    scenes = make_cinematic(llm, scenes)
    scenes = to_screenplay(llm, scenes)
    return scenes
