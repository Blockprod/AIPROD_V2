---
title: Plan d'action — Shot v2 IR Cinématographique (Étape 1)
creation: 2026-04-21 à 11:31
last_updated: 2026-04-21 à 11:47
status: completed
objectif: Extraire shot_type et camera_movement comme champs structurés dans Shot et ShotDict
prerequis: backends_ir_plan.md complété (39/39 tests, metadata ajouté, backends/ créé)
---

# Plan d'action — Shot v2 IR Cinématographique (Étape 1)

---

## Principe fondamental

**Ce plan = uniquement ce qui est déterministe sans NLP.**

| Champ | Faisable déterministement | Décision |
|---|---|---|
| `shot_type` | ✅ déjà calculé dans `_shot_type()` | À extraire comme champ |
| `camera_movement` | ✅ via règles (motion verbs présents) | À ajouter comme champ |
| `camera_angle` | 🟡 heuristiques limitées | Optionnel — évalué en C3 |
| `subject / action / object` | ❌ NLP requis | Rejeté — hors scope |

Le `prompt` **reste** dans `Shot` — il devient un artifact dérivé des champs structurés,
pas leur source de vérité.

---

## État de départ

| Composant | État |
|---|---|
| `Shot.shot_type` | ✅ FAIT — 2026-04-21 |
| `Shot.camera_movement` | ✅ FAIT — 2026-04-21 |
| `ShotDict.shot_type` | ✅ FAIT — 2026-04-21 |
| `ShotDict.camera_movement` | ✅ FAIT — 2026-04-21 |
| `core/rules/cinematography_rules.py` | ✅ FAIT — 2026-04-21 |
| `pass3_shots.py` refactor | ✅ FAIT — 2026-04-21 |
| 42/42 tests | ✅ verts |

---

## AXE 1 — RÈGLES CINÉMATOGRAPHIQUES

### C1 — `core/rules/cinematography_rules.py`

**Principe** : même pattern que `duration_rules.py` et `emotion_rules.py`.
Source de vérité unique pour les règles cinématographiques de Pass 3.

**Contenu** :

```python
# Types de shot — ordre de priorité (premier match gagne)
SHOT_TYPE_RULES: List[Tuple[str, List[str]]]
# ex: [("POV", ["pov", "point of view"]), ("CLOSE_UP", [...facial words...]), ...]

# Mouvements de caméra — détection par verbes de mouvement
CAMERA_MOVEMENT_STATIC_KEYWORDS: List[str]   # wait, stand, sit, stare, look
CAMERA_MOVEMENT_MOTION_KEYWORDS: List[str]   # walk, run, move, rush, approach
CAMERA_MOVEMENT_INTERACTION_KEYWORDS: List[str]  # reach, hand, give, touch
```

**Valeurs `shot_type`** (littérales, stables) :
- `"wide"` — environnement ou mouvement large
- `"medium"` — interaction entre personnages (défaut)
- `"close_up"` — expressions faciales ou petits objets
- `"pov"` — point de vue subjectif

**Valeurs `camera_movement`** (littérales, stables) :
- `"static"` — pas de déplacement dominant
- `"follow"` — suit un personnage en mouvement
- `"pan"` — balayage latéral (interaction ou perception)

**Règle de mapping** :
```
motion verb présent    → camera_movement = "follow"
interaction verb seul  → camera_movement = "pan"
sinon                  → camera_movement = "static"
```

**Critères de done** :
- `cinematography_rules.py` importable depuis `aiprod_adaptation.core.rules`
- mypy strict 0 erreur
- aucun import depuis `pass3_shots.py` avant C2

---

## AXE 2 — MODÈLES IR

### C2 — `ShotDict` et `Shot` — nouveaux champs

**Fichiers** :
- `aiprod_adaptation/models/intermediate.py` → `ShotDict`
- `aiprod_adaptation/models/schema.py` → `Shot`

**Spec `ShotDict`** (TypedDict) :

```python
class ShotDict(TypedDict):
    shot_id:          str
    scene_id:         str
    prompt:           str
    duration_sec:     int
    emotion:          str
    shot_type:        str   # "wide" | "medium" | "close_up" | "pov"
    camera_movement:  str   # "static" | "follow" | "pan"
    metadata:         NotRequired[dict[str, Any]]
```

**Spec `Shot`** (Pydantic) :

```python
class Shot(BaseModel):
    shot_id:          str
    scene_id:         str
    prompt:           str
    duration_sec:     int
    emotion:          str
    shot_type:        str   # "wide" | "medium" | "close_up" | "pov"
    camera_movement:  str   # "static" | "follow" | "pan"
    metadata:         dict[str, Any] = {}
```

**Règle** : pas de `Literal[]` ni de `Enum` — des `str` simples pour rester extensible sans casser mypy strict.

**Critères de done** :
- mypy strict 0 erreur
- `Shot` backward-compatible (les tests `compile_output` passent les shots comme dicts — les nouveaux champs doivent avoir des défauts ou les dicts de test doivent être mis à jour)

---

## AXE 3 — PASS 3

### C3 — Refactor `pass3_shots.py`

**Changements** :

