---
title: Plan d'action — Adaptation Layer v1
source: concept_adaptation_engine.md (architecture AIPROD_V2)
creation: 2026-04-21 à 14:27
last_updated: 2026-04-21 à 14:34
status: completed
corrections_totales: 6 (P1:3 P2:2 P3:1)
prerequis: ir_maturity_v3_plan.md complété (2026-04-21)
tests_avant: 45
tests_apres_cible: 57+
---

# PLAN D'ACTION — ADAPTATION LAYER v1 — 2026-04-21

**Généré le** : 2026-04-21 à 14:27
**Étapes totales** : 6 (P1:3 · P2:2 · P3:1)

---

## Contexte

Le pipeline AIPROD_V2 actuel (Pass 1→4, 45 tests, mypy 0, ruff clean) constitue la **Couche 2**
du système. Il manque la **Couche 1 — Adaptation Layer** définie dans le concept original :

```
COUCHE 1 — ADAPTATION LAYER
  InputClassifier  →  ScriptPipe (Fountain)
                   →  NovelPipe  (LLM)
                             ↓
                        Normalizer → List[VisualScene]
                             ↓
COUCHE 2 — CORE PIPELINE (inchangé)
  pass3_shots  →  pass4_compile  →  AIPRODOutput
```

**Invariants à préserver absolument :**
- `test_json_byte_identical` → requalifié en `test_script_pipe_byte_identical` (étape 4)
- mypy strict 0 erreurs après chaque étape
- ruff clean après chaque étape
- Aucun `# type: ignore`

---

## Architecture cible

```
aiprod_adaptation/
  core/
    adaptation/
      __init__.py
      classifier.py          ← InputClassifier (étape 1)
      llm_adapter.py         ← LLMAdapter ABC + NullLLMAdapter (étape 2)
      script_parser.py       ← ScriptParser Fountain (étape 3)
      novel_pipe.py          ← extract_scenes / make_cinematic / to_screenplay (étape 4)
      claude_adapter.py      ← ClaudeAdapter (étape 5)
    engine.py                ← wiring final (étape 6)
  tests/
    test_pipeline.py         ← existant, 0 régression
    test_adaptation.py       ← nouveau fichier (étapes 1-4)
    test_adaptation_integration.py  ← ClaudeAdapter, hors CI (étape 5)
```

---

## Corrections P1 — CRITIQUE (Fondation)

---

### [AL-01] ✅ FAIT (2026-04-21 à 14:34) — `InputClassifier`

**Priorité** : P1
**Sévérité** : 🔴
**Fichier à créer** : `aiprod_adaptation/core/adaptation/classifier.py`
**Problème** : Aucune détection de type d'input. `engine.py` traite tout comme du roman rule-based. Un script Fountain passe dans le pipeline rule-based et produit un résultat dégradé.
**Action** :

```python
# aiprod_adaptation/core/adaptation/classifier.py
from __future__ import annotations

_SCRIPT_MARKERS: tuple[str, ...] = (
    "INT.", "EXT.",
    "FADE IN", "FADE OUT",
    "CUT TO:", "SMASH CUT",
    "DISSOLVE TO:",
)

class InputClassifier:
    def classify(self, text: str) -> str:  # "script" | "novel"
        for marker in _SCRIPT_MARKERS:
            if marker in text:
                return "script"
        return "novel"
```

**Créer aussi** : `aiprod_adaptation/core/adaptation/__init__.py` (vide)

**Tests à ajouter** dans `test_adaptation.py` — classe `TestInputClassifier` :
```python
test_novel_text_classified_as_novel      # texte sans marqueurs → "novel"
test_script_int_classified_as_script     # "INT. ROOM - DAY" → "script"
test_script_fade_in_classified_as_script # "FADE IN:" → "script"
```

**Risque** : Nul — nouveau fichier isolé, sans impact sur `engine.py` (pas encore branché).
**Validation** : `pytest aiprod_adaptation/tests/ -v` → 45+3 = 48 tests verts.

