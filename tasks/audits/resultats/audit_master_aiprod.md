---
title: "Audit Master — AIPROD_V2"
creation: 2026-04-21 à 23:07
auditor: GitHub Copilot (Claude Sonnet 4.6)
baseline_commit: 42f99d7
python: "3.11.9"
tests: 278 passed
mypy_prod: "0 erreurs (41 fichiers)"
mypy_full: "52 erreurs dans 5 fichiers de tests"
ruff: "0 erreurs"
---

# AUDIT MASTER — AIPROD_V2 — 2026-04-21

## Score global : 🟡 — 0 critiques 🔴, 2 majeurs 🟠, 12 mineurs 🟡

---

## Résumé exécutif

Le codebase AIPROD_V2 présente une architecture IR en 4 passes **solide et bien segmentée**. La déterminisme est totale (vérifié par test byte-identical), les schémas Pydantic v2 sont cohérents, et le périmètre de production (41 fichiers) est **zéro-erreur** en mypy strict. Les deux points majeurs sont : (1) le `CostReport` n'est jamais alimenté par les adapters (métriques de coût toujours à zéro), et (2) `EpisodeScheduler` importe tous les adapters production au top-level (risque `ImportError` si les packages tiers ne sont pas installés). Douze points mineurs concernent essentiellement des annotations de type manquantes dans les tests et des fichiers de maintenance.

**Périmètre inspecté :** 74 fichiers Python, 10 fichiers de tests, 278 tests, pipeline complet (segmentation → visual → shots → compilation → storyboard → vidéo → audio → export).

---

## DIMENSION 1 — Structure (74 modules)

### Architecture globale

```
IR pipeline (déterministe, pure functions) :
  pass1_segment.py  → list[RawScene]
  pass2_visual.py   → list[VisualScene]
  pass3_shots.py    → list[ShotDict]
  pass4_compile.py  → AIPRODOutput

LLM pipeline :
  InputClassifier → ScriptParser | StoryExtractor → StoryValidator → IR passes

Production pipeline :
  CharacterPrepass → StoryboardGenerator → VideoSequencer → AudioSynchronizer

Orchestration :
  engine.py (run_pipeline) → EpisodeScheduler (run)
```

### Points positifs

- Découpage SRP respecté : chaque module a une responsabilité unique ✅
- Tous les passes IR sont des fonctions pures ou classes sans état ✅
- Adapters production (flux, replicate, runway, kling, elevenlabs, openai_tts) isolés dans leurs sous-packages ✅
- `novel_pipe.py` est correctement marqué `# DEAD CODE — deprecated` avec avertissement `DeprecationWarning` dans `run_novel_pipe()` ✅
- `compile_output()` (wrapper déprécié de `pass4_compile`) maintenu pour rétrocompatibilité ✅
- `frozenset` utilisé pour toutes les constantes en lecture seule (aucun `set()` mutable comme constante) ✅

### Problèmes détectés

| ID | Sévérité | Fichier | Description |
|----|----------|---------|-------------|
| M02 | 🟠 | `core/scheduling/episode_scheduler.py:1-16` | Imports adapters production au top-level (non lazy) — `ImportError` potentiel si runway/kling/elevenlabs non installés |
| m01 | 🟡 | `core/rules/duration_rules.py` | Fichier documentation-only (5 lignes, docstring seule) — confusant car `core/rules/__init__.py` l'exporte |
| m02 | 🟡 | `core/engine.py:33-38` | `CharacterRegistry()` instancié deux fois consécutivement (`.build()` puis `.enrich_from_text()`) alors qu'un seul objet suffit |
| m12 | 🟡 | `core/adaptation/novel_pipe.py` | Fichier legacy confirmé (voir docstring ligne 1) — tests `TestNovelPipe` toujours présents dans `test_adaptation.py` (2 tests) — à migrer pour suppression complète |

---

## DIMENSION 2 — Cohérence pipeline

### Contrats de types vérifiés

