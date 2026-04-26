---
type: plan_result
projet: AIPROD_V2
plan_date: 2026-04-26
creation: 2026-04-26 à 13:10
source: SCAN_result.md
---

# PLAN_result — P2 PLAN DE CORRECTION PAR BATCHES

---

## PLAN

```
PLAN = [
  {
    batch: 1,
    module: "core/rule_engine + core/global_coherence",
    files: [
      "aiprod_adaptation/core/rule_engine/conflict_resolver.py",
      "aiprod_adaptation/core/global_coherence/consistency_checker.py",
    ],
    error_types: ["ruff-ARG002", "ruff-ARG001"],
    estimated_fixes: 4,
    difficulty: "Facile",
    note: "Renommages _ sur méthodes privées — tous les call sites sont positionnels."
  },
  {
    batch: 2,
    module: "core/pass1_segment",
    files: [
      "aiprod_adaptation/core/pass1_segment.py",
    ],
    error_types: ["ruff-ARG001"],
    estimated_fixes: 5,  // 2 params renommés + 3 call sites keyword dans pass1 + 1 dans le test
    difficulty: "Moyen",
    note: "Callers dans pass1_segment.py et test_pass1_cinematic.py utilisent les
           kwargs par nom → renommage _is_act_break + _act_position + MAJ call sites."
  },
  {
    batch: 3,
    module: "video_gen/",
    files: [
      "aiprod_adaptation/video_gen/runway_adapter.py",
    ],
    error_types: ["mypy-attr-defined"],
    estimated_fixes: 2,  // 2 erreurs résolues par 1 seul changement de type
    difficulty: "Facile",
    note: "_build_runway_client() retourne object → Any.
           Les deux appels .image_to_video et .video_to_video se résolvent d'un coup."
  },
  {
    batch: 4,
    module: "image_gen/",
    files: [
      "aiprod_adaptation/image_gen/replicate_adapter.py",
      "aiprod_adaptation/image_gen/runway_image_adapter.py",
      "aiprod_adaptation/image_gen/openai_image_adapter.py",
    ],
    error_types: ["mypy-index", "mypy-call-overload", "mypy-assignment", "mypy-attr-defined"],
    estimated_fixes: 4,
    difficulty: "Facile",
    note: "Patterns distincts par fichier — fixes indépendants entre eux."
  },
  {
    batch: 5,
    module: "post_prod/",
    files: [
      "aiprod_adaptation/post_prod/runway_tts_adapter.py",
    ],
    error_types: ["mypy-arg-type", "mypy-typeddict-item", "mypy-union-attr"],
    estimated_fixes: 7,  // 7 erreurs mypy, 3 lignes à corriger
    difficulty: "Moyen",
    note: "cast(Any,...) sur model/preset_id (l45,47) + annotation Any sur result (l54).
           5 erreurs union-attr résolues par la seule annotation Any sur result."
  },
  {
    batch: 6,
    module: "tests/",
    files: [
      "aiprod_adaptation/tests/test_adaptation.py",
      "aiprod_adaptation/tests/test_cinematic_integration.py",
      "aiprod_adaptation/tests/test_pass2_cinematic.py",
      "aiprod_adaptation/tests/test_video_sequencer.py",
    ],
    error_types: ["ruff-ARG002", "ruff-ARG001", "ruff-ARG005"],
    estimated_fixes: 15,
    difficulty: "Facile",
    note: "Stubs/mocks par design — préfixer _ sur tous les args non utilisés.
           Aucun risque fonctionnel."
  },
]
```

---

## DÉTAIL DES CORRECTIONS PAR BATCH

---

### BATCH 1 — `core/rule_engine` + `core/global_coherence` — ARG (ruff)

**Priorité** : Haute — **Risque** : Nul (call sites positionnels)

#### `conflict_resolver.py` — 3 ARG002 `ctx`

Les méthodes `_hard_flag_and_annotate` (l275), méthode l322, et `_soft_compromise_movement` (l348)
reçoivent `ctx: EvalContext` mais ne l'utilisent pas dans leur corps.
Tous les call sites internes (lignes 160, 184, 315, 316) utilisent la syntaxe positionnelle.

| Ligne | Paramètre | Correction |
|------:|-----------|------------|
| 275 | `ctx: EvalContext` | `_ctx: EvalContext` |
| 322 | `ctx: EvalContext` | `_ctx: EvalContext` |
| 348 | `ctx: EvalContext` | `_ctx: EvalContext` |

