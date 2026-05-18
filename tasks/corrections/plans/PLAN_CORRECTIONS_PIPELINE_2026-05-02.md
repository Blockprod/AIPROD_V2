---
creation: 2026-05-02 à 15:10
maj: 2026-05-02 à 15:24
statut: partiellement appliqué — 4/5 corrections ✅ · 1/5 en attente GO
source_audit: tasks/audits/AUDIT_PIPELINE_2026-05-02.md
règle: Ne pas lancer d'appel API sans GO explicite. Ne pas casser ArcFace 0.9378 de Nara sans benchmark.
---

# Plan de corrections — Pipeline EP01
**District Zero · Episode 01**

Cinq corrections, deux fichiers principaux (`pipeline/shot_pipeline.py` + `production/gen_shots.py`), zéro régression tolérée sur Nara (baseline ArcFace 0.9378).

---

## Vue d'ensemble

| # | Problème | Fichier(s) cible | Criticité | Statut |
|---|----------|-----------------|-----------|--------|
| 1.1 | Pipeline Nara-only — LOCKED_NARA_CANONICAL hardcodé | `shot_pipeline.py` + `gen_shots.py` | CRITIQUE | ✅ Appliqué 2026-05-02 |
| 1.2 | Shots env = copie master plate identique | `gen_shots.py` | HAUTE | ⏳ En attente GO (API $0.03/shot) |
| 2.3 | Ordre des segments : personnage avant lieu (T5-XXL) | `shot_pipeline.py` | HAUTE | ✅ Appliqué 2026-05-02 |
| 2.4 | `_PORTRAIT_FOOTER` générique — `portrait_brief` ignoré | `aiprod_adaptation/image_gen/storyboard.py` | HAUTE | ✅ Appliqué 2026-05-02 |
| 4.2 | `lighting_context` shot ignoré au profit de `lighting_brief` lieu | `gen_shots.py` | HAUTE | ✅ Appliqué 2026-05-02 |

---

## CORRECTION 1.1 — Rendre le pipeline multi-personnages

### Problème
`LOCKED_NARA_CANONICAL` est hardcodé ligne 145 de `shot_pipeline.py` dans `build_p1_prompt()["subject"]["costume"]` et dans le corps de `build_p2_prompt()`. Tout shot de Vale, Elian, Mira ou Rook reçoit la description physique de Nara. La ref image du personnage tiraille dans l'autre sens → drift instable.

### Fichiers
- `pipeline/shot_pipeline.py`
- `production/gen_shots.py`

### Changements requis

**1. `pipeline/shot_pipeline.py` — `SceneP1Params`**

Ajouter un champ `character_canonical` avec default `LOCKED_NARA_CANONICAL` pour backward compat (Nara continue de fonctionner sans aucune modification de ses appels existants) :

```python
@dataclass
class SceneP1Params:
    # ... champs existants inchangés ...
    character_canonical: str = LOCKED_NARA_CANONICAL   # ← AJOUT
```

**2. `pipeline/shot_pipeline.py` — `build_p1_prompt()`**

Remplacer la référence directe :
```python
# AVANT
"costume": LOCKED_NARA_CANONICAL,

# APRÈS
"costume": p.character_canonical,
```

**3. `pipeline/shot_pipeline.py` — `build_p2_prompt()`**

Ajouter les paramètres `character_name` et `character_canonical` :
```python
# AVANT
def build_p2_prompt(scene_env: str, subject_action: str) -> str:
    return (
        f"{scene_env} "
        f"Nara Voss {subject_action}. "
        f"{LOCKED_NARA_CANONICAL} "
        ...
    )

# APRÈS
def build_p2_prompt(
    scene_env: str,
    subject_action: str,
    character_name: str = "Nara Voss",
    character_canonical: str = LOCKED_NARA_CANONICAL,
) -> str:
    return (
        f"{scene_env} "
        f"{character_name} {subject_action}. "
        f"{character_canonical} "
        ...
    )
```

**4. `production/gen_shots.py` — appel `run_shot()`**

Extraire le canonical depuis `characters.json` via `load_character()` (déjà importé), et passer les nouveaux paramètres :

```python
# Dans le bloc `if char_id:`, après `char = load_character(char_id)` :
char_canonical = char.get("canonical", LOCKED_NARA_CANONICAL)
char_name = char.get("name", "Nara Voss")

params = build_scene_params(shot, scene_cfg, location, grade)
# Injecter le canonical dans SceneP1Params :
params.character_canonical = char_canonical

result = run_shot(
    scene_params=params,
    shot_id=shot["shot_id"],
    ref_img=Path(ref_path),
    out_dir=out_dir,
    p2_scene_env=...,
    p2_subject_action=shot["action_brief"],
    # Ajouter :
    p2_character_name=char_name,
    p2_character_canonical=char_canonical,
    root=ROOT,
)
```

**5. `pipeline/shot_pipeline.py` — `run_shot()`**