```python
RawScene (TypedDict) :
  scene_id, characters, location, time_of_day, raw_text ✅

VisualScene (TypedDict) :
  + visual_actions, dialogues, emotion
  + pacing?, time_of_day_visual?, dominant_sound?  (SE-04, optionnel) ✅

ShotDict (TypedDict) :
  shot_id, scene_id, prompt, duration_sec, emotion,
  shot_type, camera_movement, metadata ✅

AIPRODOutput (Pydantic) :
  title: str, episodes: list[Episode] ✅
```

### Flux SE-04 (enrichissement)

Les champs SE-04 (`pacing`, `time_of_day_visual`, `dominant_sound`) sont correctement :
1. Produits par `normalizer.py` et injectés dans `VisualScene` via Pass2 ✅
2. Consommés par `StoryboardGenerator.generate()` via `shot.metadata.get("time_of_day_visual", "day")` ✅
3. Filtrés de `Scene` Pydantic par `_SCENE_KNOWN_KEYS` dans Pass4 (by design) ✅

### Points positifs

- Validation Pass4 → `ValidationError → ValueError(str(exc))` avant de propager ✅
- `StoryValidator.validate_all()` applique les règles de filtrabilité filmique séquentiellement ✅
- `PromptEnricher._enrich_prompt()` trie les clés du registre via `sorted()` → déterministe ✅

### Problèmes détectés

| ID | Sévérité | Fichier | Description |
|----|----------|---------|-------------|
| m03 | 🟡 | `core/adaptation/story_validator.py:24` | `"felt"` dans `INTERNAL_THOUGHT_WORDS` → filtre incorrectement les actions physiques sensorielles ("felt the cold wind", "felt the floor crack") |
| m04 | 🟡 | `core/engine.py:89` | Input vide → `Pass1.segment()` retourne `[]` → `StoryValidator` retourne `[]` → `ValueError("PASS 2: StoryValidator produced no filmable scenes")` — le préfixe `"PASS 2:"` est trompeur alors que la cause est un input vide (PASS 1) |

---

## DIMENSION 3 — Tests (278 tests)

### Distribution par fichier

| Fichier | Tests | Couverture principale |
|---------|-------|-----------------------|
| `test_pipeline.py` | 55 | Passes IR, byte-identical, regression |
| `test_adaptation.py` | 47 | Classifier, ScriptParser, StoryExtractor, NovelPipe, StoryValidator |
| `test_image_gen.py` | 46 | StoryboardGenerator, CharacterPrepass, adapters |
| `test_post_prod.py` | 29 | VideoSequencer, AudioSynchronizer, FFmpegExporter |
| `test_continuity.py` | 24 | CharacterRegistry, LocationRegistry, PropRegistry, PromptEnricher |
| `test_video_gen.py` | 32 | VideoSequencer, SmartVideoRouter |
| `test_scheduling.py` | 21 | EpisodeScheduler |
| `test_cli.py` | 9 | CLI commands (pipeline, storyboard, schedule) |
| `test_backends.py` | 9 | CSVExport, JSONFlatExport |
| `test_io.py` | 6 | IO (save/load JSON) |
| **TOTAL** | **278** | |

### Points positifs

- `test_rule_pipeline_byte_identical` dans `test_pipeline.py` — déterminisme vérifié ✅
- 0 test failing ✅
- Tests CLI couvrent les 3 commandes : `pipeline`, `storyboard`, `schedule` ✅
- Fixtures null-adapter systématiques pour éviter les appels réseau ✅

### Problèmes détectés

