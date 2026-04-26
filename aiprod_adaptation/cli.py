from __future__ import annotations

import argparse
import json
import os
import sys
import typing
from dataclasses import replace
from pathlib import Path

from aiprod_adaptation.core.adaptation.llm_adapter import (
    LLMAdapter,
    LLMProviderError,
    NullLLMAdapter,
)
from aiprod_adaptation.core.production_budget import ProductionBudget
from aiprod_adaptation.image_gen.image_adapter import ImageAdapter, NullImageAdapter
from aiprod_adaptation.models.schema import AIPRODOutput
from aiprod_adaptation.post_prod.audio_adapter import AudioAdapter, NullAudioAdapter
from aiprod_adaptation.video_gen.video_adapter import NullVideoAdapter, VideoAdapter

_IMAGE_ADAPTERS: dict[str, str] = {
    "null": "aiprod_adaptation.image_gen.image_adapter:NullImageAdapter",
    "flux": "aiprod_adaptation.image_gen.flux_adapter:FluxAdapter",
    "openai": "aiprod_adaptation.image_gen.openai_image_adapter:OpenAIImageAdapter",
    "runway": "aiprod_adaptation.image_gen.runway_image_adapter:RunwayImageAdapter",
    "replicate": "aiprod_adaptation.image_gen.replicate_adapter:ReplicateAdapter",
}
_LLM_ADAPTERS: dict[str, str] = {
    "null": "aiprod_adaptation.core.adaptation.llm_adapter:NullLLMAdapter",
    "claude": "aiprod_adaptation.core.adaptation.claude_adapter:ClaudeAdapter",
    "gemini": "aiprod_adaptation.core.adaptation.gemini_adapter:GeminiAdapter",
    "router": "aiprod_adaptation.core.adaptation.llm_router:LLMRouter",
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
    "runway": "aiprod_adaptation.post_prod.runway_tts_adapter:RunwayTTSAdapter",
}
_DOTENV_LOADED = False


def _load_env_file(env_path: Path | None = None) -> None:
    global _DOTENV_LOADED

    if _DOTENV_LOADED:
        return

    resolved_path = env_path or Path.cwd() / ".env"
    if not resolved_path.exists():
        _DOTENV_LOADED = True
        return

    for raw_line in resolved_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        name, value = line.split("=", 1)
        key = name.strip()
        if not key or key in os.environ:
            continue

        cleaned = value.strip()
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
            cleaned = cleaned[1:-1]
        os.environ[key] = cleaned

    _DOTENV_LOADED = True


def _add_router_short_provider_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--router-short-provider",
        choices=["claude", "gemini"],
        default=None,
        dest="router_short_provider",
        help=(
            "Override the preferred short-text provider when --llm-adapter router is used. "
            "Defaults to LLM_ROUTER_SHORT_PROVIDER or claude."
        ),
    )


def _add_router_trace_output_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--router-trace-output",
        default=None,
        dest="router_trace_output",
        help=(
            "Optional path to write the router decision trace JSON when "
            "--llm-adapter router is used."
        ),
    )


def _add_max_chars_per_chunk_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--max-chars-per-chunk",
        type=int,
        default=None,
        dest="max_chars_per_chunk",
        help=(
            "Optional override for StoryExtractor chunk size when running the novel LLM path. "
            "Useful for forcing multi-chunk real validation on shorter inputs."
        ),
    )


def _add_story_selection_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--scene-id",
        action="append",
        default=None,
        help="Optional scene id to include. Repeatable.",
    )
    parser.add_argument(
        "--shot-id",
        action="append",
        default=None,
        help="Optional shot id to include. Repeatable.",
    )


def _select_output_subset(
    output: AIPRODOutput,
    scene_ids: list[str] | None = None,
    shot_ids: list[str] | None = None,
) -> AIPRODOutput:
    selected_scene_ids = set(scene_ids or [])
    selected_shot_ids = set(shot_ids or [])
    if not selected_scene_ids and not selected_shot_ids:
        return output

    episodes = []
    for episode in output.episodes:
        kept_shots = [
            shot
            for shot in episode.shots
            if shot.scene_id in selected_scene_ids or shot.shot_id in selected_shot_ids
        ]
        if not kept_shots:
            continue

        kept_shot_ids = {shot.shot_id for shot in kept_shots}
        kept_scene_ids = {shot.scene_id for shot in kept_shots}
        kept_scenes = [
            scene.model_copy(
                update={
                    "shot_ids": [shot_id for shot_id in scene.shot_ids if shot_id in kept_shot_ids]
                }
            )
            for scene in episode.scenes
            if scene.scene_id in kept_scene_ids
        ]
        episodes.append(episode.model_copy(update={"scenes": kept_scenes, "shots": kept_shots}))

    return output.model_copy(update={"episodes": episodes})


