---
title: "Audit Master — AIPROD_V2"
creation: 2026-04-23 à 14:11
auditor: GitHub Copilot (GPT-5.4)
baseline_commit: ab9bb76
python: "3.11.9"
tests: "363 passed, 4 deselected"
mypy_prod: "0 erreur (43 fichiers)"
ruff: "0 erreur"
main_smoke: "OK"
---

# AUDIT MASTER — AIPROD_V2 — 2026-04-23

## Score global : 🟠 — 0 critique 🔴, 3 majeurs 🟠, 3 mineurs 🟡

## Résumé exécutif

Le repo est dans un état nettement plus mature que l'audit master précédent ne le laissait entendre. Le socle exécutable est propre au moment de cet audit : `pytest aiprod_adaptation/tests/ -q --tb=short` retourne `363 passed, 4 deselected`, `ruff check .` est vert, `mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py --strict` est vert, et un smoke test `python main.py --input aiprod_adaptation/examples/sample.txt --title Sample | python -m json.tool` passe.

Le coeur du concept est validé : pipeline IR 4 passes déterministe, branche LLM réelle avec routeur observable, comparateur rules vs LLM, scheduler image/video/audio, persistance JSON, CI GitHub Actions, et couverture de tests désormais répartie sur 11 fichiers. Les écarts encore ouverts ne remettent pas en cause la viabilité du système, mais ils touchent des zones importantes de contrat utilisateur et d'observabilité runtime : un flag CLI annoncé mais non effectif, plusieurs `except Exception` silencieux dans les couches de génération, et une observabilité coût encore partielle malgré une structure correcte.

## DIMENSION 1 — Structure (repo actuel)

### Constats vérifiés

- Le découpage par couches est clair et encore cohérent : IR déterministe dans `core/pass1_segment.py` → `core/pass2_visual.py` → `core/pass3_shots.py` → `core/pass4_compile.py`, adaptation LLM dans `core/adaptation/`, continuité dans `core/continuity/`, production dans `image_gen/`, `video_gen/`, `post_prod/`.
- `aiprod_adaptation/core/engine.py` reste le point d'orchestration central, avec logging structlog sur stderr et séparation nette entre chemin script, chemin novel LLM et fallback rules.
- `aiprod_adaptation/core/scheduling/episode_scheduler.py` orchestre bien image → video → audio et ne dépend pas de classes concrètes de providers au top-level, seulement des interfaces d'adapters.

### Lecture d'ensemble

La structure globale est bonne et nettement plus avancée que ce que documentait l'audit du 2026-04-21. Je ne vois pas de dette architecturale critique dans le découpage lui-même. Les fragilités actuelles sont davantage dans les bords runtime que dans l'architecture des modules.

## DIMENSION 2 — Cohérence pipeline

### Constats vérifiés

- `aiprod_adaptation/core/pass4_compile.py` verrouille bien les invariants d'assemblage : titre non vide, listes non vides, validation des `scene_id` référencés par les shots, et remontée des `ValidationError` Pydantic en `ValueError(str(exc))`.
- `aiprod_adaptation/core/engine.py` applique un enchaînement cohérent : classification d'entrée, extraction LLM ou fallback rules, `StoryValidator`, pass3, pass4, puis enrichissement continuité optionnel.
- Les tests pipeline couvrent les entrées vides, la segmentation multi-scènes, les sauts temporels, le déterminisme et les contraintes pass4 dans `aiprod_adaptation/tests/test_pipeline.py`.

### Problème détecté

- 🟡 `aiprod_adaptation/video_gen/video_sequencer.py:35`, `aiprod_adaptation/video_gen/video_sequencer.py:39`, `aiprod_adaptation/video_gen/video_sequencer.py:41`, `aiprod_adaptation/post_prod/audio_synchronizer.py:60`, `aiprod_adaptation/post_prod/audio_synchronizer.py:64` : si une frame ou un clip référence un `shot_id` absent du graphe IR, la couche aval continue avec des valeurs par défaut (`duration=4`, `scene_id=""`, `prompt=""`, ou `clip.video_url` comme texte audio) au lieu de signaler explicitement une rupture de contrat inter-couches.

## DIMENSION 3 — Tests (363 passés, 4 désélectionnés)

### Répartition constatée

