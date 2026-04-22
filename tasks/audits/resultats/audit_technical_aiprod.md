# AUDIT TECHNIQUE — AIPROD_V2 — 2026-04-21

**Périmètre** : pyproject.toml · mypy · ruff · structlog · CI/CD · nouveaux modules  
**Baseline** : commit `42f99d7` + corrections SS-01→SS-08 (278 tests, 0 mypy, 0 ruff)  
**Exécutée le** : 2026-04-21 à 22:26  
**Auditeur** : GitHub Copilot (Claude Sonnet 4.6)

---

## Résumé exécutif

L'infrastructure technique est globalement saine : mypy strict passe sur 41 fichiers, ruff est à 0, les `# type: ignore` ont été éliminés du code de production. Un CI GitHub Actions est en place et couvre les 3 outils (ruff + mypy + pytest).

**7 problèmes identifiés** : 0 critique (🔴), 2 majeurs (🟠), 5 mineurs (🟡).  
Les problèmes majeurs sont : (1) `typing.List` / `typing.Optional` encore présents dans 19 fichiers alors que Python ≥ 3.10 supporte `list[…]` / `X | None` nativement, et (2) `pytest-cov` installé en local mais absent des `dev` dependencies dans `pyproject.toml`. Les problèmes mineurs concernent l'absence de config ruff dédiée, l'absence de coverage dans le CI, et des `# type: ignore` résiduels dans les tests.

---

## BLOC 1 — pyproject.toml

### Dépendances

| Clé | Valeur | Statut |
|---|---|---|
| `requires-python` | `>=3.11` | ✅ correct |
| `pydantic` | `>=2.0` | ✅ v2 explicite |
| `structlog` | `>=21.0` | ✅ présent |
| `build-backend` | `setuptools.build_meta` | ✅ configuré |
| `[tool.mypy]` | présent, `strict = true`, `python_version = "3.11"` | ✅ |
| `[tool.pytest.ini_options]` | `addopts = "-m 'not integration'"`, `testpaths` défini | ✅ |
| `[tool.ruff]` | **ABSENT** | ⚠️ voir T01 |
| `pytest-cov` dans `dev` | **ABSENT** | ⚠️ voir T02 |

### Sections mypy

```toml
[tool.mypy]
python_version = "3.11"
strict = true
exclude = [   # 8 adapters externes exclus (anthropic, flux, replicate, runway, kling, elevenlabs, openai, gemini)
    ...
]
```

Les 8 adapters exclus sont des intégrations à des libraries tierces non typées — exclusion justifiée.  
La section mypy n'inclut pas `cli.py` dans son périmètre d'exclusion : c'est correct, `cli.py` passe sous `--strict`.

### Sections ruff

Aucune section `[tool.ruff]` dans `pyproject.toml`. Ruff fonctionne avec sa configuration par défaut (règles minimales). Le projet ne bénéficie pas d'un set de règles explicite (E/W/F/N/I/UP…). *(voir T01)*

### Dev dependencies

`pytest-cov>=4.0` est installé localement (version 7.1.0) mais pas déclaré dans `[project.optional-dependencies].dev`. Le CI ne l'installe donc pas et le WORKFLOW.md référence `pytest --cov` sans garantie d'exécution en CI. *(voir T02)*

---

## BLOC 2 — mypy

### Résultat actuel

```
Success: no issues found in 41 source files
```

Périmètre : `aiprod_adaptation/core/` + `aiprod_adaptation/models/` + `aiprod_adaptation/backends/` + `aiprod_adaptation/cli.py`.

### typing.List / typing.Optional — obsolète Python 3.11

19 fichiers importent `from typing import List`, `Optional`, `Dict`, `Tuple` alors que Python 3.11 (et ≥ 3.9) permet d'utiliser les builtins directement (`list[…]`, `X | None`, `dict[…]`, `tuple[…]`). Avec `from __future__ import annotations` présent dans tous les fichiers, cette migration est triviale.