| ID | Sévérité | Fichier | Description |
|----|----------|---------|-------------|
| m05 | 🟡 | `tests/test_video_gen.py:46` | `_storyboard_and_output()` sans annotation de retour → 12 erreurs `no-untyped-call` en cascade (mypy full) |
| m06 | 🟡 | `tests/test_post_prod.py:49` | `_video_and_output()` sans annotation de retour → 10 erreurs `no-untyped-call` en cascade |
| m07 | 🟡 | `tests/test_continuity.py:24` | `_make_output()` sans annotation de retour → 1 erreur mypy |
| m08 | 🟡 | `tests/test_adaptation.py:438,441,457` | 3× `# type: ignore[override]` devenus `unused-ignore` + `Function is missing a type annotation` (mypy full) |
| m09 | 🟡 | `tests/test_pipeline.py:51,61,72,136,149,157,164,170,209,227+` | Dicts raw non castés vers `RawScene`/`VisualScene`/`ShotDict` → 22 erreurs mypy ; clés `shot_type`/`camera_movement` manquantes dans un `ShotDict` littéral (ligne 51) |
| m10 | 🟡 | — | Aucun test pour : `LLMRouter`, `audio_utils.py`, `ssml_builder.py`, `checkpoint.py` |

---

## DIMENSION 4 — Qualité technique

### État actuel

| Outil | Périmètre | Résultat |
|-------|-----------|----------|
| **ruff** | 74 fichiers | ✅ `All checks passed!` |
| **mypy strict** | 41 fichiers production | ✅ `Success: no issues found` |
| **mypy strict** | 74 fichiers (incl. tests) | 🟡 `52 errors in 5 files` |
| **pytest** | 278 tests | ✅ `278 passed, 15 warnings` |

### Occurrences `# type: ignore` restantes (13)

| Fichier | Nb | Motif | Statut |
|---------|----|-------|--------|
| `core/adaptation/claude_adapter.py` | 2 | `attr-defined`, `index` (Anthropic SDK non typé) | ✅ Légitime |
| `video_gen/kling_adapter.py` | 2 | `import-untyped` (jwt, requests) | ✅ Légitime |
| `video_gen/runway_adapter.py` | 1 | `import-untyped` (runwayml) | ✅ Légitime |
| `image_gen/replicate_adapter.py` | 1 | `import-untyped` | ✅ Légitime |
| `image_gen/flux_adapter.py` | 1 | `import-untyped` (requests) | ✅ Légitime |
| `post_prod/openai_tts_adapter.py` | 1 | `import-untyped` | ✅ Légitime |
| `post_prod/elevenlabs_adapter.py` | 1 | `import-untyped` | ✅ Légitime |
| `tests/test_adaptation.py` | 4 | Frozen dataclass mutation + override | 🟡 3 sont `unused-ignore` (voir m08) |

**Note :** Les adapters (runway, kling, flux, replicate, elevenlabs, openai_tts, claude, gemini) sont **exclus du scope mypy CI** via `[tool.mypy] exclude` dans `pyproject.toml` — comportement intentionnel et documenté.

### CI/CD

```yaml
# .github/workflows/ci.yml
# on: push/PR → main
# ubuntu-latest, Python 3.11
# steps: ruff → mypy (41 fichiers prod) → pytest
```

Couverture CI correcte. `pytest-cov>=4.0` déclaré dans `[project.optional-dependencies.dev]` mais non activé dans le step CI (`pytest` sans `--cov`) ✅ (par design — mesure de couverture locale uniquement).

---

## DIMENSION 5 — Déterminisme

### Vérification exhaustive (grep `core/`)

| Pattern | Résultat |
|---------|----------|
| `import random` / `random.` | ✅ 0 match |
| `import uuid` / `uuid.uuid` | ✅ 0 match |
| `import datetime` / `datetime.now` | ✅ 0 match |
| `time.time()` | ✅ 0 match |
| `shuffle(` / `choice(` | ✅ 0 match |
| `set()` mutable comme ordonnateur | ✅ 0 match — uniquement `frozenset` comme constantes |

### Garanties structurelles

- `PromptEnricher._enrich_prompt()` : `sorted()` sur les clés du registre ✅
- `CharacterPrepass._unique_characters()` : `set` pour déduplication, mais l'ordre final est déterminé par un `list` d'insertion séquentielle ✅
- `PropRegistry.get_prompt_hint()` : `sorted(relevant, key=lambda p: p.name)` ✅
- **Test de régression byte-identical** : `test_rule_pipeline_byte_identical` dans `test_pipeline.py` — deux appels successifs à `run_pipeline()` produisent un JSON identique octet par octet ✅

