---
creation: 2026-04-21 à 22:32
---

# PLAN D'ACTION — AUDIT TECHNIQUE — 2026-04-21

**Source** : tasks/audits/resultats/audit_technical_aiprod.md  
**Généré le** : 2026-04-21 à 22:32  
**Corrections totales** : 7 (P1: 0 · P2: 4 · P3: 3)

---

## Résumé

La baseline est saine (278 tests, 0 mypy, 0 ruff). Les corrections P2 portent sur la chaîne outillage : ajouter `[tool.ruff]` avec les règles UP pour détecter les imports `typing` obsolètes (présents dans 19 fichiers), puis migrer ces imports, aligner le périmètre mypy du CI, et déclarer `pytest-cov` dans les dev deps. Les corrections P3 couvrent les `# type: ignore` dans les tests, la traçabilité des erreurs partielles de storyboard, et l'API de `FFmpegExporter`.

**Contrainte d'ordre** : T01 (config ruff) doit être appliqué **en même temps** que T03 (migration typing) — si T01 est appliqué seul, `ruff check .` échoue sur les 19 fichiers non encore migrés.

---

## Corrections P2 — IMPORTANT

### [T01] — Ajouter [tool.ruff] dans pyproject.toml

**Priorité** : P2  
**Sévérité** : 🟠  
**Fichier** : `pyproject.toml` (à la fin du fichier, après `[tool.pytest.ini_options.markers]`)  
**Problème** : Aucune section `[tool.ruff]` — ruff tourne avec les defaults implicites. Les règles `UP006` (use `list` au lieu de `List`) et `UP007` (use `X | Y` au lieu de `Optional[X]`) ne sont pas activées, rendant T03 invisible à ruff. Aucun `target-version`, `line-length`, ni `select` explicite.  
**Action** : Ajouter en fin de `pyproject.toml` :
```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP"]
```
**⚠️ Appliquer simultanément avec T03** — sinon `ruff check .` échoue sur les 19 fichiers non migrés.  
**Tests impactés** : Aucun test pytest. Valider avec `ruff check .` → 0 erreur.  
**Risque** : Faible — ruff est un linter pur, aucun impact sur l'exécution.

---

### [T02] — Ajouter pytest-cov aux dev dependencies