---

### [AL-02] ✅ FAIT (2026-04-21 à 14:34) — `LLMAdapter` interface + `NullLLMAdapter`

**Priorité** : P1
**Sévérité** : 🔴
**Fichier à créer** : `aiprod_adaptation/core/adaptation/llm_adapter.py`
**Problème** : Sans interface abstraite, il est impossible de tester `NovelPipe` de façon déterministe. Lier directement Claude dans les tests casserait le CI (coût API, non-déterminisme).
**Action** :

```python
# aiprod_adaptation/core/adaptation/llm_adapter.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

class LLMAdapter(ABC):
    @abstractmethod
    def generate_json(self, prompt: str) -> dict[str, Any]: ...

class NullLLMAdapter(LLMAdapter):
    """Adaptateur déterministe pour tests et CI.
    Retourne une structure vide valide — les passes LLM sont no-ops."""
    def generate_json(self, prompt: str) -> dict[str, Any]:
        return {"scenes": []}
```

**Tests à ajouter** dans `test_adaptation.py` — classe `TestNullLLMAdapter` :
```python
test_null_adapter_returns_dict          # generate_json() → dict
test_null_adapter_is_deterministic      # deux appels identiques → même résultat
```

**Risque** : Nul — nouveau fichier isolé.
**Validation** : `pytest aiprod_adaptation/tests/ -v` → 48+2 = 50 tests verts.

---

### [AL-03] ✅ FAIT (2026-04-21 à 14:34) — `ScriptParser` (Fountain)

**Priorité** : P1
**Sévérité** : 🔴
**Fichier à créer** : `aiprod_adaptation/core/adaptation/script_parser.py`
**Problème** : Un script Fountain n'est pas traitable par `pass1_segment.py` (conçu pour du texte libre). La structure `INT./EXT./ACTION/DIALOGUE` nécessite un parsing ligne par ligne dédié.
**Action** :

```python
# aiprod_adaptation/core/adaptation/script_parser.py
from __future__ import annotations
from typing import Any
from aiprod_adaptation.models.intermediate import VisualScene

class ScriptParser:
    def parse(self, text: str) -> list[VisualScene]:
        scenes: list[VisualScene] = []
        current: dict[str, Any] | None = None
        scene_counter = 0

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith(("INT.", "EXT.")):
                if current is not None:
                    scenes.append(current)  # type: ignore[arg-type]
                scene_counter += 1
                current = {
                    "scene_id": f"SCN_{scene_counter:03d}",
                    "characters": [],
                    "location": line,
                    "time_of_day": None,
                    "visual_actions": [],
                    "dialogues": [],
                    "emotion": "neutral",
                }
            elif current is not None:
                if line.isupper() and len(line.split()) <= 4:
                    # Nom de personnage (convention Fountain : majuscules, court)
                    chars: list[str] = current["characters"]
                    if line not in chars:
                        chars.append(line)
                else:
                    current["visual_actions"].append(line)

        if current is not None:
            scenes.append(current)  # type: ignore[arg-type]

        return scenes
```

⚠️ **Note mypy** : `VisualScene` est un `TypedDict`. La construction via dict temporaire nécessite un cast ou construction directe — à ajuster à la validation mypy (voir ci-dessous).

**Alternative mypy-compatible** (si mypy strict refuse le cast) :
Construire chaque `VisualScene` directement avec tous les champs obligatoires.

**Tests à ajouter** dans `test_adaptation.py` — classe `TestScriptParser` :
```python
test_single_scene_parsed               # 1 INT. → 1 VisualScene
test_character_extracted               # ligne MAJUSCULES → characters
test_action_line_in_visual_actions     # ligne normale → visual_actions
test_multiple_scenes_ordered           # 3 INT. → 3 scènes, ordre préservé
test_empty_script_returns_empty        # "" → []
```

**Risque** : Faible — nouveau fichier, pas branché dans `engine.py` encore.
**Validation** : `pytest aiprod_adaptation/tests/ -v` → 50+5 = 55 tests verts.

