---
produit: tasks/audits/fix_errors/fix_results/PLAN_result.md
date: 2026-04-22
input: tasks/audits/fix_errors/fix_results/SCAN_result.md
---

# PLAN DE CORRECTION — AIPROD_V2

## ANALYSE PRÉALABLE

### Point clé — pyproject.toml mypy exclude
Le `[tool.mypy]` exclut actuellement 7 fichiers adaptateurs de la vérification mypy.
C'est pourquoi mypy affiche 0 erreur malgré la présence de `type:ignore`.
La correction **remplace ces exclusions** par des `[[tool.mypy.overrides]]` par package tiers
(`ignore_missing_imports = true`), puis supprime tous les `type:ignore` des adaptateurs.

### Stratégie type:ignore[import-untyped]
Les packages sans stubs (requests, replicate, anthropic, runwayml, jwt, elevenlabs, openai)
sont traités via overrides mypy. Aucun inline `type:ignore` restant.

### Stratégie type:ignore[attr-defined / index,union-attr] — claude_adapter.py
anthropic déclaré via overrides → tout le module anthropic est typé `Any` →
`anthropic.Anthropic(...)` et `message.content[0].text` ne déclenchent plus d'erreurs mypy.

### Stratégie type:ignore[misc] — test_adaptation.py:419
Test de frozen dataclass. Remplacement par cast `Any` :
```python
mutable: Any = budget
try:
    mutable.max_chars_per_chunk = 999
    assert False, "Should have raised"
except Exception:
    pass
```
Import `from typing import Any` déjà présent dans le fichier.

### Stratégie ARG* (ruff)
- Fixtures pytest non utilisées (`request`) → renommer en `_request` dans la signature.
  (Pytest injecte par nom exact : retirer le paramètre serait plus propre, mais risque
  de casser des tests qui dépendraient d'un side-effect de la fixture. Underscore prefix
  est le pattern standard.)
- Argument de fonction régulier `check` (line 338) → `_check`
- Lambda arguments `check` (lines 364, 383) → `_check`

---

## PLAN

```
PLAN = [
  {
    batch: 1,
    label: "Core code — main + llm_adapter",
    files: [
      "main.py",
      "aiprod_adaptation/core/adaptation/llm_adapter.py"
    ],
    error_types: ["ruff-E501", "ruff-ARG002"],
    fixes: [
      "main.py:21 — couper la chaîne description argparse pour passer sous 100 chars",
      "llm_adapter.py:19 — renommer `prompt` → `_prompt` dans la signature"
    ],
    estimated_fixes: 2,
    difficulty: "Facile",
    depends_on: []
  },
  {
    batch: 2,
    label: "pyproject.toml — remplacement exclusions mypy par overrides",
    files: [
      "pyproject.toml"
    ],
    error_types: ["config-mypy"],
    fixes: [
      "Supprimer la section `exclude` mypy (7 fichiers adaptateurs)",
      "Ajouter [[tool.mypy.overrides]] pour : anthropic, requests, replicate, runwayml, jwt, elevenlabs, openai",
      "Chaque override : ignore_missing_imports = true"
    ],
    estimated_fixes: 1,
    difficulty: "Facile",
    depends_on: [],
    note: "Ce batch est prérequis pour les batches 3, 4, 5 (suppression type:ignore)"
  },
  {
    batch: 3,
    label: "claude_adapter — suppression type:ignore après override anthropic",
    files: [
      "aiprod_adaptation/core/adaptation/claude_adapter.py"
    ],
    error_types: ["type:ignore[attr-defined]", "type:ignore[index,union-attr]"],
    fixes: [
      "line 30 — supprimer # type: ignore[attr-defined]",
      "line 38 — supprimer # type: ignore[index,union-attr]"
    ],
    estimated_fixes: 2,
    difficulty: "Facile",
    depends_on: [2]
  },
  {
    batch: 4,
    label: "image_gen adapters — suppression type:ignore[import-untyped]",
    files: [
      "aiprod_adaptation/image_gen/flux_adapter.py",
      "aiprod_adaptation/image_gen/replicate_adapter.py"
    ],
    error_types: ["type:ignore[import-untyped]"],
    fixes: [
      "flux_adapter.py:21 — supprimer # type: ignore[import-untyped]",
      "replicate_adapter.py:23 — supprimer # type: ignore[import-untyped]"
    ],
    estimated_fixes: 2,
    difficulty: "Facile",
    depends_on: [2]
  },
  {
    batch: 5,
    label: "post_prod adapters — suppression type:ignore[import-untyped]",
    files: [
      "aiprod_adaptation/post_prod/elevenlabs_adapter.py",
      "aiprod_adaptation/post_prod/openai_tts_adapter.py"
    ],
    error_types: ["type:ignore[import-untyped]"],
    fixes: [
      "elevenlabs_adapter.py:39 — supprimer # type: ignore[import-untyped]",
      "openai_tts_adapter.py:38 — supprimer # type: ignore[import-untyped]"
    ],
    estimated_fixes: 2,
    difficulty: "Facile",
    depends_on: [2]
  },
  {
    batch: 6,
    label: "video_gen adapters — suppression type:ignore[import-untyped]",
    files: [
      "aiprod_adaptation/video_gen/runway_adapter.py",
      "aiprod_adaptation/video_gen/kling_adapter.py"
    ],
    error_types: ["type:ignore[import-untyped]"],
    fixes: [
      "runway_adapter.py:24 — supprimer # type: ignore[import-untyped]",
      "kling_adapter.py:30 — supprimer # type: ignore[import-untyped]",
      "kling_adapter.py:40 — supprimer # type: ignore[import-untyped]"
    ],
    estimated_fixes: 3,
    difficulty: "Facile",
    depends_on: [2]
  },
  {
    batch: 7,
    label: "Tests ARG — fixtures et lambdas non utilisés",
    files: [
      "aiprod_adaptation/tests/test_image_gen.py",
      "aiprod_adaptation/tests/test_video_gen.py",
      "aiprod_adaptation/tests/test_post_prod.py"
    ],
    error_types: ["ruff-ARG001", "ruff-ARG002", "ruff-ARG005"],
    fixes: [
      "test_image_gen.py:138 — `request` → `_request`",
      "test_image_gen.py:370 — `request` → `_request`",
      "test_image_gen.py:518 — `request` → `_request`",
      "test_video_gen.py:141 — `request` → `_request`",
      "test_post_prod.py:166 — `request` → `_request`",
      "test_post_prod.py:338 — `check: bool` → `_check: bool`",
      "test_post_prod.py:364 — `lambda cmd, check:` → `lambda cmd, _check:`",
      "test_post_prod.py:383 — `lambda cmd, check:` → `lambda cmd, _check:`"
    ],
    estimated_fixes: 8,
    difficulty: "Facile",
    depends_on: []
  },
  {
    batch: 8,
    label: "test_adaptation — type:ignore[misc] → cast Any",
    files: [
      "aiprod_adaptation/tests/test_adaptation.py"
    ],
    error_types: ["type:ignore[misc]"],
    fixes: [
      "line 419 — remplacer `budget.max_chars_per_chunk = 999  # type: ignore[misc]`",
      "       par `mutable: Any = budget` suivi de `mutable.max_chars_per_chunk = 999`"
    ],
    estimated_fixes: 1,
    difficulty: "Facile",
    depends_on: []
  }
]

