---
title: Plan — DOP-grade pipeline : 4 lacunes identifiées
creation: 2026-05-02 à 16:29
status: actions #1 #2 #3 terminées — #4 en attente de shots validés
référence: analyse comparative methodologie.md vs état pipeline v2
---

## Contexte

Après injection des 3 champs DOP-grade (`reference_exact`, `off_frame_tension`, `material_state`)
dans les 35 shots du storyboard, une analyse du prompt réel généré (SCN_002_SHOT_001) a révélé
4 lacunes résiduelles. Ce plan les traite dans l'ordre impact/effort.

---

## Action #1 — Troncature 200 chars P2 *(5 min)*

**Statut** : ✅ terminé — 2026-05-02  
**Fichier** : `production/gen_shots.py`

### Problème
```python
p2_scene_env=(shot.get("lighting_context") or location["lighting_brief"])[:200]
```
Le cap à 200 caractères tronque les descriptions complexes au milieu d'une phrase.
Exemple : SCN_003 (strobe 0.5Hz + dual source + ratio 12:1) perd ~180 chars de contexte.
Le modèle P2 invente le reste — erreur photométrique silencieuse.

### Fix
Supprimer la limite ou la porter à 400 caractères minimum.

```python
# AVANT
p2_scene_env=(shot.get("lighting_context") or location["lighting_brief"])[:200]

# APRÈS — 400 chars, ou supprimer la limite si le contexte P2 le supporte
p2_scene_env=(shot.get("lighting_context") or location["lighting_brief"])[:400]
```

### Test de non-régression
- `pytest pipeline/test_shot_pipeline.py production/tests/test_gen_shots.py -q`
- Vérifier en dry-run que SCN_003 affiche bien les 3 sources de lumière complètes.

---

## Action #2 — Eyeline par shot *(1h)*

**Statut** : ✅ terminé — 2026-05-02  
**Fichiers** : `production/storyboard.json`, `pipeline/shot_pipeline.py`, `production/gen_shots.py`, `_tools/inject_dop_fields.py`

### Problème
Aucun shot ne précise où le personnage regarde. Le modèle dérive librement sur la direction
du regard — ce qui crée des erreurs d'axe 180° visibles au montage (deux personnages qui se
regardent à droite dans un champ/contre-champ).

### Champ à ajouter dans le shot JSON
```json
"eyeline": "screen-left, slightly below horizontal — not at camera"
```

Valeurs types :
- `"direct address — straight into lens"` — regard caméra
- `"screen-left, slightly below horizontal"` — contrechamp gauche
- `"screen-right, eye level"` — contrechamp droit
- `"downward — toward wrist display"` — regard vers objet en main
- `"off-screen right — listening, not initiating"` — présence hors-champ
- `"N/A — environment shot, no character"` — plans décor

### Intégration dans le prompt P1
Dans `build_p1_prompt` :
```python
if p.eyeline:
    doc["subject"]["eyeline"] = p.eyeline
```

### Intégration dans `SceneP1Params`
```python
eyeline: str = ""  # direction du regard du personnage principal
```

### Intégration dans `build_scene_params`
```python
eyeline=shot.get("eyeline", ""),
```

### Population du storyboard
Ajouter les 35 valeurs d'eyeline dans `_tools/inject_dop_fields.py`
(nouvelle fonction `inject_eyelines`) et exécuter.

Valeurs recommandées par shot (à injecter) :

| shot_id | eyeline |
|---------|---------|
| SCN_001_SHOT_001 | N/A — environment shot, no character |
| SCN_001_SHOT_002 | N/A — environment shot, no character |
| SCN_002_SHOT_001 | screen-right toward vanishing point — focused, not looking at camera |
| SCN_002_SHOT_002 | downward — toward wrist display, brow slightly furrowed |
| SCN_002_SHOT_003 | screen-right into unmapped corridor — looking into darkness, not at camera |
| SCN_003_SHOT_001 | downward toward valve wheel — effort, not looking up |
| SCN_003_SHOT_002 | upward, straight ahead — just released valve, head lifting |
| SCN_003_SHOT_003 | downward toward wrist display — processing, not engaging worker |
| SCN_004_SHOT_001 | screen-left toward Elian, slightly downward toward the map on the table |
| SCN_004_SHOT_002 | screen-left toward wall — not at Nara, not at camera |
| SCN_005_SHOT_001 | N/A — environment shot, no character |
| SCN_005_SHOT_002 | downward toward atrium floor — not at aide, not at camera |
| SCN_006_SHOT_001 | downward toward display surface — tracing the route |
| SCN_006_SHOT_002 | screen-right toward Mira — level, holding eye contact, not blinking |
| SCN_007_SHOT_001 | N/A — environment shot, no character |
| SCN_007_SHOT_002 | screen-left toward display wall — slightly off-axis from camera |
| SCN_008_SHOT_001 | screen-right toward tunnel depth — leading, not looking back |
| SCN_008_SHOT_002 | downward toward control panel — reading gauges, intent |
| SCN_008_SHOT_003 | screen-left toward dark passage — overwatch, unblinking |
| SCN_008_SHOT_004 | downward toward panel, then lifting to middle distance as gate unlocks |
| SCN_009_SHOT_001 | screen-right toward opening shutters — both characters silhouetted |
| SCN_009_SHOT_002 | screen-right toward exterior light — wide eyes, not blinking |
| SCN_009_SHOT_003 | downward toward pump machinery — following the pipes |
| SCN_009_SHOT_004 | screen-right — last look toward exterior, being pulled left |
| SCN_010_SHOT_001 | straight ahead toward camera — sprint, forward urgency |
| SCN_010_SHOT_002 | N/A — environment shot, no character |
| SCN_010_SHOT_003 | screen-left — one look back before entering duct |
| SCN_010_SHOT_004 | straight ahead — diving through closing door, no time to look anywhere |
| SCN_011_SHOT_001 | downward — head slightly bowed, carrying the weight of what she saw |
| SCN_011_SHOT_002 | screen-left toward Nara — reading her face, not speaking |
| SCN_011_SHOT_003 | screen-right toward Elian — holding eye contact, absorbing the confession |
| SCN_011_SHOT_004 | downward toward his own hands — shame, offering the drive without looking up |
| SCN_011_SHOT_005 | screen-right toward Elian — receiving the instructions, not yet responding |
| SCN_011_SHOT_006 | N/A — object shot, no character present |
| SCN_011_SHOT_007 | screen-left toward door — both characters, the last look before breach |