def _add_pipeline_mode_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pipeline-mode",
        choices=["auto", "deterministic", "generative"],
        default="auto",
        dest="pipeline_mode",
        help=(
            "Execution mode: auto (default), deterministic (rules path only), "
            "or generative (LLM novel extraction required)."
        ),
    )


def _router_trace_payload(llm: LLMAdapter) -> dict[str, object] | None:
    get_trace_history = getattr(llm, "get_trace_history", None)
    if callable(get_trace_history):
        history = typing.cast(list[dict[str, object]], get_trace_history())
        last_trace = history[-1] if history else None
        return {
            "trace_history": history,
            "last_trace": last_trace,
        }
    get_last_trace = getattr(llm, "get_last_trace", None)
    if callable(get_last_trace):
        last_trace = typing.cast(dict[str, object] | None, get_last_trace())
        return {
            "trace_history": [last_trace] if last_trace is not None else [],
            "last_trace": last_trace,
        }
    return None


def _write_router_trace_output(llm: LLMAdapter, output_path: str | None) -> None:
    if not output_path:
        return
    payload = _router_trace_payload(llm)
    if payload is None:
        raise ValueError("Router trace output requires --llm-adapter router.")
    Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_budget(max_chars_per_chunk: int | None) -> ProductionBudget | None:
    if max_chars_per_chunk is None:
        return None

    return replace(
        ProductionBudget.for_short(),
        max_chars_per_chunk=max_chars_per_chunk,
    )


def _load_image_adapter(name: str) -> ImageAdapter:
    if name == "null":
        return NullImageAdapter()
    import importlib
    module_path, class_name = _IMAGE_ADAPTERS[name].split(":")
    cls = getattr(importlib.import_module(module_path), class_name)
    return typing.cast(ImageAdapter, cls())


def _load_llm_adapter(name: str, *, router_short_provider: str | None = None) -> LLMAdapter:
    if name == "null":
        return NullLLMAdapter()
    if name == "router":
        from aiprod_adaptation.core.adaptation.llm_router import LLMRouter
        cooldown_sec = float(os.environ.get("LLM_ROUTER_PROVIDER_COOLDOWN_SEC", "300"))
        default_max_cooldown_sec = str(max(300.0, cooldown_sec * 8.0))
        max_cooldown_sec = float(
            os.environ.get(
                "LLM_ROUTER_PROVIDER_MAX_COOLDOWN_SEC",
                default_max_cooldown_sec,
            )
        )
        auth_quarantine_raw = os.environ.get("LLM_ROUTER_AUTH_QUARANTINE_SEC")
        quota_quarantine_raw = os.environ.get("LLM_ROUTER_QUOTA_QUARANTINE_SEC")
        short_preference = router_short_provider or os.environ.get(
            "LLM_ROUTER_SHORT_PROVIDER",
            "claude",
        )
        return LLMRouter(
            claude=_load_llm_adapter("claude"),
            gemini=_load_llm_adapter("gemini"),
            short_preference=short_preference,
            cooldown_sec=cooldown_sec,
            max_cooldown_sec=max_cooldown_sec,
            auth_quarantine_sec=(
                float(auth_quarantine_raw) if auth_quarantine_raw is not None else None
            ),
            quota_quarantine_sec=(
                float(quota_quarantine_raw) if quota_quarantine_raw is not None else None
            ),
        )
    import importlib
    module_path, class_name = _LLM_ADAPTERS[name].split(":")
    cls = getattr(importlib.import_module(module_path), class_name)
    return typing.cast(LLMAdapter, cls())


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
    return typing.cast(VideoAdapter, cls())


