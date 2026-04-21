---
title: Plan d'action — IR & Maturité Conceptuelle
source: tasks/audits/resultats/audit_ir_maturity_aiprod.md
creation: 2026-04-21 à 12:38
last_updated: 2026-04-21 à 12:52
status: completed
corrections_totales: 5 (P1:1 P2:3 P3:1)
prerequis: audit_ir_maturity_aiprod.md (2026-04-21)
---

# PLAN D'ACTION — IR & MATURITÉ CONCEPTUELLE — 2026-04-21

**Source** : `tasks/audits/resultats/audit_ir_maturity_aiprod.md`
**Généré le** : 2026-04-21 à 12:38
**Corrections totales** : 5 (P1:1 · P2:3 · P3:1)

---

## Résumé

L'audit identifie 3 gaps architecturaux exploitables sans NLP : l'absence de validation
référentielle `shot.scene_id → scene.scene_id` en Pass 4, la duplication des listes de verbes
entre `duration_rules.py` et `cinematography_rules.py`, et l'absence de validation Pydantic sur
les valeurs de `shot_type` / `camera_movement`. Les deux autres axes (décomposition `VisualAction`
et `camera_angle`) sont des évolutions IR qui constituent un plan distinct (IR v3).

---

## Corrections P1 — CRITIQUE

### [IR-01] ✅ FAIT (2026-04-21 à 12:52) — Enforcer la référence `shot.scene_id → scene.scene_id` en Pass 4

**Priorité** : P1
**Sévérité** : 🔴
**Fichier** : `aiprod_adaptation/core/pass4_compile.py:33`
**Problème** : `compile_episode()` accepte des shots référençant des `scene_id` inexistantes sans lever d'erreur. La seule vérification est dans un test (`test_shot_scene_ids_reference_known_scenes`) — pas dans le modèle. Un bug silencieux peut produire un `AIPRODOutput` structurellement incohérent.
**Action** : Ajouter dans `compile_episode()`, après les guards `not scenes / not shots`, la vérification :
```python
known_scene_ids = {s["scene_id"] for s in scenes}
for shot in shots:
    if shot.get("scene_id") not in known_scene_ids:
        raise ValueError(
            f"PASS 4: shot '{shot.get('shot_id')}' references unknown scene_id '{shot.get('scene_id')}'"
        )
```
**Tests impactés** :
- Tous les tests `TestInvalidDuration` (les fixtures utilisent `scene_id="SC001"` + `shot scene_id="SC001"` → doivent passer)
- Ajouter `test_shot_references_unknown_scene_raises` dans `TestInvalidDuration`
**Risque** : Faible — ne change que le comportement sur données invalides. Les 42 tests existants passent tous.

---

## Corrections P2 — IMPORTANT

### [IR-02] ✅ FAIT (2026-04-21 à 12:52) — Unifier les listes de verbes dupliquées

**Priorité** : P2
**Sévérité** : 🟠
**Fichiers** :
- `aiprod_adaptation/core/rules/duration_rules.py` — `_MOTION_VERBS`, `_INTERACTION_VERBS`
- `aiprod_adaptation/core/rules/cinematography_rules.py` — `CAMERA_MOVEMENT_MOTION_KEYWORDS`, `CAMERA_MOVEMENT_INTERACTION_KEYWORDS`
**Problème** : Deux listes de verbes de mouvement coexistent avec des contenus différents. Exemple : `"rush"/"stride"/"march"` sont dans `CAMERA_MOVEMENT_MOTION_KEYWORDS` mais absents de `_MOTION_VERBS`. Toute extension future divergera silencieusement.
**Action** :
1. Créer `aiprod_adaptation/core/rules/verb_categories.py` avec les listes canoniques :
   - `MOTION_VERBS: List[str]` — union des deux listes actuelles
   - `INTERACTION_VERBS: List[str]` — idem
   - `PERCEPTION_VERBS: List[str]` — depuis `duration_rules.py` (non dupliqué)
2. `duration_rules.py` importe depuis `verb_categories.py`
3. `cinematography_rules.py` importe depuis `verb_categories.py`
4. Les deux anciens modules n'exposent plus leurs propres listes (ou les re-exportent via import)
**Tests impactés** :
- `test_all_shot_durations_valid` — vérifier que les durées ne changent pas (les verbes unifiés doivent être un superset)
- `test_json_byte_identical` — **CRITIQUE** : si des verbes sont ajoutés à `_MOTION_VERBS`, des durées peuvent changer → surveiller attentivement
**Risque** : Moyen — la fusion des listes peut changer des durées ou des `camera_movement` sur les textes de test existants. Tester avant de committer.

---

### [IR-03] ✅ FAIT (2026-04-21 à 12:52) — Valider `shot_type` et `camera_movement` via `field_validator` Pydantic

