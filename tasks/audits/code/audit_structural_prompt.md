---
modele: sonnet-4.6
mode: ask
contexte: codebase
produit: tasks/audits/resultats/audit_structural_aiprod.md
derniere_revision: 2026-04-21
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un Software Architect spécialisé en compilateurs déterministes et systèmes de traitement de données structurées.
Tu réalises un audit EXCLUSIVEMENT structurel sur AIPROD_V2.

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
  tasks/audits/resultats/audit_structural_aiprod.md

Si trouvé, affiche :
"⚠️ Audit structurel existant détecté :
 Fichier : tasks/audits/resultats/audit_structural_aiprod.md
 Date    : [date modification]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit structurel existant. Démarrage..."

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses UNIQUEMENT la structure du repo (68 modules) :
organisation des modules, couplage, SRP, interfaces,
dette technique, formats de données inter-passes.

Packages à couvrir :
  core/ · core/adaptation/ · core/continuity/ · core/rules/ · core/scheduling/
  image_gen/ · video_gen/ · post_prod/ · backends/ · models/ · cli.py

Tu n'analyses PAS les tests, le déterminisme,
les schémas Pydantic en détail, ou le CI/CD.

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Ne lis aucun fichier .md, .txt, .rst
- Cite fichier:ligne pour chaque problème
- Écris "À VÉRIFIER" sans preuve dans le code
- Sévérité : 🔴 critique · 🟠 majeure · 🟡 mineure

─────────────────────────────────────────────
BLOC 1 — PIPELINES RÉELS
─────────────────────────────────────────────
Trace le chemin complet :

PIPELINE IR :
  text → pass1_segment() → pass2_visual_rewrite() → pass3_simplify_shots() → pass4_compile() → AIPRODOutput

PIPELINE LLM :
  text → StoryExtractor.extract_all(llm, text, budget) → list[Scene] → pass4_compile → AIPRODOutput
  engine.py appelle extract_all (pas extract) depuis le commit PC-08

PIPELINE PRODUCTION :
  AIPRODOutput → EpisodeScheduler.run()
    → CharacterPrepass.run() → CharacterImageRegistry
    → StoryboardGenerator.generate() → StoryboardOutput
    → VideoSequencer.generate() → VideoOutput
    → AudioSynchronizer.generate() → ProductionOutput
    → SchedulerResult(storyboard, video, production, metrics)

Pour chaque passe/module :
- Fichier source et fonction principale
- Type d'entrée exact
- Type de sortie exact
- Cohérence avec l'étape suivante

─────────────────────────────────────────────
BLOC 2 — SÉPARATION DES RESPONSABILITÉS
─────────────────────────────────────────────
Chaque module doit avoir une seule responsabilité.
Identifie les violations SRP avec fichier:ligne :
- Logique de validation dans les passes de transformation
- Logique de transformation dans la compilation
- Imports croisés entre passes
- Fonctions qui font plus d'une chose

─────────────────────────────────────────────
BLOC 3 — COUPLAGE INTER-MODULES
─────────────────────────────────────────────
- Imports top-level vs imports runtime dans engine.py et cli.py
- Dépendances circulaires potentielles (ex: storyboard.py ↔ character_prepass.py)
  NB : la solution adoptée = storyboard.py accepte CharacterImageRegistry, pas CharacterPrepassResult
- Accès direct aux internals d'une autre passe
- Aliases backward-compat (compile_output, atomize_shots, transform_visuals) : justifiés ou dettes ?
- Adapters prod (flux, replicate, runway, kling, elevenlabs) : import lazy dans cli.py ?

─────────────────────────────────────────────
BLOC 4 — ARCHITECTURE GLOBALE
─────────────────────────────────────────────
- Correspondance entre README.md et le code réel
- Fichiers présents mais non utilisés
- Fichiers manquants attendus par la spec
- Structure des packages (aiprod_adaptation/ vs racine)

Nouveaux packages à évaluer depuis SO v1 :
  core/continuity/ : character_registry, emotion_arc, location_registry, prop_registry, prompt_enricher
  core/scheduling/ : episode_scheduler
  image_gen/ : character_prepass, character_image_registry, character_sheet, checkpoint
  video_gen/ : smart_video_router, kling_adapter, runway_adapter
  post_prod/ : ffmpeg_exporter, audio_synchronizer, ssml_builder, audio_utils, elevenlabs_adapter, openai_tts_adapter
  core/cost_report.py · core/run_metrics.py (champ cost ajouté)
  cli.py : commandes pipeline | storyboard | schedule + adapter choices

─────────────────────────────────────────────
FORMAT DE SORTIE
─────────────────────────────────────────────
# AUDIT STRUCTUREL — AIPROD_V2 — [DATE]
## Résumé exécutif
## BLOC 1 — Pipeline réel
## BLOC 2 — SRP
## BLOC 3 — Couplage
## BLOC 4 — Architecture
## Problèmes identifiés
| ID | Sévérité | Fichier:ligne | Description |
## Recommandations prioritaires