def _load_audio_adapter(name: str) -> AudioAdapter:
    if name == "null":
        return NullAudioAdapter()
    import importlib
    module_path, class_name = _AUDIO_ADAPTERS[name].split(":")
    cls = getattr(importlib.import_module(module_path), class_name)
    return typing.cast(AudioAdapter, cls())


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
        "--output-format",
        choices=["json", "csv", "json-flat"],
        default="json",
        dest="output_format",
        help="Output format (default: json/Pydantic)",
    )
    p_pipeline.add_argument(
        "--llm-adapter",
        choices=list(_LLM_ADAPTERS),
        default="null",
        help="LLM adapter for novel extraction (default: null/rules fallback)",
    )
    p_pipeline.add_argument(
        "--require-llm",
        action="store_true",
        help="Fail if LLM extraction produces no scenes instead of silently falling back to rules.",
    )
    _add_pipeline_mode_option(p_pipeline)
    _add_router_short_provider_option(p_pipeline)
    _add_router_trace_output_option(p_pipeline)
    _add_max_chars_per_chunk_option(p_pipeline)
    p_pipeline.add_argument(
        "--visual-bible",
        metavar="FILE",
        default=None,
        dest="visual_bible",
        help="Path to a VisualBible JSON file (enables reference anchoring and RQS scoring).",
    )

    p_storyboard = sub.add_parser("storyboard", help="AIPRODOutput JSON → StoryboardOutput JSON")
    p_storyboard.add_argument("--input", required=True, help="Path to AIPRODOutput JSON")
    p_storyboard.add_argument("--output", required=True, help="Path to write StoryboardOutput JSON")
    p_storyboard.add_argument("--style-token", default=None, help="Override default style token")
    p_storyboard.add_argument(
        "--reference-pack",
        default=None,
        help="Optional JSON file describing character and location reference packs",
    )
    p_storyboard.add_argument(
        "--image-adapter",
        choices=list(_IMAGE_ADAPTERS),
        default="null",
        help="Image generation adapter (default: null)",
    )
    _add_story_selection_options(p_storyboard)

    p_schedule = sub.add_parser(
        "schedule", help="AIPRODOutput → full production (image+video+audio)"
    )
    p_schedule.add_argument("--input", required=True, help="Path to AIPRODOutput JSON")
    p_schedule.add_argument(
        "--output",
        required=True,
        help="Directory to write storyboard.json, video.json, production.json, and metrics.json",
    )
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
    p_schedule.add_argument(
        "--reference-pack",
        default=None,
        help="Optional JSON file describing character and location reference packs",
    )
    _add_story_selection_options(p_schedule)

    p_compare = sub.add_parser("compare", help="compare rules output vs LLM output")
    p_compare.add_argument("--input", required=True, help="Path to input text file")
    p_compare.add_argument("--title", required=True, help="Production title")
    p_compare.add_argument(
        "--llm-adapter",
        choices=[name for name in _LLM_ADAPTERS if name != "null"],
        default="gemini",
        help="LLM adapter to compare against the rules pipeline",
    )
    p_compare.add_argument(
        "--output",
        required=False,
        help="Optional path to write the comparison summary text",
    )
    p_compare.add_argument(
        "--rules-output",
        required=False,
        help="Optional path to write the rules-based JSON output used in the comparison",
    )
    p_compare.add_argument(
        "--llm-output",
        required=False,
        help="Optional path to write the LLM-based JSON output used in the comparison",
    )
    p_compare.add_argument(
        "--output-format",
        choices=["text", "json"],
        default="text",
        dest="output_format",
        help="Comparison output format (default: text)",
    )
    _add_router_short_provider_option(p_compare)
    _add_router_trace_output_option(p_compare)
    _add_max_chars_per_chunk_option(p_compare)

    # ------------------------------------------------------------------ metrics
    p_metrics = sub.add_parser(
        "metrics",
        help="AIPRODOutput JSON → episode quality metrics JSON",
    )
    p_metrics.add_argument("--input", required=True, help="Path to AIPRODOutput JSON")
    p_metrics.add_argument(
        "--output",
        required=False,
        default=None,
        help="Optional path to write EpisodeMetrics JSON (default: stdout)",
    )
    p_metrics.add_argument(
        "--season-id",
        default="S01",
        dest="season_id",
        help="Season identifier for reporting (default: S01)",
    )

    # ------------------------------------------------------------------ export
    p_export = sub.add_parser(
        "export",
        help="AIPRODOutput JSON → post-production export (edl | resolve | audio-cue | batch | season-report)",
    )
    p_export.add_argument("--input", required=True, help="Path to AIPRODOutput JSON")
    p_export.add_argument("--output", required=True, help="Path to write the export file")
    p_export.add_argument(
        "--format",
        choices=["edl", "resolve", "audio-cue", "batch", "season-report"],
        required=True,
        dest="export_format",
        help="Export format",
    )
    p_export.add_argument(
        "--fps",
        type=float,
        default=24.0,
        help="Frames per second (default: 24.0)",
    )
    p_export.add_argument(
        "--adapter-target",
        default="runway",
        dest="adapter_target",
        help="Target adapter for batch export (default: runway)",
    )
    p_export.add_argument(
        "--season-id",
        default="S01",
        dest="season_id",
        help="Season identifier for season-report export (default: S01)",
    )
    p_export.add_argument(
        "--series-title",
        default="",
        dest="series_title",
        help="Series title for season-report export",
    )

    return parser