Ajouter les paramètres forwarding dans la signature de `run_shot()` et les passer à `build_p2_prompt()` :
```python
def run_shot(
    ...,
    p2_character_name: str = "Nara Voss",
    p2_character_canonical: str = LOCKED_NARA_CANONICAL,
) -> ShotResult:
    ...
    p2_prompt = build_p2_prompt(
        scene_env=p2_scene_env,
        subject_action=p2_subject_action,
        character_name=p2_character_name,
        character_canonical=p2_character_canonical,
    )
```

### Validation post-correction
```powershell
venv\Scripts\Activate.ps1
# Dry-run Nara — doit afficher "Nara Voss" dans le prompt P2
python production\gen_shots.py --shot SCN_001_SHOT_003 --dry-run
# Dry-run Vale — doit afficher le canonical Vale, PAS Nara
python production\gen_shots.py --shot SCN_003_SHOT_001 --dry-run
# Tests de non-régression
pytest aiprod_adaptation/tests/ -q
```

> **Règle ArcFace** : Avant tout shot réel Nara post-correction, relancer le benchmark sur `nara_hero_ref_01.png`. Le score doit rester ≥ 0.9378. Si régression : revenir à `LOCKED_NARA_CANONICAL` direct.

---

## CORRECTION 4.2 — Utiliser `lighting_context` du shot, pas `lighting_brief` du lieu

### Problème
`gen_shots.py` ligne 96 passe `location["lighting_brief"][:200]` à P2.  
`storyboard.json` contient `lighting_context` par shot — description spécifique à l'instant dramatique (ex : `"wrist display as sole key source"`). C'est ce qui fait la différence entre un éclairage de lieu générique et un éclairage de shot Deakins.

### Fichier
- `production/gen_shots.py` (ligne 96)

### Changement requis

```python
# AVANT (ligne 96)
p2_scene_env=location["lighting_brief"][:200],

# APRÈS
p2_scene_env=(shot.get("lighting_context") or location["lighting_brief"])[:200],
```

Un fallback sur `lighting_brief` si `lighting_context` est absent ou vide garantit la rétrocompatibilité sur les shots sans overrides.

### Validation
```powershell
# Vérifier que SCN_001_SHOT_002 affiche "wrist display" et non le brief générique
python production\gen_shots.py --shot SCN_001_SHOT_002 --dry-run
```

---

## CORRECTION 2.3 — Inverser l'ordre lieu / personnage dans `build_p1_prompt()`

### Problème
T5-XXL encode les tokens dans l'ordre séquentiel et pèse le début du prompt plus lourd. Le `doc` actuel place `"subject"` (description personnage) avant `"technical_quality"`. Pour les plans medium et wide, le modèle doit percevoir le lieu en premier — sinon il génère un portrait avec bokeh au lieu d'un plan contextualisé.

### Fichier
- `pipeline/shot_pipeline.py` — `build_p1_prompt()`

### Changement requis

Réordonner les clés du dict `doc` pour que l'architecture spatiale précède le personnage :

```python
doc = {
    "production_note": ...,        # 1. Intention globale (inchangé)
    "location": ...,               # 2. Lieu — architecture, matériaux (inchangé)
    "lighting_design": ...,        # 3. Lumière (inchangé)
    "colour_grade_intent": ...,    # 4. Grade (inchangé)
    "composition": ...,            # 5. Composition (inchangé)
    "technical_quality": ...,      # 6. ← MONTER ici (était en dernier)
    "subject": {                   # 7. ← DESCENDRE ici (était avant technical_quality)
        "action": p.subject_action,
        "costume": p.character_canonical,
    },
}
```

> Note : `json.dumps(doc)` en Python 3.7+ préserve l'ordre d'insertion. L'ordre des clés dans le JSON envoyé à FLUX sera exactement cet ordre.

### Validation
```powershell
# Inspecter le JSON généré pour un shot medium — "subject" doit apparaître après "technical_quality"
python -c "
import sys, json
sys.path.insert(0, '.')
from pipeline.shot_pipeline import build_p1_prompt, SceneP1Params
p = SceneP1Params('SCN_002','Episode 01','INT. LOWER TRANSIT STACK','desc','lighting','colour','composition','action')
print(json.dumps(json.loads(build_p1_prompt(p)), indent=2))
"
```

---

## CORRECTION 1.2 — Shots environnement : utiliser `refs_angles_prompts` au lieu de copier le master

### Problème
`gen_shots.py` lignes 113-120 : les shots sans `primary_character` font un `shutil.copy2` du master plate `{location_key}_master.png`. Résultat : `SCN_001_SHOT_001` (ultra-wide, searchbeam) et `SCN_001_SHOT_002` (Dutch tilt 3°, medium) sont **identiques**.  

`locations.json` contient déjà `refs_angles_prompts` — prose DOP-grade pour `wide`, `medium`, `detail` — jamais utilisée.

### Fichier
- `production/gen_shots.py`

### Changement requis

Remplacer la logique `shutil.copy2` par un appel P1-only (FLUX.2 Pro, $0.03) avec le prompt construit depuis `refs_angles_prompts` :

