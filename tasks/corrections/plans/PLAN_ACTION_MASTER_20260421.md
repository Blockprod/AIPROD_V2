---
title: "Plan d'action — Audit Master AIPROD_V2"
creation: 2026-04-21 à 23:18
source_audit: tasks/audits/resultats/audit_master_aiprod.md
baseline_commit: 42f99d7
corrections_totales: 12
p2_count: 5
p3_count: 7
---

# PLAN D'ACTION — AUDIT MASTER — 2026-04-21

**Source** : `tasks/audits/resultats/audit_master_aiprod.md`
**Généré le** : 2026-04-21 à 23:18
**Corrections totales** : 12 (P1:0 · P2:5 · P3:7)

---

## Résumé

Le codebase est en bonne santé (278 tests, mypy prod 0 erreur, ruff 0 erreur). Deux correctifs importants : rendre les imports de `EpisodeScheduler` lazy pour éviter un `ImportError` en environnement sans packages tiers, et éliminer les 52 erreurs mypy résiduelles dans les fichiers de tests (principalement des annotations de retour manquantes et des dicts raw non castés). Le `CostReport` non alimenté est un gap fonctionnel à traiter séparément. Sept mineurs de nettoyage complètent le plan.

**Cible post-corrections :**
- `pytest` : 278/278 ✅ (inchangé)
- `mypy aiprod_adaptation/ --strict --ignore-missing-imports` : 0 erreur (vs 52 actuellement)
- `mypy aiprod_adaptation/core/ ... --strict` : 0 erreur ✅ (inchangé)
- `ruff check aiprod_adaptation/` : 0 erreur ✅ (inchangé)
- `# type: ignore` dans tests : 0 (vs 4 actuellement dans test_adaptation.py)

---

## Corrections P2 — IMPORTANT

### [T08] — Rendre les imports d'EpisodeScheduler lazy

**Priorité** : P2
**Sévérité** : 🟠 Majeur
**Fichier** : `aiprod_adaptation/core/scheduling/episode_scheduler.py:1-16`
**Problème** : Tous les adapters production (`FluxAdapter`, `ReplicateAdapter`, `RunwayAdapter`, `KlingAdapter`, `ElevenLabsAdapter`, `OpenAITTSAdapter`) sont importés au top-level. Un `import EpisodeScheduler` dans un environnement sans `runwayml`, `kling` ou `elevenlabs` installé lèvera `ImportError` immédiatement, même si ces adapters ne sont pas utilisés.
**Action** : Déplacer chaque import dans la méthode `_load_*()` correspondante — pattern identique à celui déjà utilisé dans les CLI loaders (`cli.py`).
**Tests impactés** : `test_scheduling.py` (21 tests) — s'assurer que les null-adapters fonctionnent toujours
**Risque** : Faible — refactoring mécanique d'imports, comportement runtime identique

---

### [T09] — Alimenter CostReport depuis les adapters

**Priorité** : P2
**Sévérité** : 🟠 Majeur
**Fichier** : `aiprod_adaptation/core/scheduling/episode_scheduler.py:run()` + adapters image/video/audio
**Problème** : `metrics.cost` (CostReport) n'est jamais alimenté. Tous les compteurs (`image_count`, `video_count`, etc.) et coûts USD restent à zéro. `RunMetrics.total_latency_ms` est correct mais `total_cost_usd` sera toujours `0.0`.
**Action** :
1. Ajouter une méthode `get_cost() -> CostReport` (ou champ `cost: CostReport`) à `ImageAdapter`, `VideoAdapter`, `AudioAdapter` (dans les classes base)
2. Alimenter les compteurs dans chaque adapter null (coût 0, count +1 par appel)
3. Dans `EpisodeScheduler.run()`, agréger via `metrics.cost = metrics.cost.merge(adapter.get_cost())`
**Tests impactés** : `test_scheduling.py` — ajouter assertions sur `metrics.cost.image_count`, `metrics.cost.total_cost_usd`
**Risque** : Moyen — touche l'interface des adapters (base classes + null adapters)

---

### [T10] — Annotations return type dans 3 helpers de tests

**Priorité** : P2
**Sévérité** : 🟡 Mineur (impact mypy élevé)
**Fichier** :
- `aiprod_adaptation/tests/test_video_gen.py:46` — `_storyboard_and_output()`
- `aiprod_adaptation/tests/test_post_prod.py:49` — `_video_and_output()`
- `aiprod_adaptation/tests/test_continuity.py:24` — `_make_output()`
**Problème** : 3 fonctions helper sans annotation de retour → 23 erreurs `no-untyped-call` en cascade dans mypy full (12 + 10 + 1).
**Action** : Ajouter les return type annotations explicites. Pattern identique à T04 (déjà appliqué sur test_io, test_scheduling, test_backends, test_pipeline, test_image_gen).
- `_storyboard_and_output() -> tuple[StoryboardOutput, AIPRODOutput]` (ou type exact à vérifier)
- `_video_and_output() -> tuple[VideoOutput, AIPRODOutput]` (ou type exact à vérifier)
- `_make_output() -> AIPRODOutput`
**Tests impactés** : Les 3 fichiers concernés — 0 régression attendue
**Risque** : Faible