def cmd_pipeline(args: argparse.Namespace) -> int:
    from aiprod_adaptation.core.engine import run_pipeline
    from aiprod_adaptation.core.io import save_output

    _load_env_file()
    text = Path(args.input).read_text(encoding="utf-8")
    try:
        llm = _load_llm_adapter(
            args.llm_adapter,
            router_short_provider=getattr(args, "router_short_provider", None),
        )
    except (ImportError, ValueError) as exc:
        print(f"LLM adapter init failed ({args.llm_adapter}): {exc}", file=sys.stderr)
        return 1

    budget = _build_budget(getattr(args, "max_chars_per_chunk", None))

    visual_bible = None
    vb_path = getattr(args, "visual_bible", None)
    if vb_path:
        from aiprod_adaptation.core.visual_bible import VisualBible
        visual_bible = VisualBible(json.loads(Path(vb_path).read_text(encoding="utf-8")))

    try:
        output = run_pipeline(
            text,
            args.title,
            llm=llm,
            budget=budget,
            require_llm=args.require_llm,
            pipeline_mode=getattr(args, "pipeline_mode", "auto"),
            visual_bible=visual_bible,
        )
    except (LLMProviderError, ValueError) as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        return 1
    if args.output_format == "csv":
        from aiprod_adaptation.backends.csv_export import CsvExport
        Path(args.output).write_text(CsvExport().export(output), encoding="utf-8")
    elif args.output_format == "json-flat":
        from aiprod_adaptation.backends.json_flat_export import JsonFlatExport
        Path(args.output).write_text(JsonFlatExport().export(output), encoding="utf-8")
    else:
        save_output(output, args.output)
    try:
        _write_router_trace_output(llm, getattr(args, "router_trace_output", None))
    except ValueError as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        return 1
    print(f"Pipeline complete: {args.output}", file=sys.stderr)
    return 0