#### `consistency_checker.py` — 1 ARG001 `visual_bible`

`check_and_enrich(scenes, shots, visual_bible)` : appelé avec syntaxe positionnelle dans
`pass4_compile.py:163`. Renommage sans impact sur les callers.

| Ligne | Paramètre | Correction |
|------:|-----------|------------|
| 43 | `visual_bible: VisualBible \| None = None` | `_visual_bible: VisualBible \| None = None` |

---

### BATCH 2 — `core/pass1_segment` — ARG001 (ruff) + callers

**Priorité** : Haute — **Risque** : Moyen (callers keyword)

#### `pass1_segment.py` — 2 ARG001 + mise à jour call sites

Fonction `_classify_scene_type`. `_is_act_break` et `_act_position` sont intentionnellement
non utilisés (docstring : "stored separately — does NOT override the narrative classification").

**Signature (ligne 262)** :
```python
# AVANT
def _classify_scene_type(
    sentences: list[str],
    is_cliffhanger: bool,
    is_act_break: bool,
    act_position: str | None,
) -> str:

# APRÈS
def _classify_scene_type(
    sentences: list[str],
    is_cliffhanger: bool,
    _is_act_break: bool,
    _act_position: str | None,
) -> str:
```

**Call sites à mettre à jour** :

| Fichier | Ligne | Avant | Après |
|---------|------:|-------|-------|
| `pass1_segment.py` | ~521 | `_classify_scene_type(sentences_tmp, False, False, current_act)` | inchangé (positionnels) |
| `pass1_segment.py` | ~595 | `is_act_break=pending_act_break is not None` | `_is_act_break=pending_act_break is not None` |
| `pass1_segment.py` | ~599 | `act_position=current_act` | `_act_position=current_act` |
| `pass1_segment.py` | ~630 | tout keyword → vérifier | préfixer si keyword |
| `tests/test_pass1_cinematic.py` | 583–584 | `is_act_break=False, act_position="act1"` | `_is_act_break=False, _act_position="act1"` |

---

### BATCH 3 — `video_gen/runway_adapter` — mypy attr-defined

**Priorité** : Haute — **Risque** : Nul (type hint uniquement)

#### `runway_adapter.py` — 2 erreurs résolues par 1 changement

```python
# AVANT (ligne ~26)
def _build_runway_client(api_key: str) -> object:
    import runwayml
    return runwayml.RunwayML(api_key=api_key)

# APRÈS
from typing import Any   # ajouter en tête de fichier

def _build_runway_client(api_key: str) -> Any:
    import runwayml
    return runwayml.RunwayML(api_key=api_key)
```

---

### BATCH 4 — `image_gen/` — mypy (4 erreurs, 3 fichiers)

**Priorité** : Haute — **Risque** : Nul

#### `replicate_adapter.py:45` — mypy-index

`output` est `Any | Iterator[Any]` → indexation directe interdite.

```python
# AVANT
image_url=str(output[0]),

# APRÈS (à l'intérieur du return ImageResult)
output_list = list(output)
...
image_url=str(output_list[0]),
```

#### `runway_image_adapter.py` — mypy-call-overload

`create_kwargs: dict[str, object]` → overload SDK refuse le `**` unpacking.

```python
# AVANT
create_kwargs: dict[str, object] = { ... }

# APRÈS (ajouter from typing import Any en tête)
create_kwargs: dict[str, Any] = { ... }
```

#### `openai_image_adapter.py:89` — mypy-assignment

```python
# AVANT
self._quality: OpenAIImageQuality = quality or os.environ.get(
    "OPENAI_IMAGE_QUALITY",
    DEFAULT_QUALITY,
)

# APRÈS (ajouter cast à l'import typing)
from typing import cast
_raw_quality = quality or os.environ.get("OPENAI_IMAGE_QUALITY", DEFAULT_QUALITY)
self._quality = cast(OpenAIImageQuality, _raw_quality)
```

#### `openai_image_adapter.py` — mypy-attr-defined (via `_build_openai_client`)

```python
# AVANT
def _build_openai_client(api_key: str) -> object:
    from openai import OpenAI
    return OpenAI(api_key=api_key)

# APRÈS
from typing import Any

def _build_openai_client(api_key: str) -> Any:
    from openai import OpenAI
    return OpenAI(api_key=api_key)
```

---

### BATCH 5 — `post_prod/runway_tts_adapter` — mypy (7 erreurs)

**Priorité** : Haute — **Risque** : Moyen

