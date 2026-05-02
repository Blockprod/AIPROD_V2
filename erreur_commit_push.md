Run ruff check aiprod_adaptation/
  ruff check aiprod_adaptation/
  shell: /usr/bin/bash -e {0}
  env:
    pythonLocation: /opt/hostedtoolcache/Python/3.11.15/x64
    PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.11.15/x64/lib/pkgconfig
    Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.11.15/x64
    Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.11.15/x64
    Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.11.15/x64
    LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.11.15/x64/lib
I001 [*] Import block is un-sorted or un-formatted
  --> aiprod_adaptation/consistency/__init__.py:11:1
   |
 9 |       timeline_engine     — Calcule et valide les timestamps absolus
10 |   """
11 | / from aiprod_adaptation.consistency.asset_registry import AssetRegistry
12 | | from aiprod_adaptation.consistency.timeline_engine import TimelineEngine
13 | | from aiprod_adaptation.consistency.color_manager import ColorManager
14 | | from aiprod_adaptation.consistency.continuity_checker import ContinuityChecker
15 | | from aiprod_adaptation.consistency.audio_normalizer import AudioNormalizer
   | |__________________________________________________________________________^
16 |
17 |   __all__ = [
   |
help: Organize imports

UP024 [*] Replace aliased errors with `OSError`
  --> aiprod_adaptation/image_gen/huggingface_image_adapter.py:89:19
   |
87 |         token = os.environ.get("HF_TOKEN", "")
88 |         if not token:
89 |             raise EnvironmentError(
   |                   ^^^^^^^^^^^^^^^^
90 |                 "HuggingFaceImageAdapter: HF_TOKEN environment variable is not set. "
91 |                 "Generate a free token at https://huggingface.co/settings/tokens"
   |
help: Replace `EnvironmentError` with builtin `OSError`

F841 Local variable `is_dev` is assigned to but never used
   --> aiprod_adaptation/image_gen/huggingface_image_adapter.py:99:9
    |
 97 |         is_schnell = "schnell" in model.lower()
 98 |         is_sdxl = _is_sdxl(model)
 99 |         is_dev = _is_flux_dev(model)
    |         ^^^^^^
100 |
101 |         if is_schnell:
    |
help: Remove assignment to unused variable `is_dev`
1128 |               )
1129 | /             from aiprod_adaptation.image_gen.character_prepass import _unique_characters
1130 | |             from aiprod_adaptation.core.io import load_output
     | |_____________________________________________________________^
1131 |               output = load_output(str(ir_json))
1132 |               chars = _unique_characters(output)
     |
help: Organize imports

I001 [*] Import block is un-sorted or un-formatted
  --> aiprod_adaptation/tests/test_consistency.py:12:1
   |
10 |   """
11 |
12 | / from __future__ import annotations
13 | |
14 | | import pytest
15 | |
16 | | from aiprod_adaptation.models.schema import (
17 | |     AIPRODOutput,
18 | |     Episode,
19 | |     Scene,
20 | |     Shot,
21 | |     GlobalAsset,
22 | |     Timeline,
23 | | )
24 | | from aiprod_adaptation.consistency import (
25 | |     AssetRegistry,
26 | |     AudioNormalizer,
27 | |     ColorManager,
28 | |     ContinuityChecker,
29 | |     TimelineEngine,
30 | | )
   | |_^
   |
help: Organize imports

F401 [*] `pytest` imported but unused
  --> aiprod_adaptation/tests/test_consistency.py:14:8
   |
12 | from __future__ import annotations
13 |
14 | import pytest
   |        ^^^^^^
15 |
16 | from aiprod_adaptation.models.schema import (
   |
help: Remove unused import: `pytest`

F401 [*] `unittest.mock.patch` imported but unused
   --> aiprod_adaptation/tests/test_image_gen.py:981:35
    |
979 |         Prepass must NOT be skipped — generated must be 1, not 0.
980 |         If this fails, --remove-background runs waste API credits with no face-consistency benefit."""
981 |         from unittest.mock import patch
    |                                   ^^^^^
982 |
983 |         from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass
    |
help: Remove unused import: `unittest.mock.patch`

I001 [*] Import block is un-sorted or un-formatted
   --> aiprod_adaptation/tests/test_scheduling.py:268:9
    |
266 |   class TestBudgetCap:
267 |       def test_budget_cap_stops_generation_early(self) -> None:
268 | /         from aiprod_adaptation.image_gen.image_adapter import NullImageAdapter
269 | |         from aiprod_adaptation.image_gen.image_request import ImageResult
270 | |         from aiprod_adaptation.image_gen.image_request import ImageRequest
271 | |         from aiprod_adaptation.image_gen.storyboard import StoryboardGenerator
272 | |         from aiprod_adaptation.models.schema import AIPRODOutput, Episode, Shot
    | |_______________________________________________________________________________^
273 |
274 |           class FixedCostAdapter(NullImageAdapter):
    |
help: Organize imports

I001 [*] Import block is un-sorted or un-formatted
   --> aiprod_adaptation/tests/test_scheduling.py:333:9
    |
332 |       def test_claude_adapter_accumulates_token_usage(self) -> None:
333 | /         import json
334 | |         from unittest.mock import MagicMock, patch
335 | |         from aiprod_adaptation.core.adaptation.claude_adapter import ClaudeAdapter
336 | |         import os
    | |_________________^
337 |           with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
338 |               adapter = ClaudeAdapter()
    |
help: Organize imports

F401 [*] `json` imported but unused
   --> aiprod_adaptation/tests/test_scheduling.py:333:16
    |
332 |     def test_claude_adapter_accumulates_token_usage(self) -> None:
333 |         import json
    |                ^^^^
334 |         from unittest.mock import MagicMock, patch
335 |         from aiprod_adaptation.core.adaptation.claude_adapter import ClaudeAdapter
    |
help: Remove unused import: `json`

Found 22 errors.
[*] 16 fixable with the `--fix` option (1 hidden fix can be enabled with the `--unsafe-fixes` option).
Error: Process completed with exit code 1.