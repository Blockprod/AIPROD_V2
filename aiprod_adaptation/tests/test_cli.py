"""
pytest test suite — CLI argparse (SO-05)
"""

from __future__ import annotations

import argparse
import json
import tempfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aiprod_adaptation.cli import (
    _load_env_file,
    _load_llm_adapter,
    build_parser,
    cmd_compare,
    cmd_pipeline,
    cmd_schedule,
    cmd_storyboard,
)
from aiprod_adaptation.core.adaptation.llm_adapter import LLMProviderError
from aiprod_adaptation.core.production_budget import ProductionBudget
from aiprod_adaptation.models.schema import AIPRODOutput


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

    def test_cli_pipeline_rejects_removed_input_format_flag(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(
                [
                    "pipeline",
                    "--input",
                    "in.txt",
                    "--title",
                    "T",
                    "--output",
                    "out.json",
                    "--format",
                    "novel",
                ]
            )
        assert exc.value.code != 0

    def test_cli_pipeline_llm_adapter_defaults_to_null(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "pipeline", "--input", "in.txt", "--title", "T", "--output", "out.json"
        ])
        assert args.llm_adapter == "null"

    def test_cli_pipeline_require_llm_defaults_to_false(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "pipeline", "--input", "in.txt", "--title", "T", "--output", "out.json"
        ])
        assert args.require_llm is False

    def test_cli_pipeline_mode_defaults_to_auto(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "pipeline", "--input", "in.txt", "--title", "T", "--output", "out.json"
        ])
        assert args.pipeline_mode == "auto"

    def test_cli_pipeline_mode_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "pipeline",
            "--input",
            "in.txt",
            "--title",
            "T",
            "--output",
            "out.json",
            "--pipeline-mode",
            "deterministic",
        ])
        assert args.pipeline_mode == "deterministic"

    def test_cli_pipeline_router_short_provider_defaults_to_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "pipeline", "--input", "in.txt", "--title", "T", "--output", "out.json"
        ])
        assert args.router_short_provider is None

    def test_cli_pipeline_router_short_provider_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "pipeline",
            "--input",
            "in.txt",
            "--title",
            "T",
            "--output",
            "out.json",
            "--llm-adapter",
            "router",
            "--router-short-provider",
            "gemini",
            "--router-trace-output",
            "trace.json",
            "--max-chars-per-chunk",
            "256",
        ])
        assert args.router_short_provider == "gemini"
        assert args.router_trace_output == "trace.json"
        assert args.max_chars_per_chunk == 256

    def test_cli_compare_llm_adapter_defaults_to_gemini(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "compare", "--input", "in.txt", "--title", "T"
        ])
        assert args.llm_adapter == "gemini"
        assert args.output_format == "text"
        assert args.rules_output is None
        assert args.llm_output is None

    def test_cli_compare_router_short_provider_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "compare",
            "--input",
            "in.txt",
            "--title",
            "T",
            "--llm-adapter",
            "router",
            "--router-short-provider",
            "gemini",
            "--router-trace-output",
            "trace.json",
            "--max-chars-per-chunk",
            "128",
        ])
        assert args.router_short_provider == "gemini"
        assert args.router_trace_output == "trace.json"
        assert args.max_chars_per_chunk == 128

    def test_cli_compare_output_format_json_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "compare",
            "--input",
            "in.txt",
            "--title",
            "T",
            "--output-format",
            "json",
        ])
        assert args.output_format == "json"

    def test_cli_schedule_output_help_mentions_directory_only(self) -> None:
        parser = build_parser()
        subparsers_action = next(
            action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
        )
        schedule_parser = subparsers_action.choices["schedule"]
        output_action = next(
            action for action in schedule_parser._actions if action.dest == "output"
        )

        assert output_action.help == (
            "Directory to write storyboard.json, video.json, production.json, and metrics.json"
        )