| Fichier | Tests détectés |
|---|---:|
| `test_adaptation.py` | 83 |
| `test_backends.py` | 9 |
| `test_cli.py` | 40 |
| `test_comparison.py` | 5 |
| `test_continuity.py` | 24 |
| `test_image_gen.py` | 47 |
| `test_io.py` | 6 |
| `test_pipeline.py` | 64 |
| `test_post_prod.py` | 30 |
| `test_scheduling.py` | 23 |
| `test_video_gen.py` | 32 |

### Constats vérifiés

- La branche LLM est désormais bien plus couverte que dans l'ancien audit : router policy, trace, fallback, quarantaine, compare CLI et régressions `chapter1.txt` existent dans `aiprod_adaptation/tests/test_adaptation.py` et `aiprod_adaptation/tests/test_cli.py`.
- La couche comparaison a maintenant sa propre suite dédiée dans `aiprod_adaptation/tests/test_comparison.py`.
- Le scheduler et les métriques ont une couverture dédiée dans `aiprod_adaptation/tests/test_scheduling.py`.

### Gaps résiduels visibles

- 🟡 `aiprod_adaptation/cli.py:247` combiné à `aiprod_adaptation/cli.py:377-381` : le help de `schedule --output` promet "Directory or JSON path for SchedulerResult", mais les tests existants dans `aiprod_adaptation/tests/test_cli.py:728-763` ne couvrent que le mode répertoire, qui est le seul mode réellement implémenté aujourd'hui.

## DIMENSION 4 — Qualité technique

### Constats vérifiés

- `pyproject.toml` déclare `requires-python = ">=3.11"`, Pydantic v2, structlog et les dépendances dev attendues.
- `.github/workflows/ci.yml` exécute Ruff, mypy strict sur la cible prod et pytest.
- La recherche `# type: ignore` sur `**/*.py` n'a retourné aucun match dans le workspace audité.
- `aiprod_adaptation/core/engine.py:21-25` configure structlog avec `PrintLoggerFactory(file=sys.stderr)`, ce qui respecte l'invariant projet de ne pas polluer stdout.

### Lecture d'ensemble

Le niveau de qualité statique est bon. Les problèmes restants de cette dimension ne sont pas des problèmes de typage ou de style; ce sont des problèmes de comportement runtime silencieux qui échappent naturellement à Ruff et mypy.

## DIMENSION 5 — Déterminisme

### Constats vérifiés

- Les tests de déterminisme sont présents dans plusieurs couches : `aiprod_adaptation/tests/test_pipeline.py:242`, `aiprod_adaptation/tests/test_backends.py:63`, `aiprod_adaptation/tests/test_backends.py:86`, `aiprod_adaptation/tests/test_image_gen.py`, `aiprod_adaptation/tests/test_video_gen.py`, `aiprod_adaptation/tests/test_post_prod.py`, `aiprod_adaptation/tests/test_continuity.py`.
- Les constantes critiques côté core utilisent `frozenset`, notamment dans `aiprod_adaptation/core/pass1_segment.py:70`, `aiprod_adaptation/core/pass1_segment.py:79` et `aiprod_adaptation/core/pass4_compile.py:11`.
- L'enrichissement continuité maintient explicitement la stabilité d'ordre via `sorted()` dans `aiprod_adaptation/core/continuity/prompt_enricher.py:62-63` et `aiprod_adaptation/core/continuity/prop_registry.py:46`.
- La recherche ciblée sur `aiprod_adaptation/core/**` n'a trouvé aucune utilisation effective de `random`, `uuid`, `shuffle`, `choice`, `datetime.now()` ou `time.time()` dans le runtime core audité.

### Lecture d'ensemble

La dimension déterminisme reste forte. Je ne vois pas d'indice d'une régression conceptuelle sur ce point.

## DIMENSION 6 — Schémas Pydantic & validation

### Constats vérifiés

- `aiprod_adaptation/models/schema.py:29`, `aiprod_adaptation/models/schema.py:38` et `aiprod_adaptation/models/schema.py:47` valident explicitement `duration_sec`, `shot_type` et `camera_movement`.
- `aiprod_adaptation/core/pass4_compile.py:54-76` convertit les erreurs Pydantic en `ValueError`, conformément aux invariants projet.
- Les tests associés existent dans `aiprod_adaptation/tests/test_pipeline.py` et couvrent les durées invalides, les types de plans et les mouvements caméra invalides.