---

## DIMENSION 6 — Schémas Pydantic

### Modèles principaux

| Modèle | Fichier | Validations |
|--------|---------|-------------|
| `Scene` | `models/schema.py` | `scene_id, characters, location, time_of_day, shots` ✅ |
| `Shot` | `models/schema.py` | `shot_id, scene_id, prompt, duration_sec: int, emotion, shot_type, camera_movement, metadata` — validation range en Pass4 uniquement |
| `Episode` | `models/schema.py` | `episode_id, scenes, shots` ✅ |
| `AIPRODOutput` | `models/schema.py` | `title: str, episodes: list[Episode]` ✅ |
| `ShotStoryboardFrame` | `image_gen/image_request.py` | `shot_id, prompt, image_url, latency_ms` ✅ |
| `StoryboardOutput` | `image_gen/image_request.py` | `title, frames: list[ShotStoryboardFrame]` + computed `total_shots`, `generated` ✅ |
| `VideoClipResult` | `video_gen/video_request.py` | `latency_ms` ✅ |
| `TimelineClip` | `video_gen/video_request.py` | `latency_ms: int = 0` ✅ |
| `ProductionOutput` | `post_prod/audio_request.py` | `resolution="3840x2160"`, `fps=24`, `fps >= 1` validé ✅ |
| `AudioRequest` | `post_prod/audio_request.py` | `@field_validator` : `duration_hint_sec >= 1` ✅ |
| `VideoRequest` | `video_gen/video_request.py` | `motion_score` validator [1.0, 10.0], `last_frame_hint_url` ✅ |

### Problèmes détectés

| ID | Sévérité | Fichier | Description |
|----|----------|---------|-------------|
| m11 | 🟡 | `models/schema.py:Shot` | `duration_sec: int` sans `@field_validator` Pydantic pour contraindre le range — validation assurée uniquement dans `pass4_compile.py` (hors modèle) |

---

## DIMENSION 7 — Observabilité

### CostReport & RunMetrics

```python
# cost_report.py
@dataclass
class CostReport:
    image_count: int = 0
    video_count: int = 0
    audio_count: int = 0
    llm_count: int = 0
    backend_count: int = 0
    llm_cost_usd: float = 0.0
    image_cost_usd: float = 0.0
    video_cost_usd: float = 0.0
    audio_cost_usd: float = 0.0

    @property
    def total_cost_usd(self) -> float:
        return self.llm_cost_usd + self.image_cost_usd + self.video_cost_usd + self.audio_cost_usd

    def merge(self, other: CostReport) -> CostReport:
        # Somme des 9 champs ✅
```

```python
# run_metrics.py
@dataclass
class RunMetrics:
    cost: CostReport = field(default_factory=CostReport)
    total_latency_ms: int = 0
    # + latency breakdowns par adapter
```

### Logging structuré (structlog)

- Configuré **uniquement** dans `engine.py` → `JSONRenderer` + `PrintLoggerFactory(file=sys.stderr)` ✅
- `logger.info("pipeline_start")`, `logger.info("storyboard_complete")`, `logger.warning("storyboard_frame_failed")` présents ✅
- Aucun `print()` ou `logging.basicConfig()` dans le code de production ✅

### Problèmes détectés

| ID | Sévérité | Fichier | Description |
|----|----------|---------|-------------|
| M01 | 🟠 | `core/scheduling/episode_scheduler.py:run()` | `metrics.cost` (CostReport) n'est jamais alimenté — aucun adapter ne remonte ses coûts. `total_cost_usd` sera toujours `0.0` à l'exécution réelle. `total_latency_ms` est correctement calculé (somme image+video+audio latency) mais le coût USD est entièrement absent |

---

## DIMENSION 8 — CLI & Adapters