class TestCLILoadLLMAdapter:
    def test_load_env_file_reads_dotenv_without_overriding_existing_env(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                'AIPROD_TEST_ALPHA="alpha"\nAIPROD_TEST_BETA=beta\n',
                encoding="utf-8",
            )

            with pytest.MonkeyPatch.context() as local_patch:
                local_patch.delenv("AIPROD_TEST_ALPHA", raising=False)
                local_patch.setenv("AIPROD_TEST_BETA", "preserved")
                local_patch.setattr("aiprod_adaptation.cli._DOTENV_LOADED", False)

                _load_env_file(env_path)

                assert os.environ["AIPROD_TEST_ALPHA"] == "alpha"
                assert os.environ["AIPROD_TEST_BETA"] == "preserved"

    def test_load_llm_adapter_null_returns_null_adapter(self) -> None:
        from aiprod_adaptation.core.adaptation.llm_adapter import NullLLMAdapter

        assert isinstance(_load_llm_adapter("null"), NullLLMAdapter)

    def test_load_llm_adapter_router_uses_short_provider_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake_claude = object()
        fake_gemini = object()
        router_instance = object()
        monkeypatch.setenv("LLM_ROUTER_SHORT_PROVIDER", "gemini")
        monkeypatch.setenv("LLM_ROUTER_PROVIDER_COOLDOWN_SEC", "12.5")
        monkeypatch.setenv("LLM_ROUTER_PROVIDER_MAX_COOLDOWN_SEC", "45")
        monkeypatch.setenv("LLM_ROUTER_AUTH_QUARANTINE_SEC", "90")
        monkeypatch.setenv("LLM_ROUTER_QUOTA_QUARANTINE_SEC", "120")
        router_cls_mock = MagicMock(return_value=router_instance)

        with pytest.MonkeyPatch.context() as local_patch:
            local_patch.setattr(
                "aiprod_adaptation.core.adaptation.llm_router.LLMRouter",
                router_cls_mock,
            )

            original_loader = _load_llm_adapter

            def _fake_loader(name: str, *, router_short_provider: str | None = None) -> object:
                del router_short_provider
                if name == "claude":
                    return fake_claude
                if name == "gemini":
                    return fake_gemini
                return original_loader(name)

            local_patch.setattr("aiprod_adaptation.cli._load_llm_adapter", _fake_loader)

            result = original_loader("router")

        assert result is router_instance
        router_cls_mock.assert_called_once_with(
            claude=fake_claude,
            gemini=fake_gemini,
            short_preference="gemini",
            cooldown_sec=12.5,
            max_cooldown_sec=45.0,
            auth_quarantine_sec=90.0,
            quota_quarantine_sec=120.0,
        )

    def test_load_llm_adapter_router_uses_explicit_short_provider_override(self) -> None:
        fake_claude = object()
        fake_gemini = object()
        router_instance = object()
        router_cls_mock = MagicMock(return_value=router_instance)

        with pytest.MonkeyPatch.context() as local_patch:
            local_patch.setattr(
                "aiprod_adaptation.core.adaptation.llm_router.LLMRouter",
                router_cls_mock,
            )

            original_loader = _load_llm_adapter

            def _fake_loader(name: str, *, router_short_provider: str | None = None) -> object:
                del router_short_provider
                if name == "claude":
                    return fake_claude
                if name == "gemini":
                    return fake_gemini
                return original_loader(name)

            local_patch.setattr("aiprod_adaptation.cli._load_llm_adapter", _fake_loader)

            result = original_loader("router", router_short_provider="gemini")

        assert result is router_instance
        router_cls_mock.assert_called_once_with(
            claude=fake_claude,
            gemini=fake_gemini,
            short_preference="gemini",
            cooldown_sec=300.0,
            max_cooldown_sec=2400.0,
            auth_quarantine_sec=None,
            quota_quarantine_sec=None,
        )


