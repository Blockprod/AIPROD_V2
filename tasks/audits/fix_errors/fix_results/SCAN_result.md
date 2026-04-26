---
type: scan_result
projet: AIPROD_V2
scan_date: 2026-04-26
creation: 2026-04-26 à 13:03
outils: ruff · mypy · pytest · grep
---

# SCAN_result — P1 SCAN COMPLET

---

## ÉTAPE 1 — OUTILS STATIQUES

### 1.1 Ruff général
```
All checks passed!   →   0 violation(s)
```

### 1.2 Ruff ciblé (F401 · ARG · E501)
**22 violations ARG** — aucune F401 ni E501.

| Fichier | Ligne | Code | Détail |
|---------|------:|------|--------|
| `aiprod_adaptation/core/global_coherence/consistency_checker.py` | 43 | ARG001 | `visual_bible` : paramètre déclaré mais non utilisé dans le corps |
| `aiprod_adaptation/core/pass1_segment.py` | 265 | ARG001 | `is_act_break` : non utilisé |
| `aiprod_adaptation/core/pass1_segment.py` | 266 | ARG001 | `act_position` : non utilisé |
| `aiprod_adaptation/core/rule_engine/conflict_resolver.py` | 275 | ARG002 | `ctx` non utilisé (méthode 1) |
| `aiprod_adaptation/core/rule_engine/conflict_resolver.py` | 322 | ARG002 | `ctx` non utilisé (méthode 2) |
| `aiprod_adaptation/core/rule_engine/conflict_resolver.py` | 348 | ARG002 | `ctx` non utilisé (méthode 3) |
| `aiprod_adaptation/tests/test_adaptation.py` | 155–157 | ARG002 | `model`, `contents`, `config` non utilisés (stub 1) |
| `aiprod_adaptation/tests/test_adaptation.py` | 192–193 | ARG002 | `contents`, `config` non utilisés (stub 2) |
| `aiprod_adaptation/tests/test_adaptation.py` | 224–226 | ARG002 | `model`, `contents`, `config` non utilisés (stub 3) |
| `aiprod_adaptation/tests/test_adaptation.py` | 259 | ARG002 | `kwargs` non utilisé |
| `aiprod_adaptation/tests/test_adaptation.py` | 293–295 | ARG002 | `model`, `contents`, `config` non utilisés (stub 4) |
| `aiprod_adaptation/tests/test_cinematic_integration.py` | 615 | ARG002 | `char_name` non utilisé |
| `aiprod_adaptation/tests/test_cinematic_integration.py` | 618 | ARG002 | `loc_id` non utilisé |
| `aiprod_adaptation/tests/test_pass2_cinematic.py` | 37 | ARG001 | `emotion_override` non utilisé |
| `aiprod_adaptation/tests/test_video_sequencer.py` | 105 | ARG005 | lambda `token` non utilisé |

**Répartition :**
- Core production : 3 fichiers, 6 violations (ARG)
- Tests : 5 fichiers, 16 violations (ARG — stubs/mocks par design)

### 1.3 mypy --strict (scope CI officiel)
```
Scope : core/ · models/ · backends/ · cli.py · main.py
Résultat : 0 erreur(s)   ✅
```

### 1.4 mypy --ignore-missing-imports (modules hors scope strict)

| Module | Erreurs |
|--------|--------:|
| `aiprod_adaptation/image_gen/` | **4** |
| `aiprod_adaptation/post_prod/` | **7** |
| `aiprod_adaptation/video_gen/` | **2** |

**image_gen/ (4 erreurs)**

| Fichier | Ligne | Code mypy | Message |
|---------|------:|-----------|---------|
| `image_gen/replicate_adapter.py` | 45 | `index` | Value of type `Any \| Iterator[Any]` is not indexable |
| `image_gen/runway_image_adapter.py` | 59 | `call-overload` | No overload variant of `create` matches `dict[str, object]` |
| `image_gen/openai_image_adapter.py` | 89 | `assignment` | `str` assigné à `Literal['low','medium','high','auto']` |
| `image_gen/openai_image_adapter.py` | 98 | `attr-defined` | `object` n'a pas d'attribut `images` |