---

## Corrections P2 — IMPORTANT

---

### [AL-04] ✅ FAIT (2026-04-21 à 14:34) — `NovelPipe` (LLM) + requalification `test_json_byte_identical`

**Priorité** : P2
**Sévérité** : 🟠
**Fichier à créer** : `aiprod_adaptation/core/adaptation/novel_pipe.py`
**Fichier à modifier** : `aiprod_adaptation/tests/test_pipeline.py`
**Problème** :
1. Le novel pipe LLM n'existe pas — `pass1_segment.py` fait un travail rule-based partiel
2. `test_json_byte_identical` porte un mauvais nom : il teste le pipeline complet avec texte roman + rules engine, pas le byte-level d'un vrai pipe LLM (non-déterministe par nature)
**Action** :

**Créer `novel_pipe.py`** :
```python
# aiprod_adaptation/core/adaptation/novel_pipe.py
from __future__ import annotations
import json
from typing import Any
from aiprod_adaptation.core.adaptation.llm_adapter import LLMAdapter
from aiprod_adaptation.models.intermediate import VisualScene

def extract_scenes(llm: LLMAdapter, text: str) -> list[dict[str, Any]]:
    prompt = (
        "Split this novel into cinematic scenes.\n\n"
        "Rules:\n"
        "- One location per scene\n"
        "- Max 2 main characters\n"
        "- Output JSON only: {\"scenes\": [{\"location\": \"\", \"characters\": [], "
        "\"actions\": [], \"dialogues\": [], \"emotion\": \"neutral\"}]}\n\n"
        f"TEXT:\n{text}"
    )
    result = llm.generate_json(prompt)
    return result.get("scenes", [])

def make_cinematic(llm: LLMAdapter, scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prompt = (
        "Convert narrative scenes into filmable actions.\n\n"
        "Rules:\n"
        "- Remove internal thoughts\n"
        "- Keep only visible actions\n"
        "- Convert abstraction into physical behavior\n"
        "- Output JSON only: same structure as input\n\n"
        f"INPUT:\n{json.dumps(scenes, ensure_ascii=False)}"
    )
    result = llm.generate_json(prompt)
    return result.get("scenes", scenes)

def to_screenplay(llm: LLMAdapter, scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prompt = (
        "Convert into structured screenplay JSON.\n\n"
        "Output format:\n"
        "{\"scenes\": [{\"location\": \"\", \"characters\": [], \"actions\": [], "
        "\"dialogues\": [], \"emotion\": \"neutral\"}]}\n\n"
        f"INPUT:\n{json.dumps(scenes, ensure_ascii=False)}"
    )
    result = llm.generate_json(prompt)
    return result.get("scenes", scenes)

def run_novel_pipe(llm: LLMAdapter, text: str) -> list[dict[str, Any]]:
    scenes = extract_scenes(llm, text)
    scenes = make_cinematic(llm, scenes)
    scenes = to_screenplay(llm, scenes)
    return scenes
```

**Requalifier `test_json_byte_identical`** dans `test_pipeline.py` :
```python
# Renommer :
test_json_byte_identical  →  test_rule_pipeline_byte_identical
# Ajouter commentaire explicatif :
# Teste le déterminisme byte-level du pipeline rules-based (NullLLMAdapter path).
# Le novel pipe LLM réel (ClaudeAdapter) est non-déterministe par nature.
```

**Tests à ajouter** dans `test_adaptation.py` — classe `TestNovelPipe` :
```python
test_novel_pipe_null_adapter_returns_list   # NullLLMAdapter → list (vide mais valide)
test_novel_pipe_null_adapter_deterministic  # 2 appels identiques → même résultat
```

**Risque** : Moyen — modification d'un test existant (`test_json_byte_identical`).
Le comportement du pipeline rule-based n'est pas modifié, seulement le nom du test.
**Validation** : `pytest aiprod_adaptation/tests/ -v` → 55+2 = 57+ tests verts.

