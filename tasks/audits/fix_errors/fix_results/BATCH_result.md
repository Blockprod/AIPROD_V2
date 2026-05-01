---
type: batch_result
projet: AIPROD_V2
batch_date: 2026-04-27
creation: 2026-04-27 à 15:56
batches_appliques: [1, 2, 3, 4, 5, 6, "A1", "A2", "A3", "A4"]
---

# BATCH_result — P3 CORRECTIONS APPLIQUÉES (Batches 1–6)

---

## BATCH 1 — `core/rule_engine` + `core/global_coherence` — ARG

```
BATCH_1 = {
  files_corriges: [
    "aiprod_adaptation/core/rule_engine/conflict_resolver.py",
    "aiprod_adaptation/core/global_coherence/consistency_checker.py",
  ],
  fixes_appliques: [
    { file: "conflict_resolver.py", line: 275, type: "ruff-ARG002", fix: "ctx → _ctx dans _hard_flag_and_annotate" },
    { file: "conflict_resolver.py", line: 322, type: "ruff-ARG002", fix: "ctx → _ctx dans _soft_compromise_movement" },
    { file: "conflict_resolver.py", line: 348, type: "ruff-ARG002", fix: "ctx → _ctx dans _soft_narrative_yields" },
    { file: "consistency_checker.py", line: 43, type: "ruff-ARG001", fix: "visual_bible → _visual_bible dans check_and_enrich" },
  ],
  blockers: [],
  tests_apres: "998/998 ✅",
  ruff_general: "0 ✅",
  mypy_strict: "0 ✅",
}
```

---

## BATCH 2 — `core/pass1_segment` — ARG + callers keyword

```
BATCH_2 = {
  files_corriges: [
    "aiprod_adaptation/core/pass1_segment.py",
    "aiprod_adaptation/tests/test_pass1_cinematic.py",
  ],
  fixes_appliques: [
    { file: "pass1_segment.py", line: 264, type: "ruff-ARG001", fix: "is_act_break → _is_act_break dans signature _classify_scene_type" },
    { file: "pass1_segment.py", line: 265, type: "ruff-ARG001", fix: "act_position → _act_position dans signature _classify_scene_type" },
    { file: "pass1_segment.py", line: ~595, type: "call-site-keyword", fix: "is_act_break= → _is_act_break= (call site 1)" },
    { file: "pass1_segment.py", line: ~628, type: "call-site-keyword", fix: "is_act_break=False, act_position= → _is_act_break=False, _act_position= (call site 2)" },
    { file: "test_pass1_cinematic.py", line: 583, type: "call-site-keyword", fix: "is_act_break=False, act_position='act1' → _is_act_break=False, _act_position='act1'" },
  ],
  blockers: [],
  tests_apres: "998/998 ✅",
  ruff_general: "0 ✅",
  mypy_strict: "0 ✅",
}
```

---

## BATCH 3 — `video_gen/runway_adapter` — mypy attr-defined

```
BATCH_3 = {
  files_corriges: [
    "aiprod_adaptation/video_gen/runway_adapter.py",
  ],
  fixes_appliques: [
    { file: "runway_adapter.py", line: 1, type: "import", fix: "Ajout from typing import Any" },
    { file: "runway_adapter.py", line: 26, type: "mypy-attr-defined×2", fix: "_build_runway_client() -> object → -> Any (résout .image_to_video l86 + .video_to_video l117)" },
  ],
  blockers: [],
  tests_apres: "998/998 ✅",
  mypy_video_gen: "0 ✅",
}
```

---

## BATCH 4 — `image_gen/` — mypy (4 erreurs + 4 découvertes)

```
BATCH_4 = {
  files_corriges: [
    "aiprod_adaptation/image_gen/replicate_adapter.py",
    "aiprod_adaptation/image_gen/runway_image_adapter.py",
    "aiprod_adaptation/image_gen/openai_image_adapter.py",
  ],
  fixes_appliques: [
    { file: "replicate_adapter.py", line: 45, type: "mypy-index", fix: "output_list = list(output) → str(output_list[0])" },
    { file: "runway_image_adapter.py", line: 1, type: "import", fix: "Ajout from typing import Any" },
    { file: "runway_image_adapter.py", line: 52, type: "mypy-call-overload", fix: "create_kwargs: dict[str, object] → dict[str, Any]" },
    { file: "runway_image_adapter.py", line: 63, type: "mypy-union-attr (révélé)", fix: "result: Any = task.wait_for_task_output() (masqué par l'erreur précédente)" },
    { file: "openai_image_adapter.py", line: 1, type: "import", fix: "Ajout Any, cast aux imports typing" },
    { file: "openai_image_adapter.py", line: ~42, type: "mypy-attr-defined", fix: "_build_openai_client() -> object → -> Any" },
    { file: "openai_image_adapter.py", line: 89, type: "mypy-assignment", fix: "cast(OpenAIImageQuality, ...) pour _quality" },
  ],
  note: "runway_image_adapter.py avait une union-attr sur result.output masquée par call-overload — corrigée dans le même batch.",
  blockers: [],
  tests_apres: "998/998 ✅",
  mypy_image_gen: "0 ✅",
}
```