**Priorité** : P2  
**Sévérité** : 🟠  
**Fichier** : `pyproject.toml:18-21`  
**Problème** : `pytest-cov` (version 7.1.0) est installé localement mais absent de `[project.optional-dependencies].dev`. La commande `pytest --cov` du WORKFLOW.md échouerait sur un environnement CI ou une installation fraîche. Divergence local/CI non déclarée.  
**Action** : Modifier la section `dev` dans `pyproject.toml` :
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "mypy>=1.0",
    "ruff>=0.1",
]
```
**Tests impactés** : Aucun test pytest affecté. Valider avec `pip install -e ".[dev]"` → pas d'erreur.  
**Risque** : Nul — ajout de dépendance optionnelle.

---

### [T03] — Migrer typing.List/Optional → builtins Python 3.11 (19 fichiers)

**Priorité** : P2  
**Sévérité** : 🟡  
**Fichiers** :

| Fichier | Imports à supprimer | Substitutions |
|---|---|---|
| `aiprod_adaptation/models/schema.py:2` | `List`, `Optional` | `list[…]`, `X \| None` |
| `aiprod_adaptation/models/intermediate.py:16` | `List`, `Optional` | `list[…]`, `X \| None` |
| `aiprod_adaptation/core/pass1_segment.py:28` | `List`, `Optional` | `list[…]`, `X \| None` |
| `aiprod_adaptation/core/pass2_visual.py:35` | `List`, `Optional` | `list[…]`, `X \| None` |
| `aiprod_adaptation/core/pass3_shots.py:33` | `List` | `list[…]` |
| `aiprod_adaptation/core/pass4_compile.py:4` | `List` | `list[…]` |
| `aiprod_adaptation/core/rules/verb_categories.py:15` | `List` | `list[…]` |
| `aiprod_adaptation/core/rules/segmentation_rules.py:10` | `List` | `list[…]` |
| `aiprod_adaptation/core/rules/cinematography_rules.py:13` | `List`, `Tuple` | `list[…]`, `tuple[…]` |
| `aiprod_adaptation/core/rules/emotion_rules.py:13` | `List`, `Tuple` | `list[…]`, `tuple[…]` |
| `aiprod_adaptation/core/continuity/character_registry.py:3` | `List` | `list[…]` |
| `aiprod_adaptation/core/continuity/emotion_arc.py:3` | `List` | `list[…]` |
| `aiprod_adaptation/core/continuity/prompt_enricher.py:3` | `List` | `list[…]` |
| `aiprod_adaptation/image_gen/image_request.py:3` | `List`, `Optional` | `list[…]`, `X \| None` |
| `aiprod_adaptation/image_gen/storyboard.py:3` | `List`, `Optional` | `list[…]`, `X \| None` |
| `aiprod_adaptation/video_gen/video_request.py:3` | `List`, `Optional` | `list[…]`, `X \| None` |
| `aiprod_adaptation/video_gen/video_sequencer.py:3` | `Dict`, `List`, `Optional` | `dict[…]`, `list[…]`, `X \| None` |
| `aiprod_adaptation/post_prod/audio_request.py:7` | `List` | `list[…]` |
| `aiprod_adaptation/post_prod/audio_synchronizer.py:8` | `Dict`, `List` | `dict[…]`, `list[…]` |

**Problème** : `from typing import List/Optional/Dict/Tuple` est obsolète depuis Python 3.9. Tous les fichiers ont déjà `from __future__ import annotations` — la migration est mécanique et sans impact fonctionnel.  
**Action** : Pour chaque fichier :
1. Remplacer toutes les occurrences de `List[X]` → `list[X]`, `Optional[X]` → `X | None`, `Dict[K, V]` → `dict[K, V]`, `Tuple[X, Y]` → `tuple[X, Y]`
2. Supprimer les imports `from typing import ...` devenus vides (ne conserver que `Any`, `cast`, etc. si encore nécessaires)

**⚠️ Appliquer simultanément avec T01** — car après T01, `ruff check .` détecte ces violations et échoue.  
**Tests impactés** : Tous les tests (surface large) — mais changement purement syntaxique, aucun changement de comportement.  
**Risque** : Faible — `from __future__ import annotations` garantit que les annotations ne sont jamais évaluées à runtime. Mypy restera à 0. Valider avec `mypy ... --strict` + `pytest ... -v`.

---

### [T06] — Aligner le périmètre mypy du CI avec cli.py

**Priorité** : P2  
**Sévérité** : 🟡  
**Fichier** : `.github/workflows/ci.yml:27`  
**Problème** : La commande mypy dans le CI est `mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ --strict`. `cli.py` est du code de production mais n'est pas inclus dans le check CI — une régression de type dans `cli.py` passerait inaperçue en CI.  
**Action** : Modifier la ligne mypy du CI pour ajouter `aiprod_adaptation/cli.py` :
```yaml
- run: mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py --strict
```
**Tests impactés** : Aucun test pytest. Valider en local que `mypy ... aiprod_adaptation/cli.py --strict` passe (0 erreur — déjà vérifié).  
**Risque** : Nul — `cli.py` est déjà propre sous `--strict`.

---

## Corrections P3 — MINEUR

### [T04] — Éliminer les # type: ignore dans les tests (24 occurrences)

**Priorité** : P3  
**Sévérité** : 🟡  
**Fichiers** :
- `aiprod_adaptation/tests/test_pipeline.py:611-614` (4 — `arg-type` sur `simplify_shots` / `compile_episode`)
- `aiprod_adaptation/tests/test_backends.py:33,111-114` (5 — `return` + `arg-type`)
- `aiprod_adaptation/tests/test_io.py:37,41,45,49` (4 — `return` sur fixtures)
- `aiprod_adaptation/tests/test_image_gen.py:109,110,115,116,122,127,132,133,375` (9 — `arg-type`, `union-attr`)
- `aiprod_adaptation/tests/test_scheduling.py:20` (1 — `return`)

**Problème** : La règle projet stipule « aucun `# type: ignore` ». Les tests ne sont pas dans le périmètre mypy strict actuel, mais l'incohérence documentaire existe. Ces ignores masquent des désalignements entre les types passés dans les tests et les signatures réelles.  
**Action** : Pour chaque `# type: ignore`, corriger la cause racine :
- `arg-type` : construire des objets du type attendu (ex. `VisualScene`) plutôt que passer des `dict` bruts
- `return` sur fixtures : typer explicitement le retour `-> Generator[AIPRODOutput, None, None]` ou `-> AIPRODOutput`
- `union-attr` : ajouter un `assert` préalable ou utiliser `isinstance`
**Tests impactés** : Tous les tests modifiés — valider que 278/278 restent verts après.  
**Risque** : Moyen — modifier les fixtures peut cascader. Procéder fichier par fichier.