### Lecture d'ensemble

Les schémas sont cohérents et serrés. Je ne relève pas d'écart majeur dans la modélisation Pydantic actuelle.

## DIMENSION 7 — Observabilité

### Constats vérifiés

- `aiprod_adaptation/core/engine.py:64`, `aiprod_adaptation/core/engine.py:95`, `aiprod_adaptation/core/engine.py:145`, `aiprod_adaptation/core/engine.py:210` journalisent les étapes structurantes du pipeline et les échecs de frames storyboard.
- `aiprod_adaptation/core/adaptation/llm_router.py` fournit une trace de décision détaillée (`trace_history`, `last_trace`) et la CLI sait l'exporter via `aiprod_adaptation/cli.py:55-63`, `aiprod_adaptation/cli.py:79-98`, `aiprod_adaptation/cli.py:338-343`, `aiprod_adaptation/cli.py:425-430`.
- `aiprod_adaptation/core/run_metrics.py:17` et `aiprod_adaptation/core/cost_report.py:25-38` donnent une base saine pour les métriques et le coût agrégé.

### Problèmes détectés

- 🟠 `aiprod_adaptation/image_gen/checkpoint.py:19` : `CheckpointStore` avale silencieusement toute erreur de lecture/parse/cache (`except Exception: pass`). Un checkpoint corrompu ou illisible devient un cache miss muet, sans signal dans les logs.
- 🟠 `aiprod_adaptation/image_gen/storyboard.py:78`, `aiprod_adaptation/image_gen/storyboard.py:134`, `aiprod_adaptation/video_gen/video_sequencer.py:64`, `aiprod_adaptation/post_prod/audio_synchronizer.py:82`, `aiprod_adaptation/image_gen/character_prepass.py:75` : plusieurs couches de génération capturent `Exception` puis dégradent silencieusement vers `error://generation-failed` ou un simple compteur `failed += 1`, sans journaliser la cause racine. Le système reste robuste, mais devient beaucoup moins diagnostiquer en conditions réelles.
- 🟡 La structure coût est présente, mais l'observabilité économique reste partielle. La recherche workspace montre des écritures runtime pour `metrics.cost.image_api_calls`, `metrics.cost.video_api_calls` et `metrics.cost.audio_api_calls` dans `aiprod_adaptation/core/scheduling/episode_scheduler.py:63`, `aiprod_adaptation/core/scheduling/episode_scheduler.py:71`, `aiprod_adaptation/core/scheduling/episode_scheduler.py:78`. En revanche, aucune écriture runtime n'a été trouvée pour `llm_tokens_input`, `llm_tokens_output` ou `*_cost_usd` hors `aiprod_adaptation/core/cost_report.py` et les tests.

## DIMENSION 8 — CLI & adapters

### Constats vérifiés

- La CLI packagée couvre désormais `pipeline`, `storyboard`, `schedule` et `compare` dans `aiprod_adaptation/cli.py`.
- Le routeur LLM est réellement configurable et exportable côté CLI (`--router-short-provider`, `--router-trace-output`, `--max-chars-per-chunk`).
- `main.py` supporte maintenant le chemin LLM réel avec `--require-llm`, export de trace et override de chunking, et le smoke test JSON passe.
- Les imports des adapters concrets restent lazy dans les chargeurs `_load_image_adapter`, `_load_llm_adapter`, `_load_video_adapter`, `_load_audio_adapter` de `aiprod_adaptation/cli.py`.

### Problèmes détectés

- 🟠 `aiprod_adaptation/cli.py:204-207` annonce `pipeline --format` comme un moyen de "Force input format (auto-detected if omitted)", mais `cmd_pipeline()` ne lit jamais `args.format`, et `aiprod_adaptation/core/engine.py:68-70` continue à décider exclusivement via `InputClassifier().classify(text)`. C'est un contrat utilisateur cassé : le flag existe mais n'a aucun effet.
- 🟡 `aiprod_adaptation/cli.py:247` annonce pour `schedule --output` un "Directory or JSON path for SchedulerResult", mais `aiprod_adaptation/cli.py:377-381` crée systématiquement un répertoire puis y écrit `storyboard.json`, `video.json`, `production.json` et `metrics.json`. Le comportement actuel est cohérent en mode dossier, mais le help ment sur le mode fichier JSON.