---

## BATCH 5 — `post_prod/runway_tts_adapter` — mypy (7 erreurs)

```
BATCH_5 = {
  files_corriges: [
    "aiprod_adaptation/post_prod/runway_tts_adapter.py",
  ],
  fixes_appliques: [
    { file: "runway_tts_adapter.py", line: 1, type: "import", fix: "Ajout Any, cast aux imports typing" },
    { file: "runway_tts_adapter.py", line: 45, type: "mypy-arg-type", fix: "model=cast(Any, self._model)" },
    { file: "runway_tts_adapter.py", line: 47, type: "mypy-typeddict-item", fix: "voice=cast(Any, {...})" },
    { file: "runway_tts_adapter.py", line: 54, type: "mypy-union-attr×5", fix: "result: Any = task.wait_for_task_output() (résout les 5 union-attr en 1 annotation)" },
  ],
  blockers: [],
  tests_apres: "998/998 ✅",
  mypy_post_prod: "0 ✅",
}
```

---

## BATCH 6 — `tests/` — ARG stubs

```
BATCH_6 = {
  files_corriges: [
    "aiprod_adaptation/tests/test_adaptation.py",
    "aiprod_adaptation/tests/test_cinematic_integration.py",
    "aiprod_adaptation/tests/test_pass2_cinematic.py",
    "aiprod_adaptation/tests/test_video_sequencer.py",
  ],
  fixes_appliques: [
    { file: "test_adaptation.py", stubs: "_RetryingModels, _FailingModels, _MalformedModels", fix: "def generate_content(self, *, model, contents, config) → def generate_content(self, **_kwargs: object)" },
    { file: "test_adaptation.py", stub: "_FallbackModels", fix: "def generate_content(self, *, model: str, **_kwargs: object) — model gardé car utilisé dans le corps" },
    { file: "test_adaptation.py", line: 259, fix: "**kwargs → **_kwargs dans _FailingMessages.create" },
    { file: "test_cinematic_integration.py", line: 615, fix: "char_name → _char_name" },
    { file: "test_cinematic_integration.py", line: 618, fix: "loc_id → _loc_id" },
    { file: "test_pass2_cinematic.py", line: 37, fix: "emotion_override → _emotion_override" },
    { file: "test_video_sequencer.py", line: 105, fix: "lambda token → lambda _token" },
  ],
  incident: "Renommage direct keyword-only params (is_act_break→_is_act_break) cassait le runtime — corrigé en remplaçant par **_kwargs.",
  blockers: [],
  tests_apres: "998/998 ✅",
  ruff_ARG: "0 ✅",
}
```

---

## VÉRIFICATION FINALE (tous batches)

```
ruff_general      : All checks passed!   ✅
ruff_ARG          : All checks passed!   ✅  (22 → 0 violations)
mypy_strict_CI    : 0 errors (88 files)  ✅
mypy_image_gen    : 0 errors (15 files)  ✅  (4 → 0 + 1 découverte)
mypy_post_prod    : 0 errors (10 files)  ✅  (7 → 0)
mypy_video_gen    : 0 errors (8 files)   ✅  (2 → 0)
tests             : 998 passed, 4 deselected  ✅
```

---

## VERDICT

**TOUS LES BATCHES APPLIQUÉS AVEC SUCCÈS — 0 BLOCKER**

→ Passer à **P4_VERIFY_prompt.md** pour validation indépendante.

---

# SESSION 2 — Option A (rembg + images.edit) — Batches A1–A4
## (2026-04-27)

---

## BATCH A1 — `image_gen/character_mask` + `pyproject.toml`

