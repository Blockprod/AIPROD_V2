---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/fix_results/FINAL_QA_result.md
derniere_revision: 2026-04-20
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un Release Manager AIPROD_V2. Tu valides la readiness complète
du pipeline avant merge / tag de version.

─────────────────────────────────────────────
INPUT
─────────────────────────────────────────────
Lire `tasks/audits/fix_errors/fix_results/VERIFY_result.md`.
Si VERDICT GLOBAL = FAIL → arrêter immédiatement :
"❌ FINAL QA bloqué — relancer P3 + P4 d'abord."

─────────────────────────────────────────────
CHECKLIST AIPROD_V2 (10 points)
─────────────────────────────────────────────

### 1. Qualité statique (depuis VERIFY_result.md)
- [ ] ruff : 0 violation
- [ ] mypy : 0 erreur dans chaque module

### 2. Tests
- [ ] `pytest aiprod_adaptation/tests/ -v` → 32/32 passed, 0 failed
  ```powershell
  venv\Scripts\Activate.ps1
  pytest aiprod_adaptation/tests/ -v --tb=short 2>&1 | Select-Object -Last 5
  ```
- [ ] Aucun DeprecationWarning Pydantic v2
  ```powershell
  pytest aiprod_adaptation/tests/ -W error::DeprecationWarning -q --tb=no 2>&1 | Select-Object -Last 3
  ```

### 3. Déterminisme byte-level
- [ ] test_json_byte_identical présent et passant
  ```powershell
  pytest aiprod_adaptation/tests/ -v -k "byte_identical" 2>&1 | Select-Object -Last 3
  ```

### 4. Pipeline end-to-end
- [ ] `python main.py` → JSON valide, exit 0, logs sur stderr uniquement
  ```powershell
  python main.py 2>$null | python -m json.tool | Select-Object -First 5
  echo "Exit: $LASTEXITCODE"
  ```

### 5. Imports smoke test
- [ ] Tous les modules importables sans erreur
  ```powershell
  python -c "
  from aiprod_adaptation.models.schema import Scene, Shot, Episode, AIPRODOutput
  from aiprod_adaptation.core.pass1_segment import segment
  from aiprod_adaptation.core.pass2_visual import visual_rewrite, transform_visuals
  from aiprod_adaptation.core.pass3_shots import simplify_shots, atomize_shots
  from aiprod_adaptation.core.pass4_compile import compile_episode, compile_output
  from aiprod_adaptation.core.engine import run_pipeline
  print('Pipeline imports OK')
  "
  ```

### 6. Aliases backward-compat
- [ ] `transform_visuals` = alias de `visual_rewrite` dans pass2_visual.py
- [ ] `atomize_shots` = alias de `simplify_shots` dans pass3_shots.py
- [ ] `compile_output(title, scenes, shots)` = wrapper de `compile_episode` dans pass4_compile.py
  ```powershell
  Select-String -Path "aiprod_adaptation\core\pass2_visual.py" -Pattern "transform_visuals\s*="
  Select-String -Path "aiprod_adaptation\core\pass3_shots.py" -Pattern "atomize_shots\s*="
  Select-String -Path "aiprod_adaptation\core\pass4_compile.py" -Pattern "def compile_output"
  ```

### 7. Interdictions absolues
- [ ] `# type: ignore` : 0 occurrence
- [ ] `random.*` / `uuid.*` dans core/ : 0 occurrence
- [ ] `datetime.now()` / `datetime.utcnow()` dans core/ : 0 occurrence
- [ ] `print()` dans core/ : 0 occurrence (structlog uniquement)
  ```powershell
  $checks = @{
    "type:ignore"  = "# type: ignore"
    "randomness"   = "import random|import uuid|random\.|uuid\."
    "datetime"     = "datetime\.now|datetime\.utcnow"
    "print core/"  = "^\s*print\("
  }
  foreach ($k in $checks.Keys) {
    $r = Select-String -Path "aiprod_adaptation\core\*.py" -Pattern $checks[$k] -Recurse -ErrorAction SilentlyContinue
    if ($r) { Write-Host "❌ $k : $($r.Count)" } else { Write-Host "✅ $k : 0" }
  }
  ```

### 8. pyproject.toml
- [ ] `requires-python = ">=3.11"`
- [ ] `pydantic>=2.0` ET `structlog>=21.0` dans dependencies
- [ ] `pytest>=7.0` ET `mypy>=1.0` dans dev-dependencies
  ```powershell
  Select-String -Path "pyproject.toml" -Pattern "requires-python|pydantic|structlog|pytest|mypy"
  ```

### 9. Structlog → stderr
- [ ] `logger_factory=structlog.PrintLoggerFactory(file=sys.stderr)` dans engine.py
  ```powershell
  Select-String -Path "aiprod_adaptation\core\engine.py" -Pattern "stderr"
  ```

### 10. CI/CD (si applicable)
- [ ] `.github/workflows/` présent ?
  ```powershell
  Test-Path ".github\workflows"
  ```

─────────────────────────────────────────────
SCORECARD FINAL
─────────────────────────────────────────────
```
╔══════════════════════════════════════════╗
║   FINAL QA — AIPROD_V2 — [DATE]         ║
╠══════════════════════════════════════════╣
║ ruff              : ✅/❌                 ║
║ mypy              : ✅/❌                 ║
║ pytest            : [N]/32  ✅/❌         ║
║ byte-level        : ✅/❌/⚠️ absent       ║
║ pipeline E2E      : ✅/❌                 ║
║ imports smoke     : ✅/❌                 ║
║ aliases compat    : ✅/❌                 ║
║ interdits         : ✅/❌                 ║
║ pyproject.toml    : ✅/❌                 ║
║ structlog stderr  : ✅/❌                 ║
╠══════════════════════════════════════════╣
║ VERDICT : PRODUCTION-READY ✅            ║
║       ou : NON CONFORME  ❌              ║
╚══════════════════════════════════════════╝
```

─────────────────────────────────────────────
SI NON CONFORME
─────────────────────────────────────────────
"❌ [N] points non conformes.

 Corrections recommandées :
 1. [point] → [action] → relancer P3_FIX_prompt.md batch [X]
 2. ...

 Relancer P4_VERIFY_prompt.md après corrections."
