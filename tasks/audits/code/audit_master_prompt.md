---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/resultats/audit_master_aiprod.md
derniere_revision: 2026-04-21
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un Software Architect senior spécialisé en audit complet de systèmes de compilation déterministes.
Tu réalises un audit MASTER couvrant TOUTES les dimensions d'AIPROD_V2.

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
  tasks/audits/resultats/audit_master_aiprod.md

Si trouvé, affiche :
"⚠️ Audit master existant détecté :
 Fichier : tasks/audits/resultats/audit_master_aiprod.md
 Date    : [date modification]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit master existant. Démarrage..."

─────────────────────────────────────────────
PÉRIMÈTRE
─────────────────────────────────────────────
Audit complet de toutes les dimensions :
1. Structure & architecture
2. Cohérence pipeline text→AIPRODOutput→image/video/audio
3. Tests & couverture (278 tests, 10 fichiers)
4. Qualité technique (mypy/ruff/CI)
5. Déterminisme byte-level
6. Schémas Pydantic & validation
7. Observabilité (CostReport, RunMetrics, structlog)
8. CLI & adapters de production

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Cite fichier:ligne pour chaque problème
- Pas de conjecture : écris "À VÉRIFIER" sans preuve dans le code
- Sévérité : 🔴 critique · 🟠 majeure · 🟡 mineure
- Ne lis PAS les fichiers .md sauf WORKFLOW.md et lessons.md

─────────────────────────────────────────────
DIMENSION 1 — STRUCTURE
─────────────────────────────────────────────
Packages à analyser (68 modules source) :
  core/ · core/adaptation/ · core/continuity/ · core/rules/ · core/scheduling/
  image_gen/ · video_gen/ · post_prod/ · backends/ · models/ · cli.py

- Pipeline IR : pass1_segment → pass2_visual → pass3_shots → pass4_compile
- Pipeline LLM : StoryExtractor(extract_all) → LLMRouter → AIPRODOutput
- Pipeline production : CharacterPrepass → StoryboardGenerator → VideoSequencer → AudioSynchronizer
- SRP : chaque passe/module fait une seule chose
- Couplage : imports runtime vs top-level dans engine.py
- Aliases backward-compat : justifiés ou dettes techniques ?
- Fichiers présents mais non utilisés

─────────────────────────────────────────────
DIMENSION 2 — COHÉRENCE PIPELINE
─────────────────────────────────────────────
Frontières à auditer :
- Pass1 → Pass2 → Pass3 → Pass4 (IR interne)
- StoryExtractor → AIPRODOutput (contrat Pydantic)
- EpisodeScheduler : CharacterPrepass → StoryboardGenerator → VideoSequencer → AudioSynchronizer
- Contrats : clés émises = clés attendues à chaque frontière
- Guards vides : toutes les passes vérifient les entrées vides
- Préfixes d'erreur : "PASS 1:", "PASS 2:", "PASS 3:", "PASS 4:"
- Formats dict : snake_case cohérent, pas de camelCase
- Ordre scènes/shots préservé à travers les passes

─────────────────────────────────────────────
DIMENSION 3 — TESTS
─────────────────────────────────────────────
État actuel : 278 tests, 10 fichiers, 0 failing
  test_adaptation.py (47) · test_backends.py (9) · test_cli.py (9)
  test_continuity.py (24) · test_image_gen.py (46) · test_io.py (6)
  test_pipeline.py (55) · test_post_prod.py (29) · test_scheduling.py (21)
  test_video_gen.py (32)

- Couverture : fonctions non testées dans chaque package ?
- Fixtures au bon format pour chaque couche
- Test déterminisme byte-level (test_json_byte_identical) ?
- Cas limites : texte vide, listes vides, None, caractères spéciaux
- Tests d'intégration scheduler (NullAdapters) présents ?

─────────────────────────────────────────────
DIMENSION 4 — QUALITÉ TECHNIQUE
─────────────────────────────────────────────
- pyproject.toml complet (Python ≥3.11, pydantic, structlog, pytest, mypy)
- Annotations de types : toutes les fonctions publiques annotées
- Aucun # type: ignore dans le codebase (règle absolue)
- mypy --strict : 0 erreur sur 60 fichiers source
- ruff check : 0 erreur
- structlog → stderr uniquement, logs dans engine.py uniquement
- CI/CD : .github/workflows/ présent ?

─────────────────────────────────────────────
DIMENSION 5 — DÉTERMINISME
─────────────────────────────────────────────
- Aucun random/uuid/shuffle/choice dans core/
- Aucun datetime.now()/time.time() dans core/
- Aucun set() avec itération non triée
- sorted() uniquement si l'ordre final ne change pas
- Deux appels successifs run_pipeline(text, title) → JSON byte-identique

─────────────────────────────────────────────
DIMENSION 6 — SCHÉMAS PYDANTIC
─────────────────────────────────────────────
- Scene : tous les champs requis présents et typés
- Shot : duration_sec int sans contrainte Pydantic (validation Pass4 uniquement)
- Episode : episode_id = "EP01"
- AIPRODOutput : title + episodes
- ValidationError → ValueError(str(exc)) dans Pass4
- StoryboardFrame, VideoClip, TimelineClip : champs latency_ms présents ?
- ProductionOutput : resolution/fps defaults corrects ?
- AudioRequest : field_validator duration_hint_sec ≥ 1 ?

─────────────────────────────────────────────
DIMENSION 7 — OBSERVABILITÉ
─────────────────────────────────────────────
- CostReport : total_cost_usd = somme des 4 catégories ?
- CostReport.merge() : tous les champs additionnés ?
- RunMetrics.cost : field(default_factory=CostReport) présent ?
- RunMetrics.total_latency_ms = image + video + audio (pas de double-comptage) ?
- EpisodeScheduler alimente-t-il les métriques latency pour chaque stage ?

─────────────────────────────────────────────
DIMENSION 8 — CLI & ADAPTERS
─────────────────────────────────────────────
Commandes CLI disponibles : pipeline · storyboard · schedule
- --image-adapter choices: null | flux | replicate
- --video-adapter choices: null | runway | kling | smart
- --audio-adapter choices: null | elevenlabs | openai
- cmd_schedule() produit storyboard.json + video.json + production.json + metrics.json ?
- Adapters prod importés en lazy import (pas d'ImportError sans clé API) ?
- SmartVideoRouter délègue selon durée du clip (seuil à vérifier) ?

─────────────────────────────────────────────
FORMAT DE SORTIE
─────────────────────────────────────────────
# AUDIT MASTER — AIPROD_V2 — [DATE]
## Score global : [🔴/🟠/🟡] — [N problèmes critiques, M majeurs, K mineurs]
## Résumé exécutif
## DIMENSION 1 — Structure (68 modules)
## DIMENSION 2 — Cohérence pipeline
## DIMENSION 3 — Tests (278 attendus)
## DIMENSION 4 — Qualité technique
## DIMENSION 5 — Déterminisme
## DIMENSION 6 — Schémas Pydantic
## DIMENSION 7 — Observabilité
## DIMENSION 8 — CLI & Adapters
## Tableau consolidé des problèmes
| ID | Dim | Sévérité | Fichier:ligne | Description |
## Plan de correction suggéré