```
BATCH_A1 = {
  files_corriges: [
    "aiprod_adaptation/image_gen/character_mask.py",
    "pyproject.toml",
  ],
  fixes_appliques: [
    { file: "character_mask.py", line: 36, type: "interdit-type_ignore[import-untyped]", fix: "removed # type: ignore[import-untyped] on rembg import" },
    { file: "character_mask.py", line: 77, type: "interdit-type_ignore[import-untyped]", fix: "removed # type: ignore[import-untyped] on PIL import" },
    { file: "pyproject.toml", line: null, type: "mypy-import-not-found", fix: "added 'rembg' and 'rembg.*' to [[tool.mypy.overrides]] ignore_missing_imports block (PIL.* was already there)" },
  ],
  blockers: [],
  verify: "mypy strict 88 files — 0 errors ✅ | ruff character_mask.py — 0 errors ✅",
}
```

---

## BATCH A2 — `image_gen/image_adapter` + `openai_image_adapter`

```
BATCH_A2 = {
  files_corriges: [
    "aiprod_adaptation/image_gen/image_adapter.py",
    "aiprod_adaptation/image_gen/openai_image_adapter.py",
  ],
  fixes_appliques: [
    { file: "image_adapter.py", line: null, type: "missing-base-method (root cause type:ignore[override])", fix: "added concrete generate_edit(request, reference_rgba) → ImageResult to ImageAdapter ABC (delegates to self.generate()); NullImageAdapter inherits it" },
    { file: "openai_image_adapter.py", line: 138, type: "interdit-noqa PLC0415", fix: "moved 'import io' from inside generate_edit() body to top-level stdlib imports, removed # noqa: PLC0415" },
  ],
  blockers: [],
  verify: "ruff — 0 errors ✅",
}
```

---

## BATCH A3 — `image_gen/character_prepass` + `storyboard`

```
BATCH_A3 = {
  files_corriges: [
    "aiprod_adaptation/image_gen/character_prepass.py",
    "aiprod_adaptation/image_gen/storyboard.py",
  ],
  fixes_appliques: [
    { file: "character_prepass.py", line: 114, type: "interdit-noqa PLC0415", fix: "moved 'import base64' to top-level" },
    { file: "character_prepass.py", line: 115, type: "interdit-noqa PLC0415", fix: "moved 'from character_mask import build_edit_mask / remove_background as _remove_bg' to top-level (split into 2 import blocks per ruff I001)" },
    { file: "character_prepass.py", line: 141, type: "E501 (142 chars)", fix: "split long if-condition into parenthesized multi-line form" },
    { file: "storyboard.py", line: 8, type: "TYPE_CHECKING→runtime", fix: "promoted FluxKontextAdapter from TYPE_CHECKING guard to real top-level import" },
    { file: "storyboard.py", line: 320, type: "interdit-noqa PLC0415", fix: "removed inline FluxKontextAdapter import from function body; removed noqa" },
    { file: "storyboard.py", line: 406, type: "interdit-noqa PLC0415", fix: "added OpenAIImageAdapter top-level import; removed inline import from function body; removed noqa" },
    { file: "storyboard.py", line: 415, type: "E501 (142 chars)", fix: "split long if-condition into parenthesized multi-line form" },
  ],
  blockers: [],
  verify: "ruff — 0 errors ✅",
}
```

---

## BATCH A4 — `tests/test_image_gen`

```
BATCH_A4 = {
  files_corriges: [
    "aiprod_adaptation/tests/test_image_gen.py",
  ],
  fixes_appliques: [
    { file: "test_image_gen.py", line: 1361, type: "interdit-type_ignore[override]", fix: "removed; no longer needed since ImageAdapter.generate_edit() is now concrete" },
    { file: "test_image_gen.py", line: 1012, type: "F401 unused-import", fix: "removed 'import io' (unused)" },
    { file: "test_image_gen.py", line: 1017, type: "F401 unused-import", fix: "removed '_build_hf_client' from import (unused — patched via string path)" },
    { file: "test_image_gen.py", lines: [900,927,1012,1041,1215,1237,1331,1375], type: "I001 import-sort ×8", fix: "sorted all import blocks: stdlib→3rd-party→local order, blank line separations, alphabetical names" },
    { file: "test_image_gen.py", lines: [1257,1406,1410], type: "E501 ×3", fix: "wrapped patch() call + 2 ImageResult constructors onto multiple lines" },
  ],
  blockers: [],
  verify: "ruff — 0 errors ✅",
}
```

---

## VÉRIFICATION FINALE — Session 2 (Batches A1–A4)

```
ruff_image_gen_files  : All checks passed!   ✅
ruff_test_image_gen   : All checks passed!   ✅
mypy_strict_CI        : 0 errors (88 files)  ✅
tests                 : 1048 passed, 4 deselected  ✅
interdits_restants    : 0  ✅
```

**VERDICT : 0 interdit, 0 blocker, 0 régression.**


