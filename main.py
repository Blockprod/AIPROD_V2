"""
AIPROD ADAPTATION ENGINE v2 — CLI entry point
Loads examples/sample.txt, runs the deterministic pipeline, prints pretty JSON.
"""

from __future__ import annotations

import json
import pathlib
import sys

from aiprod_adaptation.core.engine import run_pipeline

SAMPLE_PATH = pathlib.Path(__file__).parent / "aiprod_adaptation" / "examples" / "sample.txt"
TITLE = "AIPROD SAMPLE EPISODE"


def main() -> None:
    if not SAMPLE_PATH.exists():
        print(f"ERROR: sample file not found: {SAMPLE_PATH}", file=sys.stderr)
        sys.exit(1)

    raw_text = SAMPLE_PATH.read_text(encoding="utf-8")
    output = run_pipeline(raw_text, TITLE)
    print(json.dumps(output.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
