"""
CharacterPrepass — generates one reference image per character before the main storyboard.
Populates CharacterImageRegistry so StoryboardGenerator can use consistent references.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry
from aiprod_adaptation.image_gen.character_sheet import CharacterSheetRegistry
from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import ImageRequest
from aiprod_adaptation.image_gen.storyboard import DEFAULT_STYLE_TOKEN
from aiprod_adaptation.models.schema import AIPRODOutput


def _unique_characters(output: AIPRODOutput) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for ep in output.episodes:
        for scene in ep.scenes:
            for char in scene.characters:
                if char not in seen:
                    seen.add(char)
                    result.append(char)
    return result


@dataclass
class CharacterPrepassResult:
    generated: int
    failed: int
    registry: CharacterImageRegistry = field(default_factory=CharacterImageRegistry)


class CharacterPrepass:
    def __init__(
        self,
        adapter: ImageAdapter,
        sheet_registry: CharacterSheetRegistry | None = None,
        base_seed: int = 0,
        style_token: str = DEFAULT_STYLE_TOKEN,
    ) -> None:
        self._adapter = adapter
        self._sheet_registry = sheet_registry or CharacterSheetRegistry()
        self._base_seed = base_seed
        self._style_token = style_token

    def run(self, output: AIPRODOutput) -> CharacterPrepassResult:
        characters = _unique_characters(output)
        registry = CharacterImageRegistry()
        generated = 0
        failed = 0

        for idx, name in enumerate(characters):
            sheet = self._sheet_registry.get(name)
            canonical = sheet.canonical_prompt if sheet is not None else name
            seed = (sheet.seed if sheet is not None else self._base_seed + idx)
            prompt = f"{canonical} {self._style_token}".strip()
            req = ImageRequest(
                shot_id=f"PREPASS_{name}",
                scene_id="CHARACTER_PREPASS",
                prompt=prompt,
                seed=seed,
            )
            try:
                result = self._adapter.generate(req)
                registry.register(name, result.image_url)
                registry.register_prompt(name, canonical)
                generated += 1
            except Exception:
                failed += 1

        return CharacterPrepassResult(
            generated=generated,
            failed=failed,
            registry=registry,
        )
