---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/fix_results/SCAN_result.md
derniere_revision: 2026-04-20
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un code quality analyst spécialisé Python / Pydantic v2 / mypy.
Tu réalises un SCAN COMPLET du projet AIPROD_V2 sans rien modifier.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Explore d'abord, ne corrige jamais. Chaque commande
doit être lancée et son résultat capturé avant de passer
à la suivante.

─────────────────────────────────────────────
ÉTAPE 1 — OUTILS STATIQUES
─────────────────────────────────────────────
Lancer dans l'ordre (terminal PowerShell, venv Python 3.11) :

```powershell
# Activer le venv
venv\Scripts\Activate.ps1

# 1. Ruff général
python -m ruff check . --exclude venv,__pycache__,build 2>&1 | Select-Object -Last 10

# 2. Ruff règles spécifiques (imports inutilisés + args non utilisés)
python -m ruff check . --exclude venv,__pycache__,build --select F401,ARG,E501 2>&1 | Select-Object -Last 10

# 3. Mypy par module (ordre priorité AIPROD)
$modules = @(
  "aiprod_adaptation/models",
  "aiprod_adaptation/core/pass1_segment.py",
  "aiprod_adaptation/core/pass2_visual.py",
  "aiprod_adaptation/core/pass3_shots.py",
  "aiprod_adaptation/core/pass4_compile.py",
  "aiprod_adaptation/core/engine.py",
  "main.py"
)
foreach ($m in $modules) {
  $out = python -m mypy $m --ignore-missing-imports 2>&1
  $errors = ($out | Select-String "error:").Count
  if ($errors -gt 0) { Write-Host "$m : $errors erreur(s)" }
  else { Write-Host "$m : OK" }
}
Write-Host "--- scan terminé ---"
```

─────────────────────────────────────────────
ÉTAPE 2 — GET_ERRORS (IDE)
─────────────────────────────────────────────
Utiliser l'outil `get_errors` (sans argument = tous les fichiers)
pour croiser avec les PROBLEMS de l'IDE.

─────────────────────────────────────────────
ÉTAPE 3 — CLASSIFICATION DES ERREURS
─────────────────────────────────────────────
Pour chaque fichier en erreur, identifier le TYPE :

| Code | Type | Exemple AIPROD |
|------|------|----------------|
| `ruff-F401` | import non utilisé | `from typing import List` non utilisé |
| `ruff-E501` | ligne trop longue | ligne > 88 caractères |
| `ruff-ARG` | argument non utilisé | paramètre de fonction inutilisé |
| `mypy-return` | retour non annoté | `def segment(text)` sans `-> List[dict]` |
| `mypy-arg-type` | type arg incorrect | `str` attendu, `Optional[str]` passé |
| `mypy-assignment` | assignation type incorrect | `x: int = None` |
| `mypy-import` | import non typé | module sans stubs mypy |
| `pydantic-v2` | usage Pydantic v1 | `@validator` au lieu de `@field_validator` |

─────────────────────────────────────────────
ÉTAPE 4 — VÉRIFICATION INTERDITS
─────────────────────────────────────────────
```powershell
# Aucun # type: ignore (INTERDIT)
$hits = Select-String -Path "aiprod_adaptation\**\*.py","main.py" -Pattern "# type: ignore" -Recurse -ErrorAction SilentlyContinue
if ($hits) { Write-Host "❌ type:ignore trouvés : $($hits.Count)" ; $hits | Select-Object -First 5 }
else { Write-Host "✅ 0 type:ignore" }

# Aucun random/uuid dans core/
$rand = Select-String -Path "aiprod_adaptation\core\*.py" -Pattern "import random|import uuid|random\.|uuid\." -ErrorAction SilentlyContinue
if ($rand) { Write-Host "❌ randomness trouvée : $($rand.Count)" ; $rand }
else { Write-Host "✅ 0 randomness dans core/" }

# Aucun datetime dans core/
$dt = Select-String -Path "aiprod_adaptation\core\*.py" -Pattern "datetime\.now|datetime\.utcnow|time\.time" -ErrorAction SilentlyContinue
if ($dt) { Write-Host "❌ datetime trouvé : $($dt.Count)" ; $dt }
else { Write-Host "✅ 0 datetime dans core/" }
```

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Créer `tasks/audits/fix_errors/fix_results/SCAN_result.md` avec :

```
FILES_TO_FIX = [
  {
    file: "chemin/relatif.py",
    errors: ["mypy-return", "ruff-F401"],
    count: N,
    lines: [L1, L2, ...]
  },
  ...
]

INTERDITS:
  type_ignore : 0 / [liste]
  randomness  : 0 / [liste]
  datetime    : 0 / [liste]

TOTAUX:
  ruff      : X violation(s)
  mypy      : X erreur(s) dans Y fichiers
  interdits : X violation(s)
  modules_propres: [liste...]
```
