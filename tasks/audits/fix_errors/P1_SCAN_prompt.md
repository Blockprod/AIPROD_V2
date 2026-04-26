---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/fix_results/SCAN_result.md
derniere_revision: 2026-04-26
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

# 3. Mypy strict — scope officiel du projet (identique à la CI)
#    Flag : --strict  (pas --ignore-missing-imports, qui masque les vraies erreurs)
$strict_scope = @(
  "aiprod_adaptation/core/",
  "aiprod_adaptation/models/",
  "aiprod_adaptation/backends/",
  "aiprod_adaptation/cli.py",
  "main.py"
)
$strict_out = python -m mypy @strict_scope --strict 2>&1
$strict_errors = ($strict_out | Select-String "error:").Count
Write-Host "mypy --strict scope principal : $strict_errors erreur(s)"
$strict_out | Select-String "error:" | Select-Object -First 30

# 4. Mypy --ignore-missing-imports sur les modules hors scope strict
#    (image_gen, post_prod, video_gen ne sont pas dans le scope strict)
$extra_modules = @(
  "aiprod_adaptation/image_gen/",
  "aiprod_adaptation/post_prod/",
  "aiprod_adaptation/video_gen/"
)
foreach ($m in $extra_modules) {
  $out = python -m mypy $m --ignore-missing-imports 2>&1
  $errors = ($out | Select-String "error:").Count
  if ($errors -gt 0) { Write-Host "$m : $errors erreur(s)" }
  else { Write-Host "$m : OK" }
}
Write-Host "--- scan mypy terminé ---"
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
| `ruff-E501` | ligne trop longue | ligne > 120 caractères (seuil pyproject.toml) |
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
# Helper : liste robuste de tous les .py du projet (hors venv)
$all_py   = (Get-ChildItem -Path "aiprod_adaptation","main.py" -Recurse -Filter "*.py" -ErrorAction SilentlyContinue).FullName
$core_py  = (Get-ChildItem -Path "aiprod_adaptation\core" -Recurse -Filter "*.py" -ErrorAction SilentlyContinue).FullName

# 4a. Aucun # type: ignore (INTERDIT absolu)
$hits = $all_py | Select-String -Pattern "# type: ignore" -ErrorAction SilentlyContinue
if ($hits) { Write-Host "❌ type:ignore trouvés : $($hits.Count)" ; $hits | Select-Object -First 10 }
else { Write-Host "✅ 0 type:ignore" }

# 4b. Aucun # noqa (masquage silencieux ruff — signaler, pas bloquer)
$noqa = $all_py | Select-String -Pattern "# noqa" -ErrorAction SilentlyContinue
if ($noqa) { Write-Host "⚠️  noqa trouvés : $($noqa.Count)" ; $noqa | Select-Object -First 10 }
else { Write-Host "✅ 0 noqa" }

# 4c. Aucun random/uuid dans core/ (déterminisme obligatoire)
$rand = $core_py | Select-String -Pattern "import random|import uuid|random\.|uuid\." -ErrorAction SilentlyContinue
if ($rand) { Write-Host "❌ randomness trouvée : $($rand.Count)" ; $rand }
else { Write-Host "✅ 0 randomness dans core/" }

# 4d. Aucun datetime.now / time.time dans core/ (pas d'horloge)
$dt = $core_py | Select-String -Pattern "datetime\.now|datetime\.utcnow|time\.time" -ErrorAction SilentlyContinue
if ($dt) { Write-Host "❌ datetime trouvé : $($dt.Count)" ; $dt }
else { Write-Host "✅ 0 datetime dans core/" }

# 4e. Aucune API Pydantic v1 (validator, .dict(), .json(), parse_obj)
$pv1 = $all_py | Select-String -Pattern "@validator|@root_validator|\.dict\(\)|\.json\(\)|parse_obj|parse_raw" -ErrorAction SilentlyContinue
if ($pv1) { Write-Host "❌ API Pydantic v1 trouvée : $($pv1.Count)" ; $pv1 | Select-Object -First 10 }
else { Write-Host "✅ 0 API Pydantic v1" }
```

─────────────────────────────────────────────
ÉTAPE 5 — TESTS (runtime smoke)
─────────────────────────────────────────────
```powershell
# Lancer la suite de tests — capturer le résultat sans afficher chaque test
python -m pytest aiprod_adaptation/tests/ -q --tb=no 2>&1 | Select-Object -Last 5
```
Ne pas ré-exécuter les tests en cas d'échec — noter les noms dans SCAN_result.md.

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
  type_ignore  : 0 / [liste si > 0]
  noqa         : 0 / [liste si > 0]
  randomness   : 0 / [liste si > 0]
  datetime     : 0 / [liste si > 0]
  pydantic_v1  : 0 / [liste si > 0]

TESTS:
  passed : N
  failed : N / [noms des tests en échec]

TOTAUX:
  ruff            : X violation(s)
  mypy_strict     : X erreur(s) dans Y fichiers  (scope CI)
  mypy_extra      : X erreur(s) dans Y fichiers  (hors scope strict)
  interdits       : X violation(s)
  modules_propres : [liste...]
```
