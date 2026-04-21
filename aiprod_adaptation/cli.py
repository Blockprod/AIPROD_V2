from __future__ import annotations

import argparse
import sys
from pathlib import Path


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
    from aiprod_adaptation.image_gen.image_adapter import NullImageAdapter
    from aiprod_adaptation.image_gen.storyboard import DEFAULT_STYLE_TOKEN, StoryboardGenerator

    output = load_output(args.input)
    style_token = args.style_token if args.style_token is not None else DEFAULT_STYLE_TOKEN
    sb = StoryboardGenerator(adapter=NullImageAdapter(), style_token=style_token).generate(output)
    save_storyboard(sb, args.output)
    print(f"Storyboard complete: {args.output}", file=sys.stderr)
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "pipeline":
        sys.exit(cmd_pipeline(args))
    elif args.command == "storyboard":
        sys.exit(cmd_storyboard(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
