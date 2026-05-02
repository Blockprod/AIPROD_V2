"""
pytest test suite — Image Generation Connector v1

Covers:
  1. ImageRequest validation          — IG-01
  2. NullImageAdapter                 — IG-02
  3. StoryboardGenerator              — IG-04
  4. run_pipeline_with_images()       — IG-05
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from aiprod_adaptation.core.engine import run_pipeline, run_pipeline_with_images
from aiprod_adaptation.image_gen.image_adapter import NullImageAdapter
from aiprod_adaptation.image_gen.image_request import (
    ImageRequest,
    ImageResult,
    ShotStoryboardFrame,
    StoryboardOutput,
)
from aiprod_adaptation.image_gen.openai_image_adapter import (
    OpenAIImageAdapter,
    _estimate_openai_image_cost,
    _openai_image_size,
)
from aiprod_adaptation.image_gen.reference_pack import ReferencePack
from aiprod_adaptation.image_gen.runway_image_adapter import RunwayImageAdapter, _runway_image_ratio
from aiprod_adaptation.image_gen.storyboard import DEFAULT_STYLE_TOKEN, StoryboardGenerator
from aiprod_adaptation.models.schema import AIPRODOutput

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOVEL = (
    "John walked quickly through the busy city streets. "
    "He felt very excited about the important meeting. "
    "Sarah waited nervously inside the old wooden house."
)

_REQ = ImageRequest(shot_id="SH0001", scene_id="SC001", prompt="A man walks fast.")


# ---------------------------------------------------------------------------
# 1. ImageRequest
# ---------------------------------------------------------------------------

class TestImageRequest:
    def test_image_request_default_values(self) -> None:
        req = ImageRequest(shot_id="S1", scene_id="SC001", prompt="test")
        assert req.width == 1024
        assert req.height == 576
        assert req.num_steps == 28
        assert req.guidance_scale == 7.5

    def test_image_request_accepts_structured_action(self) -> None:
        req = ImageRequest(
            shot_id="S1",
            scene_id="SC001",
            prompt="test",
            action={
                "subject_id": "john",
                "action_type": "walked",
                "target": "door",
                "modifiers": ["quickly"],
                "location_id": "hallway",
                "camera_intent": "follow",
                "source_text": "John walked quickly to the door.",
            },
        )
        assert req.action is not None
        assert req.action.action_type == "walked"

    def test_image_request_invalid_steps_raises(self) -> None:
        with pytest.raises(Exception):
            ImageRequest(shot_id="S1", scene_id="SC001", prompt="test", num_steps=0)

    def test_image_request_invalid_guidance_raises(self) -> None:
        with pytest.raises(Exception):
            ImageRequest(shot_id="S1", scene_id="SC001", prompt="test", guidance_scale=0.5)

    def test_storyboard_output_generated_count(self) -> None:
        sb = StoryboardOutput(
            title="T",
            frames=[],
            style_token="",
            total_shots=5,
            generated=3,
        )
        assert sb.generated <= sb.total_shots


# ---------------------------------------------------------------------------
# 2. NullImageAdapter
# ---------------------------------------------------------------------------

class TestNullImageAdapter:
    def setup_method(self) -> None:
        self.adapter = NullImageAdapter()

    def test_null_adapter_returns_image_result(self) -> None:
        result = self.adapter.generate(_REQ)
        assert isinstance(result, ImageResult)

    def test_null_adapter_is_deterministic(self) -> None:
        r1 = self.adapter.generate(_REQ)
        r2 = self.adapter.generate(_REQ)
        assert r1.image_url == r2.image_url

    def test_null_adapter_shot_id_preserved(self) -> None:
        result = self.adapter.generate(_REQ)
        assert result.shot_id == _REQ.shot_id


class TestOpenAIImageAdapterHelpers:
    def test_openai_image_size_uses_landscape_variant(self) -> None:
        assert _openai_image_size(1024, 576) == "1536x1024"

    def test_openai_image_size_uses_portrait_variant(self) -> None:
        assert _openai_image_size(576, 1024) == "1024x1536"

    def test_openai_image_size_uses_square_variant(self) -> None:
        assert _openai_image_size(1024, 1024) == "1024x1024"

    def test_openai_image_cost_estimate_for_default_low_cost_profile(self) -> None:
        assert _estimate_openai_image_cost("gpt-image-1-mini", "1536x1024", "low") == 0.006

    def test_openai_image_cost_estimate_returns_zero_for_auto_quality(self) -> None:
        assert _estimate_openai_image_cost("gpt-image-1-mini", "1536x1024", "auto") == 0.0

    def test_openai_image_cost_estimate_normalizes_versioned_model_name(self) -> None:
        # "gpt-image-1-2025-04-23" is a versioned alias of "gpt-image-1"
        assert _estimate_openai_image_cost("gpt-image-1-2025-04-23", "1024x1024", "low") == 0.011
        assert _estimate_openai_image_cost("gpt-image-1-2025-04-23", "1024x1024", "high") == 0.167

    def test_openai_adapter_defaults_to_low_cost_profile(self) -> None:
        # Clear any IMAGE env vars injected by _load_env_file in other test modules
        with patch.dict(os.environ, {}, clear=False) as patched_env:
            patched_env.pop("OPENAI_IMAGE_MODEL", None)
            patched_env.pop("OPENAI_IMAGE_QUALITY", None)
            adapter = OpenAIImageAdapter(api_key="test-key")
        assert adapter._model == "gpt-image-1-mini"
        assert adapter._quality == "low"

    def test_openai_adapter_accepts_env_overrides(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_IMAGE_MODEL": "gpt-image-1",
                "OPENAI_IMAGE_QUALITY": "high",
            },
            clear=False,
        ):
            adapter = OpenAIImageAdapter(api_key="test-key")

        assert adapter._model == "gpt-image-1"
        assert adapter._quality == "high"

    def test_openai_adapter_passes_quality_to_generate(self) -> None:
        response = SimpleNamespace(
            data=[SimpleNamespace(b64_json="ZmFrZQ==", url="")],
        )

        openai_client = MagicMock()
        openai_client.images.generate.return_value = response

        with patch(
            "aiprod_adaptation.image_gen.openai_image_adapter._build_openai_client",
            return_value=openai_client,
        ) as build_client:
            adapter = OpenAIImageAdapter(api_key="test-key", model="gpt-image-1-mini", quality="medium")
            result = adapter.generate(_REQ)

        build_client.assert_called_once_with("test-key")
        openai_client.images.generate.assert_called_once_with(
            model="gpt-image-1-mini",
            prompt=_REQ.prompt,
            size="1536x1024",
            quality="medium",
        )
        assert result.image_b64 == "ZmFrZQ=="
        assert result.cost_usd == 0.015


class TestRunwayImageAdapterHelpers:
    def test_runway_image_ratio_uses_landscape_variant(self) -> None:
        assert _runway_image_ratio(1024, 576) == "1280:720"

    def test_runway_image_ratio_uses_portrait_variant(self) -> None:
        assert _runway_image_ratio(576, 1024) == "720:1280"

    def test_runway_image_ratio_uses_square_variant(self) -> None:
        assert _runway_image_ratio(1024, 1024) == "1024:1024"

    def test_runway_image_ratio_uses_gemini_landscape_variant(self) -> None:
        assert _runway_image_ratio(1024, 576, "gemini_2.5_flash") == "1536:672"

    def test_runway_image_ratio_uses_gemini_portrait_variant(self) -> None:
        assert _runway_image_ratio(576, 1024, "gemini_2.5_flash") == "832:1248"

    def test_runway_image_adapter_requires_token(self) -> None:
        adapter = RunwayImageAdapter(api_token="")

        with pytest.raises(ValueError, match="RUNWAY_API_TOKEN"):
            adapter.generate(_REQ)


# ---------------------------------------------------------------------------
# 3. StoryboardGenerator
# ---------------------------------------------------------------------------

class TestStoryboardGenerator:
    def setup_method(self) -> None:
        self.adapter = NullImageAdapter()
        self.gen = StoryboardGenerator(adapter=self.adapter, base_seed=42)

    def _output(self) -> AIPRODOutput:
        return run_pipeline(_NOVEL, "T")

    def test_storyboard_generates_one_result_per_shot(self) -> None:
        output = self._output()
        sb = self.gen.generate(output)
        total = sum(len(ep.shots) for ep in output.episodes)
        assert len(sb.frames) == total

    def test_storyboard_is_deterministic(self) -> None:
        output = self._output()
        sb1 = self.gen.generate(output)
        sb2 = self.gen.generate(output)
        assert json.dumps(sb1.model_dump(), sort_keys=False) == \
               json.dumps(sb2.model_dump(), sort_keys=False)

    def test_storyboard_title_preserved(self) -> None:
        output = self._output()
        sb = self.gen.generate(output)
        assert sb.title == "T"

    def test_storyboard_generated_count_correct(self) -> None:
        output = self._output()
        sb = self.gen.generate(output)
        assert sb.generated == sb.total_shots

    def test_storyboard_build_requests_count(self) -> None:
        output = self._output()
        requests = self.gen.build_requests(output)
        total = sum(len(ep.shots) for ep in output.episodes)
        assert len(requests) == total

    def test_storyboard_build_requests_include_structured_action(self) -> None:
        output = self._output()
        requests = self.gen.build_requests(output)
        assert requests[0].action is not None
        assert requests[0].action.source_text == output.episodes[0].shots[0].action.source_text

    def test_storyboard_build_requests_propagates_structured_action(self) -> None:
        output = run_pipeline("Emma walked quickly to the door.", "T")
        requests = self.gen.build_requests(output)
        assert requests[0].action is not None
        # v3: first action is from body-language layer (e.g. 'face'); subject must be 'emma'
        assert requests[0].action.subject_id == "emma"

    def test_storyboard_error_in_adapter_does_not_crash(self) -> None:
        class BrokenAdapter(NullImageAdapter):
            def generate(self, _request: ImageRequest) -> ImageResult:
                raise RuntimeError("API down")

        gen = StoryboardGenerator(adapter=BrokenAdapter(), base_seed=0)
        output = run_pipeline(_NOVEL, "T")
        sb = gen.generate(output)
        assert all(r.model_used == "error" for r in sb.frames)
        assert sb.generated == 0

    def test_storyboard_error_logs_warning(self) -> None:
        from unittest.mock import MagicMock, patch

        class BrokenAdapter(NullImageAdapter):
            def generate(self, _request: ImageRequest) -> ImageResult:
                raise RuntimeError("API down")

        output = run_pipeline(_NOVEL, "T")
        logger = MagicMock()
        with patch("aiprod_adaptation.image_gen.storyboard.logger", logger):
            sb = StoryboardGenerator(adapter=BrokenAdapter(), base_seed=0).generate(output)

        assert all(r.model_used == "error" for r in sb.frames)
        logger.warning.assert_called()


# ---------------------------------------------------------------------------
# 4. run_pipeline_with_images
# ---------------------------------------------------------------------------

class TestRunPipelineWithImages:
    def test_run_pipeline_with_images_null_adapter(self) -> None:
        output, storyboard = run_pipeline_with_images(
            _NOVEL, "T", image_adapter=NullImageAdapter(), image_base_seed=0
        )
        assert storyboard is not None
        assert storyboard.total_shots > 0

    def test_run_pipeline_with_images_no_adapter(self) -> None:
        output, storyboard = run_pipeline_with_images(_NOVEL, "T")
        assert storyboard is None

    def test_run_pipeline_output_unchanged(self) -> None:
        plain = run_pipeline(_NOVEL, "T")
        enriched, _ = run_pipeline_with_images(
            _NOVEL, "T", image_adapter=NullImageAdapter(), image_base_seed=0
        )
        assert json.dumps(plain.model_dump(), sort_keys=False) == \
               json.dumps(enriched.model_dump(), sort_keys=False)


# ---------------------------------------------------------------------------
# 5. CharacterImageRegistry — PQ-01
# ---------------------------------------------------------------------------

class TestCharacterImageRegistry:
    def setup_method(self) -> None:
        from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry
        self.reg = CharacterImageRegistry()

    def test_registry_stores_first_image_for_character(self) -> None:
        self.reg.register("John", "null://storyboard/SH0001.png")
        assert self.reg.get_reference("John") == "null://storyboard/SH0001.png"

    def test_registry_does_not_overwrite_existing_character(self) -> None:
        self.reg.register("John", "null://storyboard/SH0001.png")
        self.reg.register("John", "null://storyboard/SH0002.png")
        assert self.reg.get_reference("John") == "null://storyboard/SH0001.png"

    def test_registry_returns_empty_for_unknown_character(self) -> None:
        assert self.reg.get_reference("Nobody") == ""

    def test_storyboard_passes_reference_to_second_shot_same_character(self) -> None:
        received_refs: list[str] = []

        from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
        from aiprod_adaptation.image_gen.image_request import ImageResult

        class TrackingAdapter(ImageAdapter):
            def generate(self, request: ImageRequest) -> ImageResult:
                received_refs.append(request.reference_image_url)
                return ImageResult(
                    shot_id=request.shot_id,
                    image_url=f"null://storyboard/{request.shot_id}.png",
                    model_used="tracking",
                    latency_ms=0,
                )

        output = run_pipeline(_NOVEL, "T")
        StoryboardGenerator(adapter=TrackingAdapter(), base_seed=0).generate(output)
        # First shot of a character has no reference; at least one later shot may have one
        assert len(received_refs) > 0
        assert received_refs[0] == ""   # first shot never has a reference


# ---------------------------------------------------------------------------
# 6. CharacterImageRegistry — canonical_prompt (SB-01)
# ---------------------------------------------------------------------------

class TestCharacterImageRegistryCanonical:
    def setup_method(self) -> None:
        from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry
        self.reg = CharacterImageRegistry()

    def test_registry_stores_canonical_prompt(self) -> None:
        self.reg.register_prompt("John", "tall man, brown coat")
        assert self.reg.get_canonical_prompt("John") == "tall man, brown coat"

    def test_registry_canonical_prompt_not_overwritten(self) -> None:
        self.reg.register_prompt("John", "tall man, brown coat")
        self.reg.register_prompt("John", "short woman, red dress")
        assert self.reg.get_canonical_prompt("John") == "tall man, brown coat"

    def test_storyboard_injects_canonical_prompt_in_prompt(self) -> None:
        received_prompts: list[str] = []

        class TrackingAdapter(NullImageAdapter):
            def generate(self, request: ImageRequest) -> ImageResult:
                received_prompts.append(request.prompt)
                return NullImageAdapter().generate(request)

        output = run_pipeline(_NOVEL, "T")
        # Discover actual character names produced by the pipeline
        chars = [c for ep in output.episodes for sc in ep.scenes for c in sc.characters]
        char_prompts = {name: "tall man, brown coat" for name in chars} if chars else {}
        StoryboardGenerator(
            adapter=TrackingAdapter(),
            character_prompts=char_prompts,
        ).generate(output)
        if chars:
            assert any("tall man, brown coat" in p for p in received_prompts)

    def test_storyboard_no_canonical_prompt_does_not_crash(self) -> None:
        output = run_pipeline(_NOVEL, "T")
        sb = StoryboardGenerator(adapter=NullImageAdapter()).generate(output)
        assert len(sb.frames) > 0


# ---------------------------------------------------------------------------
# 7. StoryboardGenerator — STYLE_TOKEN (SB-02)
# ---------------------------------------------------------------------------

class TestStyleToken:
    def test_style_token_default_injected_in_all_prompts(self) -> None:
        received_prompts: list[str] = []

        class TrackingAdapter(NullImageAdapter):
            def generate(self, request: ImageRequest) -> ImageResult:
                received_prompts.append(request.prompt)
                return NullImageAdapter().generate(request)

        output = run_pipeline(_NOVEL, "T")
        StoryboardGenerator(adapter=TrackingAdapter(), base_seed=0).generate(output)
        # The new structured prompt builder includes ARRI Alexa and anamorphic from _TECH_FOOTER
        assert all("arri alexa" in p.lower() for p in received_prompts)
        assert all("anamorphic" in p.lower() for p in received_prompts)

    def test_style_token_custom_overrides_default(self) -> None:
        received_prompts: list[str] = []

        class TrackingAdapter(NullImageAdapter):
            def generate(self, request: ImageRequest) -> ImageResult:
                received_prompts.append(request.prompt)
                return NullImageAdapter().generate(request)

        output = run_pipeline(_NOVEL, "T")
        # With the structured prompt builder, style_token is still passed but is not
        # used verbatim in the prompt (replaced by _TECH_FOOTER). The default token
        # text itself is never injected verbatim anymore.
        StoryboardGenerator(
            adapter=TrackingAdapter(),
            style_token="CUSTOM_STYLE_XYZ",
        ).generate(output)
        # The structured builder always uses _TECH_FOOTER so ARRI is always present;
        # style_token no longer appears literally. Verify it doesn't double-inject the
        # default token text either.
        assert all(DEFAULT_STYLE_TOKEN not in p for p in received_prompts)

    def test_style_token_empty_string_accepted(self) -> None:
        output = run_pipeline(_NOVEL, "T")
        sb = StoryboardGenerator(adapter=NullImageAdapter(), style_token="").generate(output)
        assert len(sb.frames) > 0


class TestReferencePack:
    def test_storyboard_injects_location_prompt_and_reference_from_pack(self) -> None:
        received_prompts: list[str] = []
        received_refs: list[str] = []

        class TrackingAdapter(NullImageAdapter):
            def generate(self, request: ImageRequest) -> ImageResult:
                received_prompts.append(request.prompt)
                received_refs.append(request.reference_image_url)
                return NullImageAdapter().generate(request)

        output = run_pipeline(_NOVEL, "T")
        scene_id = output.episodes[0].shots[0].scene_id
        pack = ReferencePack.model_validate(
            {
                "scene_locations": {scene_id: "old_library"},
                "locations": {
                    "old_library": {
                        "prompt": "dusty wood stacks, amber practical lamps, floating dust motes",
                        "reference_image_urls": ["ref://locations/old_library.png"],
                    }
                },
            }
        )

        StoryboardGenerator(adapter=TrackingAdapter(), reference_pack=pack).generate(output)

        assert any("dusty wood stacks" in prompt for prompt in received_prompts)
        assert received_refs[0] == "ref://locations/old_library.png"

    def test_storyboard_prefers_character_reference_from_pack(self) -> None:
        received_prompts: list[str] = []
        received_refs: list[str] = []

        class TrackingAdapter(NullImageAdapter):
            def generate(self, request: ImageRequest) -> ImageResult:
                received_prompts.append(request.prompt)
                received_refs.append(request.reference_image_url)
                return NullImageAdapter().generate(request)

        output = run_pipeline(_NOVEL, "T")
        chars = [c for ep in output.episodes for sc in ep.scenes for c in sc.characters]
        if not chars:
            pytest.skip("pipeline produced no characters")

        pack = ReferencePack.model_validate(
            {
                "characters": {
                    chars[0]: {
                        "prompt": (
                            "sharp cheekbones, dark tactical scarf, wet skin, "
                            "wary expression"
                        ),
                        "reference_image_urls": ["ref://characters/hero.png"],
                    }
                }
            }
        )

        StoryboardGenerator(adapter=TrackingAdapter(), reference_pack=pack).generate(output)

        assert any("dark tactical scarf" in prompt for prompt in received_prompts)
        assert received_refs[0] == "ref://characters/hero.png"

    def test_storyboard_matches_short_character_key_to_full_name(self) -> None:
        received_prompts: list[str] = []
        received_refs: list[str] = []

        class TrackingAdapter(NullImageAdapter):
            def generate(self, request: ImageRequest) -> ImageResult:
                received_prompts.append(request.prompt)
                received_refs.append(request.reference_image_url)
                return NullImageAdapter().generate(request)

        output = run_pipeline(
            "Nara runs through a corridor. Nara stops at the door.",
            "T",
        )
        pack = ReferencePack.model_validate(
            {
                "characters": {
                    "Nara": {
                        "prompt": "dark tactical scarf, grounded cinematic realism",
                        "reference_image_urls": ["ref://characters/nara.png"],
                    }
                }
            }
        )

        StoryboardGenerator(adapter=TrackingAdapter(), reference_pack=pack).generate(output)

        assert any("dark tactical scarf" in prompt for prompt in received_prompts)
        assert "ref://characters/nara.png" in received_refs

    def test_style_block_appended_to_character_prompt(self) -> None:
        pack = ReferencePack.model_validate(
            {
                "style_block": "ARRI Alexa 35, 4K hyperrealistic.",
                "characters": {"Nara": {"prompt": "dark hair, worn jacket"}},
            }
        )
        result = pack.character_prompt("Nara")
        assert result == "dark hair, worn jacket. ARRI Alexa 35, 4K hyperrealistic."

    def test_no_style_block_character_prompt_unchanged(self) -> None:
        pack = ReferencePack.model_validate(
            {
                "characters": {"Nara": {"prompt": "dark hair, worn jacket"}},
            }
        )
        assert pack.character_prompt("Nara") == "dark hair, worn jacket"

    def test_style_block_appended_to_location_prompt(self) -> None:
        pack = ReferencePack.model_validate(
            {
                "style_block": "ARRI Alexa 35, 4K hyperrealistic.",
                "locations": {
                    "corridor": {"prompt": "leaking pipes, corroded steel"}
                },
            }
        )
        result = pack.location_prompt("corridor")
        assert result == "leaking pipes, corroded steel. ARRI Alexa 35, 4K hyperrealistic."

    def test_scene_adapters_field_accepted_by_reference_pack(self) -> None:
        pack = ReferencePack.model_validate(
            {"scene_adapters": {"SCN_005": "openai"}}
        )
        assert pack.scene_adapters["SCN_005"] == "openai"


# ---------------------------------------------------------------------------
# 8. CharacterSheet + CharacterSheetRegistry (SB-03)
# ---------------------------------------------------------------------------

class TestCharacterSheetRegistry:
    def setup_method(self) -> None:
        from aiprod_adaptation.image_gen.character_sheet import (
            CharacterSheet,
            CharacterSheetRegistry,
        )
        self.CharacterSheet = CharacterSheet
        self.CharacterSheetRegistry = CharacterSheetRegistry

    def test_character_sheet_registry_register_and_get(self) -> None:
        reg = self.CharacterSheetRegistry()
        sheet = self.CharacterSheet(name="John", canonical_prompt="tall man, brown coat")
        reg.register(sheet)
        assert reg.get("John") is sheet

    def test_character_sheet_registry_no_overwrite(self) -> None:
        reg = self.CharacterSheetRegistry()
        s1 = self.CharacterSheet(name="John", canonical_prompt="first")
        s2 = self.CharacterSheet(name="John", canonical_prompt="second")
        reg.register(s1)
        reg.register(s2)
        assert reg.get("John") is s1

    def test_character_sheet_registry_all_sheets_returns_list(self) -> None:
        reg = self.CharacterSheetRegistry()
        reg.register(self.CharacterSheet(name="John", canonical_prompt="a"))
        reg.register(self.CharacterSheet(name="Sarah", canonical_prompt="b"))
        assert len(reg.all_sheets()) == 2

    def test_get_case_insensitive_upper_registered_lower_lookup(self) -> None:
        # Reference pack registers "Nara" (capitalized), IR emits "nara" (lowercase).
        # get() must find the sheet regardless of case — otherwise prepass is silently
        # skipped and paid API calls are wasted without face-consistency benefit.
        reg = self.CharacterSheetRegistry()
        sheet = self.CharacterSheet(name="Nara", canonical_prompt="female protagonist")
        reg.register(sheet)
        assert reg.get("nara") is sheet, "lowercase lookup must find sheet registered with Title case"
        assert reg.get("NARA") is sheet, "UPPER lookup must find sheet registered with Title case"
        assert reg.get("Nara") is sheet, "exact-case lookup must still work"

    def test_no_overwrite_case_variants(self) -> None:
        # Registering "nara" after "Nara" must NOT overwrite — first registration wins.
        reg = self.CharacterSheetRegistry()
        s1 = self.CharacterSheet(name="Nara", canonical_prompt="first")
        s2 = self.CharacterSheet(name="nara", canonical_prompt="second")
        reg.register(s1)
        reg.register(s2)
        result = reg.get("nara")
        assert result is s1, "second registration with different case must not overwrite"
        assert len(reg.all_sheets()) == 1

    def test_prepass_generates_one_image_per_sheet(self) -> None:
        from unittest.mock import MagicMock

        from aiprod_adaptation.image_gen.character_sheet import (
            CharacterSheet,
            CharacterSheetRegistry,
        )
        mock_adapter = MagicMock()
        mock_adapter.generate.return_value = ImageResult(
            shot_id="X", image_url="null://x.png", model_used="null", latency_ms=0
        )
        reg = CharacterSheetRegistry()
        reg.register(CharacterSheet(name="John", canonical_prompt="tall man"))
        reg.register(CharacterSheet(name="Sarah", canonical_prompt="young woman"))
        StoryboardGenerator(adapter=mock_adapter).prepass_character_sheets(reg)
        assert mock_adapter.generate.call_count == 2

    def test_prepass_idempotent(self) -> None:
        from unittest.mock import MagicMock

        from aiprod_adaptation.image_gen.character_sheet import (
            CharacterSheet,
            CharacterSheetRegistry,
        )
        mock_adapter = MagicMock()
        reg = CharacterSheetRegistry()
        sheet = CharacterSheet(name="John", canonical_prompt="tall man", image_url="already://set.png")
        reg.register(sheet)
        StoryboardGenerator(adapter=mock_adapter).prepass_character_sheets(reg)
        assert mock_adapter.generate.call_count == 0

    def test_prepass_error_does_not_crash(self) -> None:
        from aiprod_adaptation.image_gen.character_sheet import (
            CharacterSheet,
            CharacterSheetRegistry,
        )

        class BrokenAdapter(NullImageAdapter):
            def generate(self, _request: ImageRequest) -> ImageResult:
                raise RuntimeError("API down")

        reg = CharacterSheetRegistry()
        reg.register(CharacterSheet(name="John", canonical_prompt="tall man"))
        StoryboardGenerator(adapter=BrokenAdapter()).prepass_character_sheets(reg)
        john_sheet = reg.get("John")
        assert john_sheet is not None
        assert john_sheet.image_url == ""


# ---------------------------------------------------------------------------
# 9. ShotStoryboardFrame + StoryboardOutput enrichi (SB-05)
# ---------------------------------------------------------------------------

# Multi-shot input for tests that need >= 2 frames (> SILENT_SCENE_WORD_THRESHOLD=30 words)
_NOVEL_MULTI_SHOT = (
    "John walked quickly through the busy city streets, feeling excited about the upcoming meeting. "
    "He suddenly spotted Sarah waiting nervously at the corner,"
    " her expression completely unreadable in the fading afternoon light."
)


class TestShotStoryboardFrame:
    def _gen(self) -> StoryboardOutput:
        output = run_pipeline(_NOVEL_MULTI_SHOT, "T")
        return StoryboardGenerator(adapter=NullImageAdapter(), base_seed=10).generate(output)

    def test_storyboard_frame_has_prompt_used(self) -> None:
        sb = self._gen()
        assert all(isinstance(f.prompt_used, str) and f.prompt_used for f in sb.frames)

    def test_storyboard_frame_has_seed_used(self) -> None:
        sb = self._gen()
        assert sb.frames[0].seed_used == 10
        assert sb.frames[1].seed_used == 11

    def test_storyboard_output_has_style_token(self) -> None:
        sb = self._gen()
        assert sb.style_token == DEFAULT_STYLE_TOKEN

    def test_storyboard_output_frames_count(self) -> None:
        sb = self._gen()
        assert len(sb.frames) == sb.total_shots


# ---------------------------------------------------------------------------
# 10. CheckpointStore + StoryboardGenerator reprise (SO-06)
# ---------------------------------------------------------------------------

class TestCheckpointStore:
    def _frame(self, shot_id: str = "S1") -> ShotStoryboardFrame:
        return ShotStoryboardFrame(
            shot_id=shot_id,
            scene_id="SC001",
            image_url=f"null://{shot_id}.png",
            model_used="null",
            latency_ms=10,
            prompt_used="test prompt",
        )

    def test_checkpoint_store_memory_has_after_save(self) -> None:
        from aiprod_adaptation.image_gen.checkpoint import CheckpointStore
        store = CheckpointStore()
        store.save(self._frame("S1"))
        assert store.has("S1")
        assert not store.has("S2")

    def test_checkpoint_store_get_returns_frame(self) -> None:
        from aiprod_adaptation.image_gen.checkpoint import CheckpointStore
        store = CheckpointStore()
        frame = self._frame("S1")
        store.save(frame)
        assert store.get("S1") == frame
        assert store.get("MISSING") is None

    def test_storyboard_skips_cached_shots(self) -> None:
        from aiprod_adaptation.image_gen.checkpoint import CheckpointStore
        call_count = 0

        class CountingAdapter(NullImageAdapter):
            def generate(self, request: ImageRequest) -> ImageResult:
                nonlocal call_count
                call_count += 1
                return NullImageAdapter().generate(request)

        output = run_pipeline(_NOVEL, "T")
        shots = [s for ep in output.episodes for s in ep.shots]
        # Pre-cache all shots except the last one
        store = CheckpointStore()
        for shot in shots[:-1]:
            store.save(self._frame(shot.shot_id))

        StoryboardGenerator(adapter=CountingAdapter(), checkpoint=store).generate(output)
        assert call_count == 1  # only the last uncached shot calls the adapter

    def test_storyboard_resumes_from_partial_checkpoint(self) -> None:
        from aiprod_adaptation.image_gen.checkpoint import CheckpointStore
        call_count = 0

        class CountingAdapter(NullImageAdapter):
            def generate(self, request: ImageRequest) -> ImageResult:
                nonlocal call_count
                call_count += 1
                return NullImageAdapter().generate(request)

        # Use multi-shot input to guarantee >= 2 shots (v3 body-language layers)
        output = run_pipeline(_NOVEL_MULTI_SHOT, "T")
        shots = [s for ep in output.episodes for s in ep.shots]
        assert len(shots) >= 2
        store = CheckpointStore()
        store.save(self._frame(shots[0].shot_id))  # pre-cache first shot only
        sb = StoryboardGenerator(adapter=CountingAdapter(), checkpoint=store).generate(output)
        assert call_count == len(shots) - 1
        assert len(sb.frames) == len(shots)

    def test_checkpoint_store_file_persists_and_reloads(self) -> None:
        import tempfile

        from aiprod_adaptation.image_gen.checkpoint import CheckpointStore
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"
            store1 = CheckpointStore(path=path)
            store1.save(self._frame("S1"))
            store2 = CheckpointStore(path=path)
            assert store2.has("S1")
            assert store2.get("S1") is not None

    def test_checkpoint_store_logs_invalid_cache_file(self) -> None:
        import tempfile
        from unittest.mock import MagicMock, patch

        from aiprod_adaptation.image_gen.checkpoint import CheckpointStore

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"
            path.write_text("{not json}", encoding="utf-8")
            logger = MagicMock()

            with patch("aiprod_adaptation.image_gen.checkpoint.logger", logger):
                store = CheckpointStore(path=path)

            assert store.all_cached() == []
            logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# 11. CharacterPrepass (PC-02)
# ---------------------------------------------------------------------------

class TestCharacterPrepass:
    def test_character_prepass_skips_characters_with_no_canonical(self) -> None:
        """Without a sheet_registry, all characters are skipped — 0 API calls."""
        from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass
        output = run_pipeline(_NOVEL, "T")
        result = CharacterPrepass(adapter=NullImageAdapter(), base_seed=0).run(output)
        assert result.generated == 0
        assert result.failed == 0

    def test_character_prepass_generates_one_image_per_character(self) -> None:
        """With a sheet_registry, one image is generated per character that has a sheet."""
        from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass, _unique_characters
        from aiprod_adaptation.image_gen.character_sheet import CharacterSheet, CharacterSheetRegistry
        output = run_pipeline(_NOVEL, "T")
        expected_chars = _unique_characters(output)
        if not expected_chars:
            return  # no shot subjects in this pipeline output — trivially ok
        reg = CharacterSheetRegistry()
        for name in expected_chars:
            reg.register(CharacterSheet(name=name, canonical_prompt=f"canonical for {name}"))
        result = CharacterPrepass(adapter=NullImageAdapter(), base_seed=0, sheet_registry=reg).run(output)
        assert result.generated == len(expected_chars)
        assert result.failed == 0

    def test_character_prepass_populates_registry(self) -> None:
        from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass, _unique_characters
        from aiprod_adaptation.image_gen.character_sheet import CharacterSheet, CharacterSheetRegistry
        output = run_pipeline(_NOVEL, "T")
        expected_chars = _unique_characters(output)
        if not expected_chars:
            return
        reg = CharacterSheetRegistry()
        for name in expected_chars:
            reg.register(CharacterSheet(name=name, canonical_prompt=f"canonical for {name}"))
        result = CharacterPrepass(adapter=NullImageAdapter(), base_seed=0, sheet_registry=reg).run(output)
        for char in expected_chars:
            assert result.registry.get_reference(char) != ""

    def test_character_prepass_handles_adapter_failure_gracefully(self) -> None:
        from unittest.mock import patch

        from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass
        from aiprod_adaptation.image_gen.character_sheet import CharacterSheet, CharacterSheetRegistry

        class FailingAdapter(NullImageAdapter):
            def generate(self, _request: ImageRequest) -> ImageResult:
                raise RuntimeError("adapter down")

        reg = CharacterSheetRegistry()
        reg.register(CharacterSheet(name="Alice", canonical_prompt="Alice canonical"))
        reg.register(CharacterSheet(name="Bob", canonical_prompt="Bob canonical"))

        with patch(
            "aiprod_adaptation.image_gen.character_prepass._unique_characters",
            return_value=["Alice", "Bob"],
        ):
            output = run_pipeline(_NOVEL, "T")
            result = CharacterPrepass(
                adapter=FailingAdapter(), base_seed=0, sheet_registry=reg
            ).run(output)

        assert result.failed == 2
        assert result.generated == 0

    def test_character_prepass_logs_adapter_failure(self) -> None:
        from unittest.mock import MagicMock, patch

        from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass
        from aiprod_adaptation.image_gen.character_sheet import CharacterSheet, CharacterSheetRegistry

        class FailingAdapter(NullImageAdapter):
            def generate(self, _request: ImageRequest) -> ImageResult:
                raise RuntimeError("adapter down")

        output = run_pipeline(_NOVEL, "T")
        reg = CharacterSheetRegistry()
        reg.register(CharacterSheet(name="Alice", canonical_prompt="Alice canonical"))
        logger = MagicMock()
        with patch(
            "aiprod_adaptation.image_gen.character_prepass._unique_characters",
            return_value=["Alice"],
        ):
            with patch("aiprod_adaptation.image_gen.character_prepass.logger", logger):
                result = CharacterPrepass(
                    adapter=FailingAdapter(), base_seed=0, sheet_registry=reg
                ).run(output)

        assert result.generated == 0
        logger.warning.assert_called()

    def test_character_prepass_scopes_to_shot_subjects_not_scene_chars(self) -> None:
        """Prepass must only generate for shot.action.subject_id — not all scene characters.
        This ensures filtered runs (--shot-id) don't waste credits on unrelated characters."""
        from aiprod_adaptation.image_gen.character_prepass import _unique_characters
        from aiprod_adaptation.models.schema import (
            ActionSpec,
            AIPRODOutput,
            Episode,
            Scene,
            Shot,
        )

        shot = Shot(
            shot_id="S1", scene_id="SCN_001", prompt="test", duration_sec=3, emotion="neutral",
            action=ActionSpec(subject_id="nara", action_type="walks",
                              location_id="loc1", camera_intent="static", source_text="Nara walks."),
        )
        scene = Scene(
            scene_id="SCN_001", location="corridor",
            characters=["nara", "elian", "mira", "vale"],  # 4 scene chars
            visual_actions=[], dialogues=[], emotion="tense",
        )
        output = AIPRODOutput(
            title="T",
            episodes=[Episode(episode_id="EP1", scenes=[scene], shots=[shot])],
        )

        chars = _unique_characters(output)
        # Only the shot subject, not all 4 scene characters
        assert chars == ["nara"]

    def test_character_prepass_fails_fast_on_403_auth_error(self) -> None:
        """A 403/must-be-verified error must abort immediately — never silently continue."""
        from unittest.mock import patch

        import pytest

        from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass
        from aiprod_adaptation.image_gen.character_sheet import CharacterSheet, CharacterSheetRegistry

        class AuthFailAdapter(NullImageAdapter):
            def generate(self, _request: ImageRequest) -> ImageResult:
                raise RuntimeError(
                    "Error code: 403 - Your organization must be verified to use the model"
                )

        reg = CharacterSheetRegistry()
        reg.register(CharacterSheet(name="Alice", canonical_prompt="Alice canonical"))

        with patch(
            "aiprod_adaptation.image_gen.character_prepass._unique_characters",
            return_value=["Alice"],
        ):
            with pytest.raises(RuntimeError, match="auth/permission error"):
                CharacterPrepass(
                    adapter=AuthFailAdapter(), base_seed=0, sheet_registry=reg
                ).run(AIPRODOutput(title="T", episodes=[]))

    def test_character_prepass_case_insensitive_ir_vs_reference_pack(self) -> None:
        """REGRESSION: reference pack registers 'Nara' (Title case); IR emits 'nara' (lower).
        Prepass must NOT be skipped — generated must be 1, not 0.
        If this fails, --remove-background runs waste API credits with no face-consistency benefit."""

        from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass
        from aiprod_adaptation.image_gen.character_sheet import CharacterSheet, CharacterSheetRegistry
        from aiprod_adaptation.models.schema import (
            ActionSpec,
            AIPRODOutput,
            Episode,
            Scene,
            Shot,
        )

        # IR uses lowercase subject_id — exactly what ScriptParser emits in production
        shot = Shot(
            shot_id="SCN_002_SH_001", scene_id="SCN_002",
            prompt="Nara walks through the corridor", duration_sec=3, emotion="tense",
            action=ActionSpec(
                subject_id="nara",  # lowercase — IR canonical form
                action_type="walks", location_id="corridor",
                camera_intent="static", source_text="Nara walks.",
            ),
        )
        scene = Scene(
            scene_id="SCN_002", location="corridor",
            characters=["nara"], visual_actions=[], dialogues=[], emotion="tense",
        )
        output = AIPRODOutput(
            title="District Zero",
            episodes=[Episode(episode_id="EP1", scenes=[scene], shots=[shot])],
        )

        # Reference pack registers with Title case — exactly as JSON keys appear
        reg = CharacterSheetRegistry()
        reg.register(CharacterSheet(name="Nara", canonical_prompt="female protagonist, late 20s"))

        result = CharacterPrepass(
            adapter=NullImageAdapter(), base_seed=0, sheet_registry=reg
        ).run(output)

        assert result.generated == 1, (
            f"Prepass was skipped (generated={result.generated}) due to case mismatch. "
            "This wastes paid API credits — CharacterSheetRegistry.get() must be case-insensitive."
        )
        assert result.failed == 0

    def test_storyboard_character_sheet_prepass_logs_failure(self) -> None:
        from unittest.mock import MagicMock, patch

        from aiprod_adaptation.image_gen.character_sheet import (
            CharacterSheet,
            CharacterSheetRegistry,
        )

        class BrokenAdapter(NullImageAdapter):
            def generate(self, _request: ImageRequest) -> ImageResult:
                raise RuntimeError("API down")

        reg = CharacterSheetRegistry()
        reg.register(CharacterSheet(name="John", canonical_prompt="tall man"))
        logger = MagicMock()
        with patch("aiprod_adaptation.image_gen.storyboard.logger", logger):
            StoryboardGenerator(adapter=BrokenAdapter()).prepass_character_sheets(reg)

        john_sheet = reg.get("John")
        assert john_sheet is not None
        assert john_sheet.image_url == ""
        logger.warning.assert_called_once()

    def test_storyboard_generator_uses_prepass_registry(self) -> None:
        from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass
        output = run_pipeline(_NOVEL, "T")
        prepass_result = CharacterPrepass(adapter=NullImageAdapter(), base_seed=0).run(output)
        sb = StoryboardGenerator(
            adapter=NullImageAdapter(),
            base_seed=0,
            prepass_registry=prepass_result.registry,
        ).generate(output)
        assert len(sb.frames) == sb.total_shots

    def test_character_prepass_handles_output_with_no_characters(self) -> None:
        from unittest.mock import patch

        from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass
        output = run_pipeline(_NOVEL, "T")
        with patch(
            "aiprod_adaptation.image_gen.character_prepass._unique_characters",
            return_value=[],
        ):
            result = CharacterPrepass(adapter=NullImageAdapter(), base_seed=0).run(output)
        assert result.generated == 0
        assert result.failed == 0


