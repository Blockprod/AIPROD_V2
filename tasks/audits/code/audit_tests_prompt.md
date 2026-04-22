---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/resultats/audit_tests_aiprod.md
derniere_revision: 2026-04-21
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un QA Engineer spécialisé en suites de tests déterministes pour pipelines de traitement de données.
Tu réalises un audit EXCLUSIVEMENT sur les tests d'AIPROD_V2.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Réfléchis profondément étape par étape avant
de produire ta sortie. Explore d'abord, planifie
ensuite, puis exécute.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà :
  tasks/audits/resultats/audit_tests_aiprod.md

Si trouvé, affiche :
"⚠️ Audit tests existant détecté :
 Fichier : tasks/audits/resultats/audit_tests_aiprod.md
 Date    : [date modification]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit tests existant. Démarrage..."

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses TOUS les fichiers de test :

  test_adaptation.py  (47 tests) — LLM adaptation, story extractor, budget, validator
  test_backends.py     (9 tests) — CSV/JSON export
  test_cli.py          (9 tests) — CLI commands pipeline/storyboard/schedule, adapter choices
  test_continuity.py  (24 tests) — character registry, emotion arc, location, prop, prompt enricher
  test_image_gen.py   (46 tests) — storyboard, character prepass, image registry, checkpoint
  test_io.py           (6 tests) — save/load round-trip
  test_pipeline.py    (55 tests) — pass1→pass4 IR pipeline complet
  test_post_prod.py   (29 tests) — audio synchronizer, ffmpeg exporter, SSML, audio utils
  test_scheduling.py  (21 tests) — episode scheduler, run metrics, cost report
  test_video_gen.py   (32 tests) — video sequencer, smart router, runway/kling adapters

Baseline : 278 tests, 0 failing (commit 42f99d7, 2026-04-21)

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Cite fichier:ligne pour chaque problème
- Pas de conjecture : écris "À VÉRIFIER" sans preuve dans le code
- Sévérité : 🔴 critique · 🟠 majeure · 🟡 mineure

─────────────────────────────────────────────
BLOC 1 — INVENTAIRE DES TESTS PAR FICHIER
─────────────────────────────────────────────
Pour chaque fichier de test, liste toutes les classes et méthodes :
- Classe · Méthode · Ce qui est testé
- Total par fichier et total global (attendu: 278)
- Tous passants selon la dernière exécution ?

Fichiers à analyser dans l'ordre :
  test_pipeline.py · test_adaptation.py · test_image_gen.py · test_video_gen.py
  test_post_prod.py · test_scheduling.py · test_continuity.py
  test_cli.py · test_backends.py · test_io.py

─────────────────────────────────────────────
BLOC 2 — COUVERTURE PAR MODULE
─────────────────────────────────────────────
Pour chaque module source (pass1..pass4, engine, models/schema,
story_extractor, llm_router, episode_scheduler, storyboard,
character_prepass, video_sequencer, audio_synchronizer, cost_report,
cli, continuity/*) :
- Fonctions testées directement (liste)
- Fonctions testées indirectement via pipeline complet
- Fonctions non testées ou insuffisamment testées
- Branches non couvertes (raise ValueError, cas None, liste vide)

Points spécifiques à vérifier :
- CharacterPrepass.run() avec adapter échouant (result.failed > 0) ?
- LLMRouter : routage réel testé ou seulement isinstance(router, LLMAdapter) ?
- SmartVideoRouter : seuil de durée pour basculer runway↔kling testé ?
- CostReport.to_summary_str() testé ?
- FFmpegExporter.export() : cmd concat testé avec mock subprocess ?
- cli.py cmd_schedule() : tous les fichiers de sortie vérifiés ?

─────────────────────────────────────────────
BLOC 3 — QUALITÉ DES FIXTURES
─────────────────────────────────────────────
- Les fixtures utilisent-elles le format correct (raw_text vs visual_actions) ?
- Les scenes de test respectent-elles le format de sortie de Pass1 ?
- Les shots de test respectent-ils le format de sortie de Pass3 ?
- Dépendances entre tests (état global partagé) ?
- Fixtures de classe vs fixtures pytest.fixture : cohérence ?
- Tests d'intégration scheduler : utilisent NullImageAdapter/NullVideoAdapter/NullAudioAdapter ?
- Tests CharacterPrepass : que se passe-t-il si _unique_characters() retourne [] ?
  (vérifier test_character_prepass_handles_adapter_failure_gracefully)

─────────────────────────────────────────────
BLOC 4 — CAS LIMITES MANQUANTS
─────────────────────────────────────────────
Quels cas limites ne sont pas testés ?

Pipeline IR (test_pipeline.py) :
- Texte d'entrée vide → segment()
- Scène avec 0 visual_actions → simplify_shots()
- titre vide → compile_episode()
- Scène avec None dans la liste characters
- Episode avec 0 scènes après filtrage
- Caractères spéciaux dans le texte (guillemets, apostrophes)

Couche LLM (test_adaptation.py) :
- extract_all avec texte vide (0 chunks)
- LLMRouter avec les deux adapters en échec
- StoryValidator filtre toutes les scènes → liste vide
- ProductionBudget.max_scenes=0 → comportement ?

Pipeline production (test_scheduling.py / test_image_gen.py) :
- EpisodeScheduler avec timeline vide (0 scènes)
- CharacterPrepass avec AIPRODOutput sans personnages
- AudioSynchronizer avec VideoOutput sans clips

CLI (test_cli.py) :
- cmd_schedule avec dossier de sortie inexistant (création automatique ?)
- --image-adapter flux sans clé API → ImportError ou RuntimeError propre ?

CostReport :
- to_summary_str() format correct ?
- merge() associée à un CostReport vide (élément neutre) ?

─────────────────────────────────────────────
BLOC 5 — DÉTERMINISME BYTE-LEVEL
─────────────────────────────────────────────
- test_json_byte_identical existe et passe ?
- Le test vérifie-t-il l'identité byte-for-byte du JSON ou seulement l'égalité logique ?
- Le test garantit-il l'absence de variance entre deux runs ?

─────────────────────────────────────────────
FORMAT DE SORTIE
─────────────────────────────────────────────
# AUDIT TESTS — AIPROD_V2 — [DATE]
## Résumé exécutif (baseline: 278 tests, 0 failing)
## BLOC 1 — Inventaire des tests par fichier
## BLOC 2 — Couverture par module
## BLOC 3 — Qualité des fixtures
## BLOC 4 — Cas limites manquants
## BLOC 5 — Déterminisme byte-level
## Problèmes identifiés
| ID | Sévérité | Classe::méthode | Description |
## Tests manquants recommandés
