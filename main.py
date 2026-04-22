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
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    input_path = pathlib.Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    title: str = args.title if args.title else input_path.stem
    raw_text = input_path.read_text(encoding="utf-8")
    output = run_pipeline(raw_text, title, episode_id=args.episode_id)

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


if __name__ == "__main__":
    main()