**post_prod/ (7 erreurs)**

| Fichier | Ligne | Code mypy | Message |
|---------|------:|-----------|---------|
| `post_prod/runway_tts_adapter.py` | 45 | `arg-type` | `str` passé à `"eleven_multilingual_v2"` Literal |
| `post_prod/runway_tts_adapter.py` | 47 | `typeddict-item` | `str` assigné à `preset_id` Literal |
| `post_prod/runway_tts_adapter.py` | 54 | `union-attr` | `.output` absent sur `Pending` |
| `post_prod/runway_tts_adapter.py` | 54 | `union-attr` | `.output` absent sur `Throttled` |
| `post_prod/runway_tts_adapter.py` | 54 | `union-attr` | `.output` absent sur `Cancelled` |
| `post_prod/runway_tts_adapter.py` | 54 | `union-attr` | `.output` absent sur `Running` |
| `post_prod/runway_tts_adapter.py` | 54 | `union-attr` | `.output` absent sur `Failed` |

**video_gen/ (2 erreurs)**

| Fichier | Ligne | Code mypy | Message |
|---------|------:|-----------|---------|
| `video_gen/runway_adapter.py` | 86 | `attr-defined` | `object` n'a pas d'attribut `image_to_video` |
| `video_gen/runway_adapter.py` | 117 | `attr-defined` | `object` n'a pas d'attribut `video_to_video` |

---

## ÉTAPE 2 — GET_ERRORS (IDE)
```
No errors found.   ✅
```

---

## ÉTAPE 4 — VÉRIFICATION INTERDITS

| Interdit | Résultat | Occurrences |
|----------|----------|-------------|
| `# type: ignore` | ✅ 0 | — |
| `# noqa` | ✅ 0 | — |
| `random` / `uuid` dans `core/` | ✅ 0 | — |
| `datetime.now` / `time.time` dans `core/` | ✅ 0 | — |
| API Pydantic v1 (`.dict()`, `@validator`, etc.) | ✅ 0 | — |

---

## ÉTAPE 5 — TESTS (runtime smoke)
```
998 passed, 4 deselected in 18.55s   ✅
```
Aucun test en échec.

---

## FILES_TO_FIX

