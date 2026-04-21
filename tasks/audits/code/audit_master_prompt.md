---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/resultats/audit_master_aiprod.md
derniere_revision: 2026-04-20
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
2. Cohérence pipeline Pass1→Pass4
3. Tests & couverture
4. Qualité technique (mypy/ruff/CI)
5. Déterminisme byte-level
6. Schémas Pydantic & validation

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
- Pipeline réel : segment → visual_rewrite → simplify_shots → compile_episode
- SRP : chaque passe fait une seule chose
- Couplage : imports runtime vs top-level dans engine.py
- Aliases backward-compat : justifiés ou dettes techniques ?
- Fichiers présents mais non utilisés

─────────────────────────────────────────────
DIMENSION 2 — COHÉRENCE PIPELINE
─────────────────────────────────────────────
- Contrats inter-passes : clés émises = clés attendues ?
- Guards vides : toutes les passes vérifient les entrées vides
- Préfixes d'erreur : "PASS 1:", "PASS 2:", "PASS 3:", "PASS 4:"
- Formats dict : snake_case cohérent, pas de camelCase
- Ordre scènes/shots préservé à travers les passes

─────────────────────────────────────────────
DIMENSION 3 — TESTS
─────────────────────────────────────────────
- 32 tests présents et passants ?
- Couverture : fonctions non testées ?
- Fixtures au bon format (raw_text pour Pass1→2, visual_actions pour Pass2→3)
- Test déterminisme byte-level (test_json_byte_identical) ?
- Cas limites : texte vide, listes vides, None, caractères spéciaux

─────────────────────────────────────────────
DIMENSION 4 — QUALITÉ TECHNIQUE
─────────────────────────────────────────────
- pyproject.toml complet (Python ≥3.11, pydantic, structlog, pytest, mypy)
- Annotations de types : toutes les fonctions publiques annotées
- Aucun # type: ignore dans le codebase
- structlog → stderr uniquement
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

─────────────────────────────────────────────
FORMAT DE SORTIE
─────────────────────────────────────────────
# AUDIT MASTER — AIPROD_V2 — [DATE]
## Score global : [🔴/🟠/🟡] — [N problèmes critiques, M majeurs, K mineurs]
## Résumé exécutif
## DIMENSION 1 — Structure
## DIMENSION 2 — Pipeline
## DIMENSION 3 — Tests
## DIMENSION 4 — Qualité technique
## DIMENSION 5 — Déterminisme
## DIMENSION 6 — Schémas Pydantic
## Tableau consolidé des problèmes
| ID | Dim | Sévérité | Fichier:ligne | Description |
## Plan de correction suggéré
