"""Dry-run : affiche les 35 prompts complets + char refs avant Phase C."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.shot_pipeline_v4 import (
    _build_stylization_prompt,
    _resolve_char_ref,
    CHAR_REFS_DIR,
)

sb = json.loads((ROOT / "production/storyboard.json").read_text(encoding="utf-8"))

for s in sb["shots"]:
    sid = s["shot_id"]
    shot_type = s.get("shot_type", "?")
    scene_id = s.get("scene_id", "")
    prompt = _build_stylization_prompt(s, sb)
    pc = s.get("primary_character")
    ref = _resolve_char_ref(pc, CHAR_REFS_DIR, s) if pc else None
    ref_label = ref.name if ref else "N/A (env shot)"
    if ref and "character_bodies" in str(ref):
        ref_source = "Phase-B corps"
    elif ref and "character_faces" in str(ref):
        ref_source = "Phase-B faces"
    elif ref:
        ref_source = "Phase-A FALLBACK"
    else:
        ref_source = "-"

    print("=" * 80)
    print(sid + "  |  " + scene_id + "  |  " + shot_type)
    print("CHAR REF [" + ref_source + "]: " + ref_label)
    print("PROMPT:\n" + prompt)
    print()
