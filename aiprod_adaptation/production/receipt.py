from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

RECEIPT_VERSION = "1"
MAX_RECEIPT_AGE = timedelta(hours=24)
PAID_BACKENDS = frozenset({"replicate"})


class ReceiptValidationError(RuntimeError):
    """The production receipt is missing, stale, or does not match the run."""


@dataclass(frozen=True)
class ExecutionAuthorization:
    receipt_id: str
    budget_cap_usd: float
    estimated_cost_usd: float


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_rules(root: Path) -> str:
    digest = hashlib.sha256()
    rules_root = root / "aiprod_adaptation" / "core" / "rules"
    for path in sorted(rules_root.rglob("*.py"), key=lambda item: item.as_posix()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def build_receipt(
    *,
    root: Path,
    ir_path: Path,
    storyboard_path: Path,
    shot_ids: list[str],
    backend: str,
    budget_cap_usd: float,
    estimated_cost_usd: float,
) -> dict[str, Any]:
    _validate_v6_ir(ir_path)
    if budget_cap_usd < 0 or estimated_cost_usd < 0:
        raise ReceiptValidationError("Budget and estimated cost must be non-negative.")
    if estimated_cost_usd > budget_cap_usd:
        raise ReceiptValidationError(
            f"Estimated cost ${estimated_cost_usd:.2f} exceeds cap ${budget_cap_usd:.2f}."
        )
    issued_at = datetime.now(UTC)
    contract = {
        "receipt_version": RECEIPT_VERSION,
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + MAX_RECEIPT_AGE).isoformat(),
        "ir_path": str(ir_path.resolve()),
        "ir_sha256": sha256_file(ir_path),
        "storyboard_path": str(storyboard_path.resolve()),
        "storyboard_sha256": sha256_file(storyboard_path),
        "rules_sha256": sha256_rules(root),
        "shot_ids": list(shot_ids),
        "backend": backend,
        "budget_cap_usd": round(budget_cap_usd, 4),
        "estimated_cost_usd": round(estimated_cost_usd, 4),
    }
    canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    return {**contract, "receipt_id": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def validate_receipt(
    receipt_path: Path,
    *,
    root: Path,
    ir_path: Path,
    storyboard_path: Path,
    shot_ids: list[str],
    backend: str,
    budget_cap_usd: float,
) -> ExecutionAuthorization:
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReceiptValidationError(f"Receipt unreadable: {receipt_path}") from exc
    if not isinstance(payload, dict):
        raise ReceiptValidationError("Receipt must be a JSON object.")

    required = {
        "receipt_version", "issued_at", "expires_at", "ir_sha256",
        "storyboard_sha256", "rules_sha256", "shot_ids", "backend",
        "budget_cap_usd", "estimated_cost_usd", "receipt_id",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ReceiptValidationError(f"Receipt fields missing: {missing}")
    contract = {key: value for key, value in payload.items() if key != "receipt_id"}
    canonical = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    expected_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if payload["receipt_id"] != expected_id:
        raise ReceiptValidationError("Receipt integrity check failed.")
    try:
        expires_at = datetime.fromisoformat(str(payload["expires_at"]))
    except ValueError as exc:
        raise ReceiptValidationError("Receipt expiry is invalid.") from exc
    if expires_at.tzinfo is None or datetime.now(UTC) >= expires_at.astimezone(UTC):
        raise ReceiptValidationError("Receipt has expired.")

    _validate_v6_ir(ir_path)
    comparisons = {
        "ir_sha256": sha256_file(ir_path),
        "storyboard_sha256": sha256_file(storyboard_path),
        "rules_sha256": sha256_rules(root),
        "shot_ids": shot_ids,
        "backend": backend,
    }
    for key, actual in comparisons.items():
        if payload[key] != actual:
            raise ReceiptValidationError(f"Receipt mismatch for {key}.")
    receipt_budget = float(payload["budget_cap_usd"])
    if budget_cap_usd > receipt_budget:
        raise ReceiptValidationError(
            f"Requested cap ${budget_cap_usd:.2f} exceeds receipt cap ${receipt_budget:.2f}."
        )
    return ExecutionAuthorization(
        receipt_id=str(payload["receipt_id"]),
        budget_cap_usd=receipt_budget,
        estimated_cost_usd=float(payload["estimated_cost_usd"]),
    )


def _validate_v6_ir(path: Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReceiptValidationError(f"IR unreadable: {path}") from exc
    if not isinstance(payload, dict):
        raise ReceiptValidationError("IR must be a JSON object.")
    version = payload.get("ir_version")
    if not isinstance(version, dict) or version.get("schema_version") != "6.0":
        raise ReceiptValidationError("Production execution requires strict IR schema_version 6.0.")