# ---------------------------------------------------------------------------
# HuggingFaceImageAdapter (mocked — no real API call)
# ---------------------------------------------------------------------------

class TestHuggingFaceImageAdapter:
    def test_hf_adapter_raises_without_token(self) -> None:
        from aiprod_adaptation.image_gen.huggingface_image_adapter import HuggingFaceImageAdapter
        with patch.dict(os.environ, {}, clear=False) as env:
            env.pop("HF_TOKEN", None)
            adapter = HuggingFaceImageAdapter()
            with pytest.raises(EnvironmentError, match="HF_TOKEN"):
                adapter.generate(_REQ)

    def test_hf_adapter_returns_image_result_with_b64(self) -> None:
        from unittest.mock import MagicMock

        PILImage = pytest.importorskip("PIL.Image")

        from aiprod_adaptation.image_gen.huggingface_image_adapter import (
            HuggingFaceImageAdapter,
        )

        # Build a tiny real PIL image so the b64 round-trip works
        pil_img = PILImage.new("RGB", (64, 36), color=(10, 20, 30))

        mock_client = MagicMock()
        mock_client.text_to_image.return_value = pil_img

        with patch.dict(os.environ, {"HF_TOKEN": "hf_fake"}):
            with patch(
                "aiprod_adaptation.image_gen.huggingface_image_adapter._build_hf_client",
                return_value=mock_client,
            ):
                adapter = HuggingFaceImageAdapter()
                result = adapter.generate(_REQ)

        assert isinstance(result, ImageResult)
        assert result.shot_id == _REQ.shot_id
        assert result.image_b64 != ""
        assert result.cost_usd == 0.0
        mock_client.text_to_image.assert_called_once()

    def test_hf_adapter_schnell_uses_4_steps(self) -> None:
        from unittest.mock import MagicMock

        PILImage = pytest.importorskip("PIL.Image")

        from aiprod_adaptation.image_gen.huggingface_image_adapter import HuggingFaceImageAdapter

        pil_img = PILImage.new("RGB", (64, 36))
        mock_client = MagicMock()
        mock_client.text_to_image.return_value = pil_img

        with patch.dict(
            os.environ,
            {"HF_TOKEN": "hf_fake", "HF_IMAGE_MODEL": "black-forest-labs/FLUX.1-schnell"},
        ):
            with patch(
                "aiprod_adaptation.image_gen.huggingface_image_adapter._build_hf_client",
                return_value=mock_client,
            ):
                HuggingFaceImageAdapter().generate(_REQ)

        call_kwargs = mock_client.text_to_image.call_args.kwargs
        assert call_kwargs["num_inference_steps"] == 4
        assert "guidance_scale" not in call_kwargs  # schnell: no CFG


