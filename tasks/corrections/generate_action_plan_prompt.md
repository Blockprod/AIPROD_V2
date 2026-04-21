---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/corrections/plans/PLAN_ACTION_[TYPE]_[DATE].md
derniere_revision: 2026-04-20
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un architecte logiciel spécialisé en planification de corrections pour pipelines Python déterministes.
Tu génères un plan d'action structuré et priorisé à partir de l'audit disponible.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Réfléchis profondément étape par étape avant
de produire ta sortie. Explore d'abord, planifie
ensuite, structure soigneusement.

─────────────────────────────────────────────
ÉTAPE 0 — LOCALISATION DE L'AUDIT
─────────────────────────────────────────────
Cherche le rapport d'audit le plus récent dans :
  tasks/audits/resultats/

Sélectionne le fichier dont le nom contient la date la plus récente.
Lis entièrement ce rapport avant de commencer.

Si aucun audit trouvé :
"❌ Aucun rapport d'audit trouvé dans tasks/audits/resultats/.
 Lance d'abord un audit via tasks/audits/code/ ou tasks/audits/methode/."
→ Arrête.

─────────────────────────────────────────────
ÉTAPE 1 — ANALYSE DE L'AUDIT
─────────────────────────────────────────────
Extrait du rapport d'audit :
- Tous les problèmes avec leur sévérité
- Fichiers concernés avec numéros de lignes
- Impact sur les tests existants

─────────────────────────────────────────────
ÉTAPE 2 — PRIORISATION
─────────────────────────────────────────────
Classe les corrections en 3 priorités :

**P1 — CRITIQUE** : tout ce qui casse les tests ou le pipeline
- Tests en échec
- Erreurs de cohérence inter-passes (clés manquantes)
- Erreurs de validation qui laissent passer des données invalides
- Déterminisme non garanti

**P2 — IMPORTANT** : qualité sans régression immédiate
- Annotations de types manquantes sur fonctions publiques
- Guards clause manquantes
- Aliases backward-compat incorrects

**P3 — MINEUR** : nettoyage et amélioration
- Imports non utilisés
- Docstrings manquantes
- CI/CD manquant

─────────────────────────────────────────────
ÉTAPE 3 — GÉNÉRATION DU PLAN
─────────────────────────────────────────────
Pour chaque correction, génère une fiche structurée :

```
### [ID-NN] — [TITRE COURT]
**Priorité** : P1 / P2 / P3
**Sévérité** : 🔴 / 🟠 / 🟡
**Fichier** : chemin/vers/fichier.py:ligne
**Problème** : description précise du problème
**Action** : action minimale à effectuer
**Tests impactés** : liste des tests à vérifier après
**Risque** : risque de régression (faible/moyen/élevé)
```

─────────────────────────────────────────────
CRITÈRES DE PRODUCTION
─────────────────────────────────────────────
Le plan doit permettre d'atteindre :
- [ ] 32/32 tests pytest verts
- [ ] Déterminisme byte-level vérifié (test_json_byte_identical)
- [ ] mypy core/ models/ : exit 0
- [ ] ruff check . : 0 erreurs
- [ ] python main.py 2>$null | python -m json.tool : JSON valide
- [ ] Aucun # type: ignore dans le codebase
- [ ] CI GitHub Actions : push main → green

─────────────────────────────────────────────
FORMAT DU FICHIER PRODUIT
─────────────────────────────────────────────
Nom : `tasks/corrections/plans/PLAN_ACTION_[TYPE]_[YYYYMMDD].md`

```markdown
# PLAN D'ACTION — [TYPE AUDIT] — [DATE]
**Source** : tasks/audits/resultats/[fichier_audit].md
**Généré le** : [date heure]
**Corrections totales** : [N] (P1:[x] P2:[y] P3:[z])

## Résumé
[2-3 lignes sur les problèmes principaux]

## Corrections P1 — CRITIQUE
### [ID-01] — ...
...

## Corrections P2 — IMPORTANT
### [ID-XX] — ...
...

## Corrections P3 — MINEUR
### [ID-XX] — ...
...

## Ordre d'exécution recommandé
1. [ID-01] — [titre]
2. [ID-02] — [titre]
...

## Validation finale
- pytest aiprod_adaptation/tests/ -v → 32/32
- python main.py 2>$null | python -m json.tool → JSON valide
```
