---
title: "Plan d'action — Audit Master AIPROD_V2"
creation: 2026-04-23 à 15:07
source_audit: tasks/audits/resultats/audit_master_aiprod.md
baseline_commit: ab9bb76
corrections_totales: 6
p1_count: 1
p2_count: 3
p3_count: 2
---

# PLAN D'ACTION — AUDIT MASTER — 2026-04-23

**Source** : `tasks/audits/resultats/audit_master_aiprod.md`
**Généré le** : 2026-04-23 à 15:07
**Corrections totales** : 6 (P1:1 · P2:3 · P3:2)

---

## Résumé

Le repo est globalement sain sur le plan exécutable (`363 passed, 4 deselected`, mypy strict prod vert, Ruff vert, smoke `main.py` vert), donc le plan ne vise pas à sauver une base cassée mais à fermer les écarts les plus coûteux révélés par l'audit master du 2026-04-23. Le chemin critique tient en trois idées : rétablir les vrais contrats CLI, empêcher que des ruptures inter-couches passent silencieusement en production, puis rendre les erreurs de génération et les coûts réellement observables.

**Cible post-corrections :**
- `pytest aiprod_adaptation/tests/ -q --tb=short` : 363 passed, 4 deselected ✅
- déterminisme byte-level : inchangé ✅
- `mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py --strict` : 0 erreur ✅
- `ruff check .` : 0 erreur ✅
- `python main.py --input aiprod_adaptation/examples/sample.txt --title Sample 2>$null | python -m json.tool` : JSON valide ✅
- aucun `# type: ignore` dans le codebase ✅
- CI GitHub Actions : push main → green ✅

---

## Corrections P1 — CRITIQUE

### [M01] — Bloquer les ruptures silencieuses de références `shot_id`
**Priorité** : P1
**Sévérité** : 🟡
**Fichier** : `aiprod_adaptation/video_gen/video_sequencer.py:35`, `aiprod_adaptation/video_gen/video_sequencer.py:39`, `aiprod_adaptation/video_gen/video_sequencer.py:41`, `aiprod_adaptation/post_prod/audio_synchronizer.py:60`, `aiprod_adaptation/post_prod/audio_synchronizer.py:64`
**Problème** : Les couches aval acceptent des frames/clips pointant vers un `shot_id` absent et remplacent silencieusement les données manquantes par des valeurs par défaut (`duration=4`, `scene_id=""`, `prompt=""`, ou `clip.video_url` comme texte audio), ce qui laisse passer une incohérence inter-couches au lieu de l'arrêter.
**Action** : Ajouter une validation explicite lors de la construction des `VideoRequest` et `AudioRequest`; si `shot_id` n'est pas retrouvé dans le graphe IR, lever une `ValueError` descriptive au lieu de continuer avec des fallbacks implicites.
**Tests impactés** : `aiprod_adaptation/tests/test_video_gen.py`, `aiprod_adaptation/tests/test_post_prod.py`, `aiprod_adaptation/tests/test_scheduling.py` ; ajouter un test ciblé pour `shot_id` introuvable dans `VideoSequencer` et `AudioSynchronizer`.
**Risque** : Moyen — change le comportement d'échec runtime, mais dans le bon sens contractuel.

---

## Corrections P2 — IMPORTANT

### [M02] — Rendre effectif ou supprimer le faux flag CLI `pipeline --format`
**Priorité** : P2
**Sévérité** : 🟠
**Fichier** : `aiprod_adaptation/cli.py:204-207`, `aiprod_adaptation/core/engine.py:68-70`, `main.py`
**Problème** : Le flag `pipeline --format` est documenté comme un forçage du type d'entrée, mais `cmd_pipeline()` ne le consomme pas et `run_pipeline()` continue à classifier automatiquement l'entrée. La CLI annonce donc un contrat utilisateur qui n'existe pas.
**Action** : Choisir une seule direction et l'appliquer complètement : soit propager un paramètre `input_format` jusque dans `run_pipeline()`, soit supprimer le flag et son help des points d'entrée pour revenir à un contrat honnête.
**Tests impactés** : `aiprod_adaptation/tests/test_cli.py`, éventuellement `aiprod_adaptation/tests/test_pipeline.py` si le moteur expose un vrai override de format.
**Risque** : Moyen — touche la surface publique CLI, mais le changement est ciblé et testable.

---

### [M03] — Journaliser les exceptions aujourd'hui avalées dans checkpoint et génération
**Priorité** : P2
**Sévérité** : 🟠
**Fichier** : `aiprod_adaptation/image_gen/checkpoint.py:19`, `aiprod_adaptation/image_gen/storyboard.py:78`, `aiprod_adaptation/image_gen/storyboard.py:134`, `aiprod_adaptation/video_gen/video_sequencer.py:64`, `aiprod_adaptation/post_prod/audio_synchronizer.py:82`, `aiprod_adaptation/image_gen/character_prepass.py:75`
**Problème** : Plusieurs couches attrapent `Exception` puis passent sous silence ou dégradent vers `error://generation-failed` sans conserver la cause racine. Le système survit, mais devient difficile à diagnostiquer sur incident réel.
**Action** : Remplacer les captures silencieuses par des captures ciblées ou, à défaut, journaliser systématiquement la cause via structlog avant fallback. Pour `CheckpointStore`, au minimum logguer la lecture/validation échouée du cache.
**Tests impactés** : `aiprod_adaptation/tests/test_image_gen.py`, `aiprod_adaptation/tests/test_video_gen.py`, `aiprod_adaptation/tests/test_post_prod.py`, `aiprod_adaptation/tests/test_scheduling.py` ; ajouter des tests vérifiant que le fallback conserve l'artefact `error://...` tout en émettant un log ou en exposant la cause.
**Risque** : Faible à moyen — la logique métier reste identique, mais la télémétrie et potentiellement les signatures d'erreur changent.

