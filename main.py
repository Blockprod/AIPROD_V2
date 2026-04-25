"""
AIPROD ADAPTATION ENGINE v2 — CLI entry point
Parses a narrative text file and outputs structured cinematic JSON.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from aiprod_adaptation.backends.csv_export import CsvExport
from aiprod_adaptation.backends.json_flat_export import JsonFlatExport
from aiprod_adaptation.cli import (
    _build_budget,
    _load_env_file,
    _load_llm_adapter,
    _write_router_trace_output,
)
from aiprod_adaptation.core.adaptation.llm_adapter import LLMProviderError
from aiprod_adaptation.core.engine import run_pipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aiprod",
        description=(
            "AIPROD Adaptation Engine"
            " — transforms narrative text into structured cinematic data."
        ),
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        metavar="FILE",
        help="Path to the narrative text file to process.",
    )
    parser.add_argument(
        "--title", "-t",
        metavar="TITLE",
        default=None,
        help="Episode title. Defaults to the input filename without extension.",
    )
    parser.add_argument(
        "--episode-id",
        metavar="ID",
        default="EP01",
        help="Episode identifier (default: EP01).",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        default=None,
        help="Path to write the output. Defaults to stdout.",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "json-flat", "csv"],
        default="json",
        help="Output format: json (default), json-flat, or csv.",
    )
    parser.add_argument(
        "--llm-adapter",
        choices=["null", "claude", "gemini", "router"],
        default="null",
        help="LLM adapter for novel extraction (default: null/rules fallback).",
    )
    parser.add_argument(
        "--require-llm",
        action="store_true",
        help="Fail if LLM extraction produces no scenes instead of silently falling back to rules.",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "deterministic", "generative"],
        default="auto",
        help=(
            "Execution mode: auto (default), deterministic (rules path only), "
            "or generative (LLM novel extraction required)."
        ),
    )
    parser.add_argument(
        "--router-short-provider",
        choices=["claude", "gemini"],
        default=None,
        help=(
            "Override the preferred short-text provider when --llm-adapter router is used. "
            "Defaults to LLM_ROUTER_SHORT_PROVIDER or claude."
        ),
    )
    parser.add_argument(
        "--router-trace-output",
        metavar="FILE",
        default=None,
        help=(
            "Optional path to write the router decision trace JSON when "
            "--llm-adapter router is used."
        ),
    )
    parser.add_argument(
        "--max-chars-per-chunk",
        metavar="N",
        type=int,
        default=None,
        help=(
            "Optional override for StoryExtractor chunk size when running the novel LLM path. "
            "Useful for forcing multi-chunk real validation on shorter inputs."
        ),
    )
    return parser


def main() -> None:
    _load_env_file()
    parser = _build_parser()
    args = parser.parse_args()

    input_path = pathlib.Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    title: str = args.title if args.title else input_path.stem
    raw_text = input_path.read_text(encoding="utf-8")
    try:
        llm = _load_llm_adapter(
            args.llm_adapter,
            router_short_provider=args.router_short_provider,
        )
    except (ImportError, ValueError) as exc:
        print(f"ERROR: LLM adapter init failed ({args.llm_adapter}): {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        output = run_pipeline(
            raw_text,
            title,
            episode_id=args.episode_id,
            llm=llm,
            budget=_build_budget(args.max_chars_per_chunk),
            require_llm=args.require_llm,
            pipeline_mode=getattr(args, "mode", "auto"),
        )
    except (LLMProviderError, ValueError) as exc:
        print(f"ERROR: Pipeline failed: {exc}", file=sys.stderr)
        sys.exit(1)

    fmt: str = args.format
    if fmt == "csv":
        result = CsvExport().export(output)
    elif fmt == "json-flat":
        result = JsonFlatExport().export(output)
    else:
        result = json.dumps(output.model_dump(), indent=2, ensure_ascii=False)

    if args.output:
        output_path = pathlib.Path(args.output)
        output_path.write_text(result, encoding="utf-8")
    else:
        print(result)
    try:
        _write_router_trace_output(llm, args.router_trace_output)
    except ValueError as exc:
        print(f"ERROR: Pipeline failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