Fichiers concernés :

| Fichier | Imports obsolètes |
|---|---|
| `models/schema.py:2` | `List`, `Optional` |
| `models/intermediate.py:16` | `List`, `Optional` |
| `core/pass1_segment.py:28` | `List`, `Optional` |
| `core/pass2_visual.py:35` | `List`, `Optional` |
| `core/pass3_shots.py:33` | `List` |
| `core/pass4_compile.py:4` | `List` |
| `core/rules/verb_categories.py:15` | `List` |
| `core/rules/segmentation_rules.py:10` | `List` |
| `core/rules/cinematography_rules.py:13` | `List`, `Tuple` |
| `core/rules/emotion_rules.py:13` | `List`, `Tuple` |
| `core/continuity/character_registry.py:3` | `List` |
| `core/continuity/emotion_arc.py:3` | `List` |
| `core/continuity/prompt_enricher.py:3` | `List` |
| `image_gen/image_request.py:3` | `List`, `Optional` |
| `image_gen/storyboard.py:3` | `List`, `Optional` |
| `video_gen/video_request.py:3` | `List`, `Optional` |
| `video_gen/video_sequencer.py:3` | `Dict`, `List`, `Optional` |
| `post_prod/audio_request.py:7` | `List` |
| `post_prod/audio_synchronizer.py:8` | `Dict`, `List` |

*(voir T03)*

### # type: ignore — production

Aucun `# type: ignore` dans le code de production (`core/`, `models/`, `backends/`, `cli.py`) après corrections SS-02. ✅

### # type: ignore — adapters exclus de mypy

Les adapters exclus (`claude_adapter.py`, `flux_adapter.py`, etc.) contiennent des `# type: ignore[import-untyped]` justifiés (libs tierces sans stubs). ✅

### # type: ignore — tests

Les fichiers de test **ne sont pas dans le périmètre mypy strict** (pas dans `testpaths` mypy), mais contiennent 24 `# type: ignore` :

| Fichier | Occurrences | Nature |
|---|---|---|
| `tests/test_pipeline.py` | 4 | `arg-type` sur `simplify_shots` / `compile_episode` |
| `tests/test_backends.py` | 5 | `return` + `arg-type` |
| `tests/test_io.py` | 4 | `return` sur fixtures `@pytest.fixture` |
| `tests/test_image_gen.py` | 11 | `arg-type`, `union-attr` |
| `tests/test_scheduling.py` | 1 | `return` |

*(voir T04)*

### Optional[str] vs str | None

`image_request.py` utilise `Optional[int]` (lignes 17, 51) — cohérent avec le reste du fichier mais à migrer avec T03.  
`core/engine.py` utilise `"dict[str, str] | None"` (string forward reference) — pattern correct sous `from __future__ import annotations`.

### Annotations de retour

Toutes les fonctions publiques dans le périmètre mypy sont annotées (vérifié par `--strict` exit 0). ✅

---

## BLOC 3 — ruff

### Résultat actuel

```
All checks passed!
```

### Absence de [tool.ruff] dans pyproject.toml

Ruff utilise sa configuration par défaut. Le projet bénéficierait de :
- `line-length = 100` (cohérent avec les lignes actuelles)
- `target-version = "py311"` (activer les règles UP — pyupgrade — pour migrer `typing.List`)
- `select = ["E", "W", "F", "I", "N", "UP"]` pour couvrir les imports obsolètes et les conventions de nommage

Sans `[tool.ruff]`, la règle `UP006` (use `list` instead of `List`) et `UP007` (use `X | Y` instead of `Optional[X]`) ne sont pas activées — donc le problème T03 est invisible à ruff. *(voir T01)*

---

## BLOC 4 — structlog

### Configuration

```python
# engine.py:19-24
structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    cache_logger_on_first_use=True,
)
```