```
FILES_TO_FIX = [
  # ── CORE PRODUCTION (priorité haute) ──────────────────────────────────
  {
    file: "aiprod_adaptation/core/global_coherence/consistency_checker.py",
    errors: ["ruff-ARG001"],
    count: 1,
    lines: [43],
    note: "Paramètre visual_bible déclaré mais jamais lu — supprimer ou utiliser."
  },
  {
    file: "aiprod_adaptation/core/pass1_segment.py",
    errors: ["ruff-ARG001"],
    count: 2,
    lines: [265, 266],
    note: "is_act_break et act_position déclarés mais non utilisés."
  },
  {
    file: "aiprod_adaptation/core/rule_engine/conflict_resolver.py",
    errors: ["ruff-ARG002"],
    count: 3,
    lines: [275, 322, 348],
    note: "ctx non utilisé dans 3 méthodes — préfixer _ ou utiliser."
  },
  {
    file: "aiprod_adaptation/image_gen/replicate_adapter.py",
    errors: ["mypy-index"],
    count: 1,
    lines: [45],
    note: "Résultat Any|Iterator[Any] indexé sans guard de type."
  },
  {
    file: "aiprod_adaptation/image_gen/runway_image_adapter.py",
    errors: ["mypy-call-overload"],
    count: 1,
    lines: [59],
    note: "dict[str, object] passé à une surcharge qui attend des kwargs typés."
  },
  {
    file: "aiprod_adaptation/image_gen/openai_image_adapter.py",
    errors: ["mypy-assignment", "mypy-attr-defined"],
    count: 2,
    lines: [89, 98],
    note: "Literal mal casté (l89) + accès .images sur object non affiné (l98)."
  },
  {
    file: "aiprod_adaptation/post_prod/runway_tts_adapter.py",
    errors: ["mypy-arg-type", "mypy-typeddict-item", "mypy-union-attr"],
    count: 7,
    lines: [45, 47, 54],
    note: "str → Literal (l45,47) + accès .output sans guard sur états non-Succeeded (l54)."
  },
  {
    file: "aiprod_adaptation/video_gen/runway_adapter.py",
    errors: ["mypy-attr-defined"],
    count: 2,
    lines: [86, 117],
    note: "Client Runway typé object — cast nécessaire vers le bon type SDK."
  },
  # ── TESTS (priorité basse — stubs/mocks par design) ───────────────────
  {
    file: "aiprod_adaptation/tests/test_adaptation.py",
    errors: ["ruff-ARG002"],
    count: 11,
    lines: [155, 156, 157, 192, 193, 224, 225, 226, 259, 293, 294, 295],
    note: "Stubs LLM — préfixer les args inutilisés avec _ pour supprimer l'avertissement."
  },
  {
    file: "aiprod_adaptation/tests/test_cinematic_integration.py",
    errors: ["ruff-ARG002"],
    count: 2,
    lines: [615, 618],
    note: "Mock VisualBible — préfixer _ sur char_name et loc_id."
  },
  {
    file: "aiprod_adaptation/tests/test_pass2_cinematic.py",
    errors: ["ruff-ARG001"],
    count: 1,
    lines: [37],
    note: "emotion_override dans _make_scene() déclaré mais jamais appliqué."
  },
  {
    file: "aiprod_adaptation/tests/test_video_sequencer.py",
    errors: ["ruff-ARG005"],
    count: 1,
    lines: [105],
    note: "Lambda monkeypatch : lambda _token: mock_client."
  },
]
```

---

## INTERDITS

```
type_ignore  : 0   ✅
noqa         : 0   ✅
randomness   : 0   ✅  (core/)
datetime     : 0   ✅  (core/)
pydantic_v1  : 0   ✅
```

---

## TESTS

```
passed    : 998
failed    : 0
deselected: 4  (skip/xfail — normal)
```

---

## TOTAUX

```
ruff_general    : 0 violation(s)                          ✅
ruff_ARG        : 22 violation(s)
  ├─ core (prod): 6   → PRIORITÉ HAUTE
  └─ tests      : 16  → PRIORITÉ BASSE (stubs par design)
ruff_F401       : 0 violation(s)                          ✅
ruff_E501       : 0 violation(s)                          ✅

mypy_strict     : 0 erreur(s)                             ✅
  scope CI : core/ · models/ · backends/ · cli.py · main.py
mypy_extra      : 13 erreur(s) dans 4 fichiers
  ├─ image_gen/ : 4   → PRIORITÉ HAUTE
  ├─ post_prod/ : 7   → PRIORITÉ HAUTE
  └─ video_gen/ : 2   → PRIORITÉ HAUTE

interdits       : 0 violation(s)                          ✅
tests           : 998 passés, 0 échec                     ✅
ide_errors      : 0                                       ✅

modules_propres (mypy strict) :
  - aiprod_adaptation/core/
  - aiprod_adaptation/models/
  - aiprod_adaptation/backends/
  - aiprod_adaptation/cli.py
  - main.py
```

---

## VERDICT

| Dimension | Statut |
|-----------|--------|
| Ruff général | ✅ CLEAN |
| Ruff ARG core prod | ⚠️  6 avertissements |
| Ruff ARG tests | ℹ️  16 — stubs par design |
| mypy --strict scope CI | ✅ CLEAN |
| mypy modules externes | ⚠️  13 erreurs (image_gen · post_prod · video_gen) |
| Interdits absolus | ✅ CLEAN |
| Tests | ✅ 998/998 |
| **RELEASE READINESS** | **⚠️  CORRECTIONS NÉCESSAIRES** |

→ Passer à **P2_PLAN_prompt.md** pour définir les batches de correction.

