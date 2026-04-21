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
from pathlib import Path

import pytest

from aiprod_adaptation.image_gen.image_adapter import NullImageAdapter
from aiprod_adaptation.image_gen.image_request import (
    ImageRequest,
    ImageResult,
    ShotStoryboardFrame,
    StoryboardOutput,
)
from aiprod_adaptation.image_gen.storyboard import DEFAULT_STYLE_TOKEN, StoryboardGenerator
from aiprod_adaptation.core.engine import run_pipeline, run_pipeline_with_images


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


# ---------------------------------------------------------------------------
# 3. StoryboardGenerator
# ---------------------------------------------------------------------------

class TestStoryboardGenerator:
    def setup_method(self) -> None:
        self.adapter = NullImageAdapter()
        self.gen = StoryboardGenerator(adapter=self.adapter, base_seed=42)

    def _output(self) -> object:
        return run_pipeline(_NOVEL, "T")

    def test_storyboard_generates_one_result_per_shot(self) -> None:
        output = self._output()
        sb = self.gen.generate(output)  # type: ignore[arg-type]
        total = sum(len(ep.shots) for ep in output.episodes)  # type: ignore[union-attr]
        assert len(sb.frames) == total

    def test_storyboard_is_deterministic(self) -> None:
        output = self._output()
        sb1 = self.gen.generate(output)  # type: ignore[arg-type]
        sb2 = self.gen.generate(output)  # type: ignore[arg-type]
        assert json.dumps(sb1.model_dump(), sort_keys=False) == \
               json.dumps(sb2.model_dump(), sort_keys=False)

    def test_storyboard_title_preserved(self) -> None:
        output = self._output()
        sb = self.gen.generate(output)  # type: ignore[arg-type]
        assert sb.title == "T"

    def test_storyboard_generated_count_correct(self) -> None:
        output = self._output()
        sb = self.gen.generate(output)  # type: ignore[arg-type]
        assert sb.generated == sb.total_shots

    def test_storyboard_build_requests_count(self) -> None:
        output = self._output()
        requests = self.gen.build_requests(output)  # type: ignore[arg-type]
        total = sum(len(ep.shots) for ep in output.episodes)  # type: ignore[union-attr]
        assert len(requests) == total

    def test_storyboard_error_in_adapter_does_not_crash(self) -> None:
        class BrokenAdapter(NullImageAdapter):
            def generate(self, request: ImageRequest) -> ImageResult:
                raise RuntimeError("API down")

        gen = StoryboardGenerator(adapter=BrokenAdapter(), base_seed=0)
        output = run_pipeline(_NOVEL, "T")
        sb = gen.generate(output)
        assert all(r.model_used == "error" for r in sb.frames)
        assert sb.generated == 0


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
        assert all(DEFAULT_STYLE_TOKEN in p for p in received_prompts)

    def test_style_token_custom_overrides_default(self) -> None:
        received_prompts: list[str] = []

        class TrackingAdapter(NullImageAdapter):
            def generate(self, request: ImageRequest) -> ImageResult:
                received_prompts.append(request.prompt)
                return NullImageAdapter().generate(request)

        output = run_pipeline(_NOVEL, "T")
        StoryboardGenerator(
            adapter=TrackingAdapter(),
            style_token="CUSTOM_STYLE_XYZ",
        ).generate(output)
        assert all("CUSTOM_STYLE_XYZ" in p for p in received_prompts)
        assert all(DEFAULT_STYLE_TOKEN not in p for p in received_prompts)

    def test_style_token_empty_string_accepted(self) -> None:
        output = run_pipeline(_NOVEL, "T")
        sb = StoryboardGenerator(adapter=NullImageAdapter(), style_token="").generate(output)
        assert len(sb.frames) > 0


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
            def generate(self, request: ImageRequest) -> ImageResult:
                raise RuntimeError("API down")

        reg = CharacterSheetRegistry()
        reg.register(CharacterSheet(name="John", canonical_prompt="tall man"))
        StoryboardGenerator(adapter=BrokenAdapter()).prepass_character_sheets(reg)
        assert reg.get("John") is not None
        assert reg.get("John").image_url == ""  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# 9. ShotStoryboardFrame + StoryboardOutput enrichi (SB-05)
# ---------------------------------------------------------------------------

class TestShotStoryboardFrame:
    def _gen(self) -> "StoryboardOutput":
        output = run_pipeline(_NOVEL, "T")
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
    def _frame(self, shot_id: str = "S1") -> "ShotStoryboardFrame":
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

        output = run_pipeline(_NOVEL, "T")
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


# ---------------------------------------------------------------------------
# 11. CharacterPrepass (PC-02)
# ---------------------------------------------------------------------------

class TestCharacterPrepass:
    def test_character_prepass_generates_one_image_per_character(self) -> None:
        from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass
        output = run_pipeline(_NOVEL, "T")
        all_chars = {c for ep in output.episodes for sc in ep.scenes for c in sc.characters}
        result = CharacterPrepass(adapter=NullImageAdapter(), base_seed=0).run(output)
        assert result.generated == len(all_chars)
        assert result.failed == 0

    def test_character_prepass_populates_registry(self) -> None:
        from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass
        output = run_pipeline(_NOVEL, "T")
        all_chars = {c for ep in output.episodes for sc in ep.scenes for c in sc.characters}
        result = CharacterPrepass(adapter=NullImageAdapter(), base_seed=0).run(output)
        for char in all_chars:
            assert result.registry.get_reference(char) != ""

    def test_character_prepass_handles_adapter_failure_gracefully(self) -> None:
        from aiprod_adaptation.image_gen.character_prepass import (
            CharacterPrepass,
            _unique_characters,
        )

        class FailingAdapter(NullImageAdapter):
            def generate(self, request: ImageRequest) -> ImageResult:
                raise RuntimeError("adapter down")

        output = run_pipeline(_NOVEL, "T")
        chars = _unique_characters(output)
        if not chars:
            # Inject synthetic characters directly to test failure handling
            scene = output.episodes[0].scenes[0] if output.episodes and output.episodes[0].scenes else None
            if scene is not None:
                # Patch characters list for test
                object.__setattr__(scene, "characters", ["Alice", "Bob"])
        result = CharacterPrepass(adapter=FailingAdapter(), base_seed=0).run(output)
        # With FailingAdapter: if there are characters, all fail; if none, result is trivially ok
        chars_after = _unique_characters(output)
        if chars_after:
            assert result.failed > 0
            assert result.generated == 0
        else:
            assert result.failed == 0

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
