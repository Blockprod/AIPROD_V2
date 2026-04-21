---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/fix_results/PLAN_result.md
derniere_revision: 2026-04-20
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un Software Architect spécialisé en compilateurs Python déterministes.
Tu crées un plan de correction OPTIMAL à partir du SCAN.

─────────────────────────────────────────────
INPUT
─────────────────────────────────────────────
Lire `tasks/audits/fix_errors/fix_results/SCAN_result.md` (FILES_TO_FIX).

Si absent :
"❌ SCAN_result.md manquant. Lance d'abord P1_SCAN_prompt.md."
→ Arrête.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Ne modifie rien. Raisonne sur les dépendances et groupe
les fichiers de façon à minimiser les itérations de
vérification inter-batch.

─────────────────────────────────────────────
RÈGLES DE PRIORITÉ AIPROD
─────────────────────────────────────────────
Batch 1 (fondations — importées par tout le reste) :
  aiprod_adaptation/models/schema.py

Batch 2 (passes dans l'ordre du pipeline) :
  aiprod_adaptation/core/pass1_segment.py
  aiprod_adaptation/core/pass2_visual.py

Batch 3 (passes aval) :
  aiprod_adaptation/core/pass3_shots.py
  aiprod_adaptation/core/pass4_compile.py

Batch 4 (orchestration) :
  aiprod_adaptation/core/engine.py
  main.py

Batch 5 (tests) :
  aiprod_adaptation/tests/test_pipeline.py

─────────────────────────────────────────────
RÈGLES DE GROUPEMENT
─────────────────────────────────────────────
1. Max 3 fichiers par batch (projet compact)
2. Fichiers de la même passe = même batch
3. Si A importe B → B dans un batch antérieur
4. Erreurs Pydantic v2 (schema.py) → toujours Batch 1
5. Erreurs de type sur les dicts inter-passes → grouper avec la passe émettrice

─────────────────────────────────────────────
CATALOGUE DE PATTERNS CONNUS AIPROD
─────────────────────────────────────────────
(pour qualifier la difficulté de chaque batch)

| Pattern | Fix | Difficulté |
|---------|-----|-----------|
| Annotation retour manquante `def f(x)` | `def f(x: str) -> List[dict]:` | Facile |
| `List` sans import `from __future__ import annotations` | Ajouter import ou utiliser `list[...]` | Facile |
| `Optional[str]` sans import | Ajouter `from typing import Optional` | Facile |
| `@validator` Pydantic v1 | Migrer vers `@field_validator(mode='before')` | Moyen |
| `orm_mode = True` Pydantic v1 | Migrer vers `model_config = ConfigDict(from_attributes=True)` | Moyen |
| Retour `dict` non typé dans les passes | `-> list[dict[str, Any]]` ou TypedDict | Moyen |
| `set()` avec itération → non déterministe | Remplacer par `list` + dédup manuelle | Complexe |

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Créer `tasks/audits/fix_errors/fix_results/PLAN_result.md` avec :

```
PLAN = [
  {
    batch: 1,
    module: "models/",
    files: ["aiprod_adaptation/models/schema.py"],
    error_types: ["pydantic-v2", "mypy-return"],
    estimated_fixes: N,
    difficulty: Facile | Moyen | Complexe
  },
  ...
]

RÉSUMÉ:
  total_batches    : X
  total_files      : Y
  estimated_fixes  : Z
  ordre_execution  : [Batch1 → Batch2 → ...]
```
