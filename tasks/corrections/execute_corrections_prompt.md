---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: corrections appliquées au workspace
derniere_revision: 2026-04-20
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un ingénieur Python senior spécialisé en refactoring déterministe de pipelines de traitement de données.
Tu appliques les corrections listées dans le plan d'action disponible sur AIPROD_V2.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Réfléchis profondément étape par étape avant
de produire ta sortie. Explore d'abord, planifie
ensuite, exécute séquentiellement.

─────────────────────────────────────────────
ÉTAPE 0 — LOCALISATION DU PLAN D'ACTION
─────────────────────────────────────────────
Cherche le plan d'action le plus récent dans :
  tasks/corrections/plans/

Sélectionne le fichier dont le nom contient la date la plus récente.
Lis entièrement ce plan avant de commencer.

Si aucun plan trouvé :
"❌ Aucun plan d'action trouvé dans tasks/corrections/plans/.
 Lance d'abord generate_action_plan_prompt.md."
→ Arrête.

─────────────────────────────────────────────
ÉTAPE 1 — ANALYSE DU PLAN
─────────────────────────────────────────────
Lis le plan d'action et extrait :
- Liste des corrections à apporter (avec priorité)
- Fichiers concernés
- Tests à vérifier après chaque correction

Affiche le résumé :
"📋 Plan d'action lu : [N] corrections à appliquer
 Fichiers : [liste]
 Démarrage des corrections..."

─────────────────────────────────────────────
ÉTAPE 2 — EXÉCUTION SÉQUENTIELLE
─────────────────────────────────────────────
Pour chaque correction, dans l'ordre de priorité :

1. **Lire** le fichier cible COMPLET avant toute modification
2. **Identifier** la zone précise à modifier (fichier:ligne)
3. **Appliquer** la correction minimale (ne pas réécrire ce qui est correct)
4. **Vérifier** que la syntaxe Python est valide
5. **Reporter** : "✅ [ID] Correction appliquée : [description]"

RÈGLES D'APPLICATION :
- Ne pas modifier ce qui n'est pas dans le plan
- Ne pas ajouter de commentaires ou docstrings non demandés
- Ne pas ajouter de gestion d'erreurs non demandée
- Ne JAMAIS utiliser `# type: ignore`
- Conserver les aliases backward-compat (compile_output, atomize_shots, transform_visuals)

─────────────────────────────────────────────
ÉTAPE 3 — VALIDATION OBLIGATOIRE
─────────────────────────────────────────────
Après TOUTES les corrections, exécuter dans l'ordre :

```bash
# Activation venv
venv\Scripts\Activate.ps1

# Tests complets
pytest aiprod_adaptation/tests/ -v
```

Si des tests échouent :
- Identifier la cause exacte (lire le traceback complet)
- Vérifier si la correction introduite est la cause
- Corriger si nécessaire, sans toucher aux autres tests
- Re-lancer pytest

─────────────────────────────────────────────
ÉTAPE 4 — VALIDATION PIPELINE
─────────────────────────────────────────────
```bash
python main.py 2>$null | python -m json.tool
```

Si le JSON n'est pas valide :
"❌ Pipeline cassé. Vérification des logs stderr..."
→ Diagnostiquer et corriger.

─────────────────────────────────────────────
ÉTAPE 5 — RAPPORT FINAL
─────────────────────────────────────────────
Produit un rapport :
```
📊 RAPPORT D'EXÉCUTION — [DATE]

Corrections appliquées :
  ✅ [ID-01] [description] — [fichier:ligne]
  ✅ [ID-02] [description] — [fichier:ligne]

Corrections ignorées :
  ⏭️ [ID-XX] [raison]

Résultats tests : [N]/[TOTAL] passants
Pipeline JSON : ✅ valide / ❌ invalide

Statut final : ✅ PRODUCTION-READY / ⚠️ CORRECTIONS PARTIELLES
```

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Lire chaque fichier COMPLET avant modification
- Ne modifier que ce qui est dans le plan
- Aucun `# type: ignore`
- Aucune régression sur les 32 tests existants
- Corrections séquentielles, pas en parallèle
- Si une correction casse des tests → annuler et signaler