```python
else:
    # Shot environnement : générer depuis refs_angles_prompts (P1 only, $0.03)
    shot_type_key = _map_shot_type_to_angle_key(shot["shot_type"])
    angle_prompt = location.get("refs_angles_prompts", {}).get(shot_type_key, "")
    if not angle_prompt:
        # Fallback sur master plate si aucun prompt d'angle disponible
        shutil.copy2(str(location_ref), str(out_path))
        ...
    else:
        params = build_scene_params(shot, scene_cfg, location, grade)
        # P1 only — pas de P2 (pas de personnage)
        p1_url = _call_p1(params, seed_override=scene_cfg["seed"])
        ...
```

Fonction helper à ajouter dans `gen_shots.py` :
```python
def _map_shot_type_to_angle_key(shot_type: str) -> str:
    """Mappe un shot_type storyboard vers une clé refs_angles_prompts."""
    if "wide" in shot_type.lower() or "establishing" in shot_type.lower():
        return "wide"
    if "detail" in shot_type.lower() or "insert" in shot_type.lower() or "extreme_close" in shot_type.lower():
        return "detail"
    return "medium"
```

### Coût supplémentaire
Les shots env EP01 actuel : à compter depuis `storyboard.json`. Chaque appel P1 = $0.03.  
**Attendre GO explicite avant toute exécution payante.**

### Validation
```powershell
# Dry-run — lister les shots env et vérifier qu'aucun shutil.copy2 n'est annoncé
python production\gen_shots.py --dry-run
```

---

## CORRECTION 2.4 — `_PORTRAIT_FOOTER` générique : injecter `portrait_brief` par personnage

### Problème
`aiprod_adaptation/image_gen/storyboard.py` applique `_PORTRAIT_FOOTER` identique à tous les personnages : `Kodak Portra 400, f/2.0, shallow DOF, soft natural bokeh`. Vale doit être 6500K fluorescent, ratio 9:1, Fincher/Social Network. Rook doit être overhead platinum, Kubrick.  

`characters.json` contient `portrait_brief` complet par personnage (camera, framing, lighting, background, dop_ref) — il n'est pas lu.

### Fichier
- `aiprod_adaptation/image_gen/storyboard.py`

### Changement requis

Dans `StoryboardGenerator`, remplacer `_PORTRAIT_FOOTER` statique par une résolution dynamique depuis `characters.json` :

```python
def _get_portrait_footer(self, character_id: str) -> str:
    """Retourne le footer DOP du personnage depuis characters.json."""
    char = self._characters.get(character_id)
    if not char or "portrait_brief" not in char:
        return _PORTRAIT_FOOTER   # fallback générique
    pb = char["portrait_brief"]
    return (
        f"Camera: {pb.get('camera', '')}. "
        f"Framing: {pb.get('framing', '')}. "
        f"Lighting: {pb.get('lighting', '')}. "
        f"Background: {pb.get('background', '')}. "
        f"DOP ref: {pb.get('dop_ref', '')}."
    )
```

Charger `characters.json` à l'init du générateur et utiliser `_get_portrait_footer(char_id)` aux points d'utilisation de `_PORTRAIT_FOOTER`.

> Note : `StoryboardGenerator` n'est pas sur le chemin EP01 direct (`production/gen_shots.py` → `pipeline/shot_pipeline.py`). Cette correction cible le moteur générique AIPROD. Priorité secondaire par rapport aux corrections 1.1, 4.2, 2.3.

### Validation
```powershell
pytest aiprod_adaptation/tests/ -q -k "portrait"
```

---

## Ordre d'exécution — état final

```
✅ 1. CORRECTION 4.2  — appliqué le 2026-05-02 à 15:24
✅ 2. CORRECTION 2.3  — appliqué le 2026-05-02 à 15:24
✅ 3. CORRECTION 1.1  — appliqué le 2026-05-02 à 15:24
✅ 4. CORRECTION 2.4  — appliqué le 2026-05-02 à 15:24
⏳ 5. CORRECTION 1.2  — en attente GO explicite (API payante)
```

**Résultats CI post-corrections :**
- pytest : 1072 passed, 4 deselected ✅
- mypy storyboard.py : 0 erreur ✅
- ruff : 0 nouvelle erreur introduite ✅

### Checkpoint CI après chaque correction
```powershell
venv\Scripts\Activate.ps1
ruff check pipeline/ production/ aiprod_adaptation/
mypy pipeline/ production/ aiprod_adaptation/core/ aiprod_adaptation/models/ --strict
pytest aiprod_adaptation/tests/ -q
# Attendu : 1072 passed, 4 deselected
```

---

## Règles absolues

- `LOCKED_NARA_CANONICAL` reste dans `shot_pipeline.py` en tant que constante de référence et valeur par défaut — ne jamais supprimer.
- Le score ArcFace Nara doit rester ≥ **0.9378** après correction 1.1. Tout appel réel sur Nara post-correction nécessite benchmark.
- Aucun appel API sans GO explicite (correction 1.2 surtout).
- Pas de `# type: ignore`. Toute adaptation de type doit être explicite.
- T5-XXL : ne pas mentionner un concept interdit même en négatif — reformuler.