---

### [T11] — Nettoyer unused-ignore dans test_adaptation.py

**Priorité** : P2
**Sévérité** : 🟡 Mineur (impact mypy élevé)
**Fichier** : `aiprod_adaptation/tests/test_adaptation.py:438,441,457`
**Problème** : 3× `# type: ignore[override]` devenus `unused-ignore` après T04. Les fonctions aux lignes 438, 441, 457 sont également sans annotation complète (`Function is missing a type annotation`). La ligne 447 a un `no-untyped-call` sur `extract_all`.
**Action** :
1. Retirer les 3 `# type: ignore[override]` (ils ne suppriment plus rien)
2. Ajouter les annotations manquantes sur les 3 fonctions (lignes 438, 441, 457)
3. Vérifier si `extract_all` (ligne 447) nécessite une annotation ou un cast
4. Conserver le `# type: ignore` de mutation de frozen dataclass s'il est toujours actif
**Tests impactés** : `test_adaptation.py` (47 tests) — 0 régression attendue
**Risque** : Faible

---

### [T12] — Caster les dicts raw dans test_pipeline.py

**Priorité** : P2
**Sévérité** : 🟡 Mineur (impact mypy élevé)
**Fichier** : `aiprod_adaptation/tests/test_pipeline.py:51,61,72,136,149,157,164,170,209,227,237,246,256,265,275,378`
**Problème** : 22 erreurs mypy issues de dicts raw non castés vers `RawScene`, `VisualScene`, `ShotDict`. À la ligne 51, clés `shot_type` et `camera_movement` manquantes dans un `ShotDict` littéral. Lignes 136, 209, 378 : `dict` et `list` sans type arguments.
**Action** :
1. Ajouter `cast(RawScene, {...})`, `cast(VisualScene, {...})`, `cast(ShotDict, {...})` aux listes concernées
2. Ajouter `shot_type` et `camera_movement` au dict ShotDict ligne 51 (ou caster vers `ShotDict` avec `cast()`)
3. Typer les `dict` et `list` génériques (lignes 136, 209, 378)
4. S'assurer que `cast`, `RawScene`, `VisualScene`, `ShotDict` sont importés
**Tests impactés** : `test_pipeline.py` (55 tests) — 0 régression attendue
**Risque** : Faible

---

## Corrections P3 — MINEUR

### [T13] — Corriger le préfixe "PASS 2:" pour input vide

**Priorité** : P3
**Sévérité** : 🟡 Mineur
**Fichier** : `aiprod_adaptation/core/pass1_segment.py` (ou `core/engine.py:89`)
**Problème** : Un input vide retourne `[]` depuis Pass1, mais l'erreur levée en engine.py est `ValueError("PASS 2: StoryValidator produced no filmable scenes")` — préfixe `"PASS 2:"` trompeur quand la vraie cause est un input vide.
**Action** : Dans `pass1_segment.segment()`, ajouter un guard en début de fonction :
```python
if not text or not text.strip():
    raise ValueError("PASS 1: empty input text")
```
**Tests impactés** : `test_pipeline.py` — vérifier qu'un test couvre ce cas (sinon ajouter)
**Risque** : Faible

---

### [T14] — Dédupliquer CharacterRegistry dans engine.py

**Priorité** : P3
**Sévérité** : 🟡 Mineur
**Fichier** : `aiprod_adaptation/core/engine.py:33-38`
**Problème** : `CharacterRegistry()` instancié deux fois consécutivement — une fois pour `.build(output)` et une fois passé à `.enrich_from_text()`. Un seul objet suffit.
**Action** : Lire les lignes 33-38 de `engine.py`, puis refactorer en une seule instance :
```python
registry = CharacterRegistry().build(output)
output = _apply_continuity_enrichment(output, registry, raw_text)
```
**Tests impactés** : `test_pipeline.py`, `test_continuity.py` — comportement inchangé
**Risque** : Faible (refactoring cosmétique)

---

### [T15] — Retirer "felt" de INTERNAL_THOUGHT_WORDS

**Priorité** : P3
**Sévérité** : 🟡 Mineur
**Fichier** : `aiprod_adaptation/core/adaptation/story_validator.py:24`
**Problème** : `"felt"` dans `INTERNAL_THOUGHT_WORDS` filtre des actions physiques sensorielles filmables ("felt the cold breeze", "felt the floor shake"). Seul `"felt that"` est un marqueur de pensée interne.
**Action** : Retirer `"felt"` de la liste. Si la protection contre "felt that" est souhaitée, ajouter `"felt that"` à la place.
**Tests impactés** : `test_adaptation.py` — vérifier que les tests `TestStoryValidator` couvrent ce cas
**Risque** : Très faible — changement de comportement intentionnel et isolé

---

### [T16] — Migrer et supprimer novel_pipe.py