---

### [M04] — Restaurer un contrat clair pour `schedule --output`
**Priorité** : P2
**Sévérité** : 🟡
**Fichier** : `aiprod_adaptation/cli.py:247`, `aiprod_adaptation/cli.py:377-381`
**Problème** : Le help promet `Directory or JSON path for SchedulerResult`, alors que l'implémentation force toujours un répertoire contenant `storyboard.json`, `video.json`, `production.json` et `metrics.json`.
**Action** : Aligner la CLI sur une seule vérité : soit corriger le help et les docs pour annoncer uniquement un dossier, soit implémenter réellement un mode fichier JSON agrégé si cette sémantique est utile.
**Tests impactés** : `aiprod_adaptation/tests/test_cli.py` ; ajouter un test qui verrouille explicitement la sémantique choisie.
**Risque** : Faible — essentiellement un alignement contrat/implémentation.

---

## Corrections P3 — MINEUR

### [M05] — Compléter l'observabilité économique runtime
**Priorité** : P3
**Sévérité** : 🟡
**Fichier** : `aiprod_adaptation/core/cost_report.py:12-38`, `aiprod_adaptation/core/run_metrics.py:17`, `aiprod_adaptation/core/scheduling/episode_scheduler.py:63`, `aiprod_adaptation/core/scheduling/episode_scheduler.py:71`, `aiprod_adaptation/core/scheduling/episode_scheduler.py:78`, adapters LLM/image/video/audio concernés
**Problème** : La structure de coût est correcte et les compteurs d'appels image/video/audio sont alimentés, mais aucune preuve runtime n'existe pour `llm_tokens_input`, `llm_tokens_output` ou les champs `*_cost_usd` hors tests et dataclasses.
**Action** : Ajouter une remontée minimale et déterministe des métriques coût/tokens depuis les adapters quand l'information est disponible; sinon documenter explicitement les champs qui restent non alimentés pour éviter toute fausse lecture des `metrics.json`.
**Tests impactés** : `aiprod_adaptation/tests/test_scheduling.py`, potentiellement `aiprod_adaptation/tests/test_adaptation.py` et `aiprod_adaptation/tests/test_cli.py` si les métriques sont exportées.
**Risque** : Moyen — touche plusieurs interfaces d'adapters si on choisit une intégration complète.

---

### [M06] — Fermer le trou de couverture sur les nouveaux contrats CLI/observabilité
**Priorité** : P3
**Sévérité** : 🟡
**Fichier** : `aiprod_adaptation/tests/test_cli.py`, `aiprod_adaptation/tests/test_image_gen.py`, `aiprod_adaptation/tests/test_video_gen.py`, `aiprod_adaptation/tests/test_post_prod.py`
**Problème** : L'audit a mis en évidence des zones où le comportement réel n'est pas verrouillé par des tests dédiés : `pipeline --format`, sémantique exacte de `schedule --output`, journalisation/fallback des exceptions de génération, et erreurs explicites sur références `shot_id` perdues.
**Action** : Ajouter les tests de non-régression correspondant aux corrections M01–M04 pour empêcher le retour des contrats faux ou des fallbacks silencieux.
**Tests impactés** : nouveaux tests uniquement, avec extension directe des suites existantes.
**Risque** : Faible.

---

## Ordre d'exécution recommandé

1. **M01** — Bloquer les ruptures silencieuses de références `shot_id`
2. **M02** — Rendre effectif ou supprimer le faux flag CLI `pipeline --format`
3. **M03** — Journaliser les exceptions aujourd'hui avalées dans checkpoint et génération
4. **M04** — Restaurer un contrat clair pour `schedule --output`
5. **M06** — Fermer le trou de couverture sur les nouveaux contrats CLI/observabilité
6. **M05** — Compléter l'observabilité économique runtime

**Rationale ordre :** M01 ferme le seul vrai problème de validation inter-couches. M02 et M04 rétablissent immédiatement l'honnêteté de la surface CLI. M03 rend enfin les échecs exploitables. M06 verrouille les nouveaux contrats. M05 vient ensuite car utile mais non bloquant pour la sûreté fonctionnelle actuelle.

---

## Validation finale

```powershell
venv\Scripts\Activate.ps1

# Validation principale
pytest aiprod_adaptation/tests/ -q --tb=short
ruff check .
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py --strict
python main.py --input aiprod_adaptation/examples/sample.txt --title Sample 2>$null | python -m json.tool > $null

# Validation ciblée après M01–M04
pytest aiprod_adaptation/tests/test_cli.py -q --tb=short
pytest aiprod_adaptation/tests/test_video_gen.py -q --tb=short
pytest aiprod_adaptation/tests/test_post_prod.py -q --tb=short
pytest aiprod_adaptation/tests/test_scheduling.py -q --tb=short
pytest aiprod_adaptation/tests/test_image_gen.py -q --tb=short
```

**Résultat attendu :** base verte inchangée, contrats CLI réalignés avec l'implémentation, erreurs de génération observables, et validation inter-couches renforcée.
