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

Pour la **correction d'erreurs statiques** (mypy · ruff · type errors), un pipeline dédié en **5 passes** est disponible :

| Passe | Prompt | Mode | Produit |
|:---:|---|:---:|---|
| **P1** | `P1_SCAN_prompt.md` | Agent | `fix_results/SCAN_result.md` |
| **P2** | `P2_PLAN_prompt.md` | Agent | `fix_results/PLAN_result.md` |
| **P3** | `P3_FIX_prompt.md` | Agent | `fix_results/BATCH_result.md` |
| **P4** | `P4_VERIFY_prompt.md` | Agent | `fix_results/VERIFY_result.md` |
| **P5** | `P5_FINAL_QA_prompt.md` | Agent | `fix_results/FINAL_QA_result.md` |

> Toujours exécuter **P1 → P2 → P3 → P4 → P5** dans l'ordre strict.
> P3 est répété pour chaque batch défini par P2. P4 valide sans modifier.
> Ne jamais lancer P5 si P4 affiche VERDICT GLOBAL = FAIL.

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
| 8 | [IR & Maturité Conceptuelle](#8--ir--maturité-conceptuelle) | Maturité IR · Gaps architecturaux · Qualité prompt vs vrai IR · Risques à l'échelle | Agent |
| 9 | [Fix Errors](#9--fix-errors) | Scan mypy/ruff · Plan batches · Correction · Vérification · Final QA | Agent |

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

## `8 · IR & MATURITÉ CONCEPTUELLE`

> Maturité IR · Gaps architecturaux · Qualité prompt vs vrai IR · Risques à l'échelle · Score /10

**Produit A** : `tasks/audits/resultats/audit_ir_maturity_aiprod.md`

**A — Audit**
```
#file:tasks/audits/code/audit_ir_maturity_prompt.md
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

## `9 · FIX ERRORS`

> Scan mypy · ruff · type errors · Correction par batches · Vérification · Final QA release

**Dossier** : `tasks/audits/fix_errors/`  
**Résultats** : `tasks/audits/fix_errors/fix_results/`

**P1 — Scan complet**
```
#file:tasks/audits/fix_errors/P1_SCAN_prompt.md
Lance le scan complet du workspace.
```

**P2 — Plan de correction**
```
#file:tasks/audits/fix_errors/P2_PLAN_prompt.md
Génère le plan de correction par batches depuis le scan.
```

**P3 — Correction (répéter par batch)**
```
#file:tasks/audits/fix_errors/P3_FIX_prompt.md
Applique les corrections du batch demandé.
```

**P4 — Vérification post-correction**
```
#file:tasks/audits/fix_errors/P4_VERIFY_prompt.md
Valide les corrections appliquées. Ne modifie rien.
```

**P5 — Final QA (release readiness)**
```
#file:tasks/audits/fix_errors/P5_FINAL_QA_prompt.md
Valide la readiness complète avant merge.
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

- [ ] 42/42 tests pytest verts
- [ ] Déterminisme byte-level vérifié (`test_json_byte_identical`)
- [ ] mypy core/ models/ backends/ : exit 0
- [ ] ruff check . : 0 erreurs
- [ ] `python main.py | python -m json.tool` : JSON valide, exit 0
- [ ] Aucun `random`, `uuid4`, `shuffle`, `datetime.now()` dans core/
- [ ] Aucun `# type: ignore` dans le codebase
- [ ] CI GitHub Actions : push main → green