---

## Action #3 — Face IRE anchor *(30 min)*

**Statut** : ✅ terminé — 2026-05-02  
**Fichiers** : `production/grade.json`, `pipeline/shot_pipeline.py`

### Problème
Le prompt spécifie la palette globale en hex et les IRE globaux, mais ne contraint jamais
la valeur d'exposition du visage du personnage. Sans ça, le modèle invente son exposition
shot par shot — les ratios lumière/ombre dérivent entre les shots d'une même scène.

### Structure à ajouter dans `grade.json`
```json
"character_exposure": {
  "face_key_ire": 55,
  "face_shadow_ire": 8,
  "ratio_label": "7:1 — face key to shadow side",
  "note": "Applicable à tous les personnages. Dérogatoire uniquement sur shots de silhouette intentionnels."
}
```

### Intégration dans le prompt P1
Dans `build_p1_prompt`, ajouter dans `colour_grade_intent` :
```python
if char_exposure := grade.get("character_exposure"):
    doc["colour_grade_intent"] += (
        f" Face exposure: key side at {char_exposure['face_key_ire']}% IRE, "
        f"shadow side at {char_exposure['face_shadow_ire']}% IRE "
        f"({char_exposure['ratio_label']})."
    )
```

Ou ajouter un champ `face_exposure` dédié dans `SceneP1Params` :
```python
face_exposure: str = ""  # ex: "Key side 55% IRE, shadow 8% IRE, ratio 7:1"
```
→ injecté dans `build_p1_prompt` comme `doc["face_exposure_target"]`.

### Cas dérogatoires
Les shots de silhouette intentionnels (`SCN_009_SHOT_001`, `SCN_011_SHOT_001`,
`SCN_010_SHOT_002`) doivent surcharger la valeur via `state_override` ou un champ
`exposure_override` dans le shot JSON.

---

## Action #4 — Photometric anchor *(post-production, nécessite shots validés)*

**Statut** : ⏳ bloqué — nécessite shots générés (déclencher après première session EP01)  
**Fichiers** : `production/dashboard.json`, `pipeline/shot_pipeline.py`, `production/gen_shots.py`

### Problème
Chaque shot est généré indépendamment. La lumière entre SHOT_001 (wide) et SHOT_002
(close) de la même scène ne matche pas photométriquement — la direction, le ratio et
la température dérivent car le modèle ne voit pas le shot précédent.

### Approche
1. Après validation du premier shot d'une scène (le "photometric master"), enregistrer
   son path dans `dashboard.json` :
   ```json
   "SCN_002": {
     "seed": 22,
     "photometric_anchor": "production/shots/SCN_002/SCN_002_SHOT_001/result_2x.png"
   }
   ```
2. Dans `gen_shots.py`, si `photometric_anchor` existe pour la scène, l'injecter
   dans le prompt P1 des shots suivants via `extra_notes` :
   ```python
   "Match photometry of validated master shot: direction, ratio, and colour temperature
    must be consistent with SCN_002_SHOT_001."
   ```
3. Long terme : encoder les valeurs photométriques mesurées (IRE, CCT, direction vecteur)
   depuis l'image master via OpenCV, et les injecter comme contraintes numériques.

### Déclencheur
À implémenter après la première session de génération EP01 — quand les premiers shots
SCN_002 et SCN_003 sont validés à score ArcFace ≥ 0.85.

---

## Ordre d'exécution

```
Action #1  →  Action #3  →  Action #2  →  [générer EP01]  →  Action #4
   5 min        30 min         1h            ~$2.80             post-prod
```

## Tests à passer après chaque action

```powershell
pytest pipeline/test_shot_pipeline.py production/tests/test_gen_shots.py -q
ruff check pipeline/ production/
```
