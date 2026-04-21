from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aiprod_adaptation.image_gen.image_adapter import ImageAdapter, NullImageAdapter
from aiprod_adaptation.video_gen.video_adapter import NullVideoAdapter, VideoAdapter
from aiprod_adaptation.post_prod.audio_adapter import AudioAdapter, NullAudioAdapter

_IMAGE_ADAPTERS: dict[str, str] = {
    "null": "aiprod_adaptation.image_gen.image_adapter:NullImageAdapter",
    "flux": "aiprod_adaptation.image_gen.flux_adapter:FluxAdapter",
    "replicate": "aiprod_adaptation.image_gen.replicate_adapter:ReplicateAdapter",
}
_VIDEO_ADAPTERS: dict[str, str] = {
    "null": "aiprod_adaptation.video_gen.video_adapter:NullVideoAdapter",
    "runway": "aiprod_adaptation.video_gen.runway_adapter:RunwayAdapter",
    "kling": "aiprod_adaptation.video_gen.kling_adapter:KlingAdapter",
    "smart": "aiprod_adaptation.video_gen.smart_video_router:SmartVideoRouter",
}
_AUDIO_ADAPTERS: dict[str, str] = {
    "null": "aiprod_adaptation.post_prod.audio_adapter:NullAudioAdapter",
    "elevenlabs": "aiprod_adaptation.post_prod.elevenlabs_adapter:ElevenLabsAdapter",
    "openai": "aiprod_adaptation.post_prod.openai_tts_adapter:OpenAITTSAdapter",
}


def _load_image_adapter(name: str) -> ImageAdapter:
    if name == "null":
        return NullImageAdapter()
    import importlib
    module_path, class_name = _IMAGE_ADAPTERS[name].split(":")
    cls = getattr(importlib.import_module(module_path), class_name)
    return cls()  # type: ignore[no-any-return]


def _load_video_adapter(name: str) -> VideoAdapter:
    if name == "null":
        return NullVideoAdapter()
    if name == "smart":
        from aiprod_adaptation.video_gen.smart_video_router import SmartVideoRouter
        return SmartVideoRouter(
            runway_adapter=_load_video_adapter("runway"),
            kling_adapter=_load_video_adapter("kling"),
        )
    import importlib
    module_path, class_name = _VIDEO_ADAPTERS[name].split(":")
    cls = getattr(importlib.import_module(module_path), class_name)
    return cls()  # type: ignore[no-any-return]


def _load_audio_adapter(name: str) -> AudioAdapter:
    if name == "null":
        return NullAudioAdapter()
    import importlib
    module_path, class_name = _AUDIO_ADAPTERS[name].split(":")
    cls = getattr(importlib.import_module(module_path), class_name)
    return cls()  # type: ignore[no-any-return]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aiprod",
        description="AIPROD v2 — narrative-to-cinematic IR compiler",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_pipeline = sub.add_parser("pipeline", help="text → AIPRODOutput JSON")
    p_pipeline.add_argument("--input", required=True, help="Path to input text file")
    p_pipeline.add_argument("--title", required=True, help="Production title")
    p_pipeline.add_argument("--output", required=True, help="Path to write AIPRODOutput JSON")
    p_pipeline.add_argument(
        "--format",
        choices=["novel", "script"],
        default=None,
        help="Force input format (auto-detected if omitted)",
    )

    p_storyboard = sub.add_parser("storyboard", help="AIPRODOutput JSON → StoryboardOutput JSON")
    p_storyboard.add_argument("--input", required=True, help="Path to AIPRODOutput JSON")
    p_storyboard.add_argument("--output", required=True, help="Path to write StoryboardOutput JSON")
    p_storyboard.add_argument("--style-token", default=None, help="Override default style token")
    p_storyboard.add_argument(
        "--image-adapter",
        choices=list(_IMAGE_ADAPTERS),
        default="null",
        help="Image generation adapter (default: null)",
    )

    p_schedule = sub.add_parser("schedule", help="AIPRODOutput → full production (image+video+audio)")
    p_schedule.add_argument("--input", required=True, help="Path to AIPRODOutput JSON")
    p_schedule.add_argument("--output", required=True, help="Directory or JSON path for SchedulerResult")
    p_schedule.add_argument(
        "--image-adapter",
        choices=list(_IMAGE_ADAPTERS),
        default="null",
        help="Image generation adapter (default: null)",
    )
    p_schedule.add_argument(
        "--video-adapter",
        choices=list(_VIDEO_ADAPTERS),
        default="null",
        help="Video generation adapter (default: null)",
    )
    p_schedule.add_argument(
        "--audio-adapter",
        choices=list(_AUDIO_ADAPTERS),
        default="null",
        help="Audio generation adapter (default: null)",
    )

    return parser


def cmd_pipeline(args: argparse.Namespace) -> int:
    from aiprod_adaptation.core.engine import run_pipeline
    from aiprod_adaptation.core.io import save_output

    text = Path(args.input).read_text(encoding="utf-8")
    output = run_pipeline(text, args.title)
    save_output(output, args.output)
    print(f"Pipeline complete: {args.output}", file=sys.stderr)
    return 0


def cmd_storyboard(args: argparse.Namespace) -> int:
    from aiprod_adaptation.core.io import load_output, save_storyboard
    from aiprod_adaptation.image_gen.storyboard import DEFAULT_STYLE_TOKEN, StoryboardGenerator

    output = load_output(args.input)
    style_token = args.style_token if args.style_token is not None else DEFAULT_STYLE_TOKEN
    image_adapter = _load_image_adapter(getattr(args, "image_adapter", "null"))
    sb = StoryboardGenerator(adapter=image_adapter, style_token=style_token).generate(output)
    save_storyboard(sb, args.output)
    print(f"Storyboard complete: {args.output}", file=sys.stderr)
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    import json as _json
    from aiprod_adaptation.core.io import load_output, save_storyboard, save_video, save_production
    from aiprod_adaptation.core.scheduling.episode_scheduler import EpisodeScheduler

    output = load_output(args.input)
    scheduler = EpisodeScheduler(
        image_adapter=_load_image_adapter(args.image_adapter),
        video_adapter=_load_video_adapter(args.video_adapter),
        audio_adapter=_load_audio_adapter(args.audio_adapter),
    )
    result = scheduler.run(output)
    out_path = Path(args.output)
    out_path.mkdir(parents=True, exist_ok=True)
    save_storyboard(result.storyboard, out_path / "storyboard.json")
    save_video(result.video, out_path / "video.json")
    save_production(result.production, out_path / "production.json")
    metrics_path = out_path / "metrics.json"
    from dataclasses import asdict
    metrics_path.write_text(_json.dumps(asdict(result.metrics), indent=2), encoding="utf-8")
    print(f"Schedule complete: {args.output}", file=sys.stderr)
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "pipeline":
        sys.exit(cmd_pipeline(args))
    elif args.command == "storyboard":
        sys.exit(cmd_storyboard(args))
    elif args.command == "schedule":
        sys.exit(cmd_schedule(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