RÉSUMÉ:
  total_batches    : 8
  total_files      : 13  (+pyproject.toml)
  estimated_fixes  : 21
  ordre_execution  : [Batch1 → Batch2 → Batch3 → Batch4 → Batch5 → Batch6 → Batch7 → Batch8]

GRAPHE DE DÉPENDANCES:
  Batch1  ─── (indépendant)
  Batch2  ─── (indépendant — prérequis de 3,4,5,6)
  Batch3  ─── dépend de Batch2
  Batch4  ─── dépend de Batch2
  Batch5  ─── dépend de Batch2
  Batch6  ─── dépend de Batch2
  Batch7  ─── (indépendant)
  Batch8  ─── (indépendant)

ORDRE OPTIMAL (séquentiel sûr) :
  Batch1 → Batch2 → Batch3 → Batch4 → Batch5 → Batch6 → Batch7 → Batch8
```

---

## DÉTAIL DES CORRECTIONS PAR FICHIER

### Batch 1

**main.py:21** — E501 (107 > 100)
```python
# AVANT
description="AIPROD Adaptation Engine — transforms narrative text into structured cinematic data.",

# APRÈS
description=(
    "AIPROD Adaptation Engine"
    " — transforms narrative text into structured cinematic data."
),
```

**llm_adapter.py:19** — ARG002
```python
# AVANT
def generate_json(self, prompt: str) -> dict[str, Any]:

# APRÈS
def generate_json(self, _prompt: str) -> dict[str, Any]:
```

---

### Batch 2

**pyproject.toml** — Remplacer :
```toml
# SUPPRIMER ces lignes du [tool.mypy] :
exclude = [
    "aiprod_adaptation/core/adaptation/claude_adapter\\.py",
    "aiprod_adaptation/image_gen/flux_adapter\\.py",
    "aiprod_adaptation/image_gen/replicate_adapter\\.py",
    "aiprod_adaptation/video_gen/runway_adapter\\.py",
    "aiprod_adaptation/video_gen/kling_adapter\\.py",
    "aiprod_adaptation/post_prod/elevenlabs_adapter\\.py",
    "aiprod_adaptation/post_prod/openai_tts_adapter\\.py",
    "aiprod_adaptation/core/adaptation/gemini_adapter\\.py",
]

# AJOUTER après [tool.mypy] :
[[tool.mypy.overrides]]
module = ["anthropic.*", "requests.*", "replicate.*", "runwayml.*", "jwt.*", "elevenlabs.*", "openai.*"]
ignore_missing_imports = true
```

---

### Batches 3–6

Pour chaque adaptateur : supprimer le commentaire `# type: ignore[...]` en fin de ligne.
Aucune autre modification du code source.

---

### Batch 7

Prefixer les arguments non utilisés avec `_` dans les signatures et lambdas.

---

### Batch 8

**test_adaptation.py:419** — type:ignore[misc]
```python
# AVANT
budget.max_chars_per_chunk = 999  # type: ignore[misc]
assert False, "Should have raised"

# APRÈS
mutable: Any = budget
mutable.max_chars_per_chunk = 999
assert False, "Should have raised"
```
Note : `Any` est déjà importé dans ce fichier via `from typing import Any` (ou équivalent).

---

## VERDICT PLAN

```
VERDICT PLAN: PRÊT
  Complexité globale  : Facile (pas de refactoring logique)
  Risque tests        : Faible (renommages ARG non utilisés, cast Any en test)
  Risque pipeline     : Nul (aucune modification de logique core)
  Prochaine étape     : Lancer P3_FIX_prompt.md avec "Batch 1"
```