### Commandes CLI

| Commande | Flag adapters | Sortie |
|----------|--------------|--------|
| `aiprod pipeline` | `--llm-adapter` | JSON stdout / `--output` fichier |
| `aiprod storyboard` | `--image-adapter` (null\|flux\|replicate) | JSON storyboard |
| `aiprod schedule` | `--video-adapter` (null\|runway\|kling\|smart), `--audio-adapter` (null\|elevenlabs\|openai) | JSON ProductionOutput |

### SmartVideoRouter

```python
DEFAULT_THRESHOLD_SEC = 5
# duration_sec <= 5 → runway
# duration_sec > 5  → kling
```

### Imports lazy (adapters)

- `FluxAdapter`, `ReplicateAdapter`, `RunwayAdapter`, `KlingAdapter`, `ElevenLabsAdapter`, `OpenAITTSAdapter` : tous importés via `_load_*()` functions dans leurs modules respectifs ✅

### Problèmes détectés

| ID | Sévérité | Fichier | Description |
|----|----------|---------|-------------|
| M02 | 🟠 | `core/scheduling/episode_scheduler.py:1-16` | Tous les adapters de production sont importés au top-level (`from aiprod_adaptation.image_gen.flux_adapter import FluxAdapter`, etc.) — alors que les CLI loaders sont lazy. En environnement sans `runwayml` ou `kling` installé, `import EpisodeScheduler` lèvera `ImportError` immédiatement |

---

## Tableau consolidé des problèmes

| ID | Dim | Sévérité | Fichier:ligne | Description |
|----|-----|----------|---------------|-------------|
| **M01** | D7 | 🟠 Majeur | `episode_scheduler.py:run()` | CostReport non alimenté — `total_cost_usd` toujours `0.0` à l'exécution réelle |
| **M02** | D1/D8 | 🟠 Majeur | `episode_scheduler.py:1-16` | Imports adapters production au top-level (non lazy) — risque `ImportError` sans packages tiers |
| m01 | D1 | 🟡 Mineur | `core/rules/duration_rules.py` | Fichier documentation-only sans code exécutable |
| m02 | D1 | 🟡 Mineur | `core/engine.py:33-38` | `CharacterRegistry()` instancié deux fois inutilement |
| m03 | D2 | 🟡 Mineur | `core/adaptation/story_validator.py:24` | `"felt"` dans `INTERNAL_THOUGHT_WORDS` filtre les actions physiques sensorielles |
| m04 | D2 | 🟡 Mineur | `core/engine.py:89` | Input vide → `ValueError("PASS 2:")` au lieu de `"PASS 1:"` |
| m05 | D3 | 🟡 Mineur | `tests/test_video_gen.py:46` | `_storyboard_and_output()` sans return type → 12 erreurs mypy cascade |
| m06 | D3 | 🟡 Mineur | `tests/test_post_prod.py:49` | `_video_and_output()` sans return type → 10 erreurs mypy cascade |
| m07 | D3 | 🟡 Mineur | `tests/test_continuity.py:24` | `_make_output()` sans return type → 1 erreur mypy |
| m08 | D3/D4 | 🟡 Mineur | `tests/test_adaptation.py:438,441,457` | 3× `# type: ignore[override]` devenus `unused-ignore` + annotations manquantes |
| m09 | D3 | 🟡 Mineur | `tests/test_pipeline.py:51,61,72+` | Dicts raw non castés vers TypedDicts → 22 erreurs mypy ; clés manquantes dans `ShotDict` ligne 51 |
| m10 | D3 | 🟡 Mineur | — | Aucun test unitaire pour `LLMRouter`, `audio_utils.py`, `ssml_builder.py`, `checkpoint.py` |
| m11 | D6 | 🟡 Mineur | `models/schema.py:Shot` | `duration_sec: int` sans `@field_validator` Pydantic (validation range uniquement en Pass4) |
| m12 | D1 | 🟡 Mineur | `core/adaptation/novel_pipe.py` | Fichier legacy confirmé avec tests orphelins — bloquer la suppression tant que `TestNovelPipe` existe |

