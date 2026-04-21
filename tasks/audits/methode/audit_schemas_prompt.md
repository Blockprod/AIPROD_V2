---
modele: sonnet-4.6
mode: ask
contexte: codebase
produit: tasks/audits/resultats/audit_schemas_aiprod.md
derniere_revision: 2026-04-20
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un expert Pydantic v2 et validation de données structurées.
Tu réalises un audit EXCLUSIVEMENT sur les schémas et la validation d'AIPROD_V2.

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
  tasks/audits/resultats/audit_schemas_aiprod.md

Si trouvé, affiche :
"⚠️ Audit schémas existant détecté :
 Fichier : tasks/audits/resultats/audit_schemas_aiprod.md
 Date    : [date modification]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit schémas existant. Démarrage..."

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses UNIQUEMENT :
  aiprod_adaptation/models/schema.py
  aiprod_adaptation/core/pass4_compile.py (bloc validation)

─────────────────────────────────────────────
BLOC 1 — MODÈLES PYDANTIC V2
─────────────────────────────────────────────
Pour chaque modèle (Scene, Shot, Episode, AIPRODOutput) :
- Champs requis vs optionnels (avec valeur par défaut)
- Types : List vs list, Optional[str] vs str | None
- Validateurs custom (@field_validator, @model_validator) : présents ? correctement déclarés (mode='before'/'after') ?
- model_config (ConfigDict) : présent ? immutabilité ?
- Compat Pydantic v2 : pas de @validator (v1), pas de orm_mode=True

─────────────────────────────────────────────
BLOC 2 — CONTRAINTES PAR CHAMP
─────────────────────────────────────────────
- Shot.duration_sec : plain int ? Pas de Field(ge=..., le=...) ? (Conforme à la spec Prompt 1/6)
- Scene.emotion : str libre ? Pas de Enum ?
- Shot.emotion : str libre ? Pas de Enum ?
- episode_id : hardcodé "EP01" dans Pass4 ou dans le modèle ?

─────────────────────────────────────────────
BLOC 3 — VALIDATION DANS PASS4
─────────────────────────────────────────────
- Ordre des vérifications : empty title → empty scenes → empty shots → Pydantic Scene → Pydantic Shot (+ durée [3,8]) → Pydantic Episode → Pydantic AIPRODOutput
- ValidationError capturé et re-levé comme ValueError(str(exc)) ?
- Validation de durée [3,8] : code exact et fichier:ligne ?
- Vérification que Scene(**scene_dict) ne passe pas avec des champs manquants

─────────────────────────────────────────────
BLOC 4 — SÉRIALISATION JSON
─────────────────────────────────────────────
- output.model_dump_json() ou output.model_dump() + json.dumps() ?
- Indentation : utilisée dans main.py ?
- Champs None exclus ou inclus dans le JSON de sortie ?
- bytes vs str en sortie de sérialisation

─────────────────────────────────────────────
FORMAT DE SORTIE
─────────────────────────────────────────────
# AUDIT SCHÉMAS — AIPROD_V2 — [DATE]
## Résumé exécutif
## BLOC 1 — Modèles Pydantic v2
## BLOC 2 — Contraintes par champ
## BLOC 3 — Validation dans Pass4
## BLOC 4 — Sérialisation JSON
## Problèmes identifiés
| ID | Sévérité | Modèle / Fichier:ligne | Description |
## Recommandations
