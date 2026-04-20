"""
AIPROD ADAPTATION ENGINE — Entry point
Orchestrates the four deterministic passes in strict order:
  PASS 1 (segment) → PASS 2 (transform visuals) → PASS 3 (atomize shots) → PASS 4 (compile)
"""

from __future__ import annotations

from aiprod_adaptation.core.pass1_segment import segment
from aiprod_adaptation.core.pass2_visual import transform_visuals
from aiprod_adaptation.core.pass3_shots import atomize_shots
from aiprod_adaptation.core.pass4_compile import compile_output
from aiprod_adaptation.models.schema import AIPRODOutput


def run_pipeline(text: str, title: str) -> AIPRODOutput:
    """Strict deterministic pipeline: PASS 1 → PASS 2 → PASS 3 → PASS 4."""
    scenes_raw   = segment(text)
    scenes_visual = transform_visuals(scenes_raw)
    shots_raw     = atomize_shots(scenes_visual)
    return compile_output(title, scenes_visual, shots_raw)