## Écarts par rapport à l'audit master du 2026-04-21

L'ancien audit n'est plus une photographie fiable du repo. Les écarts les plus nets sont :

1. La base de tests n'est plus à `278`, mais à `363 passed, 4 deselected`, répartis sur 11 fichiers.
2. La couche router/compare a désormais une couverture et une opérabilité réelles : tests de matrice routeur, compare CLI, trace exportable et validations `chapter1.txt` existent.
3. Le scheduler n'est plus un chantier théorique : il existe, écrit ses artefacts attendus, et alimente déjà les compteurs d'appels image/video/audio.
4. Le problème ancien sur les imports top-level d'adapters concrets dans le scheduler n'est plus représentatif de l'état actuel de `aiprod_adaptation/core/scheduling/episode_scheduler.py`.

## Tableau consolidé des problèmes

| ID | Dim | Sévérité | Fichier:ligne | Description |
|---|---|---|---|---|
| M-01 | 8 | 🟠 | `aiprod_adaptation/cli.py:204-207`, `aiprod_adaptation/core/engine.py:68-70` | Le flag `pipeline --format` est documenté comme forçage du type d'entrée, mais il n'est jamais consommé; l'auto-classification reste toujours active. |
| M-02 | 7 | 🟠 | `aiprod_adaptation/image_gen/checkpoint.py:19` | Lecture de checkpoint protégée par `except Exception: pass`, ce qui masque corruption de cache et erreurs I/O. |
| M-03 | 7 | 🟠 | `aiprod_adaptation/image_gen/storyboard.py:78`, `aiprod_adaptation/image_gen/storyboard.py:134`, `aiprod_adaptation/video_gen/video_sequencer.py:64`, `aiprod_adaptation/post_prod/audio_synchronizer.py:82`, `aiprod_adaptation/image_gen/character_prepass.py:75` | Les couches de génération attrapent des exceptions larges sans journalisation structurée de la cause, ce qui réduit fortement la diagnosabilité runtime. |
| m-01 | 2 | 🟡 | `aiprod_adaptation/video_gen/video_sequencer.py:35`, `:39`, `:41`, `aiprod_adaptation/post_prod/audio_synchronizer.py:60`, `:64` | Les ruptures de référence `shot_id` dans les couches aval sont converties en valeurs de repli silencieuses au lieu d'échouer explicitement. |
| m-02 | 8 | 🟡 | `aiprod_adaptation/cli.py:247`, `aiprod_adaptation/cli.py:377-381` | Le help de `schedule --output` promet un chemin fichier JSON ou un dossier, mais seule la sémantique dossier est implémentée. |
| m-03 | 7 | 🟡 | `aiprod_adaptation/core/cost_report.py:12-38`, `aiprod_adaptation/core/run_metrics.py:17`, `aiprod_adaptation/core/scheduling/episode_scheduler.py:63`, `:71`, `:78` | La structure de coût est bonne, mais l'alimentation runtime reste partielle : appels image/video/audio incrémentés, pas de preuve d'alimentation runtime pour tokens LLM ni coûts USD. |

## Plan de correction suggéré

1. Corriger ou supprimer le faux contrat `pipeline --format`, puis ajouter un test CLI qui prouve le forçage réel du type d'entrée.
2. Remplacer les `except Exception` silencieux des couches storyboard/video/audio/prepass/checkpoint par des captures ciblées avec logs structurés et conservation de la cause racine.
3. Faire échouer explicitement `VideoSequencer` et `AudioSynchronizer` quand un `shot_id` attendu n'est plus résolu depuis l'IR amont.
4. Aligner le help de `schedule --output` sur le comportement réel, ou implémenter réellement le mode fichier JSON agrégé promis par l'aide.
5. Compléter l'observabilité économique en alimentant `llm_tokens_input`, `llm_tokens_output` et `*_cost_usd` dans les chemins runtime réels, pas seulement dans les dataclasses et les tests.

## Verdict

Le projet est proche d'un état v1 technique crédible. Les fondations sont bonnes, la validation est solide, et la fermeture router récente change clairement la lecture globale du repo. Les prochains gains à fort levier ne sont plus dans la création de nouvelles briques fondamentales, mais dans la cohérence des contrats CLI et dans l'observabilité fine des erreurs et des coûts en production locale.
