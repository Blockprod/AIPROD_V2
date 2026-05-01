---
type: scan_result
projet: AIPROD_V2
scan_date: 2026-04-27
creation: 2026-04-27 à 15:34
outils: ruff · mypy strict · get_errors IDE · interdits
---

# SCAN_result — P1 SCAN COMPLET (2026-04-27)

---

## ÉTAPE 1 — OUTILS STATIQUES

### 1.1 Ruff général
32 violations (22 auto-fixables)

| Fichier | L | Code | Détail |
|---------|--:|------|--------|
| `image_gen/character_prepass.py` | 114 | I001 | Import block non trié |
| `image_gen/character_prepass.py` | 141 | E501 | Ligne 142 chars (> 120) |
| `image_gen/huggingface_image_adapter.py` | 89 | UP024 | EnvironmentError → OSError |
| `image_gen/huggingface_image_adapter.py` | 99 | F841 | `is_dev` assignée mais non utilisée |
| `image_gen/huggingface_image_adapter.py` | 155 | F811 | HuggingFaceImageAdapter redéfini |
| `image_gen/huggingface_image_adapter.py` | 180 | UP024 | EnvironmentError → OSError |
| `image_gen/ideogram_image_adapter.py` | 4 | F401 | `io` importé mais non utilisé |
| `image_gen/ideogram_image_adapter.py` | 75 | UP024 | EnvironmentError → OSError |
| `image_gen/ideogram_image_adapter.py` | 115 | I001 | Import block non trié |
| `image_gen/replicate_adapter.py` | 142 | I001 | Import block non trié |
| `image_gen/replicate_adapter.py` | 152 | N806 | `_MAX_UPSCALE_PIXELS` SCREAMING_CASE dans fonction |
| `image_gen/replicate_adapter.py` | 247 | N806 | `_MAX_RETRIES` SCREAMING_CASE dans fonction |
| `image_gen/replicate_adapter.py` | 248 | N806 | `_BASE_WAIT` SCREAMING_CASE dans fonction |
| `image_gen/storyboard.py` | 415 | E501 | Ligne 142 chars (> 120) |
| `tests/test_cli.py` | 1036 | F401 | `sys` importé mais non utilisé |
| `tests/test_image_gen.py` | 900 | I001 | Import block non trié |
| `tests/test_image_gen.py` | 926 | I001 | Import block non trié |
| `tests/test_image_gen.py` | 1012 | I001 | Import block non trié |
| `tests/test_image_gen.py` | 1012 | F401 | `io` importé mais non utilisé |
| `tests/test_image_gen.py` | 1017 | F401 | `_build_hf_client` importé mais non utilisé |
| `tests/test_image_gen.py` | 1041 | I001 | Import block non trié |
| `tests/test_image_gen.py` | 1215 | I001 | Import block non trié |
| `tests/test_image_gen.py` | 1237 | I001 | Import block non trié |
| `tests/test_image_gen.py` | 1257 | E501 | Ligne 144 chars |
| `tests/test_image_gen.py` | 1331 | I001 | Import block non trié |
| `tests/test_image_gen.py` | 1361 | ARG002 | `reference_rgba` non utilisé (TrackingAdapter) |
| `tests/test_image_gen.py` | 1375 | I001 | Import block non trié |
| `tests/test_image_gen.py` | 1406 | E501 | Ligne 128 chars |
| `tests/test_image_gen.py` | 1408 | ARG002 | `reference_rgba` non utilisé (TrackingAdapter) |
| `tests/test_image_gen.py` | 1410 | E501 | Ligne 133 chars |
| `tests/test_scheduling.py` | 268 | I001 | Import block non trié |
| `tests/test_scheduling.py` | 333 | I001 | Import block non trié |
| `tests/test_scheduling.py` | 333 | F401 | `json` importé mais non utilisé |

### 1.2 Ruff ciblé (F401, ARG, E501)
12 violations détaillées (sous-ensemble du tableau ci-dessus).

### 1.3 mypy --strict (scope CI : core/ · models/ · backends/ · cli.py · main.py)
**3 erreurs dans 1 fichier (character_mask.py tracé transitivement via cli.py)**