| Critère | Statut |
|---|---|
| `logger_factory` → `sys.stderr` | ✅ |
| `JSONRenderer` configuré | ✅ |
| Un seul `structlog.configure()` dans le codebase | ✅ |
| Logger uniquement dans `engine.py` | ✅ — aucun `import structlog` ailleurs |
| Levels cohérents | ✅ — `debug` pour les transitions d'état internes, `info` pour les événements métier |

### Absence de `warning` / `error`

Aucun `logger.warning()` ni `logger.error()` n'est utilisé. Les erreurs de pipeline lèvent des `ValueError` (propagées au caller). Ce choix est cohérent pour un pipeline déterministe, mais les cas d'échec de storyboard (erreur adapter → `image_url = "error://..."`) sont silencieux côté logs. *(voir T05)*

### `cache_logger_on_first_use=True`

Correct pour la performance en production. Peut masquer des reconfigurations de structlog dans les tests (à noter si des tests modifient la config). ✅

---

## BLOC 5 — CI/CD

### Fichier présent

`.github/workflows/ci.yml` — déclenchement sur `push` et `pull_request` vers `main`. ✅

### Matrice Python

```yaml
- name: Set up Python 3.11
  uses: actions/setup-python@v5
  with:
    python-version: "3.11"
```

Une seule version (3.11). Pas de matrice multi-version — acceptable pour un projet à version fixe. ✅

### Séquence CI

```
pip install -e ".[dev]"
ruff check aiprod_adaptation/
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ --strict
pytest aiprod_adaptation/tests/ -v --tb=short
```

| Étape | Statut |
|---|---|
| ruff | ✅ présent |
| mypy | ✅ présent, `--strict` |
| pytest | ✅ présent |
| Coverage (pytest-cov) | ❌ absent du CI — voir T02 |
| Cache pip | ❌ absent — chaque run réinstalle toutes les dépendances |
| Activation venv | N/A — CI Ubuntu, `pip install -e` suffit |

### mypy — périmètre CI vs local

CI : `mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ --strict`  
Local (WORKFLOW.md) : `mypy aiprod_adaptation/core/ aiprod_adaptation/models/`

CI couvre en plus `backends/` — périmètre CI **plus large** que le local. Incohérence documentaire mineure. `cli.py` n'est pas dans le périmètre CI mypy. *(voir T06)*

---

## BLOC 6 — Observabilité & Nouveau code

### core/cost_report.py ✅

| Critère | Statut |
|---|---|
| `@dataclass` (mutable, pas frozen) | ✅ — cohérent (champs incrémentaux) |
| `total_cost_usd` property — somme 4 float | ✅ correct |
| `merge()` retourne `CostReport` (construction explicite) | ✅ — pas `asdict` |
| `to_summary_str()` présent | ✅ |

### core/run_metrics.py ✅

| Critère | Statut |
|---|---|
| `cost: CostReport = field(default_factory=CostReport)` | ✅ |
| `success_rate` — guard division par zéro | ✅ (`if shots_requested == 0: return 1.0`) |
| `average_latency_ms` — guard division par zéro | ✅ (`if shots_generated == 0: return 0.0`) |

### cli.py ✅

| Critère | Statut |
|---|---|
| `_load_image_adapter()` → `ImageAdapter` | ✅ (`typing.cast` après SS-02) |
| `_load_video_adapter()` → `VideoAdapter` | ✅ |
| `_load_audio_adapter()` → `AudioAdapter` | ✅ |
| `cmd_schedule()` appelle `save_storyboard/save_video/save_production` | ✅ depuis `core.io` |
| `save_video()` et `save_production()` existent dans `core/io.py` | ✅ |

### post_prod/ffmpeg_exporter.py ✅

| Critère | Statut |
|---|---|
| `subprocess.run` sans `shell=True` | ✅ — OWASP OS injection évitée |
| `check=True` passé | ✅ |
| `FileNotFoundError` sur binaire ffmpeg absent | ✅ — relancée explicitement avec message clair |
| `is_available()` / `shutil.which` | `is_available()` **absent** — À VÉRIFIER |

