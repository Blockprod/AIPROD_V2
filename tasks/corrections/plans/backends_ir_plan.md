---
title: Plan d'action — Architecture Backends (IR universel + couche renderer)
creation: 2026-04-21 à 11:07
last_updated: 2026-04-21 à 11:19
status: completed — 39/39 tests verts, mypy strict 0 erreur, ruff propre
objectif: Stabiliser le JSON comme IR universel et introduire la couche backends sans polluer core/
prerequis: production_ready_plan.md complété (33/33 tests, mypy strict, CLI argparse)
---

# Plan d'action — Architecture Backends

---

## Principe fondamental (non négociable)

```
core/   ← compilateur déterministe — INTOUCHABLE (sauf metadata)
   ↓
  Shot (IR universel)
   ↓
backends/  ← couche renderer — indépendante, extensible, testable
```

> **Le core ne connaît JAMAIS le backend.**
> Les backends lisent `AIPRODOutput`. Ils n'écrivent jamais dans `core/`.

---

## État courant (21 avril 2026 — après exécution complète)

| Composant | État |
|---|---|
| `Shot.metadata` | ✅ `dict[str, Any] = {}` |
| `ShotDict.metadata` | ✅ `NotRequired[dict[str, Any]]` |
| `pass3_shots.py` peuple `metadata={}` | ✅ fait |
| `backends/__init__.py` | ✅ créé |
| `backends/base.py` (`BackendBase` ABC) | ✅ créé |
| `backends/csv_export.py` | ✅ créé |
| `backends/json_flat_export.py` | ✅ créé |
| `tests/test_backends.py` (6 cas) | ✅ verts |
| `--format json\|csv\|json-flat` dans CLI | ✅ implémenté |
| mypy strict (17 fichiers) | ✅ 0 erreur |
| ruff | ✅ 0 warning |
| 39/39 tests | ✅ verts |

---

## AXE 1 — STABILISER L'IR

### B1 — Ajouter `metadata` dans `Shot` et `ShotDict`

**Principe** : champ optionnel, ignoré par tout le core, réservé aux backends.

**Fichiers à modifier** :
- `aiprod_adaptation/models/schema.py` → `Shot`
- `aiprod_adaptation/models/intermediate.py` → `ShotDict`

**Spec exacte** :

```python
# schema.py — Shot
from typing import Any
metadata: dict[str, Any] = {}

# intermediate.py — ShotDict (TypedDict)
from typing import Any
metadata: dict[str, Any]  # optionnel via NotRequired
```

**Règles** :
- `dict[str, Any]` (pas `dict[str, str]`) — pour permettre valeurs numériques (seed, fps)
- Valeur par défaut `{}` dans Pydantic — ne casse aucun test existant
- `NotRequired` dans `ShotDict` — mypy strict doit passer
- Pass 3 (`pass3_shots.py`) peuple `metadata={}` dans chaque shot produit
- `test_json_byte_identical` doit rester vert

**Critères de done** :
- mypy strict 0 erreur
- 33/33 tests verts
- `python main.py --input examples/sample.txt 2>/dev/null` — `metadata: {}` présent dans chaque shot du JSON

---

## AXE 2 — CRÉER LA COUCHE BACKENDS

### B2 — Structure du package

**Arborescence cible** :

```
aiprod_adaptation/
└── backends/
    ├── __init__.py          ← package marker vide
    ├── base.py              ← protocole/interface commune (ABC)
    ├── csv_export.py        ← backend CSV (zéro dépendance externe)
    └── json_flat_export.py  ← backend JSON à plat (zéro dépendance externe)
```

**Règle** : `backends/image/` et `backends/video/` ne sont PAS créés maintenant.
Ils seront ajoutés quand un renderer réel sera choisi.

---

### B3 — `backends/base.py` — Protocole commun

**Spec** :

```python
from abc import ABC, abstractmethod
from aiprod_adaptation.models.schema import AIPRODOutput

class BackendBase(ABC):
    @abstractmethod
    def export(self, output: AIPRODOutput) -> str:
        """Convert AIPRODOutput to a string representation."""
        ...
```

**Critères de done** :
- mypy strict 0 erreur sur `backends/base.py`
- `BackendBase` importable depuis `aiprod_adaptation.backends`

---

### B4 — `backends/csv_export.py`

**Spec** : une ligne par shot, colonnes fixes.

**Colonnes** :
```
episode_id, scene_id, shot_id, prompt, duration_sec, emotion
```

**Comportement** :
- `metadata` exclu des colonnes (il sera géré par les backends spécialisés)
- séparateur `,`, encodage UTF-8, header inclus
- retourne une `str` (pas d'écriture fichier — le CLI s'en charge)

**Exemple de sortie** :
```csv
episode_id,scene_id,shot_id,prompt,duration_sec,emotion
EP01,SCN_001,SCN_001_SH001,"Marcus ran quickly... [WIDE SHOT]",4,nervous
```

