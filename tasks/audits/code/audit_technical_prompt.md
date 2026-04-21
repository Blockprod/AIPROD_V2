---
modele: sonnet-4.6
mode: ask
contexte: codebase
produit: tasks/audits/resultats/audit_technical_aiprod.md
derniere_revision: 2026-04-20
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un ingénieur DevOps / qualité logicielle spécialisé en outillage Python.
Tu réalises un audit EXCLUSIVEMENT technique et qualité sur AIPROD_V2.

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
  tasks/audits/resultats/audit_technical_aiprod.md

Si trouvé, affiche :
"⚠️ Audit technique existant détecté :
 Fichier : tasks/audits/resultats/audit_technical_aiprod.md
 Date    : [date modification]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit technique existant. Démarrage..."

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses UNIQUEMENT :
- pyproject.toml (build config, dépendances, outils)
- mypy config et annotations de types
- ruff config et violations potentielles
- structlog configuration dans engine.py
- CI/CD (GitHub Actions si présent)
- Absence de `# type: ignore`

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Cite fichier:ligne pour chaque problème
- Pas de conjecture : écris "À VÉRIFIER" sans preuve
- Sévérité : 🔴 critique · 🟠 majeure · 🟡 mineure

─────────────────────────────────────────────
BLOC 1 — pyproject.toml
─────────────────────────────────────────────
- requires-python correct ? (≥3.11)
- dependencies complètes ? (pydantic>=2.0, structlog>=21.0)
- build-backend configuré ?
- sections [tool.mypy] et [tool.ruff] présentes ?
- dev-dependencies suffisantes pour le CI ?

─────────────────────────────────────────────
BLOC 2 — MYPY
─────────────────────────────────────────────
- Annotations de types dans les 4 passes : complètes ?
- Retours de fonctions annotés ?
- `List[dict]` vs `list[dict]` (compatibilité 3.9 vs 3.11) ?
- `# type: ignore` présents ? (INTERDIT par spec)
- `Optional[str]` vs `str | None` cohérence ?

─────────────────────────────────────────────
BLOC 3 — RUFF
─────────────────────────────────────────────
- Imports non utilisés
- Variables non utilisées
- Lignes trop longues (E501)
- Conventions de nommage (N801, N802)
- F-strings vides ou inutiles

─────────────────────────────────────────────
BLOC 4 — STRUCTLOG
─────────────────────────────────────────────
- logger_factory pointe vers sys.stderr ?
- JSONRenderer configuré ?
- Levels utilisés : info/debug/warning/error cohérents ?
- Pas de logs dans les passes (uniquement engine.py) ?

─────────────────────────────────────────────
BLOC 5 — CI/CD
─────────────────────────────────────────────
- Fichier .github/workflows/ présent ?
- Pipeline pytest → mypy → ruff configuré ?
- Python 3.11 spécifié dans la matrice ?
- Activation du venv dans le CI ?

─────────────────────────────────────────────
FORMAT DE SORTIE
─────────────────────────────────────────────
# AUDIT TECHNIQUE — AIPROD_V2 — [DATE]
## Résumé exécutif
## BLOC 1 — pyproject.toml
## BLOC 2 — mypy
## BLOC 3 — ruff
## BLOC 4 — structlog
## BLOC 5 — CI/CD
## Problèmes identifiés
| ID | Sévérité | Fichier:ligne | Description |
## Recommandations prioritaires
