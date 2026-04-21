---
modele: sonnet-4.6
mode: ask
contexte: codebase
produit: tasks/audits/resultats/audit_structural_aiprod.md
derniere_revision: 2026-04-20
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
Tu analyses UNIQUEMENT la structure du repo :
organisation des modules, couplage, SRP, interfaces,
dette technique, formats de données inter-passes.

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
BLOC 1 — PIPELINE RÉEL
─────────────────────────────────────────────
Trace le chemin complet text → AIPRODOutput :
  segment() → visual_rewrite() → simplify_shots() → compile_episode()

Pour chaque passe :
- Fichier source et fonction principale
- Type d'entrée exact (clés de dict attendues)
- Type de sortie exact (clés de dict produites)
- Vérification de cohérence entrée/sortie avec la passe suivante

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
- Imports top-level vs imports runtime dans engine.py
- Dépendances circulaires potentielles
- Accès direct aux internals d'une autre passe
- Alias backward-compat (compile_output, atomize_shots, transform_visuals) : justifiés ou dettes ?

─────────────────────────────────────────────
BLOC 4 — ARCHITECTURE GLOBALE
─────────────────────────────────────────────
- Correspondance entre README.md et le code réel
- Fichiers présents mais non utilisés
- Fichiers manquants attendus par la spec
- Structure des packages (aiprod_adaptation/ vs racine)

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