| Fichier | L | Code mypy | Message |
|---------|--:|-----------|---------|
| `image_gen/character_mask.py` | 36 | import-not-found | Cannot find implementation for "rembg" |
| `image_gen/character_mask.py` | 36 | unused-ignore | Unused `# type: ignore` comment |
| `image_gen/character_mask.py` | 77 | unused-ignore | Unused `# type: ignore` comment |

### 1.4 mypy --ignore-missing-imports (image_gen, post_prod, video_gen)

| Module | Erreurs |
|--------|--------:|
| `image_gen/` | 8 |
| `post_prod/` | 2 (character_mask transitive) |
| `video_gen/` | 2 (character_mask transitive) |

**image_gen/ (hors doublons character_mask) :**

| Fichier | L | Code | Message |
|---------|--:|------|---------|
| `character_mask.py` | 36 | unused-ignore | rembg non installé → ignore inutile |
| `character_mask.py` | 77 | unused-ignore | PIL ignore inutile |
| `ideogram_image_adapter.py` | 48 | no-any-return | Returning Any from bytes |
| `ideogram_image_adapter.py` | 147 | no-any-return | Returning Any from str |
| `replicate_adapter.py` | 155 | assignment | Image assignée à ImageFile |
| `replicate_adapter.py` | 155 | attr-defined | Image.LANCZOS non exporté |
| `replicate_adapter.py` | 243 | attr-defined | replicate.Client non exporté |
| `huggingface_image_adapter.py` | 155 | no-redef | HuggingFaceImageAdapter redéfini |

---

## ÉTAPE 2 — GET_ERRORS (IDE)
```
0 erreur(s)   ✅
```

---

## ÉTAPE 4 — VÉRIFICATION INTERDITS

### 4a. # type: ignore
**14 occurrences — VIOLATIONS ❌**

| Fichier | L | Commentaire | Origine |
|---------|--:|-------------|---------|
| `image_gen/character_mask.py` | 36 | `# type: ignore[import-untyped]` | ❌ CE SESSION |
| `image_gen/character_mask.py` | 77 | `# type: ignore[import-untyped]` | ❌ CE SESSION |
| `tests/test_image_gen.py` | 1361 | `# type: ignore[override]` | ❌ CE SESSION |
| `tests/test_pass2_cinematic.py` | 56 | `# type: ignore` | pré-existant |
| `tests/test_pass4_cinematic.py` | 519 | `# type: ignore` | pré-existant |
| `tests/test_pass4_cinematic.py` | 523 | `# type: ignore` | pré-existant |
| `tests/test_pass4_cinematic.py` | 527 | `# type: ignore` | pré-existant |
| `tests/test_pass4_cinematic.py` | 550 | `# type: ignore` | pré-existant |
| `tests/test_pass4_cinematic.py` | 555 | `# type: ignore` | pré-existant |
| `tests/test_pass4_cinematic.py` | 559 | `# type: ignore` | pré-existant |
| `tests/test_pass4_cinematic.py` | 563 | `# type: ignore` | pré-existant |
| `tests/test_pass4_cinematic.py` | 567 | `# type: ignore` | pré-existant |
| `tests/test_rule_engine.py` | 537 | `# type: ignore` | pré-existant |
| `tests/test_rule_engine.py` | 567 | `# type: ignore` | pré-existant |

### 4b. # noqa
**11 occurrences — VIOLATIONS ❌**

| Fichier | L | Commentaire | Origine |
|---------|--:|-------------|---------|
| `core/pass2_visual.py` | 314 | `# noqa` | pré-existant |
| `core/pass4_compile.py` | 245 | `# noqa: BLE001` | pré-existant |
| `image_gen/character_prepass.py` | 114 | `# noqa: PLC0415` | ❌ CE SESSION |
| `image_gen/character_prepass.py` | 115 | `# noqa: PLC0415` | ❌ CE SESSION |
| `image_gen/ideogram_image_adapter.py` | 47 | `# noqa` | pré-existant |
| `image_gen/ideogram_image_adapter.py` | 140 | `# noqa` | pré-existant |
| `image_gen/openai_image_adapter.py` | 138 | `# noqa: PLC0415` | ❌ CE SESSION |
| `image_gen/replicate_adapter.py` | 129 | `# noqa` | pré-existant |
| `image_gen/replicate_adapter.py` | 254 | `# noqa` | pré-existant |
| `image_gen/storyboard.py` | 320 | `# noqa: PLC0415` | ❌ CE SESSION |
| `image_gen/storyboard.py` | 406 | `# noqa: PLC0415` | ❌ CE SESSION |

