"""
pytest test suite — CLI argparse (SO-05)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from aiprod_adaptation.cli import build_parser, cmd_pipeline, cmd_storyboard


class TestCLIParser:
    def test_cli_help_does_not_crash(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["--help"])
        assert exc.value.code == 0

    def test_cli_pipeline_missing_input_exits_nonzero(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["pipeline", "--title", "T", "--output", "out.json"])
        assert exc.value.code != 0

    def test_cli_pipeline_missing_title_exits_nonzero(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["pipeline", "--input", "in.txt", "--output", "out.json"])
        assert exc.value.code != 0


class TestCLIPipeline:
    def test_cli_pipeline_outputs_valid_json(self) -> None:
        novel = (
            "Alice walked into the old library and picked up a dusty book. "
            "Later, in the garden, she read quietly while birds sang above."
        )
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            out_path = Path(tmp) / "output.json"
            in_path.write_text(novel, encoding="utf-8")
            parser = build_parser()
            args = parser.parse_args(["pipeline", "--input", str(in_path), "--title", "T", "--output", str(out_path)])
            rc = cmd_pipeline(args)
            assert rc == 0
            assert out_path.exists()
            data = json.loads(out_path.read_text(encoding="utf-8"))
            assert "title" in data
            assert "episodes" in data

    def test_cli_storyboard_reads_output_json(self) -> None:
        novel = (
            "Alice walked into the old library and picked up a dusty book. "
            "Later, in the garden, she read quietly while birds sang above."
        )
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            pipeline_out = Path(tmp) / "pipeline.json"
            sb_out = Path(tmp) / "storyboard.json"
            in_path.write_text(novel, encoding="utf-8")

            parser = build_parser()
            args_p = parser.parse_args(["pipeline", "--input", str(in_path), "--title", "T", "--output", str(pipeline_out)])
            cmd_pipeline(args_p)

            args_s = parser.parse_args(["storyboard", "--input", str(pipeline_out), "--output", str(sb_out)])
            rc = cmd_storyboard(args_s)
            assert rc == 0
            assert sb_out.exists()
            data = json.loads(sb_out.read_text(encoding="utf-8"))
            assert "frames" in data