**Priorité** : P3
**Sévérité** : 🟡 Mineur
**Fichier** : `aiprod_adaptation/core/adaptation/novel_pipe.py` + `aiprod_adaptation/tests/test_adaptation.py:126-140`
**Problème** : `novel_pipe.py` est marqué `# DEAD CODE — deprecated` mais 2 tests `TestNovelPipe` persistent (`test_novel_pipe_null_adapter_returns_list`, `test_novel_pipe_null_adapter_deterministic`). Le fichier ne peut pas être supprimé tant que ces tests existent.
**Action** :
1. Vérifier si les 2 tests `TestNovelPipe` sont couverts par `TestStoryExtractor` (comportement équivalent)
2. Si oui, supprimer `TestNovelPipe` dans `test_adaptation.py`
3. Supprimer `novel_pipe.py`
**Tests impactés** : `test_adaptation.py` — 2 tests en moins (total : 276)
**Risque** : Faible si couverture StoryExtractor confirmée

---

### [T17] — Ajouter @field_validator range sur Shot.duration_sec

**Priorité** : P3
**Sévérité** : 🟡 Mineur
**Fichier** : `aiprod_adaptation/models/schema.py:Shot`
**Problème** : `duration_sec: int` sans contrainte Pydantic — la validation de range n'est assurée qu'en `pass4_compile.py`. Un `Shot` construit directement (hors pipeline) peut avoir `duration_sec=0` ou négatif sans erreur Pydantic.
**Action** : Ajouter un `@field_validator("duration_sec")` ou utiliser `Annotated[int, Field(ge=1, le=120)]`. Aligner la valeur max avec la constante utilisée dans `pass4_compile.py`.
**Tests impactés** : `test_pipeline.py`, `test_backends.py` — vérifier que les fixtures utilisent des valeurs valides
**Risque** : Faible — peut casser des fixtures avec `duration_sec=0` (à vérifier)

---

### [T18] — Ajouter tests unitaires manquants

**Priorité** : P3
**Sévérité** : 🟡 Mineur
**Fichier** : Nouveau fichier `tests/test_llm_router.py` (ou dans `test_adaptation.py`)
**Problème** : Aucun test pour : `LLMRouter` (routing null/claude/gemini), `audio_utils.py`, `ssml_builder.py`, `checkpoint.py`.
**Action** :
- `LLMRouter` : tester `route("null")` → `NullLLMAdapter`, `route("claude")` → `ClaudeAdapter` (mock), `route("gemini")` → `GeminiAdapter` (mock)
- `audio_utils.py` : tester les fonctions utilitaires exposées
- `ssml_builder.py` : tester la construction de balises SSML
- `checkpoint.py` : tester save/load state
**Tests impactés** : Nouveaux tests uniquement
**Risque** : Nul

---

## Ordre d'exécution recommandé

| Étape | ID | Titre | Fichiers touchés | Impact mypy |
|-------|-----|-------|-----------------|-------------|
| 1 | T10 | Annotations return type — 3 helpers | test_video_gen.py, test_post_prod.py, test_continuity.py | −23 erreurs |
| 2 | T11 | Nettoyer unused-ignore test_adaptation | test_adaptation.py | −8 erreurs |
| 3 | T12 | Caster dicts raw test_pipeline | test_pipeline.py | −22 erreurs |
| 4 | T08 | Imports lazy EpisodeScheduler | episode_scheduler.py | — |
| 5 | T13 | Corriger préfixe "PASS 2:" | pass1_segment.py | — |
| 6 | T14 | Dédupliquer CharacterRegistry | engine.py | — |
| 7 | T15 | Retirer "felt" de INTERNAL_THOUGHT_WORDS | story_validator.py | — |
| 8 | T17 | field_validator Shot.duration_sec | models/schema.py | — |
| 9 | T09 | Alimenter CostReport | episode_scheduler.py + adapters | — |
| 10 | T16 | Migrer/supprimer novel_pipe.py | novel_pipe.py, test_adaptation.py | — |
| 11 | T18 | Tests unitaires manquants | test_llm_router.py (nouveau) | — |

**Rationale ordre :** T10→T11→T12 en premier pour éliminer les 52 erreurs mypy full en masse (−53 erreurs attendues), puis T08 (risque le plus élevé en production), puis les correctifs fonctionnels purs (T13–T15, T17), puis les plus lourds (T09, T16, T18).

---

## Validation finale

```powershell
# Après chaque groupe de corrections :
venv\Scripts\Activate.ps1

# 1. Tests
pytest aiprod_adaptation/tests/ -q --tb=short
# → 278 passed (276 si T16 supprime 2 tests TestNovelPipe)

# 2. Mypy prod (doit rester à 0)
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py --strict
# → Success: no issues found in 41 source files

# 3. Mypy full (cible post T10+T11+T12)
mypy aiprod_adaptation/ --strict --ignore-missing-imports
# → cible : 0 erreurs (vs 52 actuellement)

# 4. Ruff
ruff check aiprod_adaptation/
# → All checks passed!
```