**Critères de done** :
- `CsvExport(BackendBase).export(output)` retourne une str CSV valide
- déterministe (même input → même output byte-identical)
- mypy strict 0 erreur
- testé dans `tests/test_backends.py`

---

### B5 — `backends/json_flat_export.py`

**Spec** : liste plate de shots (sans la hiérarchie `episodes > scenes > shots`).

**Comportement** :
- chaque shot enrichi avec `episode_id` et `scene_id` au niveau racine
- `metadata` inclus s'il est non vide
- retourne une `str` JSON indenté à 2 espaces

**Exemple de sortie** :
```json
[
  {
    "episode_id": "EP01",
    "scene_id": "SCN_001",
    "shot_id": "SCN_001_SH001",
    "prompt": "Marcus ran quickly... [WIDE SHOT]",
    "duration_sec": 4,
    "emotion": "nervous"
  }
]
```

**Critères de done** :
- `JsonFlatExport(BackendBase).export(output)` retourne un JSON valide
- déterministe
- mypy strict 0 erreur
- testé dans `tests/test_backends.py`

---

## AXE 3 — TESTS BACKENDS

### B6 — `tests/test_backends.py`

**Spec** : fichier de tests dédié aux backends, indépendant de `test_pipeline.py`.

**Cas à couvrir** :

| Test | Description |
|---|---|
| `test_csv_export_header` | Le CSV contient les 6 colonnes attendues en header |
| `test_csv_export_row_count` | Autant de lignes de données que de shots dans l'output |
| `test_csv_export_deterministic` | Même input → même CSV byte-identical |
| `test_json_flat_export_is_list` | La sortie est un tableau JSON |
| `test_json_flat_export_episode_id_present` | Chaque item contient `episode_id` |
| `test_json_flat_export_deterministic` | Même input → même JSON byte-identical |

**Critères de done** :
- tous les tests passent
- `pytest aiprod_adaptation/tests/ -v` = 33 + N tests verts (N = nombre de tests backends)

---

## AXE 4 — INTÉGRATION CLI (optionnel, après B1-B6)

### B7 — Flag `--format` dans `main.py`

**Spec** :

```bash
python main.py --input chapter.txt --format json      # défaut (comportement actuel)
python main.py --input chapter.txt --format json-flat
python main.py --input chapter.txt --format csv
```

**Règle** : le backend est instancié dans `main.py`, pas dans `core/`.
`run_pipeline()` retourne toujours `AIPRODOutput` — inchangé.

**Critères de done** :
- `--format json` = comportement identique à aujourd'hui
- `--format csv` = sortie CSV sur stdout (ou fichier via `--output`)
- `--format json-flat` = liste plate de shots
- mypy strict 0 erreur
- 33 + N tests verts

---

## Ordre d'exécution

```
B1 (metadata dans Shot + ShotDict)     ✅ FAIT — 2026-04-21
    ↓
B2 + B3 (structure backends/ + base)   ✅ FAIT — 2026-04-21
    ↓
B4 (csv_export.py)                     ✅ FAIT — 2026-04-21
    ↓
B5 (json_flat_export.py)               ✅ FAIT — 2026-04-21
    ↓
B6 (tests/test_backends.py)            ✅ FAIT — 2026-04-21
    ↓
B7 (--format dans CLI)                 ✅ FAIT — 2026-04-21
```

---

## Invariants à respecter tout au long

- **Le core ne connaît JAMAIS les backends** — aucun import de `backends/` dans `core/`
- **`Shot` reste l'IR universel** — ne pas ajouter de champs renderer-specific dans `schema.py`
- **33/33 tests core verts** à chaque étape
- **`test_json_byte_identical` doit toujours passer**
- **mypy strict — 0 erreur** sur `core/`, `models/`, `backends/`
- **Zéro `# type: ignore`**
- **`metadata={}` dans pass3** — le core peuple le champ vide, les backends le lisent

---

## Ce qui n'est PAS dans ce plan (décision délibérée)

| Exclu | Raison |
|---|---|
| `backends/image/midjourney_adapter.py` | Prématuré — aucune API choisie |
| `backends/video/runway_adapter.py` | Prématuré — aucun renderer choisi |
| Enrichissement cinématographique de l'IR | Décision stratégique séparée (camera, framing, blocking) |
| API REST FastAPI | Hors scope de ce plan |

---

## Définition de "done" — ATTEINT ✅

1. ✅ `Shot.metadata` et `ShotDict.metadata` existent — mypy strict passe
2. ✅ `backends/csv_export.py` et `backends/json_flat_export.py` fonctionnent
3. ✅ 39/39 tests (core + backends) passent
4. ✅ `python main.py --input examples/chapter1.txt --format csv` produit un CSV valide
5. ✅ Le core n'a aucun import de `backends/`
