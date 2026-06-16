from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from aiprod_adaptation.core.adaptation.llm_adapter import (
    LLMFailureCategory,
    LLMProviderError,
)
from aiprod_adaptation.core.adaptation.llm_router import LLMRouter
from aiprod_adaptation.core.rules.cinematography_catalog import (
    CAMERA_MOVEMENT_RULES,
    CAMERA_MOVEMENTS,
    SHOT_TYPE_RULES,
    SHOT_TYPES,
    resolve_first_match,
)
from aiprod_adaptation.models.migration import migrate_ir_file
from aiprod_adaptation.models.schema import AIPRODOutput, Shot, validated_model_update
from aiprod_adaptation.production.certification import write_certification
from aiprod_adaptation.production.receipt import (
    ReceiptValidationError,
    build_receipt,
    validate_receipt,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _minimal_ir_payload(schema_version: str = "6.0") -> dict[str, Any]:
    return {
        "title": "Contract Test",
        "episodes": [
            {
                "episode_id": "EP01",
                "scenes": [
                    {
                        "scene_id": "SCN_001",
                        "characters": ["Alice"],
                        "location": "Archive",
                        "visual_actions": ["Alice walks through the archive."],
                        "dialogues": [],
                        "emotion": "neutral",
                    }
                ],
                "shots": [
                    {
                        "shot_id": "EP01_SCN_001_SH001",
                        "scene_id": "SCN_001",
                        "prompt": "Alice walks through the archive.",
                        "duration_sec": 5,
                        "emotion": "neutral",
                        "shot_type": "medium",
                        "camera_movement": "static",
                    }
                ],
            }
        ],
        "ir_version": {
            "schema_version": schema_version,
            "compiler_version": "6.0.0",
            "visual_bible_hash": "no_vb",
            "rules_hash": "rules",
            "text_hash": "text",
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _sign_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    contract = {key: value for key, value in payload.items() if key != "receipt_id"}
    canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    return {**contract, "receipt_id": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


class TestIRV6Strictness:
    def test_unknown_fields_are_rejected(self) -> None:
        payload = _minimal_ir_payload()
        payload["unexpected"] = True

        with pytest.raises(ValidationError):
            AIPRODOutput.model_validate(payload)

    def test_implicit_coercion_is_rejected(self) -> None:
        shot_payload = _minimal_ir_payload()["episodes"][0]["shots"][0]
        shot_payload["duration_sec"] = "5"

        with pytest.raises(ValidationError):
            Shot.model_validate(shot_payload)

    def test_models_are_frozen_and_updates_are_revalidated(self) -> None:
        shot = AIPRODOutput.model_validate(_minimal_ir_payload()).episodes[0].shots[0]

        with pytest.raises(ValidationError):
            shot.duration_sec = 6
        with pytest.raises(ValidationError):
            validated_model_update(shot, duration_sec="5")

    def test_legacy_ir_migrates_to_v6_without_dropping_fields(self, tmp_path: Path) -> None:
        legacy = _minimal_ir_payload()
        del legacy["ir_version"]
        input_path = tmp_path / "legacy.json"
        output_path = tmp_path / "v6.json"
        _write_json(input_path, legacy)

        migrated = migrate_ir_file(input_path, output_path, rules_hash="rules-hash")
        written = json.loads(output_path.read_text(encoding="utf-8"))

        assert migrated.ir_version is not None
        assert migrated.ir_version.schema_version == "6.0"
        assert written["episodes"][0]["scenes"][0]["location"] == "Archive"


class TestDeterministicCompilerBoundary:
    def test_pipeline_output_is_byte_identical_across_hash_seeds(self) -> None:
        code = textwrap.dedent(
            """
            from aiprod_adaptation.core.engine import run_pipeline

            text = "Alice walked into the archive. She opened the metal drawer."
            output = run_pipeline(text, "Determinism", pipeline_mode="deterministic")
            print(output.model_dump_json())
            """
        )
        outputs: list[bytes] = []
        for seed in ("1", "17", "97"):
            env = {**os.environ, "PYTHONHASHSEED": seed}
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=_repo_root(),
                env=env,
                check=True,
                capture_output=True,
            )
            outputs.append(result.stdout)

        assert outputs[0] == outputs[1] == outputs[2]


class TestCinematographyCatalog:
    def test_catalog_declares_contract_cardinality(self) -> None:
        assert len(SHOT_TYPES) == 11
        assert len(CAMERA_MOVEMENTS) == 16

    def test_every_documented_value_is_generable(self) -> None:
        generated_shot_types = {
            resolve_first_match(keywords[0], SHOT_TYPE_RULES, default="medium")
            for _, keywords in SHOT_TYPE_RULES
        }
        generated_shot_types.add(resolve_first_match("plain coverage", SHOT_TYPE_RULES, default="medium"))
        generated_movements = {
            resolve_first_match(keywords[0], CAMERA_MOVEMENT_RULES, default="static")
            for _, keywords in CAMERA_MOVEMENT_RULES
        }
        generated_movements.add(resolve_first_match("plain locked camera", CAMERA_MOVEMENT_RULES, default="static"))

        assert list(SHOT_TYPES) == [value for value in SHOT_TYPES if value in generated_shot_types]
        assert list(CAMERA_MOVEMENTS) == [value for value in CAMERA_MOVEMENTS if value in generated_movements]

    def test_first_match_wins_for_overlapping_keywords(self) -> None:
        assert resolve_first_match("extreme close face detail", SHOT_TYPE_RULES, "medium") == "extreme_close_up"
        assert resolve_first_match("whip pan as camera pans", CAMERA_MOVEMENT_RULES, "static") == "whip_pan"


class TestProductionReceipt:
    def test_receipt_validates_matching_inputs(self, tmp_path: Path) -> None:
        root = _repo_root()
        ir_path = tmp_path / "ir.json"
        storyboard_path = tmp_path / "storyboard.json"
        receipt_path = tmp_path / "receipt.json"
        _write_json(ir_path, _minimal_ir_payload())
        _write_json(storyboard_path, {"frames": [{"shot_id": "S01"}]})

        receipt = build_receipt(
            root=root,
            ir_path=ir_path,
            storyboard_path=storyboard_path,
            shot_ids=["S01"],
            backend="replicate",
            budget_cap_usd=25.0,
            estimated_cost_usd=4.0,
        )
        _write_json(receipt_path, receipt)

        authorization = validate_receipt(
            receipt_path,
            root=root,
            ir_path=ir_path,
            storyboard_path=storyboard_path,
            shot_ids=["S01"],
            backend="replicate",
            budget_cap_usd=25.0,
        )

        assert authorization.receipt_id == receipt["receipt_id"]
        assert authorization.estimated_cost_usd == 4.0

    def test_receipt_blocks_legacy_ir_and_changed_storyboard(self, tmp_path: Path) -> None:
        root = _repo_root()
        ir_path = tmp_path / "ir.json"
        storyboard_path = tmp_path / "storyboard.json"
        receipt_path = tmp_path / "receipt.json"
        legacy = _minimal_ir_payload()
        del legacy["ir_version"]
        _write_json(ir_path, legacy)
        _write_json(storyboard_path, {"frames": [{"shot_id": "S01"}]})

        with pytest.raises(ReceiptValidationError):
            build_receipt(
                root=root,
                ir_path=ir_path,
                storyboard_path=storyboard_path,
                shot_ids=["S01"],
                backend="replicate",
                budget_cap_usd=25.0,
                estimated_cost_usd=4.0,
            )

        _write_json(ir_path, _minimal_ir_payload())
        receipt = build_receipt(
            root=root,
            ir_path=ir_path,
            storyboard_path=storyboard_path,
            shot_ids=["S01"],
            backend="replicate",
            budget_cap_usd=25.0,
            estimated_cost_usd=4.0,
        )
        _write_json(receipt_path, receipt)
        _write_json(storyboard_path, {"frames": [{"shot_id": "S02"}]})

        with pytest.raises(ReceiptValidationError, match="storyboard_sha256"):
            validate_receipt(
                receipt_path,
                root=root,
                ir_path=ir_path,
                storyboard_path=storyboard_path,
                shot_ids=["S01"],
                backend="replicate",
                budget_cap_usd=25.0,
            )

    def test_receipt_blocks_expired_or_over_budget_execution(self, tmp_path: Path) -> None:
        root = _repo_root()
        ir_path = tmp_path / "ir.json"
        storyboard_path = tmp_path / "storyboard.json"
        receipt_path = tmp_path / "receipt.json"
        _write_json(ir_path, _minimal_ir_payload())
        _write_json(storyboard_path, {"frames": [{"shot_id": "S01"}]})
        receipt = build_receipt(
            root=root,
            ir_path=ir_path,
            storyboard_path=storyboard_path,
            shot_ids=["S01"],
            backend="replicate",
            budget_cap_usd=25.0,
            estimated_cost_usd=4.0,
        )

        expired = _sign_receipt({**receipt, "expires_at": "2000-01-01T00:00:00+00:00"})
        _write_json(receipt_path, expired)
        with pytest.raises(ReceiptValidationError, match="expired"):
            validate_receipt(
                receipt_path,
                root=root,
                ir_path=ir_path,
                storyboard_path=storyboard_path,
                shot_ids=["S01"],
                backend="replicate",
                budget_cap_usd=25.0,
            )

        _write_json(receipt_path, receipt)
        with pytest.raises(ReceiptValidationError, match="exceeds receipt cap"):
            validate_receipt(
                receipt_path,
                root=root,
                ir_path=ir_path,
                storyboard_path=storyboard_path,
                shot_ids=["S01"],
                backend="replicate",
                budget_cap_usd=26.0,
            )


class TestCertification:
    def test_offline_certification_marks_cloud_as_not_certified(self, tmp_path: Path) -> None:
        output_path = tmp_path / "certification.json"
        certification = write_certification(output_path)
        written = json.loads(output_path.read_text(encoding="utf-8"))

        assert written == certification
        assert certification["smoke_budget_usd"] == 25.0
        assert certification["capabilities"]["core.compiler"]["status"] == "certified"
        assert certification["capabilities"]["video.runway"]["status"] in {
            "contract-tested",
            "unavailable",
        }


class TestLLMRouterQuarantine:
    def test_quarantined_provider_is_not_reused_as_fallback(self) -> None:
        now = [100.0]
        claude = MagicMock()
        gemini = MagicMock()
        claude.generate_json.side_effect = [
            LLMProviderError("claude auth failed", category=LLMFailureCategory.AUTH),
        ]
        gemini.generate_json.return_value = {"scenes": [{"location": "gemini"}]}
        router = LLMRouter(
            claude,
            gemini,
            token_threshold=1000,
            cooldown_sec=10.0,
            max_cooldown_sec=40.0,
            auth_quarantine_sec=160.0,
            time_fn=lambda: now[0],
        )

        assert router.generate_json("short text") == {"scenes": [{"location": "gemini"}]}
        assert router.generate_json("short text again") == {"scenes": [{"location": "gemini"}]}

        assert claude.generate_json.call_count == 1
        assert gemini.generate_json.call_count == 2