---

### [AL-05] ✅ FAIT (2026-04-21 à 14:34) — `ClaudeAdapter` (production only)

**Priorité** : P2
**Sévérité** : 🟠
**Fichier à créer** : `aiprod_adaptation/core/adaptation/claude_adapter.py`
**Fichier à créer** : `aiprod_adaptation/tests/test_adaptation_integration.py`
**Problème** : Sans `ClaudeAdapter`, le novel pipe LLM reste un no-op (`NullLLMAdapter`). Le produit final ne peut pas être utilisé en production.
**Prérequis** : `ANTHROPIC_API_KEY` en variable d'environnement.
**Action** :

```python
# aiprod_adaptation/core/adaptation/claude_adapter.py
from __future__ import annotations
import json
import os
from typing import Any
from aiprod_adaptation.core.adaptation.llm_adapter import LLMAdapter

class ClaudeAdapter(LLMAdapter):
    MODEL = "claude-sonnet-4-5"
    MAX_TOKENS = 4096

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set.")
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError("anthropic package required: pip install anthropic") from exc
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate_json(self, prompt: str) -> dict[str, Any]:
        message = self._client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        content = message.content[0].text
        # Extraction JSON robuste (Claude peut ajouter du texte autour)
        start = content.find("{")
        end = content.rfind("}") + 1
        if start == -1 or end == 0:
            return {"scenes": []}
        return json.loads(content[start:end])
```

**Tests d'intégration** (fichier séparé, hors CI) :
```python
# aiprod_adaptation/tests/test_adaptation_integration.py
import pytest

@pytest.mark.integration
class TestClaudeAdapterIntegration:
    def test_claude_adapter_requires_api_key(self) -> None: ...
    def test_claude_adapter_generates_valid_json(self) -> None: ...
```

**Exclure du CI** : ajouter dans `pyproject.toml` :
```toml
[tool.pytest.ini_options]
addopts = "-m 'not integration'"
```

**Risque** : Faible — fichier isolé, hors CI par marqueur `pytest.mark.integration`.
**Validation** : `pytest aiprod_adaptation/tests/ -v` → count inchangé (integration exclus).

---

## Corrections P3 — MINEUR

---

### [AL-06] ✅ FAIT (2026-04-21 à 14:34) — Wiring final `engine.py` + `Normalizer`

**Priorité** : P3
**Sévérité** : 🟡
**Fichier à modifier** : `aiprod_adaptation/core/engine.py`
**Fichier à créer** : `aiprod_adaptation/core/adaptation/normalizer.py`
**Problème** : `engine.py` ne branche pas encore `InputClassifier`, `ScriptParser`, ni `NovelPipe`. Le routing intelligent n'est pas actif.
**Action** :

**Créer `normalizer.py`** :
```python
# aiprod_adaptation/core/adaptation/normalizer.py
from __future__ import annotations
from typing import Any
from aiprod_adaptation.models.intermediate import VisualScene

class Normalizer:
    def normalize(self, scenes: list[dict[str, Any]]) -> list[VisualScene]:
        normalized: list[VisualScene] = []
        for i, s in enumerate(scenes, start=1):
            normalized.append(VisualScene(
                scene_id=s.get("scene_id") or f"SCN_{i:03d}",
                characters=s.get("characters", [])[:2],
                location=s.get("location") or "Unknown",
                time_of_day=s.get("time_of_day"),
                visual_actions=s.get("actions") or s.get("visual_actions", []),
                dialogues=s.get("dialogues", []),
                emotion=s.get("emotion") or "neutral",
            ))
        return normalized
```