### 4c. Randomness dans core/
```
0   ✅
```

### 4d. datetime dans core/
**1 occurrence**

| Fichier | L | Ligne |
|---------|--:|-------|
| `core/postproduction/__init__.py` | 45 | `clock: Callable[[], str] = lambda: datetime.now(UTC).isoformat()` |

Note : il s'agit d'une valeur par défaut de paramètre (injection), pas d'un appel direct au niveau module. Pré-existant.

### 4e. API Pydantic v1
```
0 vrai cas   ✅
```
(5 faux positifs : resp.json() sur réponses HTTP dans adaptateurs image/video)

---

## ÉTAPE 5 — TESTS

```
1048 passed, 4 deselected in 18.95s   ✅
0 échec
```

---

## FILES_TO_FIX

```
FILES_TO_FIX = [
  # ── P0 ROUGE — Introduits ce session ──────────────────────────────────
  {
    file: "aiprod_adaptation/image_gen/character_mask.py",
    errors: ["interdit-type_ignore×2", "mypy-import-not-found", "mypy-unused-ignore×2"],
    count: 5,
    lines: [36, 77],
    note: "type:ignore INTERDIT. Supprimer les ignore, implémenter
           un wrapper conditionnel proprement typé sans ignorer mypy."
  },
  {
    file: "aiprod_adaptation/tests/test_image_gen.py",
    errors: ["interdit-type_ignore", "ruff-F401×2", "ruff-I001×8", "ruff-ARG002×2", "ruff-E501×4"],
    count: 17,
    lines: [900, 926, 1012, 1017, 1041, 1215, 1237, 1257, 1331, 1361, 1375, 1406, 1408, 1410],
    note: "type:ignore[override] L.1361 INTERDIT. F401 × 2. I001 × 8 (trier imports).
           ARG002 × 2 (préfixer _ sur reference_rgba). E501 × 4."
  },
  {
    file: "aiprod_adaptation/image_gen/character_prepass.py",
    errors: ["interdit-noqa×2", "ruff-E501"],
    count: 3,
    lines: [114, 115, 141],
    note: "noqa INTERDIT. Déplacer les imports locaux au top du fichier
           ou refactorer pour éviter PLC0415. L.141 : couper la ligne."
  },
  {
    file: "aiprod_adaptation/image_gen/storyboard.py",
    errors: ["interdit-noqa×2", "ruff-E501"],
    count: 3,
    lines: [320, 406, 415],
    note: "noqa INTERDIT. Même cause : imports locaux dans boucle. L.415 : couper."
  },
  {
    file: "aiprod_adaptation/image_gen/openai_image_adapter.py",
    errors: ["interdit-noqa"],
    count: 1,
    lines: [138],
    note: "noqa: PLC0415 — déplacer import io en tête de fichier (io est stdlib)."
  },
  # ── P1 ORANGE — Pré-existants avec impact mypy/strict ─────────────────
  {
    file: "aiprod_adaptation/image_gen/huggingface_image_adapter.py",
    errors: ["ruff-F811", "mypy-no-redef"],
    count: 2,
    lines: [70, 155],
    note: "Classe redéfinie conditionnellement. Unifier en une seule définition."
  },
  {
    file: "aiprod_adaptation/image_gen/ideogram_image_adapter.py",
    errors: ["ruff-F401", "mypy-no-any-return×2"],
    count: 3,
    lines: [4, 48, 147],
    note: "Supprimer import io L.4. Annoter les retours Any en bytes/str."
  },
  {
    file: "aiprod_adaptation/image_gen/replicate_adapter.py",
    errors: ["ruff-N806×3", "mypy-assignment", "mypy-attr-defined×2"],
    count: 5,
    lines: [152, 155, 243, 247, 248],
    note: "Déplacer constantes hors des fonctions. Cast PIL Image/LANCZOS."
  },
  # ── P2 JAUNE — Pré-existants non-bloquants ─────────────────────────────
  {
    file: "aiprod_adaptation/tests/test_cli.py",
    errors: ["ruff-F401"],
    count: 1,
    lines: [1036],
    note: "Supprimer import sys inutilisé."
  },
  {
    file: "aiprod_adaptation/tests/test_scheduling.py",
    errors: ["ruff-F401", "ruff-I001×2"],
    count: 3,
    lines: [268, 333],
    note: "Supprimer import json. Trier imports."
  },
  {
    file: "aiprod_adaptation/core/pass2_visual.py",
    errors: ["interdit-noqa"],
    count: 1,
    lines: [314],
    note: "noqa pré-existant — corriger la cause sous-jacente."
  },
  {
    file: "aiprod_adaptation/core/pass4_compile.py",
    errors: ["interdit-noqa"],
    count: 1,
    lines: [245],
    note: "noqa: BLE001 — affiner le type d'exception capturée."
  },
]
```

