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

import pytest

from aiprod_adaptation.image_gen.image_adapter import NullImageAdapter
from aiprod_adaptation.image_gen.image_request import (
    ImageRequest,
    ImageResult,
    StoryboardOutput,
)
from aiprod_adaptation.image_gen.storyboard import StoryboardGenerator
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
            images=[],
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
        assert len(sb.images) == total

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
        assert all(r.model_used == "error" for r in sb.images)
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