---

### [T05] — Tracer les erreurs partielles de storyboard avec logger.warning

**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/core/engine.py` (dans `generate_storyboard()` ou `run_full_pipeline()`)  
**Problème** : Quand un adapter image retourne `image_url = "error://..."`, l'échec est enregistré dans le résultat mais aucun log n'est émis. En production, les erreurs partielles passent inaperçues dans les journaux.  
**Action** : Dans la boucle de génération storyboard, ajouter après la détection d'une erreur :
```python
if result.image_url.startswith("error://"):
    logger.warning("storyboard_frame_failed", shot_id=result.shot_id, url=result.image_url)
```
**Tests impactés** : Aucun test de comportement affecté (logs vont sur `sys.stderr`). Vérifier que les tests de storyboard passent toujours.  
**Risque** : Faible — ajout de log uniquement, aucun changement de flux.

---

### [T07] — Ajouter is_available() à FFmpegExporter

**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/post_prod/ffmpeg_exporter.py`  
**Problème** : `FFmpegExporter` n'expose pas de méthode permettant de vérifier la disponibilité de ffmpeg avant d'appeler `export()`. L'appelant découvre l'absence de ffmpeg via `FileNotFoundError` au milieu du traitement, sans possibilité de vérification préalable.  
**Action** : Ajouter en tête de classe, après les imports :
```python
import shutil

# Dans la classe FFmpegExporter :
@staticmethod
def is_available(ffmpeg_bin: str = "ffmpeg") -> bool:
    """Return True if ffmpeg binary is found on PATH."""
    return shutil.which(ffmpeg_bin) is not None
```
**Tests impactés** : Aucun test existant. Peut être testé avec un mock `shutil.which`.  
**Risque** : Nul — méthode statique additionnelle.

---

## Ordre d'exécution recommandé

| # | ID | Titre | Dépendances |
|---|---|---|---|
| 1 | T02 | Ajouter pytest-cov aux dev deps | aucune |
| 2 | T01 + T03 | Config ruff + migration typing (simultané) | T01 ↔ T03 couplés |
| 3 | T06 | Aligner périmètre mypy CI | T01+T03 terminés |
| 4 | T07 | is_available() FFmpegExporter | aucune |
| 5 | T05 | logger.warning storyboard partiel | aucune |
| 6 | T04 | Éliminer # type: ignore dans les tests | T03 terminé |

---

## Validation finale

```powershell
# Activation venv
venv\Scripts\Activate.ps1

# 1. ruff (doit passer avec [tool.ruff] + migration typing faits)
ruff check aiprod_adaptation/

# 2. mypy (doit inclure cli.py après T06)
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py --strict

# 3. pytest
pytest aiprod_adaptation/tests/ -v --tb=short

# 4. Coverage (disponible après T02)
pytest aiprod_adaptation/tests/ --cov=aiprod_adaptation --cov-report=term-missing
```

**Critères de succès** :
- [ ] `ruff check .` → 0 erreur (avec `[tool.ruff]` + règles UP)
- [ ] `mypy ... --strict` → `Success: no issues found in 41 source files`
- [ ] `pytest` → 278/278 verts
- [ ] `pytest --cov` → s'exécute sans `ModuleNotFoundError`
- [ ] Aucun `# type: ignore` dans le code de production
- [ ] CI GitHub Actions : push main → green
