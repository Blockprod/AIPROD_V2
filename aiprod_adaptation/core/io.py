from __future__ import annotations

import json
from pathlib import Path

from aiprod_adaptation.image_gen.image_request import StoryboardOutput
from aiprod_adaptation.models.schema import AIPRODOutput
from aiprod_adaptation.post_prod.audio_request import ProductionOutput
from aiprod_adaptation.video_gen.video_request import VideoOutput


def _write(data: str, path: Path | str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data, encoding="utf-8")


def save_output(output: AIPRODOutput, path: Path | str) -> None:
    _write(output.model_dump_json(indent=2), path)


def load_output(path: Path | str) -> AIPRODOutput:
    raw = Path(path).read_text(encoding="utf-8")
    return AIPRODOutput.model_validate(json.loads(raw))


def save_storyboard(sb: StoryboardOutput, path: Path | str) -> None:
    _write(sb.model_dump_json(indent=2), path)


def load_storyboard(path: Path | str) -> StoryboardOutput:
    raw = Path(path).read_text(encoding="utf-8")
    return StoryboardOutput.model_validate(json.loads(raw))


def save_video(vo: VideoOutput, path: Path | str) -> None:
    _write(vo.model_dump_json(indent=2), path)


def load_video(path: Path | str) -> VideoOutput:
    raw = Path(path).read_text(encoding="utf-8")
    return VideoOutput.model_validate(json.loads(raw))


def save_production(po: ProductionOutput, path: Path | str) -> None:
    _write(po.model_dump_json(indent=2), path)


def load_production(path: Path | str) -> ProductionOutput:
    raw = Path(path).read_text(encoding="utf-8")
    return ProductionOutput.model_validate(json.loads(raw))