**Priorité** : P2
**Sévérité** : 🟠
**Fichier** : `aiprod_adaptation/models/schema.py:15-22`
**Problème** : `Shot.shot_type` et `Shot.camera_movement` sont des `str` libres avec défaut. Une valeur invalide (`"zoom"`, `"extreme_close"`, `""`) passe sans erreur ni warning. Le contrat n'est garanti que par les tests, pas par le modèle.
**Action** : Ajouter des `field_validator` Pydantic v2 dans `Shot` :
```python
from pydantic import field_validator

_VALID_SHOT_TYPES = frozenset({"wide", "medium", "close_up", "pov"})
_VALID_CAMERA_MOVEMENTS = frozenset({"static", "follow", "pan"})

@field_validator("shot_type")
@classmethod
def validate_shot_type(cls, v: str) -> str:
    if v not in _VALID_SHOT_TYPES:
        raise ValueError(f"Invalid shot_type: {v!r}. Must be one of {sorted(_VALID_SHOT_TYPES)}")
    return v

@field_validator("camera_movement")
@classmethod
def validate_camera_movement(cls, v: str) -> str:
    if v not in _VALID_CAMERA_MOVEMENTS:
        raise ValueError(f"Invalid camera_movement: {v!r}. Must be one of {sorted(_VALID_CAMERA_MOVEMENTS)}")
    return v
```
**Tests impactés** :
- `TestShotStructure` — les validators renforcent ce que les tests vérifient déjà → aucun test ne doit casser
- Ajouter `test_shot_invalid_shot_type_raises` et `test_shot_invalid_camera_movement_raises` dans `TestInvalidDuration` ou une nouvelle classe `TestShotValidation`
**Risque** : Faible. Les défauts (`"medium"`, `"static"`) sont dans les ensembles valides.

---

### [IR-04] ✅ FAIT (2026-04-21 à 12:52) — Aliases backward-compat documentés

**Priorité** : P2
**Sévérité** : 🟠
**Fichiers** :
- `aiprod_adaptation/core/pass3_shots.py:180` — `atomize_shots = simplify_shots`
- `aiprod_adaptation/core/pass4_compile.py:61` — `compile_output = compile_episode`
**Problème** : Ces aliases existent parce que les tests et `engine.py` les importent encore. Ce n'est pas un problème immédiat mais crée de l'ambiguïté sur quelle fonction est l'API publique.
**Action** :
1. Mettre à jour `engine.py` pour importer `simplify_shots` et `compile_episode` directement
2. Mettre à jour `test_pipeline.py` pour importer `atomize_shots` depuis `pass3_shots` et `compile_output` depuis `pass4_compile` — **OU** conserver les aliases en les rendant explicitement documentés comme "deprecated"
3. **Décision recommandée** : conserver les aliases mais ajouter un commentaire `# Deprecated — use simplify_shots` pour éviter la régression
**Tests impactés** : Tous les tests qui importent `atomize_shots` ou `compile_output` — à vérifier avec grep
**Risque** : Moyen si on migre les imports. Faible si on documente seulement les aliases.

---

## Corrections P3 — MINEUR

### [IR-05] ✅ FAIT (2026-04-21 à 12:52) — Documenter le format attendu des `visual_actions` dans `VisualScene`

**Priorité** : P3
**Sévérité** : 🟡
**Fichier** : `aiprod_adaptation/models/intermediate.py:33`
**Problème** : `VisualScene.visual_actions: List[str]` n'a aucune contrainte documentée sur le format des chaînes. `_atomize_action()` en Pass 3 split sur `", "` — ce comportement implicite n'est nulle part spécifié comme contrat.
**Action** : Ajouter un commentaire de contrat dans `VisualScene` et dans le docstring de `simplify_shots()` :
```python
visual_actions: List[str]
# Format attendu : phrase simple ou liste d'actions séparées par ", "
# Ex: "walks to the door" ou "fidgets, paces, bites lip"
# Pass 3 atomise sur ", " — chaque élément devient un shot distinct
```
**Tests impactés** : Aucun
**Risque** : Nul

---

## Ordre d'exécution recommandé

```
IR-01 (Pass 4 — validation référentielle)
  ↓ impact isolé, zéro dépendance externe
IR-03 (Shot — field_validator Pydantic)
  ↓ impact isolé sur schema.py
IR-02 (verb_categories.py — unification listes)
  ↓ surveiller test_json_byte_identical après
IR-04 (aliases backward-compat — documentation)
  ↓
IR-05 (documentation contrat visual_actions)
  ↓
Validation finale
```

**Pourquoi IR-02 après IR-03 ?** IR-02 peut changer des durées si des verbes sont ajoutés — il faut que le modèle soit solide (validators en place) avant de toucher aux règles.

---

## Ce qui n'est PAS dans ce plan (hors scope — IR v3)

| Exclu | Raison | Plan futur |
|---|---|---|
| `VisualAction` TypedDict (subject/verb/object) | Refactor majeur de Pass 2 + Pass 3 | IR v3 |
| `camera_angle` (low/high/eye-level) | Extension IR — nécessite nouvelles règles | IR v3 |
| Chunking / streaming long narratif | Feature — pas une correction | Feature plan |
| Multi-épisodes dans `engine.py` | Feature — pas une correction | Feature plan |

---

## Validation finale

```bash
# Activer l'environnement
venv\Scripts\Activate.ps1

# Ruff
ruff check aiprod_adaptation/

# Mypy strict
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ --strict

# Tests (cible : 42+ tests verts)
pytest aiprod_adaptation/tests/ -v --tb=short

# Déterminisme byte-level
pytest aiprod_adaptation/tests/ -v -k "test_json_byte_identical"
```

Cibles après exécution :
- [x] 45/45 tests pytest verts (42 + 3 nouveaux : IR-01 + IR-03×2) ✅
- [x] ruff 0 erreurs ✅
- [x] mypy strict 0 erreurs (19 fichiers) ✅
- [x] test_json_byte_identical ✅
- [x] Pipeline JSON valide ✅
- [ ] `test_json_byte_identical` vert
- [ ] mypy strict 0 erreur
- [ ] ruff 0 warning
- [ ] Aucun `# type: ignore`