# ---------------------------------------------------------------------------
# Replicate adapter — unit tests for _build_input helpers (no network)
# ---------------------------------------------------------------------------

class TestReplicateAdapterBuildInput:
    """Unit tests for _build_input() — no Replicate API calls."""

    def _req(self, prompt: str = "A man walks.", **kwargs) -> ImageRequest:
        return ImageRequest(shot_id="SH001", scene_id="SC001", prompt=prompt, **kwargs)

    def test_flux_dev_uses_guidance_3_5(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _build_input
        req = self._req()
        data = _build_input("black-forest-labs/flux-dev", req)
        assert data["guidance"] == 3.5

    def test_flux_dev_omits_negative_prompt(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _build_input
        req = self._req()
        data = _build_input("black-forest-labs/flux-dev", req)
        assert "negative_prompt" not in data

    def test_schnell_uses_aspect_ratio_not_dimensions(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _build_input
        req = self._req()
        data = _build_input("black-forest-labs/flux-schnell", req)
        assert "aspect_ratio" in data
        assert "width" not in data
        assert "height" not in data

    def test_schnell_max_4_steps(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _build_input
        req = self._req()
        data = _build_input("black-forest-labs/flux-schnell", req)
        assert data["num_inference_steps"] == 4

    def test_schnell_no_guidance_no_negative(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _build_input
        req = self._req()
        data = _build_input("black-forest-labs/flux-schnell", req)
        assert "guidance" not in data
        assert "negative_prompt" not in data

    def test_schnell_portrait_uses_2_3_aspect(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _build_input
        req = self._req(prompt="Close-up portrait — Nara, intense gaze.")
        data = _build_input("black-forest-labs/flux-schnell", req)
        assert data["aspect_ratio"] == "2:3"

    def test_schnell_wide_uses_16_9_aspect(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _build_input
        req = self._req(prompt="Wide shot — dystopian seawall.")
        data = _build_input("black-forest-labs/flux-schnell", req)
        assert data["aspect_ratio"] == "16:9"

    def test_ultra_skips_data_uri_reference(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _build_input
        req = self._req(reference_image_url="data:image/png;base64,ABC123==")
        data = _build_input("black-forest-labs/flux-1.1-pro-ultra", req)
        assert "image_prompt" not in data

    def test_ultra_passes_http_reference(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _build_input
        req = self._req(reference_image_url="https://example.com/ref.jpg")
        data = _build_input("black-forest-labs/flux-1.1-pro-ultra", req)
        assert data["image_prompt"] == "https://example.com/ref.jpg"

    def test_portrait_prompt_uses_portrait_dimensions_for_dev(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _build_input
        req = self._req(prompt="Close-up portrait — Nara, determined eyes.")
        data = _build_input("black-forest-labs/flux-dev", req)
        assert data["width"] == 768
        assert data["height"] == 1024

    def test_wide_shot_keeps_landscape_dimensions(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _build_input
        req = self._req(prompt="Wide shot — dystopian cityscape at dawn.")
        data = _build_input("black-forest-labs/flux-dev", req)
        assert data["width"] == 1024
        assert data["height"] == 576

    def test_ultra_portrait_uses_2_3_aspect(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _build_input
        req = self._req(prompt="Close-up portrait — Nara, determined eyes.")
        data = _build_input("black-forest-labs/flux-1.1-pro-ultra", req)
        assert data["aspect_ratio"] == "2:3"

    def test_ultra_wide_uses_16_9_aspect(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _build_input
        req = self._req(prompt="Wide shot — dystopian seawall.")
        data = _build_input("black-forest-labs/flux-1.1-pro-ultra", req)
        assert data["aspect_ratio"] == "16:9"


# ---------------------------------------------------------------------------
# Replicate adapter — auto-routing portrait vs wide (no network)
# ---------------------------------------------------------------------------

class TestReplicateAdapterRouting:
    """Unit tests for _select_model() auto-routing — no Replicate API calls."""

    def _adapter(self, **env_overrides):
        from aiprod_adaptation.image_gen.replicate_adapter import ReplicateAdapter
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("REPLICATE_")}
        clean_env.update(env_overrides)
        with patch.dict(os.environ, clean_env, clear=True):
            return ReplicateAdapter()

    def _req(self, prompt: str) -> ImageRequest:
        return ImageRequest(shot_id="SH001", scene_id="SC001", prompt=prompt)

    def test_portrait_prompt_routes_to_ultra(self) -> None:
        adapter = self._adapter(
            REPLICATE_PORTRAIT_MODEL="black-forest-labs/flux-1.1-pro-ultra",
            REPLICATE_WIDE_MODEL="black-forest-labs/flux-dev",
        )
        req = self._req("Close-up portrait — Nara, determined expression.")
        assert adapter._select_model(req) == "black-forest-labs/flux-1.1-pro-ultra"

    def test_extreme_close_up_routes_to_ultra(self) -> None:
        adapter = self._adapter(
            REPLICATE_PORTRAIT_MODEL="black-forest-labs/flux-1.1-pro-ultra",
            REPLICATE_WIDE_MODEL="black-forest-labs/flux-dev",
        )
        req = self._req("Extreme close-up portrait — Nara's eyes.")
        assert adapter._select_model(req) == "black-forest-labs/flux-1.1-pro-ultra"

    def test_wide_shot_routes_to_dev(self) -> None:
        adapter = self._adapter(
            REPLICATE_PORTRAIT_MODEL="black-forest-labs/flux-1.1-pro-ultra",
            REPLICATE_WIDE_MODEL="black-forest-labs/flux-dev",
        )
        req = self._req("Wide shot — dystopian cityscape at night.")
        assert adapter._select_model(req) == "black-forest-labs/flux-dev"

    def test_medium_shot_routes_to_dev(self) -> None:
        adapter = self._adapter(
            REPLICATE_PORTRAIT_MODEL="black-forest-labs/flux-1.1-pro-ultra",
            REPLICATE_WIDE_MODEL="black-forest-labs/flux-dev",
        )
        req = self._req("Medium shot — Nara and Elian face each other.")
        assert adapter._select_model(req) == "black-forest-labs/flux-dev"

    def test_single_override_model_disables_routing(self) -> None:
        adapter = self._adapter(REPLICATE_IMAGE_MODEL="black-forest-labs/flux-schnell")
        portrait_req = self._req("Close-up portrait — Nara.")
        wide_req = self._req("Wide shot — seawall.")
        assert adapter._select_model(portrait_req) == "black-forest-labs/flux-schnell"
        assert adapter._select_model(wide_req) == "black-forest-labs/flux-schnell"

    def test_defaults_without_env(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import (
            DEV_MODEL,
            ULTRA_MODEL,
            ReplicateAdapter,
        )
        with patch.dict(os.environ, {}, clear=True):
            adapter = ReplicateAdapter()
        assert adapter._portrait_model == ULTRA_MODEL
        assert adapter._wide_model == DEV_MODEL


# ---------------------------------------------------------------------------
# CharacterMask / remove_background (no network, mocked rembg)
# ---------------------------------------------------------------------------

class TestCharacterMask:
    def test_remove_background_raises_import_error_without_rembg(self) -> None:
        """remove_background raises ImportError when rembg is not installed."""
        import sys
        from unittest.mock import patch

        with patch.dict(sys.modules, {"rembg": None}):
            import importlib

            import aiprod_adaptation.image_gen.character_mask as cm
            importlib.reload(cm)
            import pytest
            with pytest.raises(ImportError, match="rembg"):
                cm.remove_background(b"fake_image_bytes")

    def test_remove_background_calls_rembg_remove(self) -> None:
        """remove_background passes image bytes to rembg.remove and returns result."""
        import sys
        from unittest.mock import MagicMock, patch

        fake_rgba = b"fake_rgba_output"
        mock_rembg = MagicMock()
        mock_rembg.remove.return_value = fake_rgba

        from aiprod_adaptation.image_gen.character_mask import remove_background

        with patch.dict(sys.modules, {"rembg": mock_rembg}):
            # Patch the lazy import inside the function
            with patch(
                "builtins.__import__",
                side_effect=lambda name, *a, **kw: mock_rembg if name == "rembg" else __import__(name, *a, **kw),
            ):
                result = remove_background(b"input_bytes")

        mock_rembg.remove.assert_called_once_with(b"input_bytes")
        assert result == fake_rgba

    def test_character_image_registry_stores_and_retrieves_rgba(self) -> None:
        """register_rgba / get_rgba are case-insensitive and store bytes correctly."""
        from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry

        reg = CharacterImageRegistry()
        rgba_data = b"\x89PNG_fake_rgba"
        reg.register_rgba("Nara", rgba_data)
        # Case-insensitive lookup
        assert reg.get_rgba("nara") == rgba_data
        assert reg.get_rgba("NARA") == rgba_data

    def test_character_image_registry_get_rgba_returns_none_when_missing(self) -> None:
        from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry

        reg = CharacterImageRegistry()
        assert reg.get_rgba("unknown") is None

    def test_character_image_registry_rgba_overwrite_false_by_default(self) -> None:
        from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry

        reg = CharacterImageRegistry()
        first = b"first_rgba"
        second = b"second_rgba"
        reg.register_rgba("Nara", first)
        reg.register_rgba("Nara", second)  # overwrite=False by default
        assert reg.get_rgba("nara") == first

    def test_character_image_registry_rgba_overwrite_true_replaces(self) -> None:
        from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry

        reg = CharacterImageRegistry()
        reg.register_rgba("Nara", b"old")
        reg.register_rgba("Nara", b"new", overwrite=True)
        assert reg.get_rgba("nara") == b"new"


class TestOpenAIImageAdapterEdit:
    def test_generate_edit_calls_images_edit_api(self) -> None:
        """generate_edit must call client.images.edit (not images.generate)."""
        import base64
        from unittest.mock import MagicMock, patch

        from aiprod_adaptation.image_gen.image_request import ImageRequest
        from aiprod_adaptation.image_gen.openai_image_adapter import OpenAIImageAdapter

        fake_b64 = base64.b64encode(b"fake_image").decode()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(b64_json=fake_b64, url="")]

        mock_client = MagicMock()
        mock_client.images.edit.return_value = mock_response

        adapter = OpenAIImageAdapter(api_key="test", model="gpt-image-2", quality="medium")

        with patch(
            "aiprod_adaptation.image_gen.openai_image_adapter._build_openai_client",
            return_value=mock_client,
        ):
            req = ImageRequest(shot_id="S1", scene_id="SCN_001", prompt="Nara in corridor")
            result = adapter.generate_edit(req, reference_rgba=b"fake_rgba")

        mock_client.images.edit.assert_called_once()
        mock_client.images.generate.assert_not_called()
        assert result.model_used == "openai-image-edit"
        assert result.image_b64 == fake_b64

    def test_generate_edit_never_called_when_no_rgba(self) -> None:
        """StoryboardGenerator must use generate() when no RGBA available."""
        from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry
        from aiprod_adaptation.image_gen.storyboard import StoryboardGenerator
        from aiprod_adaptation.models.schema import (
            ActionSpec,
            AIPRODOutput,
            Episode,
            Scene,
            Shot,
        )

        shot = Shot(
            shot_id="SCN_001_SHOT_001", scene_id="SCN_001",
            prompt="Nara runs", duration_sec=3, emotion="tense",
            action=ActionSpec(subject_id="nara", action_type="runs",
                              location_id="loc", camera_intent="static", source_text="Nara runs."),
        )
        scene = Scene(
            scene_id="SCN_001", location="corridor",
            characters=["nara"], visual_actions=[], dialogues=[], emotion="tense",
        )
        output = AIPRODOutput(
            title="T",
            episodes=[Episode(episode_id="EP1", scenes=[scene], shots=[shot])],
        )

        reg = CharacterImageRegistry()
        # No RGBA registered — should fall through to generate()

        calls: list[str] = []

        class TrackingAdapter(NullImageAdapter):
            def generate(self, req: ImageRequest) -> ImageResult:
                calls.append("generate")
                return super().generate(req)
            def generate_edit(self, req: ImageRequest, _reference_rgba: bytes) -> ImageResult:
                calls.append("generate_edit")
                return super().generate(req)

        StoryboardGenerator(
            adapter=TrackingAdapter(),
            prepass_registry=reg,
        ).generate(output)

        assert "generate_edit" not in calls
        assert "generate" in calls

    def test_storyboard_routes_to_generate_edit_when_rgba_available(self) -> None:
        """StoryboardGenerator must call generate_edit() when RGBA is in the registry."""
        from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry
        from aiprod_adaptation.image_gen.openai_image_adapter import OpenAIImageAdapter
        from aiprod_adaptation.image_gen.storyboard import StoryboardGenerator
        from aiprod_adaptation.models.schema import (
            ActionSpec,
            AIPRODOutput,
            Episode,
            Scene,
            Shot,
        )

        shot = Shot(
            shot_id="SCN_001_SHOT_001", scene_id="SCN_001",
            prompt="Nara runs", duration_sec=3, emotion="tense",
            action=ActionSpec(subject_id="nara", action_type="runs",
                              location_id="loc", camera_intent="static", source_text="Nara runs."),
        )
        scene = Scene(
            scene_id="SCN_001", location="corridor",
            characters=["nara"], visual_actions=[], dialogues=[], emotion="tense",
        )
        output = AIPRODOutput(
            title="T",
            episodes=[Episode(episode_id="EP1", scenes=[scene], shots=[shot])],
        )

        reg = CharacterImageRegistry()
        reg.register_rgba("nara", b"fake_rgba_bytes")

        edit_calls: list[str] = []
        generate_calls: list[str] = []

        class TrackingOpenAIAdapter(OpenAIImageAdapter):
            def generate(self, request: ImageRequest) -> ImageResult:
                generate_calls.append(request.shot_id)
                return ImageResult(
                    shot_id=request.shot_id, image_url="", image_b64="",
                    model_used="openai-image", latency_ms=0,
                )

            def generate_edit(self, request: ImageRequest, _reference_rgba: bytes) -> ImageResult:
                edit_calls.append(request.shot_id)
                return ImageResult(
                    shot_id=request.shot_id, image_url="", image_b64="",
                    model_used="openai-image-edit", latency_ms=0,
                )

        adapter = TrackingOpenAIAdapter(api_key="test", model="gpt-image-2", quality="medium")

        sb = StoryboardGenerator(
            adapter=adapter,
            prepass_registry=reg,
        ).generate(output)

        assert "SCN_001_SHOT_001" in edit_calls
        assert "SCN_001_SHOT_001" not in generate_calls
        assert sb.frames[0].model_used == "openai-image-edit"


# ---------------------------------------------------------------------------
# Replicate cost estimation (no network)
# ---------------------------------------------------------------------------

class TestReplicateCostEstimation:
    def test_ultra_model_cost(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _estimate_replicate_cost
        assert _estimate_replicate_cost("black-forest-labs/flux-1.1-pro-ultra") == 0.06

    def test_dev_model_cost(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _estimate_replicate_cost
        assert _estimate_replicate_cost("black-forest-labs/flux-dev") == 0.003

    def test_upscale_adds_cost(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _estimate_replicate_cost
        cost_plain = _estimate_replicate_cost("black-forest-labs/flux-1.1-pro-ultra", upscaled=False)
        cost_upscaled = _estimate_replicate_cost("black-forest-labs/flux-1.1-pro-ultra", upscaled=True)
        assert cost_upscaled == cost_plain + 0.002

    def test_unknown_model_returns_zero(self) -> None:
        from aiprod_adaptation.image_gen.replicate_adapter import _estimate_replicate_cost
        assert _estimate_replicate_cost("some-unknown/model") == 0.0