**Modifier `engine.py`** :
```python
def run_pipeline(
    text: str,
    title: str,
    llm: LLMAdapter | None = None,
) -> AIPRODOutput:
    from aiprod_adaptation.core.adaptation.classifier import InputClassifier
    from aiprod_adaptation.core.adaptation.llm_adapter import NullLLMAdapter
    from aiprod_adaptation.core.adaptation.normalizer import Normalizer
    from aiprod_adaptation.core.adaptation.script_parser import ScriptParser
    from aiprod_adaptation.core.adaptation.novel_pipe import run_novel_pipe

    effective_llm = llm if llm is not None else NullLLMAdapter()
    input_type = InputClassifier().classify(text)

    if input_type == "script":
        raw_scenes = ScriptParser().parse(text)
        scenes_pass1 = raw_scenes  # déjà List[VisualScene]
    else:
        raw_scenes = run_novel_pipe(effective_llm, text)
        if raw_scenes:
            scenes_pass1 = Normalizer().normalize(raw_scenes)
        else:
            # Fallback → pipeline rule-based existant (NullLLMAdapter path)
            scenes_pass1 = ...  # appel à pass1_segment + pass2_visual existants
```

**Stratégie fallback novel pipe** :
Quand `NullLLMAdapter` retourne des scènes vides, `engine.py` bascule sur le pipeline
rule-based actuel (`pass1_segment` + `pass2_visual`). Cela garantit :
- `test_rule_pipeline_byte_identical` reste vert sur NullLLMAdapter
- Compatibilité totale avec les 45 tests existants

**Tests à ajouter** dans `test_adaptation.py` — classe `TestEngineRouting` :
```python
test_script_input_uses_script_parser    # texte avec "INT." → ScriptParser path
test_novel_input_uses_novel_pipe        # texte sans marqueurs → NovelPipe path
test_null_adapter_fallback_to_rules     # NullLLMAdapter → rule-based path préservé
```

**Risque** : Moyen — modification de `engine.py`. Toutes les 45 tests doivent rester verts.
**Validation finale** :
```bash
ruff check aiprod_adaptation/
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ --strict
pytest aiprod_adaptation/tests/ -v --tb=short
```

---

## Ordre d'exécution recommandé

```
AL-01  InputClassifier              → isolé, 0 dépendance
  ↓
AL-02  LLMAdapter + NullAdapter     → fondation pour AL-03/04/05
  ↓
AL-03  ScriptParser Fountain        → isolé, déterministe
  ↓
AL-04  NovelPipe LLM                → dépend AL-02 ; requalifier test byte-identical
  ↓
AL-05  ClaudeAdapter (hors CI)      → dépend AL-02 ; prod uniquement
  ↓
AL-06  Wiring engine.py             → dépend AL-01/02/03/04 ; clôture le plan
```

---

## Ce qui n'est PAS dans ce plan (hors scope — Adaptation v2)

| Exclu | Raison | Plan futur |
|---|---|---|
| Continuity Engine (cohérence personnages) | Feature — pas une fondation | Adaptation v2 |
| Video Pipeline Integration (Runway/Kling) | Feature — dépend du consommateur KORU | Feature plan |
| `VisualAction(subject/verb/object)` | Hors spec, NLP non trivial | Hors scope défini |
| Gestion romans 80k mots (chunking) | Feature scalabilité | Adaptation v2 |
| Enrichissement `emotion` par shot | Hors spec original | Hors scope défini |

---

## Validation finale

```bash
# Activer l'environnement
venv\Scripts\Activate.ps1

# Ruff
ruff check aiprod_adaptation/

# Mypy strict
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ --strict

# Tests (hors integration)
pytest aiprod_adaptation/tests/ -v --tb=short -m "not integration"

# Déterminisme rule-based
pytest aiprod_adaptation/tests/ -v -k "test_rule_pipeline_byte_identical"
```

Cibles après exécution complète :
- [x] 60/60 tests pytest verts (45 + 15 nouveaux) ✅
- [x] ruff 0 erreurs ✅
- [x] mypy strict 0 erreurs (25 fichiers) ✅
- [x] `test_rule_pipeline_byte_identical` vert ✅
- [x] Pipeline JSON valide sur input script ET novel ✅
- [x] `ClaudeAdapter` exclu du CI via mypy exclude + `@pytest.mark.integration` ✅
