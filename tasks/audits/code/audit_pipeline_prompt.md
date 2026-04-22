---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/resultats/audit_pipeline_aiprod.md
derniere_revision: 2026-04-21
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un ingénieur en traitement de données spécialisé en pipelines déterministes.
Tu réalises un audit EXCLUSIVEMENT sur la cohérence des pipelines d'AIPROD_V2.

Deux pipelines à auditer :
  PIPELINE IR  : pass1_segment → pass2_visual → pass3_shots → pass4_compile → AIPRODOutput
  PIPELINE PROD: CharacterPrepass → StoryboardGenerator → VideoSequencer → AudioSynchronizer

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
  tasks/audits/resultats/audit_pipeline_aiprod.md

Si trouvé, affiche :
"⚠️ Audit pipeline existant détecté :
 Fichier : tasks/audits/resultats/audit_pipeline_aiprod.md
 Date    : [date modification]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit pipeline existant. Démarrage..."

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
PIPELINE IR (représentation interne) :
  pass1_segment.py · pass2_visual.py · pass3_shots.py · pass4_compile.py · engine.py

COUCHE LLM (adaptation narrative) :
  core/adaptation/story_extractor.py · llm_router.py · llm_adapter.py
  classifier.py · normalizer.py · novel_pipe.py · script_parser.py · story_validator.py

PIPELINE PRODUCTION (rendu) :
  core/scheduling/episode_scheduler.py
  image_gen/character_prepass.py · image_gen/storyboard.py
  video_gen/video_sequencer.py · post_prod/audio_synchronizer.py

CONTINUITÉ :
  core/continuity/prompt_enricher.py · location_registry.py · prop_registry.py
  image_gen/character_image_registry.py

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Cite fichier:ligne pour chaque problème
- Pas de conjecture : écris "À VÉRIFIER" sans preuve dans le code
- Sévérité : 🔴 critique · 🟠 majeure · 🟡 mineure

─────────────────────────────────────────────
BLOC 1 — CONTRATS INTER-PASSES (PIPELINE IR)
─────────────────────────────────────────────
Pour chaque frontière entre deux passes :

**Pass1 → Pass2** : segment() → visual_rewrite()
- Clés émises par Pass1 : [liste exacte depuis le code]
- Clés attendues par Pass2 : [liste exacte depuis le code]
- Clés manquantes / en trop : [diff]

**Pass2 → Pass3** : visual_rewrite() → simplify_shots()
- Clés émises par Pass2 : [liste exacte]
- Clés attendues par Pass3 : [liste exacte]
- Clés manquantes / en trop : [diff]

**Pass3 → Pass4** : simplify_shots() → compile_episode()
- Clés émises par Pass3 : [liste exacte]
- Clés attendues par Pass4 : [liste exacte]
- Clés manquantes / en trop : [diff]

─────────────────────────────────────────────
BLOC 1b — CONTRATS COUCHE LLM
─────────────────────────────────────────────
**engine.py → StoryExtractor.extract_all()**
- Signature : (llm: LLMAdapter, text: str, budget: ProductionBudget) → list[Scene]
- budget.max_chars_per_chunk utilisé pour chunker le texte ?
- prior_summary transmis entre chunks successifs ?
- Prompt contient "Maximum N scenes" quand max_scenes défini ?

**LLMRouter**
- Implémente LLMAdapter ?
- Clé de routage : sur quoi se base-t-il (longueur, type, config) ?

**StoryValidator**
- Filtre quelles scènes ? (scenes vides ? mood non reconnu ?)
- Modifie-t-il les données ou seulement filtre ?

─────────────────────────────────────────────
BLOC 1c — CONTRATS PIPELINE PRODUCTION
─────────────────────────────────────────────
**CharacterPrepass → StoryboardGenerator**
- prepass_result.registry transmis comme prepass_registry ?
- CharacterImageRegistry.get() retourne url ou None si absent ?

**StoryboardGenerator → VideoSequencer**
- StoryboardOutput.frames : liste de StoryboardFrame
- VideoSequencer attend quelles clés de StoryboardFrame ?

**VideoSequencer → AudioSynchronizer**
- VideoOutput.clips : liste de VideoClip
- AudioSynchronizer produit ProductionOutput.timeline : liste de TimelineClip
- latency_ms alimenté sur TimelineClip depuis AudioResult.latency_ms ?

**EpisodeScheduler.run() → SchedulerResult**
- metrics.image_latency_ms = sum(f.latency_ms for f in storyboard.frames) ?
- metrics.video_latency_ms = sum(c.latency_ms for c in video.clips) ?
- metrics.audio_latency_ms = sum(c.latency_ms for c in production.timeline) ?
- metrics.total_latency_ms = image + video + audio (sans double comptage) ?
─────────────────────────────────────────────
Pour chaque passe :
- Guard clause d'entrée vide ou None : présente/absente/correcte
- Type d'exception levée : ValueError ? TypeError ? AssertionError ?
- Message d'erreur : contient le préfixe "PASS N: " ?
- Cas limite non gérés : liste vide, champ vide, None dans sous-liste

─────────────────────────────────────────────
BLOC 3 — LOGIQUE DE TRANSFORMATION
─────────────────────────────────────────────
Pass1 — Segmentation :
- Conditions de split : location + time + paragraphe double `\n\n`
- scene_id format : f"SCN_{n:03d}" ?
- time_of_day : valeur par défaut ? None ou chaîne ?
- location par défaut : "Unknown" (capital U) ?

Pass2 — Visual rewrite :
- _INTERNAL_THOUGHT_WORDS : liste exacte dans le code ?
- EMOTION_RULES : 5 émotions ? ordre ? format tuple ?
- _DIALOGUE_RE : pattern exact ?
- transform_visuals alias vers visual_rewrite ?

Pass3 — Shot decomposition :
- shot_id format : f"{scene_id}_SHOT_{n:03d}" par scène ?
- shot_type assignment : CLOSE UP / WIDE SHOT / MEDIUM SHOT / POV ?
- Duration calcul : base=3, +1 chaque modificateur, clamp [3,8] ?
- atomize_shots alias vers simplify_shots ?

Pass4 — Compilation :
- Ordre validation : empty title → empty scenes → empty shots → Pydantic → ValueError ?
- episode_id : "EP01" hardcodé ?
- ValidationError → re-levé comme ValueError(str(exc)) ?
- compile_output alias avec inversion d'arguments ?

─────────────────────────────────────────────
BLOC 4 — DÉTERMINISME DU PIPELINE
─────────────────────────────────────────────
- Présence de random/uuid/shuffle/datetime dans les 4 passes
- Utilisation de set() avec itération : peut réordonner ?
- Tri explicite ou implicite : préserve-t-il l'ordre des scenes/shots ?
- Fonctions appelées deux fois avec le même input → même output garanti ?

─────────────────────────────────────────────
FORMAT DE SORTIE
─────────────────────────────────────────────
# AUDIT PIPELINE — AIPROD_V2 — [DATE]
## Résumé exécutif
## BLOC 1 — Contrats inter-passes (IR)
## BLOC 1b — Contrats couche LLM
## BLOC 1c — Contrats pipeline production
## BLOC 2 — Gardes et gestion d'erreurs
## BLOC 3 — Logique de transformation
## BLOC 4 — Déterminisme
## Problèmes identifiés
| ID | Sévérité | Passe | Fichier:ligne | Description |
## Recommandations prioritaires
