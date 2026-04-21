---
type: guide
projet: AIPROD_V2
stack: Python 3.11.9 · Pydantic v2 · pytest · structlog · Windows
derniere_revision: 2026-04-20
creation: 2026-04-20 à 17:56
---

# WORKFLOW — Audit → Plan → Corrections
# AIPROD — Compilateur narratif déterministe (texte → données cinématiques structurées)

Chaque audit suit le même pipeline en **3 étapes** :

| Étape | Prompt | Mode | Produit |
|:---:|---|:---:|---|
| **A** | `audit_<type>_prompt.md` | Ask / Agent | `tasks/audits/resultats/audit_<type>_aiprod.md` |
| **B** | `generate_action_plan_prompt.md` | Agent | `tasks/corrections/plans/PLAN_ACTION_<type>_[DATE].md` |
| **C** | `execute_corrections_prompt.md` | Agent | corrections appliquées · ⏳ → ✅ |

> Toujours exécuter **A → B → C** dans l'ordre strict.
> Ne jamais lancer B sans avoir l'audit A complet.

---

## AUDITS DISPONIBLES

| # | Audit | Dimension | Mode A |
|:---:|---|---|:---:|
| 1 | [Structurel](#1--structurel) | Pipeline 4 passes · SRP · Couplage modules · Schémas Pydantic | Ask |
| 2 | [Pipeline](#2--pipeline) | Cohérence pass1→pass4 · Formats inter-passes · Déterminisme · Guards | Agent |
| 3 | [Tests](#3--tests) | Couverture pytest · Fixtures · Cas limites · Régression · Déterminisme byte-level | Agent |
| 4 | [Technique & Qualité](#4--technique--qualité) | mypy · ruff · structlog · pyproject.toml · CI/CD GitHub Actions | Ask |
| 5 | [Déterminisme](#5--déterminisme) | Invariants byte-level · Absence randomness/datetime/sets/sorting · Reproductibilité | Ask |
| 6 | [Schémas & Validation](#6--schémas--validation) | Pydantic v2 · Contraintes · ValueError · AIPRODOutput · Episode · Scene · Shot | Ask |
| 7 | [Master](#7--master) | Audit complet toutes dimensions | Agent |

---

## `1 · STRUCTUREL`

> Pipeline 4 passes · Couplage modules · SRP · Doublons fonctionnels · Schémas Pydantic

**Produit A** : `tasks/audits/resultats/audit_structural_aiprod.md`

**A — Audit**
```
#file:tasks/audits/code/audit_structural_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `2 · PIPELINE`

> Cohérence pass1→pass4 · Formats inter-passes · Guards · Modèle de données

**Produit A** : `tasks/audits/resultats/audit_pipeline_aiprod.md`

**A — Audit**
```
#file:tasks/audits/code/audit_pipeline_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `3 · TESTS`

> Couverture pytest · Fixtures · Cas limites · Régression · Déterminisme byte-level

**Produit A** : `tasks/audits/resultats/audit_tests_aiprod.md`

**A — Audit**
```
#file:tasks/audits/code/audit_tests_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `4 · TECHNIQUE & QUALITÉ`

> mypy · ruff · structlog · pyproject.toml · CI/CD GitHub Actions · Dépendances

**Produit A** : `tasks/audits/resultats/audit_technical_aiprod.md`

**A — Audit**
```
#file:tasks/audits/code/audit_technical_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `5 · DÉTERMINISME`

> Invariants byte-level · Absence randomness/datetime/sets/sorting implicite · Reproductibilité

**Produit A** : `tasks/audits/resultats/audit_determinism_aiprod.md`

**A — Audit**
```
#file:tasks/audits/methode/audit_determinism_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `6 · SCHÉMAS & VALIDATION`

> Pydantic v2 · Contraintes Scene/Shot/Episode/AIPRODOutput · ValueError · Intégrité

**Produit A** : `tasks/audits/resultats/audit_schemas_aiprod.md`

**A — Audit**
```
#file:tasks/audits/methode/audit_schemas_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `7 · MASTER`

> Audit complet : structure · pipeline · tests · qualité · déterminisme · schémas

**Produit A** : `tasks/audits/resultats/audit_master_aiprod.md`

**A — Audit**
```
#file:tasks/audits/code/audit_master_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## INVARIANTS ABSOLUS DU PROJET

Ces règles ne doivent **jamais** être violées :

| Invariant | Vérification |
|---|---|
| Déterminisme byte-level | `test_json_byte_identical` doit passer |
| Pas de randomness | grep `random\|uuid\|shuffle\|choice` → 0 résultat dans core/ |
| Pas de datetime pour tri | grep `datetime\|time.time` dans core/ → 0 |
| Pas de set pour ordre | grep `set(` dans core/ → justifié ou absent |
| ValueError sur validation | `compile_episode` doit lever ValueError, jamais corriger |
| Ordre des listes préservé | Aucun `sorted()` implicite sur les listes de scènes/shots |
| Python 3.11+ | `requires-python = ">=3.11"` dans pyproject.toml |
| Pydantic v2 uniquement | `from pydantic import BaseModel` — pas v1 compat |

---

## COMMANDES DE VALIDATION

```bash
# Activer l'environnement
venv\Scripts\Activate.ps1

# Tests complets
pytest aiprod_adaptation/tests/ -v

# Tests avec couverture
pytest aiprod_adaptation/tests/ --cov=aiprod_adaptation --cov-report=term

# Vérification pipeline complet
python main.py 2>$null | python -m json.tool

# Mypy
mypy aiprod_adaptation/core/ aiprod_adaptation/models/

# Ruff
ruff check .
```

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] 32/32 tests pytest verts
- [ ] Déterminisme byte-level vérifié (`test_json_byte_identical`)
- [ ] mypy core/ models/ : exit 0
- [ ] ruff check . : 0 erreurs
- [ ] `python main.py | python -m json.tool` : JSON valide, exit 0
- [ ] Aucun `random`, `uuid4`, `shuffle`, `datetime.now()` dans core/
- [ ] Aucun `# type: ignore` dans le codebase
- [ ] CI GitHub Actions : push main → green
