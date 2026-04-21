"""
pytest test suite — core/io.py persistance JSON (SO-03)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from aiprod_adaptation.core.engine import run_pipeline
from aiprod_adaptation.core.io import (
    load_output,
    load_production,
    load_storyboard,
    load_video,
    save_output,
    save_production,
    save_storyboard,
    save_video,
)
from aiprod_adaptation.image_gen.image_adapter import NullImageAdapter
from aiprod_adaptation.image_gen.storyboard import StoryboardGenerator
from aiprod_adaptation.post_prod.audio_adapter import NullAudioAdapter
from aiprod_adaptation.post_prod.audio_synchronizer import AudioSynchronizer
from aiprod_adaptation.video_gen.video_adapter import NullVideoAdapter
from aiprod_adaptation.video_gen.video_sequencer import VideoSequencer

_NOVEL = (
    "Alice walked into the old library and picked up a dusty book. "
    "Later, in the garden, she read quietly while birds sang above."
)


def _pipeline():  # type: ignore[return]
    return run_pipeline(_NOVEL, "IO Test")


def _storyboard(output):  # type: ignore[return]
    return StoryboardGenerator(adapter=NullImageAdapter(), base_seed=0).generate(output)


def _video(sb, output):  # type: ignore[return]
    return VideoSequencer(adapter=NullVideoAdapter(), base_seed=0).generate(sb, output)


def _production(video, output):  # type: ignore[return]
    _audio_results, prod = AudioSynchronizer(adapter=NullAudioAdapter()).generate(video, output)
    return prod


class TestSaveLoadOutput:
    def test_save_load_output_roundtrip(self) -> None:
        output = _pipeline()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        save_output(output, path)
        loaded = load_output(path)
        assert loaded == output

    def test_save_output_creates_parent_dirs(self) -> None:
        output = _pipeline()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a" / "b" / "out.json"
            save_output(output, path)
            assert path.exists()

    def test_load_output_invalid_json_raises_validation_error(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write('{"title": "X", "episodes": "INVALID"}')
            path = Path(f.name)
        with pytest.raises(ValidationError):
            load_output(path)


class TestSaveLoadStoryboard:
    def test_save_load_storyboard_roundtrip(self) -> None:
        sb = _storyboard(_pipeline())
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        save_storyboard(sb, path)
        loaded = load_storyboard(path)
        assert loaded == sb


class TestSaveLoadVideo:
    def test_save_load_video_roundtrip(self) -> None:
        output = _pipeline()
        sb = _storyboard(output)
        video = _video(sb, output)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        save_video(video, path)
        loaded = load_video(path)
        assert loaded == video


class TestSaveLoadProduction:
    def test_save_load_production_roundtrip(self) -> None:
        output = _pipeline()
        sb = _storyboard(output)
        video = _video(sb, output)
        prod = _production(video, output)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        save_production(prod, path)
        loaded = load_production(path)
        assert loaded == prod