**Total : 0 critique 🔴 / 2 majeurs 🟠 / 12 mineurs 🟡**

---

## Plan de correction suggéré

### Priorité HAUTE (🟠 Majeurs)

**[T08] — Rendre les imports `EpisodeScheduler` lazy**
- Fichier : `aiprod_adaptation/core/scheduling/episode_scheduler.py`
- Action : Déplacer les imports `FluxAdapter`, `ReplicateAdapter`, `RunwayAdapter`, `KlingAdapter`, `ElevenLabsAdapter`, `OpenAITTSAdapter` à l'intérieur des méthodes `_load_*()` correspondantes (pattern identique à celui déjà utilisé dans les CLI loaders)
- Risque : Faible (refactoring mécanique d'imports)

**[T09] — Alimenter `CostReport` depuis les adapters**
- Fichier : `aiprod_adaptation/core/scheduling/episode_scheduler.py` + adapters image/video/audio
- Action : Définir un protocol/convention pour que chaque adapter retourne un `CostReport` partiel ; agréger dans `EpisodeScheduler.run()` via `CostReport.merge()`
- Note : Nécessite de définir les tarifs par adapter (ou laisser en `0.0` avec un TODO explicite)
- Risque : Modéré (interface entre adapters et scheduler)

### Priorité NORMALE (🟡 Mineurs — tests)

**[T10] — Annotations return type dans 3 fonctions helper de tests**
- Fichiers : `test_video_gen.py:46`, `test_post_prod.py:49`, `test_continuity.py:24`
- Action : Ajouter les return type annotations pour éliminer les 23 erreurs mypy en cascade
- Pattern : Même correction que T04 (déjà appliquée sur 5 autres fichiers)

**[T11] — Nettoyer `test_adaptation.py:438,441,457`**
- Action : Retirer les `# type: ignore[override]` devenus `unused-ignore` ; ajouter les annotations complètes aux fonctions concernées

**[T12] — Caster les dicts raw dans `test_pipeline.py`**
- Action : Ajouter `cast(RawScene, {...})`, `cast(VisualScene, {...})`, `cast(ShotDict, {...})` ; ajouter `shot_type`/`camera_movement` à la ligne 51

### Priorité BASSE (🟡 Mineurs — code)

**[T13] — Corriger le préfixe `"PASS 2:"` pour input vide**
- Fichier : `aiprod_adaptation/core/engine.py:89` ou `pass1_segment.py`
- Action : Lever `ValueError("PASS 1: empty input")` dans `segment()` si le texte est vide, avant que `StoryValidator` soit appelé

**[T14] — Dédupliquer `CharacterRegistry()` dans `engine.py`**
- Fichier : `aiprod_adaptation/core/engine.py:33-38`
- Action : Instancier une seule fois : `registry = CharacterRegistry().build(output)` puis `CharacterRegistry.enrich_from_text(registry, ...)` → vérifier la signature exacte

**[T15] — Retirer `"felt"` de `INTERNAL_THOUGHT_WORDS`**
- Fichier : `aiprod_adaptation/core/adaptation/story_validator.py:24`
- Action : Supprimer `"felt"` ou le remplacer par `"felt that"` (marqueur de pensée interne avec subordination)

### Priorité TRÈS BASSE (dette technique)

**[T16] — Migrer/supprimer `novel_pipe.py`**
- Dépendance : Migrer `TestNovelPipe` → `TestStoryExtractor` puis supprimer `novel_pipe.py`

**[T17] — Ajouter `@field_validator` range sur `Shot.duration_sec`**
- Fichier : `models/schema.py`
- Action : `@field_validator("duration_sec") → ge=1, le=120` (ou valeur config)

**[T18] — Tests unitaires manquants**
- Couvrir `LLMRouter` (routing null/claude/gemini), `audio_utils.py`, `ssml_builder.py`, `checkpoint.py`