def cmd_storyboard(args: argparse.Namespace) -> int:
    from aiprod_adaptation.core.io import load_output, save_storyboard
    from aiprod_adaptation.image_gen.reference_pack import load_reference_pack
    from aiprod_adaptation.image_gen.storyboard import DEFAULT_STYLE_TOKEN, StoryboardGenerator

    _load_env_file()
    output = load_output(args.input)
    output = _select_output_subset(
        output,
        scene_ids=getattr(args, "scene_id", None),
        shot_ids=getattr(args, "shot_id", None),
    )
    style_token = args.style_token if args.style_token is not None else DEFAULT_STYLE_TOKEN
    image_adapter = _load_image_adapter(getattr(args, "image_adapter", "null"))
    reference_pack = (
        load_reference_pack(args.reference_pack) if getattr(args, "reference_pack", None) else None
    )
    if not output.episodes or not any(ep.shots for ep in output.episodes):
        print("Storyboard failed: selection matched no shots.", file=sys.stderr)
        return 1
    sb = StoryboardGenerator(
        adapter=image_adapter,
        style_token=style_token,
        reference_pack=reference_pack,
    ).generate(output)
    save_storyboard(sb, args.output)
    print(f"Storyboard complete: {args.output}", file=sys.stderr)
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    import json as _json

    from aiprod_adaptation.core.io import load_output, save_production, save_storyboard, save_video
    from aiprod_adaptation.core.scheduling.episode_scheduler import EpisodeScheduler
    from aiprod_adaptation.image_gen.reference_pack import load_reference_pack

    _load_env_file()
    output = load_output(args.input)
    output = _select_output_subset(
        output,
        scene_ids=getattr(args, "scene_id", None),
        shot_ids=getattr(args, "shot_id", None),
    )
    reference_pack = (
        load_reference_pack(args.reference_pack) if getattr(args, "reference_pack", None) else None
    )
    if not output.episodes or not any(ep.shots for ep in output.episodes):
        print("Schedule failed: selection matched no shots.", file=sys.stderr)
        return 1
    scheduler = EpisodeScheduler(
        image_adapter=_load_image_adapter(args.image_adapter),
        video_adapter=_load_video_adapter(args.video_adapter),
        audio_adapter=_load_audio_adapter(args.audio_adapter),
        reference_pack=reference_pack,
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


def cmd_compare(args: argparse.Namespace) -> int:
    from aiprod_adaptation.core.comparison import compare_outputs
    from aiprod_adaptation.core.engine import run_pipeline
    from aiprod_adaptation.core.io import save_output

    _load_env_file()
    text = Path(args.input).read_text(encoding="utf-8")
    rules_output = run_pipeline(text, args.title, llm=NullLLMAdapter())
    try:
        llm = _load_llm_adapter(
            args.llm_adapter,
            router_short_provider=getattr(args, "router_short_provider", None),
        )
    except (ImportError, ValueError) as exc:
        print(f"LLM adapter init failed ({args.llm_adapter}): {exc}", file=sys.stderr)
        return 1

    budget = _build_budget(getattr(args, "max_chars_per_chunk", None))

    try:
        llm_output = run_pipeline(
            text,
            args.title,
            llm=llm,
            budget=budget,
            require_llm=True,
            pipeline_mode="generative",
        )
    except (LLMProviderError, ValueError) as exc:
        print(f"Compare failed: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "rules_output", None):
        save_output(rules_output, args.rules_output)
    if getattr(args, "llm_output", None):
        save_output(llm_output, args.llm_output)

    comparison = compare_outputs(rules_output, llm_output, args.llm_adapter)
    output_format = getattr(args, "output_format", "text")
    if output_format == "json":
        summary = json.dumps(comparison.to_dict(), indent=2)
    else:
        summary = comparison.to_summary_str()
    if args.output:
        Path(args.output).write_text(summary, encoding="utf-8")
    else:
        print(summary)
    try:
        _write_router_trace_output(llm, getattr(args, "router_trace_output", None))
    except ValueError as exc:
        print(f"Compare failed: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_metrics(args: argparse.Namespace) -> int:
    from aiprod_adaptation.core.io import load_output
    from aiprod_adaptation.core.metrics import MetricsEngine

    _load_env_file()
    output = load_output(args.input)
    engine = MetricsEngine()
    ep_metrics = engine.compute_episode(output)
    result = ep_metrics.model_dump()
    result["broadcast_gate"] = "PASS" if ep_metrics.passes_broadcast_gate() else "FAIL"
    import json as _json
    text = _json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Metrics written: {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from aiprod_adaptation.core.exports import (
        export_audio_cue_sheet,
        export_batch_generation,
        export_edl_json,
        export_resolve_timeline,
        export_season_report,
    )
    from aiprod_adaptation.core.io import load_output

    _load_env_file()
    output = load_output(args.input)
    fps: float = getattr(args, "fps", 24.0)
    fmt: str = args.export_format

    if fmt == "edl":
        result = export_edl_json(output, fps=fps)
    elif fmt == "resolve":
        result = export_resolve_timeline(output, fps=fps)
    elif fmt == "audio-cue":
        result = export_audio_cue_sheet(output, fps=fps)
    elif fmt == "batch":
        result = export_batch_generation(
            output,
            adapter_target=getattr(args, "adapter_target", "runway"),
            fps=fps,
        )
    elif fmt == "season-report":
        result = export_season_report(
            [output],
            season_id=getattr(args, "season_id", "S01"),
            series_title=getattr(args, "series_title", ""),
        )
    else:
        print(f"Unknown export format: {fmt}", file=sys.stderr)
        return 1

    Path(args.output).write_text(result, encoding="utf-8")
    print(f"Export complete: {args.output}", file=sys.stderr)
    return 0


def main() -> None:
    _load_env_file()
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "pipeline":
        sys.exit(cmd_pipeline(args))
    elif args.command == "storyboard":
        sys.exit(cmd_storyboard(args))
    elif args.command == "schedule":
        sys.exit(cmd_schedule(args))
    elif args.command == "compare":
        sys.exit(cmd_compare(args))
    elif args.command == "metrics":
        sys.exit(cmd_metrics(args))
    elif args.command == "export":
        sys.exit(cmd_export(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
