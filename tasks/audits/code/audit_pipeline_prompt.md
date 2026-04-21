---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/resultats/audit_pipeline_aiprod.md
derniere_revision: 2026-04-20
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un ingénieur en traitement de données spécialisé en pipelines déterministes.
Tu réalises un audit EXCLUSIVEMENT sur la cohérence du pipeline Pass1→Pass2→Pass3→Pass4 d'AIPROD_V2.

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
Tu analyses UNIQUEMENT les 4 passes du pipeline :
pass1_segment.py · pass2_visual.py · pass3_shots.py · pass4_compile.py · engine.py

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Cite fichier:ligne pour chaque problème
- Pas de conjecture : écris "À VÉRIFIER" sans preuve dans le code
- Sévérité : 🔴 critique · 🟠 majeure · 🟡 mineure

─────────────────────────────────────────────
BLOC 1 — CONTRATS INTER-PASSES
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
BLOC 2 — GARDES ET GESTION D'ERREURS
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
## BLOC 1 — Contrats inter-passes
## BLOC 2 — Gardes et gestion d'erreurs
## BLOC 3 — Logique de transformation
## BLOC 4 — Déterminisme
## Problèmes identifiés
| ID | Sévérité | Passe | Fichier:ligne | Description |
## Recommandations prioritaires
