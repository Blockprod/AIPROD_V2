---
type: plan_action
creation: 2026-04-26 à 13:55
source: tasks/audits/fix_errors/fix_results/FINAL_QA_result.md
scope: hors-scope-P3 · pré-existants
tickets: 2
---

# Plan d'action — Points pré-existants hors scope P3

Issues identifiées lors du FINAL QA (P5) le 2026-04-26.
Non introduites par le fix pass P1→P4. Nécessitent un traitement séparé.

---

## TICKET 1 — Supprimer `# type: ignore` dans `conflict_resolver.py`

**Fichier** : `aiprod_adaptation/core/rule_engine/conflict_resolver.py`  
**Ligne** : 145  
**Priorité** : HAUTE (violation règle d'or : 0 `# type: ignore`)

### Contexte

```python
# l143–147  conflict_resolver.py
active.sort(
    key=lambda r: (
        r.conflict.priority,                       # type: ignore[union-attr]
        0 if r.conflict_type == ConflictType.HARD else 1,
    )
)
```

`r.conflict` a le type `ConflictRecord | None` dans `RuleEvalResult` (models.py l186).
mypy ne peut pas savoir que le filtre `r.conflict is not None` (l135–140) garantit
que `r.conflict` est non-None pour tout élément de `active`. D'où l'union-attr.

### Cause racine

Le filtre :
```python
active: list[RuleEvalResult] = [
    r for r in eval_results
    if r.matched
    and r.conflict_type != ConflictType.NONE
    and r.conflict is not None          # ← mypy ne propage pas ce narrowing dans sort()
]
```
mypy ne propage pas le narrowing `is not None` hors de la compréhension.
`active` reste typée `list[RuleEvalResult]` (avec `conflict: ConflictRecord | None`).

### Solution

**Option A — Créer un type intermédiaire `ActiveRuleEvalResult`** (recommandée)

Définir dans `models.py` :
```python
class ActiveRuleEvalResult(RuleEvalResult):
    """RuleEvalResult garanti matched=True, conflict non-None."""
    conflict: ConflictRecord          # non-Optional — override du champ parent
```

Modifier `conflict_resolver.py` :
```python
from .models import ..., ActiveRuleEvalResult

active: list[ActiveRuleEvalResult] = [
    ActiveRuleEvalResult.model_validate(r.model_dump())
    for r in eval_results
    if r.matched
    and r.conflict_type != ConflictType.NONE
    and r.conflict is not None
]
```
Après ce changement, `r.conflict.priority` est bien `int` → `# type: ignore` supprimable.

**Option B — Type assertion via `assert`** (plus légère, sans modèle supplémentaire)

Extraire le sort key dans une fonction locale typée :
```python
def _sort_key(r: RuleEvalResult) -> tuple[int, int]:
    assert r.conflict is not None
    return (r.conflict.priority, 0 if r.conflict_type == ConflictType.HARD else 1)

active.sort(key=_sort_key)
```
mypy accepte l'`assert` comme narrowing dans le corps de la fonction.
**Aucun modèle supplémentaire. Aucune régression.**

> **Choix recommandé : Option B** — minimal, idiomatique, sans overhead Pydantic.

### Vérification post-correction

```powershell
python -m mypy aiprod_adaptation/core/rule_engine/ --strict --ignore-missing-imports 2>&1 | Select-Object -Last 3
# Expected: Success: no issues found in N source files

python -m ruff check aiprod_adaptation/core/rule_engine/ 2>&1
# Expected: All checks passed!

pytest aiprod_adaptation/tests/ -q --tb=short -k "rule_engine or conflict" 2>&1 | Select-Object -Last 3
# Expected: N passed
```

---

## TICKET 2 — `datetime.now(UTC)` dans `postproduction/__init__.py`

**Fichier** : `aiprod_adaptation/core/postproduction/__init__.py`  
**Lignes** : 63, 95  
**Priorité** : MOYENNE (non déterministe · invariant `datetime.now` dans core/ → 0)

### Contexte

```python
# l63  (branche vide — pas d'épisodes)
created_at=datetime.now(UTC).isoformat(),

# l95  (branche normale — assemblage manifest)
created_at=datetime.now(UTC).isoformat(),
```

`PostProductionManifest.created_at: str` reçoit `datetime.now(UTC).isoformat()`.
Ce champ est une métadonnée de génération (horodatage du manifest), pas un
champ de tri ou de pipeline déterministe — mais l'invariant projet l'interdit
dans `core/`.

### Solution

**Option A — Injecter le clock via paramètre** (recommandée)

```python
from collections.abc import Callable

def build_manifest_for_episode(
    output: AIPRODOutput,
    fps: float = 24.0,
    *,
    clock: Callable[[], str] = lambda: datetime.now(UTC).isoformat(),
) -> PostProductionManifest:
```

Remplacer les 2 occurrences `datetime.now(UTC).isoformat()` par `clock()`.

Avantages :
- Les tests peuvent passer `clock=lambda: "2026-01-01T00:00:00+00:00"` → déterministe.
- Le caller de production passe le default (comportement identique à aujourd'hui).
- 0 `datetime.now` dans `core/` hors paramètre de défaut.

**Option B — Déplacer le timestamp hors de `core/`**

Déplacer `created_at` en paramètre obligatoire de `build_manifest_for_episode` ;
laisser le caller (`main.py` ou `engine.py`) injecter `datetime.now(UTC).isoformat()`.

> **Choix recommandé : Option A** — rétrocompat totale (le caller existant ne change pas),
> testabilité immédiate.

### Impact sur les tests existants

```powershell
pytest aiprod_adaptation/tests/ -q --tb=short -k "post_prod or manifest" 2>&1 | Select-Object -Last 3
```

Les tests existants de post_prod passent le default → comportement inchangé.
Les tests déterministes peuvent désormais passer `clock=lambda: "2026-01-01T00:00:00+00:00"`.

### Vérification post-correction

```powershell
# 0 datetime.now dans core/
$r = Get-ChildItem -Recurse -Filter "*.py" -Path "aiprod_adaptation\core" | Select-String "datetime\.now|datetime\.utcnow"
if ($r) { Write-Host "FAIL: $($r.Count)" } else { Write-Host "OK: 0" }

# mypy
python -m mypy aiprod_adaptation/core/postproduction/ --strict --ignore-missing-imports 2>&1 | Select-Object -Last 3

# tests
pytest aiprod_adaptation/tests/ -q --tb=short 2>&1 | Select-Object -Last 3
# Expected: 998 passed, 4 deselected
```

---

## Récapitulatif

| # | Fichier | Ligne(s) | Issue | Solution | Complexité |
|:---:|---|---|---|---|:---:|
| 1 | `core/rule_engine/conflict_resolver.py` | 145 | `# type: ignore[union-attr]` | Extraire `_sort_key()` avec `assert` | XS |
| 2 | `core/postproduction/__init__.py` | 63, 95 | `datetime.now(UTC)` | Paramètre `clock` injectable | S |

## Ordre d'exécution recommandé

1. **Ticket 1** en premier (le plus simple, 0 impact API)
2. **Ticket 2** ensuite (légère modification de signature)
3. Relancer `pytest 998 tests` après chaque ticket
4. Relancer `mypy --strict` (88 fichiers) après Ticket 2

## Commande de validation finale

```powershell
python -m ruff check . --exclude venv,__pycache__,build
python -m mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py main.py --strict
pytest aiprod_adaptation/tests/ -q --tb=short 2>&1 | Select-Object -Last 3

# Vérifications interdits
$ti = (Get-ChildItem -Recurse -Filter "*.py" -Path "aiprod_adaptation\core" | Select-String "# type: ignore" | Measure-Object).Count
$dt = (Get-ChildItem -Recurse -Filter "*.py" -Path "aiprod_adaptation\core" | Select-String "datetime\.now|datetime\.utcnow" | Measure-Object).Count
Write-Host "type:ignore=$ti  datetime=$dt"
# Expected: type:ignore=0  datetime=0
```
