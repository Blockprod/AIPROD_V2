from __future__ import annotations

import hashlib
import json
from pathlib import Path

from aiprod_adaptation.models.schema import AIPRODOutput, IRVersion


def migrate_ir_file(input_path: Path, output_path: Path, rules_hash: str) -> AIPRODOutput:
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Legacy IR must be a JSON object.")
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    previous = raw.get("ir_version")
    visual_bible_hash = "no_vb"
    if isinstance(previous, dict) and isinstance(previous.get("visual_bible_hash"), str):
        visual_bible_hash = previous["visual_bible_hash"]
    raw["ir_version"] = IRVersion(
        compiler_version="6.0.0-migration",
        visual_bible_hash=visual_bible_hash,
        rules_hash=rules_hash,
        text_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16],
    ).model_dump(mode="json")
    migrated = AIPRODOutput.model_validate(raw)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(migrated.model_dump_json(indent=2), encoding="utf-8")
    return migrated
