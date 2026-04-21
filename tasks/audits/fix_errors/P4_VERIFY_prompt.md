---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/fix_results/VERIFY_result.md
derniere_revision: 2026-04-20
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un QA Engineer indépendant. Tu valides UNIQUEMENT — tu ne corriges rien.
Vérification complète post-correction AIPROD_V2.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Lance chaque commande, capture le résultat COMPLET,
puis formule un verdict binaire par catégorie.

─────────────────────────────────────────────
ACTIONS (dans cet ordre exact)
─────────────────────────────────────────────

```powershell
venv\Scripts\Activate.ps1

# 1. Ruff global
python -m ruff check . --exclude venv,__pycache__,build 2>&1 | Select-Object -Last 5

# 2. Ruff règles ciblées
python -m ruff check . --exclude venv,__pycache__,build --select F401,ARG,E501 2>&1 | Select-Object -Last 5

# 3. Mypy module par module
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
  if ($errors -gt 0) { Write-Host "❌ $m : $errors erreur(s)" }
  else { Write-Host "✅ $m" }
}

# 4. Tests complets
pytest aiprod_adaptation/tests/ -v --tb=short 2>&1 | Select-Object -Last 10

# 5. Tests déterminisme byte-level
pytest aiprod_adaptation/tests/ -v -k "byte_identical" 2>&1 | Select-Object -Last 5

# 6. Pipeline end-to-end
python main.py 2>$null | python -m json.tool | Select-Object -Last 5
```

─────────────────────────────────────────────
VÉRIFICATION INTERDITS
─────────────────────────────────────────────
```powershell
# Aucun # type: ignore
$hits = Select-String -Path "aiprod_adaptation\**\*.py","main.py" -Pattern "# type: ignore" -Recurse -ErrorAction SilentlyContinue
if ($hits) { Write-Host "❌ type:ignore : $($hits.Count)" } else { Write-Host "✅ 0 type:ignore" }

# Aucun random/uuid dans core/
$rand = Select-String -Path "aiprod_adaptation\core\*.py" -Pattern "import random|import uuid|random\.|uuid\." -ErrorAction SilentlyContinue
if ($rand) { Write-Host "❌ randomness : $($rand.Count)" } else { Write-Host "✅ 0 randomness core/" }

# Aucun datetime dans core/
$dt = Select-String -Path "aiprod_adaptation\core\*.py" -Pattern "datetime\.now|datetime\.utcnow|time\.time" -ErrorAction SilentlyContinue
if ($dt) { Write-Host "❌ datetime : $($dt.Count)" } else { Write-Host "✅ 0 datetime core/" }

# Aucun print() dans core/ (structlog uniquement)
$printhits = Select-String -Path "aiprod_adaptation\core\*.py" -Pattern "^\s*print\(" -ErrorAction SilentlyContinue
if ($printhits) { Write-Host "❌ print() core/ : $($printhits.Count)" } else { Write-Host "✅ 0 print() core/" }

# Aliases backward-compat présents
Select-String -Path "aiprod_adaptation\core\pass2_visual.py" -Pattern "transform_visuals"
Select-String -Path "aiprod_adaptation\core\pass3_shots.py" -Pattern "atomize_shots"
Select-String -Path "aiprod_adaptation\core\pass4_compile.py" -Pattern "compile_output"
```

─────────────────────────────────────────────
SEUIL DE RÉUSSITE
─────────────────────────────────────────────
| Catégorie | Seuil PASS |
|-----------|------------|
| ruff | 0 violation |
| mypy | 0 erreur dans chaque module |
| pytest | 32/32 passed, 0 failed |
| byte-level | test_json_byte_identical pass |
| pipeline E2E | JSON valide, exit 0 |
| type:ignore | 0 occurrence |
| randomness | 0 occurrence dans core/ |

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Créer `tasks/audits/fix_errors/fix_results/VERIFY_result.md` avec :

```
VERIFY_STATUS:
  ruff          : ✅ OK / ❌ FAIL (X violations)
  mypy          : ✅ OK / ❌ FAIL — modules KO : [...]
  pytest        : ✅ OK (32/32) / ❌ FAIL (N/32 — [échecs])
  byte-level    : ✅ OK / ❌ FAIL / ⚠️ ABSENT
  pipeline_e2e  : ✅ OK / ❌ FAIL
  type_ignore   : ✅ 0 / ❌ [fichiers:lignes]
  randomness    : ✅ 0 / ❌ [fichiers:lignes]

VERDICT GLOBAL : PASS ✅ / FAIL ❌
BLOCKERS RESTANTS:
  - [fichier:ligne — description] ou "aucun"
```

Confirmer dans le chat :
"✅ VERIFY terminé · ruff OK · mypy OK · 32/32 tests pass"
ou
"❌ VERIFY : X blockers — relancer P3 batch Y"