class TestCLIPipeline:
    def test_cli_pipeline_can_emit_router_trace_json(self) -> None:
        from unittest.mock import patch

        class _TraceableRouter:
            def get_trace_history(self) -> list[dict[str, object]]:
                return [
                    {
                        "prompt_profile": "short",
                        "selected_provider": "claude",
                        "result": "success",
                    }
                ]

            def get_token_usage(self) -> tuple[int, int]:
                return 0, 0

        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            out_path = Path(tmp) / "output.json"
            trace_path = Path(tmp) / "router_trace.json"
            in_path.write_text("Alice walked into the room.", encoding="utf-8")
            args = Namespace(
                input=str(in_path),
                title="T",
                output=str(out_path),
                output_format="json",
                llm_adapter="router",
                require_llm=False,
                pipeline_mode="auto",
                router_short_provider="gemini",
                router_trace_output=str(trace_path),
            )
            with patch("aiprod_adaptation.cli._load_llm_adapter") as load_llm:
                load_llm.return_value = _TraceableRouter()
                with patch("aiprod_adaptation.core.engine.run_pipeline") as run_pipeline_mock:
                    run_pipeline_mock.return_value = AIPRODOutput.model_validate(
                        {
                            "title": "T",
                            "episodes": [{"episode_id": "EP01", "scenes": [], "shots": []}],
                        }
                    )
                    assert cmd_pipeline(args) == 0

            payload = json.loads(trace_path.read_text(encoding="utf-8"))
            assert payload["last_trace"]["selected_provider"] == "claude"
            assert payload["trace_history"][0]["prompt_profile"] == "short"

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
            args = parser.parse_args(
                ["pipeline", "--input", str(in_path), "--title", "T", "--output", str(out_path)]
            )
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
            args_p = parser.parse_args(
                ["pipeline", "--input", str(in_path), "--title", "T", "--output", str(pipeline_out)]
            )
            cmd_pipeline(args_p)

            args_s = parser.parse_args(
                ["storyboard", "--input", str(pipeline_out), "--output", str(sb_out)]
            )
            rc = cmd_storyboard(args_s)
            assert rc == 0
            assert sb_out.exists()
            data = json.loads(sb_out.read_text(encoding="utf-8"))
            assert "frames" in data

    def test_cli_storyboard_accepts_reference_pack(self) -> None:
        novel = "Alice walked into the old library and picked up a dusty book."
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            pipeline_out = Path(tmp) / "pipeline.json"
            sb_out = Path(tmp) / "storyboard.json"
            reference_pack_path = Path(tmp) / "reference_pack.json"
            in_path.write_text(novel, encoding="utf-8")

            parser = build_parser()
            args_p = parser.parse_args(
                ["pipeline", "--input", str(in_path), "--title", "T", "--output", str(pipeline_out)]
            )
            cmd_pipeline(args_p)

            pipeline_payload = json.loads(pipeline_out.read_text(encoding="utf-8"))
            first_scene_id = pipeline_payload["episodes"][0]["shots"][0]["scene_id"]
            reference_pack_path.write_text(
                json.dumps(
                    {
                        "scene_locations": {first_scene_id: "old_library"},
                        "locations": {
                            "old_library": {
                                "prompt": "dusty library shelves, amber lamps",
                                "reference_image_urls": ["ref://locations/old_library.png"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            args_s = parser.parse_args(
                [
                    "storyboard",
                    "--input",
                    str(pipeline_out),
                    "--output",
                    str(sb_out),
                    "--reference-pack",
                    str(reference_pack_path),
                ]
            )
            rc = cmd_storyboard(args_s)
            assert rc == 0
            data = json.loads(sb_out.read_text(encoding="utf-8"))
            assert data["frames"][0]["reference_image_url"] == "ref://locations/old_library.png"

    def test_cli_storyboard_can_filter_to_selected_shot(self) -> None:
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
            cmd_pipeline(
                parser.parse_args(
                    [
                        "pipeline",
                        "--input",
                        str(in_path),
                        "--title",
                        "T",
                        "--output",
                        str(pipeline_out),
                    ]
                )
            )
            pipeline_payload = json.loads(pipeline_out.read_text(encoding="utf-8"))
            selected_shot_id = pipeline_payload["episodes"][0]["shots"][0]["shot_id"]

            rc = cmd_storyboard(
                parser.parse_args(
                    [
                        "storyboard",
                        "--input",
                        str(pipeline_out),
                        "--output",
                        str(sb_out),
                        "--shot-id",
                        selected_shot_id,
                    ]
                )
            )
            assert rc == 0
            data = json.loads(sb_out.read_text(encoding="utf-8"))
            assert len(data["frames"]) == 1
            assert data["frames"][0]["shot_id"] == selected_shot_id

    def test_cli_pipeline_llm_init_error_returns_nonzero(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            out_path = Path(tmp) / "output.json"
            in_path.write_text("Alice walked into the room.", encoding="utf-8")
            args = Namespace(
                input=str(in_path),
                title="T",
                output=str(out_path),
                output_format="json",
                llm_adapter="gemini",
                require_llm=False,
                pipeline_mode="auto",
            )
            with patch(
                "aiprod_adaptation.cli._load_llm_adapter",
                side_effect=ValueError("missing key"),
            ):
                assert cmd_pipeline(args) == 1

    def test_cli_pipeline_require_llm_returns_nonzero_on_llm_fallback(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            out_path = Path(tmp) / "output.json"
            in_path.write_text("Alice walked into the room.", encoding="utf-8")
            args = Namespace(
                input=str(in_path),
                title="T",
                output=str(out_path),
                output_format="json",
                llm_adapter="gemini",
                require_llm=True,
                pipeline_mode="auto",
            )
            with patch("aiprod_adaptation.cli._load_llm_adapter") as load_llm:
                load_llm.return_value = object()
                with patch(
                    "aiprod_adaptation.core.engine.run_pipeline",
                    side_effect=ValueError(
                        "LLM extraction produced no scenes; rule-based fallback is disabled."
                    ),
                ):
                    assert cmd_pipeline(args) == 1

    def test_cli_pipeline_passes_router_short_provider_to_loader(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            out_path = Path(tmp) / "output.json"
            in_path.write_text("Alice walked into the room.", encoding="utf-8")
            args = Namespace(
                input=str(in_path),
                title="T",
                output=str(out_path),
                output_format="json",
                llm_adapter="router",
                require_llm=False,
                pipeline_mode="deterministic",
                router_short_provider="gemini",
                max_chars_per_chunk=321,
            )
            with patch("aiprod_adaptation.cli._load_llm_adapter") as load_llm:
                load_llm.return_value = object()
                with patch("aiprod_adaptation.core.engine.run_pipeline") as run_pipeline_mock:
                    run_pipeline_mock.return_value = AIPRODOutput.model_validate(
                        {
                            "title": "T",
                            "episodes": [{"episode_id": "EP01", "scenes": [], "shots": []}],
                        }
                    )
                    assert cmd_pipeline(args) == 0
        load_llm.assert_called_once_with("router", router_short_provider="gemini")
        _, kwargs = run_pipeline_mock.call_args
        assert isinstance(kwargs["budget"], ProductionBudget)
        assert kwargs["budget"].max_chars_per_chunk == 321
        assert kwargs["pipeline_mode"] == "deterministic"

    def test_cli_pipeline_passes_chunk_override_budget_to_engine(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            out_path = Path(tmp) / "output.json"
            in_path.write_text("Alice walked into the room.", encoding="utf-8")
            args = Namespace(
                input=str(in_path),
                title="T",
                output=str(out_path),
                output_format="json",
                llm_adapter="router",
                require_llm=False,
                pipeline_mode="auto",
                router_short_provider=None,
                router_trace_output=None,
                max_chars_per_chunk=222,
            )
            with patch("aiprod_adaptation.cli._load_llm_adapter") as load_llm:
                load_llm.return_value = object()
                with patch("aiprod_adaptation.core.engine.run_pipeline") as run_pipeline_mock:
                    run_pipeline_mock.return_value = AIPRODOutput.model_validate(
                        {
                            "title": "T",
                            "episodes": [{"episode_id": "EP01", "scenes": [], "shots": []}],
                        }
                    )
                    assert cmd_pipeline(args) == 0

        _, kwargs = run_pipeline_mock.call_args
        assert isinstance(kwargs["budget"], ProductionBudget)
        assert kwargs["budget"].max_chars_per_chunk == 222


class TestCLICompare:
    def test_cli_compare_can_emit_router_trace_json(self) -> None:
        from unittest.mock import patch

        class _TraceableRouter:
            def get_trace_history(self) -> list[dict[str, object]]:
                return [
                    {
                        "prompt_profile": "contextual_short",
                        "selected_provider": "gemini",
                        "result": "fallback_success",
                    }
                ]

            def get_token_usage(self) -> tuple[int, int]:
                return 0, 0

        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            out_path = Path(tmp) / "compare.txt"
            trace_path = Path(tmp) / "router_trace.json"
            in_path.write_text("Alice walked into the room.", encoding="utf-8")
            args = Namespace(
                input=str(in_path),
                title="T",
                output=str(out_path),
                llm_adapter="router",
                output_format="text",
                rules_output=None,
                llm_output=None,
                router_short_provider="gemini",
                router_trace_output=str(trace_path),
            )
            pipeline_output = AIPRODOutput.model_validate(
                {
                    "title": "T",
                    "episodes": [{"episode_id": "EP01", "scenes": [], "shots": []}],
                }
            )
            with patch("aiprod_adaptation.cli._load_llm_adapter") as load_llm:
                load_llm.return_value = _TraceableRouter()
                with patch(
                    "aiprod_adaptation.core.engine.run_pipeline",
                    side_effect=[pipeline_output, pipeline_output],
                ):
                    assert cmd_compare(args) == 0

            payload = json.loads(trace_path.read_text(encoding="utf-8"))
            assert payload["last_trace"]["selected_provider"] == "gemini"
            assert payload["trace_history"][0]["prompt_profile"] == "contextual_short"

    def test_cli_compare_writes_summary_file(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            out_path = Path(tmp) / "compare.txt"
            rules_json = Path(tmp) / "rules.json"
            llm_json = Path(tmp) / "llm.json"
            in_path.write_text("Alice walked into the room.", encoding="utf-8")
            args = Namespace(
                input=str(in_path),
                title="T",
                output=str(out_path),
                llm_adapter="gemini",
                output_format="text",
                rules_output=str(rules_json),
                llm_output=str(llm_json),
                max_chars_per_chunk=144,
            )
            rules_output = AIPRODOutput.model_validate(
                {
                    "title": "T",
                    "episodes": [
                        {
                            "episode_id": "EP01",
                            "scenes": [
                                {
                                    "scene_id": "SCN_001",
                                    "characters": ["Alice"],
                                    "location": "Unknown",
                                    "time_of_day": None,
                                    "visual_actions": ["Alice enters the room."],
                                    "dialogues": [],
                                    "emotion": "neutral",
                                }
                            ],
                            "shots": [
                                {
                                    "shot_id": "SHOT_001",
                                    "scene_id": "SCN_001",
                                    "prompt": "Alice enters the room.",
                                    "duration_sec": 3,
                                    "emotion": "neutral",
                                    "shot_type": "medium",
                                    "camera_movement": "static",
                                    "metadata": {},
                                }
                            ],
                        }
                    ],
                }
            )
            llm_output = AIPRODOutput.model_validate(
                {
                    "title": "T",
                    "episodes": [
                        {
                            "episode_id": "EP01",
                            "scenes": [
                                {
                                    "scene_id": "SCN_001",
                                    "characters": ["Alice"],
                                    "location": "Library interior",
                                    "time_of_day": None,
                                    "visual_actions": ["Alice enters the library."],
                                    "dialogues": [],
                                    "emotion": "neutral",
                                }
                            ],
                            "shots": [
                                {
                                    "shot_id": "SHOT_001",
                                    "scene_id": "SCN_001",
                                    "prompt": "Alice enters the library.",
                                    "duration_sec": 3,
                                    "emotion": "neutral",
                                    "shot_type": "medium",
                                    "camera_movement": "static",
                                    "metadata": {},
                                }
                            ],
                        }
                    ],
                }
            )
            with patch("aiprod_adaptation.cli._load_llm_adapter") as load_llm:
                load_llm.return_value = object()
                with patch(
                    "aiprod_adaptation.core.engine.run_pipeline",
                    side_effect=[rules_output, llm_output],
                ) as run_pipeline_mock:
                    assert cmd_compare(args) == 0
            llm_kwargs = run_pipeline_mock.call_args_list[1].kwargs
            assert isinstance(llm_kwargs["budget"], ProductionBudget)
            assert llm_kwargs["budget"].max_chars_per_chunk == 144
            summary = out_path.read_text(encoding="utf-8")
            assert "LLM adapter: gemini" in summary
            assert "Dialogue lines: rules=0, llm=0, delta=0" in summary
            assert "Rules locations: Unknown" in summary
            assert "LLM locations: Library interior" in summary
            assert "Locations only in LLM: Library interior" in summary
            assert json.loads(rules_json.read_text(encoding="utf-8"))["title"] == "T"
            assert json.loads(llm_json.read_text(encoding="utf-8"))["title"] == "T"

    def test_cli_compare_provider_error_returns_nonzero(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            in_path.write_text("Alice walked into the room.", encoding="utf-8")
            args = Namespace(
                input=str(in_path),
                title="T",
                output=None,
                llm_adapter="gemini",
                output_format="text",
                rules_output=None,
                llm_output=None,
            )
            rules_output = AIPRODOutput.model_validate(
                {
                    "title": "T",
                    "episodes": [{"episode_id": "EP01", "scenes": [], "shots": []}],
                }
            )
            with patch("aiprod_adaptation.cli._load_llm_adapter") as load_llm:
                load_llm.return_value = object()
                with patch(
                    "aiprod_adaptation.core.engine.run_pipeline",
                    side_effect=[rules_output, LLMProviderError("Gemini request failed")],
                ):
                    assert cmd_compare(args) == 1

    def test_cli_compare_passes_router_short_provider_to_loader(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            in_path.write_text("Alice walked into the room.", encoding="utf-8")
            args = Namespace(
                input=str(in_path),
                title="T",
                output=None,
                llm_adapter="router",
                output_format="text",
                rules_output=None,
                llm_output=None,
                router_short_provider="gemini",
            )
            pipeline_output = AIPRODOutput.model_validate(
                {
                    "title": "T",
                    "episodes": [{"episode_id": "EP01", "scenes": [], "shots": []}],
                }
            )
            with patch("aiprod_adaptation.cli._load_llm_adapter") as load_llm:
                load_llm.return_value = object()
                with patch(
                    "aiprod_adaptation.core.engine.run_pipeline",
                    side_effect=[pipeline_output, pipeline_output],
                ):
                    assert cmd_compare(args) == 0
        load_llm.assert_called_once_with("router", router_short_provider="gemini")

    def test_cli_compare_writes_json_summary_file(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            out_path = Path(tmp) / "compare.json"
            in_path.write_text("Alice walked into the room.", encoding="utf-8")
            args = Namespace(
                input=str(in_path),
                title="T",
                output=str(out_path),
                llm_adapter="gemini",
                output_format="json",
                rules_output=None,
                llm_output=None,
            )
            rules_output = AIPRODOutput.model_validate(
                {
                    "title": "T",
                    "episodes": [{"episode_id": "EP01", "scenes": [], "shots": []}],
                }
            )
            llm_output = AIPRODOutput.model_validate(
                {
                    "title": "T",
                    "episodes": [{"episode_id": "EP01", "scenes": [], "shots": []}],
                }
            )
            with patch("aiprod_adaptation.cli._load_llm_adapter") as load_llm:
                load_llm.return_value = object()
                with patch(
                    "aiprod_adaptation.core.engine.run_pipeline",
                    side_effect=[rules_output, llm_output],
                ):
                    assert cmd_compare(args) == 0

            payload = json.loads(out_path.read_text(encoding="utf-8"))
            assert payload["title"] == "T"
            assert payload["llm_adapter"] == "gemini"
            assert payload["scene_counts"] == {"rules": 0, "llm": 0, "delta": 0}
            assert payload["shared_scene_diffs"] == []
            assert payload["aligned_scene_diffs"] == []

    def test_cli_pipeline_provider_error_returns_nonzero(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            out_path = Path(tmp) / "output.json"
            in_path.write_text("Alice walked into the room.", encoding="utf-8")
            args = Namespace(
                input=str(in_path),
                title="T",
                output=str(out_path),
                output_format="json",
                llm_adapter="gemini",
                require_llm=False,
                pipeline_mode="auto",
            )
            with patch("aiprod_adaptation.cli._load_llm_adapter") as load_llm:
                load_llm.return_value = object()
                with patch(
                    "aiprod_adaptation.core.engine.run_pipeline",
                    side_effect=LLMProviderError("Gemini request failed: quota exceeded"),
                ):
                    assert cmd_pipeline(args) == 1


# ---------------------------------------------------------------------------
# PC-03 — CLI adapters de prod
# ---------------------------------------------------------------------------

_NOVEL_TEXT = (
    "Alice walked into the old library and picked up a dusty book. "
    "Later, in the garden, she read quietly while birds sang above."
)


class TestCLIAdapters:
    def test_cli_image_adapter_null_is_default(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["storyboard", "--input", "in.json", "--output", "out.json"])
        assert args.image_adapter == "null"

    def test_cli_image_adapter_invalid_name_exits_nonzero(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["storyboard", "--input", "in.json", "--output", "out.json",
                               "--image-adapter", "nonexistent"])
        assert exc.value.code != 0

    def test_cli_schedule_command_outputs_scheduler_result_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            in_txt = Path(tmp) / "in.txt"
            ir_json = Path(tmp) / "ir.json"
            out_dir = Path(tmp) / "result"
            in_txt.write_text(_NOVEL_TEXT, encoding="utf-8")

            parser = build_parser()
            cmd_pipeline(parser.parse_args(["pipeline", "--input", str(in_txt),
                                            "--title", "T", "--output", str(ir_json)]))
            rc = cmd_schedule(parser.parse_args([
                "schedule", "--input", str(ir_json), "--output", str(out_dir),
                "--image-adapter", "null", "--video-adapter", "null", "--audio-adapter", "null",
            ]))
            assert rc == 0
            assert (out_dir / "storyboard.json").exists()
            assert (out_dir / "video.json").exists()
            assert (out_dir / "production.json").exists()
            assert (out_dir / "metrics.json").exists()

    def test_cli_schedule_saves_storyboard_video_production_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            in_txt = Path(tmp) / "in.txt"
            ir_json = Path(tmp) / "ir.json"
            out_dir = Path(tmp) / "result2"
            in_txt.write_text(_NOVEL_TEXT, encoding="utf-8")

            parser = build_parser()
            cmd_pipeline(parser.parse_args(["pipeline", "--input", str(in_txt),
                                            "--title", "T2", "--output", str(ir_json)]))
            cmd_schedule(parser.parse_args([
                "schedule", "--input", str(ir_json), "--output", str(out_dir),
            ]))
            sb_data = json.loads((out_dir / "storyboard.json").read_text(encoding="utf-8"))
            assert "frames" in sb_data
            vid_data = json.loads((out_dir / "video.json").read_text(encoding="utf-8"))
            assert "clips" in vid_data

    def test_cli_schedule_output_path_is_always_treated_as_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            in_txt = Path(tmp) / "in.txt"
            ir_json = Path(tmp) / "ir.json"
            out_dir = Path(tmp) / "result.json"
            in_txt.write_text(_NOVEL_TEXT, encoding="utf-8")

            parser = build_parser()
            cmd_pipeline(
                parser.parse_args(
                    ["pipeline", "--input", str(in_txt), "--title", "T3", "--output", str(ir_json)]
                )
            )
            rc = cmd_schedule(
                parser.parse_args(
                    ["schedule", "--input", str(ir_json), "--output", str(out_dir)]
                )
            )

            assert rc == 0
            assert out_dir.is_dir()
            assert (out_dir / "production.json").exists()

    def test_cli_schedule_can_filter_to_selected_shot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            in_txt = Path(tmp) / "in.txt"
            ir_json = Path(tmp) / "ir.json"
            out_dir = Path(tmp) / "result_filtered"
            in_txt.write_text(_NOVEL_TEXT, encoding="utf-8")

            parser = build_parser()
            cmd_pipeline(
                parser.parse_args(
                    ["pipeline", "--input", str(in_txt), "--title", "T", "--output", str(ir_json)]
                )
            )
            payload = json.loads(ir_json.read_text(encoding="utf-8"))
            selected_shot_id = payload["episodes"][0]["shots"][0]["shot_id"]

            rc = cmd_schedule(
                parser.parse_args(
                    [
                        "schedule",
                        "--input",
                        str(ir_json),
                        "--output",
                        str(out_dir),
                        "--image-adapter",
                        "null",
                        "--video-adapter",
                        "null",
                        "--audio-adapter",
                        "null",
                        "--shot-id",
                        selected_shot_id,
                    ]
                )
            )

            assert rc == 0
            storyboard_data = json.loads((out_dir / "storyboard.json").read_text(encoding="utf-8"))
            video_data = json.loads((out_dir / "video.json").read_text(encoding="utf-8"))
            production_data = json.loads((out_dir / "production.json").read_text(encoding="utf-8"))
            assert len(storyboard_data["frames"]) == 1
            assert len(video_data["clips"]) == 1
            assert len(production_data["timeline"]) == 1

    def test_cli_schedule_dry_run_flag_accepted_by_parser(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "schedule", "--input", "x.json", "--output", "out",
            "--image-adapter", "null", "--video-adapter", "null",
            "--audio-adapter", "null", "--dry-run",
        ])
        assert args.dry_run is True

    def test_cli_schedule_budget_cap_flag_accepted_by_parser(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "schedule", "--input", "x.json", "--output", "out",
            "--image-adapter", "null", "--video-adapter", "null",
            "--audio-adapter", "null", "--budget-cap", "2.50",
        ])
        assert args.budget_cap == pytest.approx(2.50)

    def test_cli_schedule_dry_run_returns_zero_without_api_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            in_txt = Path(tmp) / "in.txt"
            ir_json = Path(tmp) / "ir.json"
            out_dir = Path(tmp) / "result_dry"
            in_txt.write_text(_NOVEL_TEXT, encoding="utf-8")
            parser = build_parser()
            cmd_pipeline(
                parser.parse_args(
                    ["pipeline", "--input", str(in_txt), "--title", "T", "--output", str(ir_json)]
                )
            )
            rc = cmd_schedule(
                parser.parse_args([
                    "schedule",
                    "--input", str(ir_json),
                    "--output", str(out_dir),
                    "--image-adapter", "replicate",
                    "--video-adapter", "null",
                    "--audio-adapter", "null",
                    "--dry-run",
                ])
            )
            assert rc == 0
            # output directory must NOT have been created (no adapter calls)
            assert not out_dir.exists()

    def test_cli_schedule_dry_run_reports_prepass_characters(self, capsys: pytest.CaptureFixture[str]) -> None:
        """dry-run must list which characters would be prepass'd vs skipped."""
        import json as _json
        import tempfile as _tmp
        with _tmp.TemporaryDirectory() as tmp:
            in_txt = Path(tmp) / "in.txt"
            ir_json = Path(tmp) / "ir.json"
            ref_json = Path(tmp) / "ref.json"
            out_dir = Path(tmp) / "result"
            in_txt.write_text(_NOVEL_TEXT, encoding="utf-8")
            parser = build_parser()
            cmd_pipeline(
                parser.parse_args(
                    ["pipeline", "--input", str(in_txt), "--title", "T", "--output", str(ir_json)]
                )
            )
            # Build reference pack with at least one character that matches IR subjects
            from aiprod_adaptation.core.io import load_output
            from aiprod_adaptation.image_gen.character_prepass import _unique_characters
            output = load_output(str(ir_json))
            chars = _unique_characters(output)
            if not chars:
                return  # no subjects in this novel — trivially ok
            first_char = chars[0]
            ref_pack = {
                "style_block": "",
                "characters": {
                    first_char: {"prompt": f"canonical for {first_char}", "reference_image_urls": []}
                },
                "locations": {},
            }
            ref_json.write_text(_json.dumps(ref_pack), encoding="utf-8")
            rc = cmd_schedule(
                parser.parse_args([
                    "schedule",
                    "--input", str(ir_json),
                    "--output", str(out_dir),
                    "--image-adapter", "null",
                    "--video-adapter", "null",
                    "--audio-adapter", "null",
                    "--reference-pack", str(ref_json),
                    "--dry-run",
                ])
            )
            assert rc == 0
            captured = capsys.readouterr()
            assert "Prepass resolved" in captured.err
            assert first_char in captured.err

    def test_cli_schedule_dry_run_remove_background_no_canonical_returns_1(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--remove-background + --dry-run must return exit code 1 when no character
        has a canonical in the reference pack — prevents wasted paid runs."""
        import json as _json
        import tempfile as _tmp
        with _tmp.TemporaryDirectory() as tmp:
            in_txt = Path(tmp) / "in.txt"
            ir_json = Path(tmp) / "ir.json"
            ref_json = Path(tmp) / "ref.json"
            out_dir = Path(tmp) / "result"
            in_txt.write_text(_NOVEL_TEXT, encoding="utf-8")
            parser = build_parser()
            cmd_pipeline(
                parser.parse_args(
                    ["pipeline", "--input", str(in_txt), "--title", "T", "--output", str(ir_json)]
                )
            )
            from aiprod_adaptation.core.io import load_output
            from aiprod_adaptation.image_gen.character_prepass import _unique_characters
            output = load_output(str(ir_json))
            chars = _unique_characters(output)
            if not chars:
                return  # no subjects — can't test this path
            # Empty reference pack — no canonical for any character
            ref_pack = {"style_block": "", "characters": {}, "locations": {}}
            ref_json.write_text(_json.dumps(ref_pack), encoding="utf-8")
            rc = cmd_schedule(
                parser.parse_args([
                    "schedule",
                    "--input", str(ir_json),
                    "--output", str(out_dir),
                    "--image-adapter", "openai",
                    "--video-adapter", "null",
                    "--audio-adapter", "null",
                    "--reference-pack", str(ref_json),
                    "--remove-background",
                    "--dry-run",
                ])
            )
            assert rc == 1, "dry-run must return 1 when --remove-background has no canonical"
            captured = capsys.readouterr()
            assert "ERROR" in captured.err

    def test_cli_schedule_dry_run_reports_paid_adapters(self, capsys: pytest.CaptureFixture[str]) -> None:
        """dry-run must flag every active paid adapter (image/video/audio) with [PAID]."""
        with tempfile.TemporaryDirectory() as tmp:
            in_txt = Path(tmp) / "in.txt"
            ir_json = Path(tmp) / "ir.json"
            out_dir = Path(tmp) / "result"
            in_txt.write_text(_NOVEL_TEXT, encoding="utf-8")
            parser = build_parser()
            cmd_pipeline(
                parser.parse_args(
                    ["pipeline", "--input", str(in_txt), "--title", "T", "--output", str(ir_json)]
                )
            )
            rc = cmd_schedule(
                parser.parse_args([
                    "schedule",
                    "--input", str(ir_json),
                    "--output", str(out_dir),
                    "--image-adapter", "openai",
                    "--video-adapter", "runway",
                    "--audio-adapter", "elevenlabs",
                    "--dry-run",
                ])
            )
            assert rc == 0
            captured = capsys.readouterr()
            assert "openai [PAID]" in captured.err
            assert "runway [PAID]" in captured.err
            assert "elevenlabs [PAID]" in captured.err

    def test_cli_schedule_dry_run_reports_all_cost_lines(self, capsys: pytest.CaptureFixture[str]) -> None:
        """dry-run report must include image, video, audio and total cost lines."""
        with tempfile.TemporaryDirectory() as tmp:
            in_txt = Path(tmp) / "in.txt"
            ir_json = Path(tmp) / "ir.json"
            out_dir = Path(tmp) / "result"
            in_txt.write_text(_NOVEL_TEXT, encoding="utf-8")
            parser = build_parser()
            cmd_pipeline(
                parser.parse_args(
                    ["pipeline", "--input", str(in_txt), "--title", "T", "--output", str(ir_json)]
                )
            )
            rc = cmd_schedule(
                parser.parse_args([
                    "schedule",
                    "--input", str(ir_json),
                    "--output", str(out_dir),
                    "--image-adapter", "openai",
                    "--video-adapter", "runway",
                    "--audio-adapter", "openai",
                    "--dry-run",
                ])
            )
            assert rc == 0
            captured = capsys.readouterr()
            assert "Est. image cost" in captured.err
            assert "Est. video cost" in captured.err
            assert "Est. audio cost" in captured.err
            assert "Est. TOTAL" in captured.err
            assert "DRY-RUN OK" in captured.err

    def test_cli_schedule_dry_run_no_output_created_for_any_paid_adapter(self) -> None:
        """dry-run must NEVER create output files regardless of which adapters are active."""
        with tempfile.TemporaryDirectory() as tmp:
            in_txt = Path(tmp) / "in.txt"
            ir_json = Path(tmp) / "ir.json"
            out_dir = Path(tmp) / "result_paid"
            in_txt.write_text(_NOVEL_TEXT, encoding="utf-8")
            parser = build_parser()
            cmd_pipeline(
                parser.parse_args(
                    ["pipeline", "--input", str(in_txt), "--title", "T", "--output", str(ir_json)]
                )
            )
            rc = cmd_schedule(
                parser.parse_args([
                    "schedule",
                    "--input", str(ir_json),
                    "--output", str(out_dir),
                    "--image-adapter", "openai",
                    "--video-adapter", "runway",
                    "--audio-adapter", "elevenlabs",
                    "--dry-run",
                ])
            )
            assert rc == 0
            assert not out_dir.exists(), "dry-run must never write output — credits not consumed"

_NOVEL_SHORT = (
    "Alice walked into the old library and picked up a dusty book. "
    "Later, in the garden, she read quietly while birds sang above."
)


class TestCLIPipelineFormats:
    def _run_pipeline_with_format(self, fmt: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "input.txt"
            out_path = Path(tmp) / "output.out"
            in_path.write_text(_NOVEL_SHORT, encoding="utf-8")
            parser = build_parser()
            args = parser.parse_args([
                "pipeline", "--input", str(in_path), "--title", "T",
                "--output", str(out_path), "--output-format", fmt,
            ])
            rc = cmd_pipeline(args)
            content = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
            return rc, content

    def test_output_format_csv_exits_zero(self) -> None:
        rc, _ = self._run_pipeline_with_format("csv")
        assert rc == 0

    def test_output_format_csv_produces_non_empty_file(self) -> None:
        _, content = self._run_pipeline_with_format("csv")
        assert len(content) > 0

    def test_output_format_json_flat_exits_zero(self) -> None:
        rc, _ = self._run_pipeline_with_format("json-flat")
        assert rc == 0

    def test_output_format_json_flat_produces_valid_json(self) -> None:
        _, content = self._run_pipeline_with_format("json-flat")
        data = json.loads(content)
        assert isinstance(data, (list, dict))


class TestCLIAdapterLoaders:
    def test_load_llm_adapter_null_returns_null_adapter(self) -> None:
        from aiprod_adaptation.cli import _load_llm_adapter
        from aiprod_adaptation.core.adaptation.llm_adapter import NullLLMAdapter
        assert isinstance(_load_llm_adapter("null"), NullLLMAdapter)

    def test_load_image_adapter_null_returns_null_adapter(self) -> None:
        from aiprod_adaptation.cli import _load_image_adapter
        from aiprod_adaptation.image_gen.image_adapter import NullImageAdapter
        assert isinstance(_load_image_adapter("null"), NullImageAdapter)

    def test_load_image_adapter_openai_returns_openai_adapter(self) -> None:
        from aiprod_adaptation.cli import _load_image_adapter
        from aiprod_adaptation.image_gen.openai_image_adapter import OpenAIImageAdapter
        assert isinstance(_load_image_adapter("openai"), OpenAIImageAdapter)

    def test_load_image_adapter_runway_returns_runway_adapter(self) -> None:
        from aiprod_adaptation.cli import _load_image_adapter
        from aiprod_adaptation.image_gen.runway_image_adapter import RunwayImageAdapter
        assert isinstance(_load_image_adapter("runway"), RunwayImageAdapter)

    def test_load_video_adapter_null_returns_null_adapter(self) -> None:
        from aiprod_adaptation.cli import _load_video_adapter
        from aiprod_adaptation.video_gen.video_adapter import NullVideoAdapter
        assert isinstance(_load_video_adapter("null"), NullVideoAdapter)

    def test_load_audio_adapter_null_returns_null_adapter(self) -> None:
        from aiprod_adaptation.cli import _load_audio_adapter
        from aiprod_adaptation.post_prod.audio_adapter import NullAudioAdapter
        assert isinstance(_load_audio_adapter("null"), NullAudioAdapter)

    def test_load_audio_adapter_runway_returns_runway_adapter(self) -> None:
        from aiprod_adaptation.cli import _load_audio_adapter
        from aiprod_adaptation.post_prod.runway_tts_adapter import RunwayTTSAdapter
        assert isinstance(_load_audio_adapter("runway"), RunwayTTSAdapter)

    def test_load_image_adapter_nonexistent_raises(self) -> None:
        from unittest.mock import patch

        import pytest

        from aiprod_adaptation.cli import _load_image_adapter
        with patch("importlib.import_module", side_effect=ModuleNotFoundError("no module")):
            with pytest.raises(ModuleNotFoundError):
                _load_image_adapter("flux")

    def test_load_audio_adapter_nonexistent_raises(self) -> None:
        from unittest.mock import patch

        import pytest

        from aiprod_adaptation.cli import _load_audio_adapter
        with patch("importlib.import_module", side_effect=ModuleNotFoundError("no module")):
            with pytest.raises(ModuleNotFoundError):
                _load_audio_adapter("elevenlabs")
