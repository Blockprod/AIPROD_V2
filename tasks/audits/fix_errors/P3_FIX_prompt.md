---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/fix_results/BATCH_result.md
derniere_revision: 2026-04-20
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un Senior Python Engineer spécialisé en typage statique Pydantic v2 / mypy.
Tu corriges UN seul batch du plan AIPROD.

─────────────────────────────────────────────
INPUT
─────────────────────────────────────────────
Lire `tasks/audits/fix_errors/fix_results/PLAN_result.md`.
Traiter le batch demandé (précisé par l'utilisateur ou Batch 1 par défaut).

─────────────────────────────────────────────
PROTOCOLE DE CORRECTION — 5 ÉTAPES
─────────────────────────────────────────────

### ÉTAPE A — LIRE avant d'écrire
Pour chaque fichier du batch :
1. Lire les lignes d'erreur exactes (output mypy/ruff de P1)
2. Lire le fichier COMPLET autour de chaque ligne (+/- 15 lignes)
3. Identifier la cause racine (pas le symptôme)

### ÉTAPE B — APPLIQUER les patterns AIPROD

**CATALOGUE DE FIXES OBLIGATOIRES :**

```python
# ── Annotations de types manquantes ───────────────────────
# ❌  def segment(raw_text):
# ✅  def segment(raw_text: str) -> list[dict]:

# ── Import typing (Python 3.11 = list[dict] natif) ────────
# ❌  from typing import List, Dict
#     def f() -> List[Dict[str, str]]:
# ✅  def f() -> list[dict[str, str]]:   # Python ≥3.9

# ── Optional propre ────────────────────────────────────────
# ❌  time_of_day: Optional[str] = None  (sans import)
# ✅  from typing import Optional        (ou str | None en Python 3.10+)

# ── Pydantic v2 : @validator → @field_validator ────────────
# ❌  @validator('duration_sec', pre=True)
#     def check_duration(cls, v): ...
# ✅  @field_validator('duration_sec', mode='before')
#     @classmethod
#     def check_duration(cls, v: int) -> int: ...

# ── Pydantic v2 : orm_mode → model_config ──────────────────
# ❌  class Config: orm_mode = True
# ✅  model_config = ConfigDict(from_attributes=True)

# ── Pydantic v2 : ValidationError ──────────────────────────
# ❌  from pydantic import ValidationError  (puis re-lever)
# ✅  try:
#        obj = Model(**data)
#    except ValidationError as exc:
#        raise ValueError(str(exc)) from exc

# ── Déterminisme : set() → list ────────────────────────────
# ❌  seen = set()
#     for x in some_set:   # ordre non garanti
# ✅  seen: list[str] = []
#     for x in list_var:   # ordre préservé

# ── Structlog : ne pas écrire dans stdout ──────────────────
# ❌  structlog.configure(...)  # sans logger_factory
# ✅  structlog.configure(
#        processors=[structlog.processors.JSONRenderer()],
#        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
#        cache_logger_on_first_use=True,
#    )
```

**IMPORTS À AJOUTER si absents :**
```python
from __future__ import annotations   # si Python < 3.10 et types natifs utilisés
from typing import Optional           # si Optional[x] utilisé
import sys                            # si structlog configuré
```

### ÉTAPE C — CONTRAINTES ABSOLUES AIPROD

```
❌ INTERDIT — jamais écrire ces lignes :
   # type: ignore
   Any  (comme raccourci de type sans justification)
   random.*, uuid.*        → déterminisme violé
   datetime.now()          → déterminisme violé
   set()  (avec itération) → ordre non garanti
   sorted()  (sur scènes/shots) → ordre insertion détruit
   print()   → utiliser structlog dans engine.py seulement
   assert    → utiliser ValueError explicite dans core/
```

**RÈGLE ALIASES BACKWARD-COMPAT :**
Ne jamais supprimer ces aliases — ils sont utilisés dans les tests :
```python
transform_visuals = visual_rewrite   # pass2_visual.py
atomize_shots = simplify_shots       # pass3_shots.py
def compile_output(title, scenes, shots):  # pass4_compile.py
    return compile_episode(scenes, shots, title)
```

### ÉTAPE D — VÉRIFICATION PAR FICHIER (max 3 itérations)

Après chaque fichier corrigé :
```powershell
# mypy sur le seul fichier modifié
python -m mypy aiprod_adaptation/core/pass1_segment.py --ignore-missing-imports 2>&1 | Select-Object -Last 5

# ruff sur le seul fichier
python -m ruff check aiprod_adaptation/core/pass1_segment.py 2>&1 | Select-Object -Last 5
```

Si encore des erreurs après 3 itérations → marquer BLOCKER,
passer au fichier suivant sans s'acharner.

### ÉTAPE E — VÉRIFICATION BATCH COMPLÈTE

Quand tous les fichiers du batch sont traités :
```powershell
# Tests du module concerné
pytest aiprod_adaptation/tests/ -q --tb=short 2>&1 | Select-Object -Last 5
```

─────────────────────────────────────────────
STOP RULE
─────────────────────────────────────────────
Si un fichier introduit une régression sur les 32 tests existants :
→ Annuler la correction de ce fichier
→ Marquer BLOCKER
→ Continuer avec les autres fichiers du batch

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Créer / mettre à jour `tasks/audits/fix_errors/fix_results/BATCH_result.md` avec :

```
BATCH_N = {
  files_corriges: ["fichier1.py", "fichier2.py"],
  fixes_appliques: [
    { file: "...", line: N, type: "mypy-return", fix: "..." },
    ...
  ],
  blockers: ["fichier:ligne — raison"] ou [],
  tests_apres: "32/32" ou "N/32 — [échecs]"
}
```
