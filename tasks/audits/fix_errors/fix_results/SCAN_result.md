---
produit: tasks/audits/fix_errors/fix_results/SCAN_result.md
date: 2026-04-22
---

# SCAN RESULT — AIPROD_V2

## RÉSUMÉ EXÉCUTIF

| Outil | Résultat |
|---|---|
| ruff (général) | 1 violation |
| ruff (F401/ARG/E501) | 10 violations |
| mypy (74 fichiers) | 0 erreur ✅ |
| get_errors IDE | 0 erreur ✅ |
| type:ignore | 10 occurrences ⚠️ |
| randomness dans core/ | 0 ✅ |
| datetime dans core/ | 0 ✅ |

---

## FILES_TO_FIX

```
FILES_TO_FIX = [
  {
    file: "main.py",
    errors: ["ruff-E501"],
    count: 1,
    lines: [21],
    detail: "Line too long (107 > 100) — description argparse contient '—' (U+2014)"
  },
  {
    file: "aiprod_adaptation/core/adaptation/llm_adapter.py",
    errors: ["ruff-ARG002"],
    count: 1,
    lines: [19],
    detail: "Unused method argument: `prompt` — méthode abstraite / interface stub"
  },
  {
    file: "aiprod_adaptation/tests/test_image_gen.py",
    errors: ["ruff-ARG002"],
    count: 3,
    lines: [138, 370, 518],
    detail: "Unused method argument: `request` — fixture pytest non utilisée dans le corps"
  },
  {
    file: "aiprod_adaptation/tests/test_post_prod.py",
    errors: ["ruff-ARG001", "ruff-ARG002", "ruff-ARG005"],
    count: 4,
    lines: [166, 338, 364, 383],
    detail: "line 166: ARG002 `request`; line 338: ARG001 `check`; lines 364/383: ARG005 lambda `check`"
  },
  {
    file: "aiprod_adaptation/tests/test_video_gen.py",
    errors: ["ruff-ARG002"],
    count: 1,
    lines: [141],
    detail: "Unused method argument: `request` — fixture pytest non utilisée dans le corps"
  },
  {
    file: "aiprod_adaptation/core/adaptation/claude_adapter.py",
    errors: ["type:ignore"],
    count: 2,
    lines: [30, 38],
    detail: "line 30: type:ignore[attr-defined] anthropic.Anthropic; line 38: type:ignore[index,union-attr] message.content[0].text"
  },
  {
    file: "aiprod_adaptation/image_gen/flux_adapter.py",
    errors: ["type:ignore"],
    count: 1,
    lines: [21],
    detail: "type:ignore[import-untyped] — import conditionnel `requests`"
  },
  {
    file: "aiprod_adaptation/image_gen/replicate_adapter.py",
    errors: ["type:ignore"],
    count: 1,
    lines: [23],
    detail: "type:ignore[import-untyped] — import conditionnel `replicate`"
  },
  {
    file: "aiprod_adaptation/post_prod/elevenlabs_adapter.py",
    errors: ["type:ignore"],
    count: 1,
    lines: [39],
    detail: "type:ignore[import-untyped] — import conditionnel `elevenlabs`"
  },
  {
    file: "aiprod_adaptation/post_prod/openai_tts_adapter.py",
    errors: ["type:ignore"],
    count: 1,
    lines: [38],
    detail: "type:ignore[import-untyped] — import conditionnel `openai`"
  },
  {
    file: "aiprod_adaptation/video_gen/runway_adapter.py",
    errors: ["type:ignore"],
    count: 1,
    lines: [24],
    detail: "type:ignore[import-untyped] — import conditionnel `runwayml`"
  },
  {
    file: "aiprod_adaptation/video_gen/kling_adapter.py",
    errors: ["type:ignore"],
    count: 2,
    lines: [30, 40],
    detail: "line 30: type:ignore[import-untyped] `jwt`; line 40: type:ignore[import-untyped] `requests`"
  },
  {
    file: "aiprod_adaptation/tests/test_adaptation.py",
    errors: ["type:ignore"],
    count: 1,
    lines: [419],
    detail: "type:ignore[misc] — assignation à un attribut frozen dans un test de mutation"
  }
]
```

---

## INTERDITS

```
INTERDITS:
  type_ignore : 10 occurrences / [
    claude_adapter.py:30  → [attr-defined]
    claude_adapter.py:38  → [index,union-attr]
    flux_adapter.py:21    → [import-untyped]
    replicate_adapter.py:23 → [import-untyped]
    elevenlabs_adapter.py:39 → [import-untyped]
    openai_tts_adapter.py:38 → [import-untyped]
    runway_adapter.py:24  → [import-untyped]
    kling_adapter.py:30   → [import-untyped]
    kling_adapter.py:40   → [import-untyped]
    test_adaptation.py:419 → [misc]
  ]
  randomness  : 0 ✅
  datetime    : 0 ✅  (time.time() dans video_gen/kling_adapter.py — hors périmètre core/)
```

---

## TOTAUX

```
TOTAUX:
  ruff      : 10 violations (1 E501 + 9 ARG)
  mypy      : 0 erreur
  type:ignore: 10 occurrences
  randomness : 0
  datetime   : 0
```

---

## ANALYSE PAR CATÉGORIE

### Priorité P1 — À corriger (ruff actif)

| Fichier | Règle | Ligne | Correction |
|---|---|---|---|
| `main.py` | E501 | 21 | Couper la chaîne description en deux lignes ou remplacer `—` par `--` |
| `llm_adapter.py` | ARG002 | 19 | Préfixer `prompt` → `_prompt` (interface stub) |
| `test_image_gen.py` | ARG002 | 138, 370, 518 | Préfixer `request` → `_request` |
| `test_post_prod.py` | ARG002 | 166 | Préfixer `request` → `_request` |
| `test_post_prod.py` | ARG001 | 338 | Préfixer `check` → `_check` |
| `test_post_prod.py` | ARG005 | 364, 383 | Préfixer lambda `check` → `_check` |
| `test_video_gen.py` | ARG002 | 141 | Préfixer `request` → `_request` |

### Priorité P2 — À évaluer (type:ignore)

| Fichier | Ligne | Catégorie | Recommandation |
|---|---|---|---|
| `claude_adapter.py` | 30, 38 | `attr-defined`, `union-attr` | Ajouter stubs anthropic ou cast explicite |
| `flux_adapter.py` | 21 | `import-untyped` | Acceptable — import conditionnel sans stubs |
| `replicate_adapter.py` | 23 | `import-untyped` | Acceptable — import conditionnel sans stubs |
| `elevenlabs_adapter.py` | 39 | `import-untyped` | Acceptable — import conditionnel sans stubs |
| `openai_tts_adapter.py` | 38 | `import-untyped` | Acceptable — import conditionnel sans stubs |
| `runway_adapter.py` | 24 | `import-untyped` | Acceptable — import conditionnel sans stubs |
| `kling_adapter.py` | 30, 40 | `import-untyped` | Acceptable — import conditionnel sans stubs |
| `test_adaptation.py` | 419 | `misc` | À examiner — mutation d'attribut frozen en test |

---

## VERDICT

```
VERDICT SCAN: PARTIEL
  ruff   : ⚠️  10 violations actives (toutes ARG/E501 — pas de logique cassée)
  mypy   : ✅  0 erreur
  interdits:
    type:ignore  : ⚠️  10 occurrences (8 import-untyped acceptables, 2 claude_adapter à traiter, 1 test misc)
    randomness   : ✅  0
    datetime     : ✅  0

ACTION REQUISE: Lancer P2_PLAN_prompt.md pour générer le plan de correction batché.
```