---

## INTERDITS

```
type_ignore  : 14 (dont 3 ❌ CE SESSION — character_mask.py:36,77 + test_image_gen.py:1361)
noqa         : 11 (dont 5 ❌ CE SESSION — character_prepass.py:114,115 + openai_image_adapter.py:138 + storyboard.py:320,406)
randomness   : 0  ✅
datetime     : 1  (core/postproduction/__init__.py:45 — lambda default, pré-existant)
pydantic_v1  : 0  ✅
```

---

## TESTS

```
passed    : 1048
failed    : 0
deselected: 4
```

---

## TOTAUX

```
ruff            : 32 violation(s)
  dont I001     : 10  (imports non triés — auto-fixable)
  dont E501     : 5   (lignes > 120)
  dont F401     : 5   (imports inutilisés)
  dont N806     : 3   (constantes dans fonctions)
  dont ARG002   : 2   (args inutilisés)
  dont F811     : 1   (classe redéfinie)
  dont F841     : 1   (variable non utilisée)
  dont UP024    : 2   (EnvironmentError → OSError)

mypy_strict     : 3 erreur(s) dans 1 fichier (character_mask.py tracé transitivement)
mypy_extra      : 8 erreur(s) dans image_gen/ (4 uniques + 4 transitive character_mask)

interdits       : 25 violation(s) TOTALES
  type_ignore   : 14 (dont 3 ce session ❌)
  noqa          : 11 (dont 5 ce session ❌)
  datetime      : 1  (pré-existant)

tests           : 1048/1048 passés   ✅
ide_errors      : 0   ✅
```

---

## PRIORITÉ DES CORRECTIONS

| Priorité | Fichier | Violations | Origine |
|----------|---------|-----------|---------|
| P0 🔴 | `character_mask.py` | type:ignore ×2 + mypy ×3 | ❌ CE SESSION |
| P0 🔴 | `test_image_gen.py` | type:ignore ×1 + ruff ×16 | ❌ CE SESSION |
| P0 🔴 | `character_prepass.py` | noqa ×2 + E501 | ❌ CE SESSION |
| P0 🔴 | `storyboard.py` | noqa ×2 + E501 | ❌ CE SESSION |
| P0 🔴 | `openai_image_adapter.py` | noqa ×1 | ❌ CE SESSION |
| P1 🟠 | `huggingface_image_adapter.py` | F811 + no-redef | pré-existant |
| P1 🟠 | `ideogram_image_adapter.py` | F401 + no-any-return | pré-existant |
| P1 🟠 | `replicate_adapter.py` | N806 + mypy ×3 | pré-existant |
| P2 🟡 | `pass2_visual.py`, `pass4_compile.py` | noqa pré-existants | pré-existant |
| P3 🔵 | Tests divers (cli, scheduling) | F401, I001 | pré-existant/ce session |

→ Corriger P0 en premier — toutes introduites ce session, bloquantes (type:ignore + noqa INTERDITS).