`FFmpegExporter` n'expose pas de méthode `is_available()`. L'appel `ffmpeg` directement dans `export()` lève `FileNotFoundError` si ffmpeg est absent. Pas de check préalable. *(voir T07)*

---

## Problèmes identifiés

| ID | Sévérité | Fichier:ligne | Description |
|---|---|---|---|
| T01 | 🟠 | `pyproject.toml` | Absence de `[tool.ruff]` — pas de `target-version`, `line-length`, ni de règles `UP` (pyupgrade). Les imports `typing.List`/`Optional` (19 fichiers) sont invisibles à ruff. |
| T02 | 🟠 | `pyproject.toml:18-21` | `pytest-cov` absent des `dev` dependencies. Installé localement (v7.1.0) mais non garanti en CI. La commande `pytest --cov` du WORKFLOW.md échouerait en CI. |
| T03 | 🟡 | 19 fichiers (voir BLOC 2) | `from typing import List/Optional/Dict/Tuple` — obsolète depuis Python 3.9. Avec `from __future__ import annotations` déjà présent, la migration vers builtins (`list[…]`, `X \| None`) est triviale et alignée avec Python 3.11. |
| T04 | 🟡 | `tests/test_pipeline.py:611-614`, `tests/test_backends.py:33,111-114`, `tests/test_io.py:37-49`, `tests/test_image_gen.py:109-133`, `tests/test_scheduling.py:20` | 24 `# type: ignore` dans les fichiers de test. Tests hors périmètre mypy strict — non bloquant, mais incohérent avec la règle projet. |
| T05 | 🟡 | `core/engine.py` | Aucun `logger.warning()` ni `logger.error()` — les erreurs de storyboard (`model_used = "error"`) ne sont pas tracées en logs. Silencieux en cas d'échec partiel de génération. |
| T06 | 🟡 | `.github/workflows/ci.yml:27` | `mypy` dans le CI ne couvre pas `cli.py`. Le périmètre CI (`core/ models/ backends/`) diverge du périmètre local (`core/ models/`). `cli.py` ne bénéficie pas du check CI. |
| T07 | 🟡 | `post_prod/ffmpeg_exporter.py` | Absence de méthode `is_available()` ou de check préalable `shutil.which`. Aucun moyen pour l'appelant de tester la disponibilité ffmpeg avant d'invoquer `export()`. L'erreur n'est détectable qu'à l'exécution. |

---

## Recommandations prioritaires

### 🟠 T01 — Ajouter [tool.ruff] dans pyproject.toml

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP"]
```

Avec `UP006` (list au lieu de List) et `UP007` (X | Y au lieu de Optional[X]), ruff détectera automatiquement les violations T03.

### 🟠 T02 — Ajouter pytest-cov aux dev dependencies

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "mypy>=1.0",
    "ruff>=0.1",
]
```

Et dans le CI :
```yaml
- name: Pytest with coverage
  run: pytest aiprod_adaptation/tests/ -v --tb=short --cov=aiprod_adaptation --cov-report=term-missing
```

### 🟡 T03 — Migrer typing.List → list[…] (19 fichiers)

Avec `from __future__ import annotations` déjà présent dans tous les fichiers, la migration est mécanique :
- `List[X]` → `list[X]`
- `Optional[X]` → `X | None`
- `Dict[K, V]` → `dict[K, V]`
- `Tuple[X, Y]` → `tuple[X, Y]`
- Supprimer les `from typing import List, Optional, Dict, Tuple` devenus vides

### 🟡 T06 — Aligner le périmètre mypy du CI

```yaml
- name: Mypy
  run: mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py --strict
```

### 🟡 T07 — Ajouter is_available() à FFmpegExporter

```python
import shutil

@staticmethod
def is_available(ffmpeg_bin: str = "ffmpeg") -> bool:
    return shutil.which(ffmpeg_bin) is not None
```

---

*Rapport généré depuis analyse statique + exécution locale — baseline post-corrections SS-01→SS-08.*