1. Remplacer l'import `_shot_type` local par `cinematography_rules`
2. Extraire `shot_type` et `camera_movement` comme variables locales
3. Passer `shot_type` dans le dict produit (plus dans le prompt comme préfixe texte)
4. Mettre à jour `_build_prompt` : retirer le préfixe `"WIDE SHOT: "` — le prompt devient le texte brut enrichi de la location
5. Ajouter `shot_type` et `camera_movement` dans chaque `ShotDict` produit

**Avant** :
```python
stype  = _shot_type(part)
prompt = _build_prompt(part, stype, location, characters)
# prompt = "WIDE SHOT: Marcus ran..., in the market."
```

**Après** :
```python
shot_type        = _compute_shot_type(part)         # "wide"
camera_movement  = _compute_camera_movement(part)   # "follow"
prompt           = _build_prompt(part, location)    # "Marcus ran..., in the market."
```

**Critères de done** :
- `simplify_shots()` peuple `shot_type` et `camera_movement` dans chaque shot
- `prompt` ne contient plus le préfixe `"WIDE SHOT: "` etc.
- mypy strict 0 erreur

---

## AXE 4 — TESTS

### C4 — Mise à jour `test_pipeline.py` + `test_backends.py`

**Tests à mettre à jour** :

| Test | Changement requis |
|---|---|
| `test_duration_boundary_low_valid` | Ajouter `shot_type` et `camera_movement` dans les dicts de shots des fixtures |
| `test_duration_boundary_high_valid` | Idem |
| `test_duration_too_low_raises` | Idem |
| `test_duration_too_high_raises` | Idem |
| `test_shot_model_rejects_invalid_duration_directly` | Idem |
| `test_pass4_empty_shots` | Idem |
| `test_pass4_empty_scenes` | Idem |
| `TestCsvExport` (header) | Décision : ajouter ou non `shot_type`/`camera_movement` dans le CSV |

**Nouveaux tests à ajouter dans `test_pipeline.py`** :

```python
class TestShotStructure:
    def test_shot_type_field_present(self)  # shot.shot_type in {"wide","medium","close_up","pov"}
    def test_camera_movement_field_present(self)  # shot.camera_movement in {"static","follow","pan"}
    def test_prompt_has_no_shot_type_prefix(self)  # "WIDE SHOT:" absent du prompt
```

**Critères de done** :
- tous les tests passent (39 + N)
- `test_json_byte_identical` vert
- `test_csv_export_header` mis à jour si colonnes CSV changent

---

## AXE 5 — BACKENDS (mise à jour)

### C5 — `csv_export.py` — colonnes mises à jour

**Décision** : ajouter `shot_type` et `camera_movement` dans le CSV export.

**Nouvelles colonnes** :
```
episode_id, scene_id, shot_id, shot_type, camera_movement, prompt, duration_sec, emotion
```

**Critères de done** :
- `CsvExport().export(output)` produit le nouveau header
- `test_csv_export_header` mis à jour
- déterminisme conservé

---

## Ordre d'exécution

```
C1 (cinematography_rules.py)          ✅ FAIT — 2026-04-21
    ↓
C2 (ShotDict + Shot — nouveaux champs) ✅ FAIT — 2026-04-21
    ↓
C3 (pass3_shots.py — refactor)         ✅ FAIT — 2026-04-21
    ↓
C4 (tests — mise à jour + nouveaux)    ✅ FAIT — 2026-04-21 (42/42 tests)
    ↓
C5 (csv_export.py — nouvelles colonnes) ✅ FAIT — 2026-04-21
    ↓
Validation finale : mypy + ruff + pytest ✅ FAIT — 42/42 passed in 0.88s
```

---

## Invariants à respecter tout au long

- **`test_json_byte_identical` doit rester vert** — le refactor de `_build_prompt` ne doit pas changer la logique de contenu
- **Zéro `# type: ignore`**
- **Le core ne connaît pas les backends**
- **`prompt` reste dans `Shot`** — il est dérivé, pas supprimé
- **Valeurs de `shot_type` et `camera_movement` = str minuscules avec underscore** (`"close_up"`, pas `"CLOSE UP"`)
- **Aucun NLP** — si une règle n'est pas implémentable en regex/liste, elle n'entre pas dans ce plan

---

## Ce qui n'est PAS dans ce plan (Étape 2 future)

| Exclu | Raison |
|---|---|
| `subject / action / object` | NLP requis (spaCy ou équivalent) |
| `camera_angle` (low/high/eye-level) | Heuristiques trop fragiles sans NLP |
| `Enum` pour `shot_type` | Complexité mypy inutile — str suffit |
| Backends image/vidéo réels | Hors scope — pas de renderer choisi |

---

## Définition de "done" pour ce plan

1. `Shot.shot_type` et `Shot.camera_movement` présents dans l'IR ✅
2. `prompt` = texte brut sans préfixe `"WIDE SHOT:"` etc. ✅
3. `core/rules/cinematography_rules.py` = source de vérité ✅
4. mypy strict 0 erreur sur tous les fichiers ✅ (18 fichiers)
5. ruff 0 warning ✅
6. tous les tests (39 + 3 nouveaux) passent ✅ (42/42)
7. `test_json_byte_identical` vert ✅