#### Lignes 45-47 — mypy-arg-type + mypy-typeddict-item

```python
# AVANT
task = client.text_to_speech.create(
    model=self._model,
    prompt_text=request.text,
    voice={"type": "runway-preset", "preset_id": voice},
)

# APRÈS
from typing import Any, cast
task = client.text_to_speech.create(
    model=cast(Any, self._model),
    prompt_text=request.text,
    voice=cast(Any, {"type": "runway-preset", "preset_id": voice}),
)
```

#### Ligne 54 — mypy-union-attr (5 erreurs)

`task.wait_for_task_output()` retourne une union. Seul `Succeeded` a `.output`.
Le SDK lève déjà une exception si non-Succeeded → `Any` est sûr ici.

```python
# AVANT
result = task.wait_for_task_output()

# APRÈS
from typing import Any
result: Any = task.wait_for_task_output()
```

---

### BATCH 6 — `tests/` — ARG stubs (ruff, 15 fixes)

**Priorité** : Basse — **Risque** : Nul

#### `test_adaptation.py` — 11 ARG002

Stubs `generate_content(self, *, model, contents, config)` ignorent leurs args.

| Lignes | Params | Correction |
|--------|--------|------------|
| 155–157 | `model`, `contents`, `config` (stub 1) | `_model`, `_contents`, `_config` |
| 192–193 | `contents`, `config` (stub 2) | `_contents`, `_config` |
| 224–226 | `model`, `contents`, `config` (stub 3) | `_model`, `_contents`, `_config` |
| 259 | `**kwargs` | `**_kwargs` |
| 293–295 | `model`, `contents`, `config` (stub 4) | `_model`, `_contents`, `_config` |

#### `test_cinematic_integration.py` — 2 ARG002

| Ligne | Avant | Après |
|------:|-------|-------|
| 615 | `char_name: str` | `_char_name: str` |
| 618 | `loc_id: str` | `_loc_id: str` |

#### `test_pass2_cinematic.py` — 1 ARG001

| Ligne | Avant | Après |
|------:|-------|-------|
| 37 | `emotion_override: str \| None = None` | `_emotion_override: str \| None = None` |

#### `test_video_sequencer.py` — 1 ARG005

| Ligne | Avant | Après |
|------:|-------|-------|
| 105 | `lambda token: mock_client` | `lambda _token: mock_client` |

---

## CONTRAINTES DE VÉRIFICATION

Après **chaque batch** :
```bash
pytest aiprod_adaptation/tests/ -q --tb=short         # 998 passed obligatoire
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py main.py --strict  # 0 errors
ruff check . --exclude venv,__pycache__,build          # All checks passed
```

Après batch 3, 4, 5 — vérifier aussi les modules externes :
```bash
mypy aiprod_adaptation/video_gen/ --ignore-missing-imports   # 0 après batch 3
mypy aiprod_adaptation/image_gen/ --ignore-missing-imports   # 0 après batch 4
mypy aiprod_adaptation/post_prod/ --ignore-missing-imports   # 0 après batch 5
```

---

## RÉSUMÉ

```
RÉSUMÉ:
  total_batches    : 6
  total_files      : 12
  estimated_fixes  : 35  (22 ARG ruff + 13 mypy)
  ordre_execution  : [Batch1 → Batch2 → Batch3 → Batch4 → Batch5 → Batch6]

  répartition:
    batch_1 : 4 fixes  · Facile  · core/rule_engine + global_coherence — _ prefix (positionnels)
    batch_2 : 5 ops    · Moyen   · core/pass1 — _ prefix + MAJ callers keyword + 1 test
    batch_3 : 1 fix    · Facile  · video_gen/ — _build_runway_client -> Any (résout 2 erreurs)
    batch_4 : 4 fixes  · Facile  · image_gen/ — cast / Any / list() patterns
    batch_5 : 3 fixes  · Moyen   · post_prod/ — cast(Any) + Any annotation (résout 7 erreurs)
    batch_6 : 15 fixes · Facile  · tests/ — _ prefix stubs/mocks

  zero_risk_batches    : 1, 3, 4, 6  (type hints / signatures uniquement)
  moderate_risk_batches: 2, 5        (callers keyword / union-attr guard)

  baseline_a_preserver:
    ruff_general   : 0 violations
    mypy_strict_ci : 0 errors
    tests          : 998 passed
```

---

## VERDICT

→ Passer à **P3_FIX_prompt.md** en commençant par **Batch 1**.

