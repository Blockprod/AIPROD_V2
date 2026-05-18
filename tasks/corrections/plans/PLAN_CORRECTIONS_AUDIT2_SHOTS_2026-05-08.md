---
title: Plan de corrections — Audit 2 Phase C (35 shots EP01)
creation: 2026-05-08 à 16:26
statut: en_cours
auteur: audit_agent
---

# Plan de corrections — Audit 2 Phase C
## District Zero EP01 — 35 shots

> Objectif : 0 défaut bloquant, 0 expression incorrecte, 100 % du corpus Phase B exploité avant tout lancement Phase C.

---

## Ordre d'exécution

```
B1 + B2 + T1  →  pipeline/shot_pipeline_v4.py  (3 corrections code)
B3 + T2 + N1  →  production/storyboard.json    (10 corrections données)
dry-run       →  validation 35 prompts
IMG           →  gen_location_refs.py --execute ($0.30)
Phase C       →  GO
```

---

## B1 — 🔴 BLOQUANT — Word-boundary + filtre négation pour `anger`

**Fichier :** `pipeline/shot_pipeline_v4.py`
**Fonction :** `_resolve_char_ref()` → table `_EMOTION_TO_EXPR`
**Shots impactés :** SCN_003_SHOT_002, SCN_009_SHOT_002

### Problème
La correspondance `"anger"` est une simple sous-chaîne. Elle matche :
- `"danger"` → SCN_003_S2 : *"the immediate **danger** is gone"* → reçoit `expr_10_anger_suppressed` ❌
- `"Not anger"` → SCN_009_S2 : *"**Not anger** — not yet"* → reçoit `expr_10_anger_suppressed` ❌

SCN_009_S2 est le shot pivot de l'épisode (Nara : *"They lied."*). Recevoir une expression de colère au lieu d'un choc diagnostique froid est une erreur narrative majeure.

### Correction requise
1. Remplacer le test `keyword in emotion_full` par un test word-boundary (regex `r'\b{keyword}\b'`)
2. Ajouter un filtre de négation : si `"not anger"` ou `"not yet"` précède le keyword dans la fenêtre de 3 mots, ignorer le match
3. Vérifier que SCN_003_S2 (`"danger"`) ne matche plus `anger`
4. Vérifier que SCN_009_S2 (`"Not anger — not yet"`) ne matche plus `anger`

### Expressions cibles après correction
| Shot | Expression correcte | Keyword déclencheur |
|---|---|---|
| SCN_003_SHOT_002 | `expr_09_exhaustion_deep` | `"exhaustion"` dans `emotion_intent` (à ajouter via B3) |
| SCN_009_SHOT_002 | `expr_08_surprise_flash` | `"disbelief"` dans `emotion_intent` (à ajouter via B3) |

### Statut
- [ ] Code modifié
- [ ] Test dry-run SCN_003_S2 : confirme `expr_09_exhaustion_deep`
- [ ] Test dry-run SCN_009_S2 : confirme `expr_08_surprise_flash`

---

## B2 — 🔴 BLOQUANT — Matching expression absent pour shots `medium`

**Fichier :** `pipeline/shot_pipeline_v4.py`
**Fonction :** `_resolve_char_ref()` — Level 2 / Level 3
**Shots impactés :** 12 shots medium avec personnage

### Problème
Le Level 2 (matching expression) n'est exécuté que pour `shot_type in ("close", "ecu", "close_handheld", "cu_handheld", "insert")`. Les shots `medium` et `medium_wide` tombent directement sur Level 3 (angle neutre), **court-circuitant tout le corpus d'expressions Phase B** pour les plans moyens.

### Shots affectés — expression correcte après fix

| Shot | Personnage | emotion_intent (fragment) | Expression cible |
|---|---|---|---|
| SCN_002_SHOT_003 | nara | "determination" (à ajouter B3) | `expr_06_determination_jaw` |
| SCN_003_SHOT_003 | nara | "realisation" | `expr_08_surprise_flash` |
| SCN_004_SHOT_001 | elian (après N1) | "distrust / recognises danger" (B3) | `expr_12_distrust_guarded` |
| SCN_005_SHOT_002 | vale | "predator ... cold" | `expr_05_contempt_cold` |
| SCN_006_SHOT_001 | mira | "calculates" | `expr_11_calculation_cold` |
| SCN_009_SHOT_003 | nara | "cold calculation" (à ajouter B3) | `expr_11_calculation_cold` |
| SCN_009_SHOT_004 | mira | "urgency" | `expr_06_determination_jaw` |
| SCN_010_SHOT_003 | mira | "escape" (via action_brief) | `expr_06_determination_jaw` |
| SCN_010_SHOT_004 | nara | "escape" (via action_brief) | `expr_06_determination_jaw` |
| SCN_011_SHOT_001 | nara | "exhaustion" (à ajouter B3) | `expr_09_exhaustion_deep` |
| SCN_011_SHOT_004 | elian | "grief" (à ajouter B3) | `expr_07_grief_suppressed` |
| SCN_011_SHOT_005 | nara | "grief" (à ajouter B3) | `expr_07_grief_suppressed` |

### Correction requise
Dans `_resolve_char_ref()` Level 3 (plans moyens/OTS), **avant** de sélectionner l'angle neutre :
- Appliquer le loop `_EMOTION_TO_EXPR` sur `emotion_full`
- Si match → retourner l'expression (depuis `character_faces/{slug}/`)
- Si pas de match → continuer vers l'angle de visage par défaut (`_SHOT_TYPE_TO_FACE_ANGLE`)

Autrement dit : Level 3 devient Level 3a (expression match) + Level 3b (angle fallback).

### Statut
- [ ] Code modifié
- [ ] Dry-run : SCN_005_S2 (vale) confirme `expr_05_contempt_cold`
- [ ] Dry-run : SCN_006_S1 (mira) confirme `expr_11_calculation_cold`

---

## T1 — 🟡 MODÉRÉ — Action override exertion (valve)

**Fichier :** `pipeline/shot_pipeline_v4.py`
**Fonction :** `_resolve_char_ref()` — Level 1, action overrides
**Shot impacté :** SCN_003_SHOT_001

### Problème
Shot `medium_wide` → `_SHOT_TYPE_TO_POSE["medium_wide"] = "turn_00_front.png"` (turnaround neutre).
Or le storyboard est explicite : *"Both hands on a valve wheel, turning hard against pressure. Feet braced, body weight forward."*
La ref corps doit être `pose_01_alert_forward_lean` (corps tendu, projeté en avant) et non un turnaround debout neutre.

### Correction requise
Dans les action overrides du Level 1, ajouter :
```
"turning hard" / "braced" / "weight forward" / "body weight" / "pushing" → pose_01_alert_forward_lean.png
```

### Statut
- [ ] Code modifié
- [ ] Dry-run : SCN_003_S1 (nara) confirme `pose_01_alert_forward_lean`

---

## B3 — 🟠 MAJEUR — 9 ajouts de keyword dans `emotion_intent` (storyboard)

**Fichier :** `production/storyboard.json`
**Impact :** 9 shots reçoivent `angle_00_front_neutral` faute de keyword déclencheur

### Corrections (un mot ajouté par shot, en fin de champ)

| Shot | emotion_intent actuel (extrait) | Ajout | Expression résultante |
|---|---|---|---|
| SCN_002_SHOT_003 | *"The choice. She could turn back. She doesn't."* | `"determination"` | `expr_06_determination_jaw` |
| SCN_003_SHOT_002 | *"From crisis to clarity. The immediate danger is gone."* | `"exhaustion"` | `expr_09_exhaustion_deep` |
| SCN_004_SHOT_002 | *"Suppressed knowledge breaking to the surface. He has been carrying this for years."* | `"grief"` | `expr_07_grief_suppressed` |
| SCN_008_SHOT_003 | *"Tactical awareness. She is providing overwatch while Mira works. Professional."* | `"alert"` | `expr_01_alert_watchful` |
| SCN_008_SHOT_004 | *"She expected a maintenance access. What she's found is something that shouldn't exist."* | `"disbelief"` | `expr_08_surprise_flash` |
| SCN_009_SHOT_002 | *"Not anger — not yet."* | `"disbelief"` | `expr_08_surprise_flash` |
| SCN_009_SHOT_003 | *"The second blow. The first was discovering the lie. The second is understanding the crime."* | `"cold calculation"` | `expr_11_calculation_cold` |
| SCN_011_SHOT_001 | *"She is carrying something enormous and trying not to show it."* | `"exhaustion"` | `expr_09_exhaustion_deep` |
| SCN_011_SHOT_002 | *"Recognition. He always knew this day was coming."* | `"grief"` | `expr_07_grief_suppressed` |
| SCN_011_SHOT_004 | *"Atonement, not absolution. He knows it's too late for forgiveness."* | `"grief"` | `expr_07_grief_suppressed` |
| SCN_011_SHOT_005 | *"She wanted him to come with her. The handoff of a mission..."* | `"grief"` | `expr_07_grief_suppressed` |

> Note : SCN_003_S2 reçoit `"exhaustion"` (relâchement post-effort musculaire intense — c'est le beat physique réel). L'expression `anger_suppressed` était fausse.
> Note : SCN_009_S2 reçoit `"disbelief"` (diagnostic froid, pas réaction émotionnelle). Cohérent avec le texte *"like a diagnosis"*.

### Statut
- [ ] 11 champs `emotion_intent` modifiés dans storyboard.json
- [ ] Dry-run global : 0 shot restant sur `angle_00_front_neutral` avec personnage + émotion non-neutre

---

## T2 — 🟡 MODÉRÉ — Action override breach/detonates (fin épisode)

**Fichier :** `pipeline/shot_pipeline_v4.py` ou `production/storyboard.json`
**Shot impacté :** SCN_011_SHOT_007

### Problème
Shot `wide` final → `_SHOT_TYPE_TO_POSE["wide"] = "turn_00_front.png"`.
Le storyboard : *"The door detonates. A white light overexposes the entire frame."* Les deux personnages font face à la porte, tension maximale. `turn_00_front` est une pose d'inventaire — pas de menace imminente.

### Options
- **Option A (pipeline)** : Ajouter `"door"` / `"detonates"` / `"breach"` comme action override → `pose_01_alert_forward_lean`
- **Option B (storyboard)** : Ajouter `"braced"` dans `action_brief` de SCN_011_S7

**Recommandation :** Option A (pipeline, plus robuste pour cas similaires futurs)

### Statut
- [ ] Action override ajouté dans Level 1 de `_resolve_char_ref()`
- [ ] Dry-run : SCN_011_S7 confirme `pose_01_alert_forward_lean`

---

## N1 — 🟡 MODÉRÉ — `primary_character` SCN_004_SHOT_001

**Fichier :** `production/storyboard.json`
**Shot impacté :** SCN_004_SHOT_001

### Problème
SCN_004_S1 est un 2-shot Nara/Elian à la table. `primary_character = "nara"`.
Or le beat dramatique est : **Elian voit la carte et freeze**. C'est son visage qui porte la scène (*"His jaw tightens. He recognises what he's seeing."*). La ref image ref devrait être Elian, pas Nara.

### Correction
`primary_character` : `"nara"` → `"elian"`

Après B2 fix, l'expression de Elian sera matchée sur `emotion_intent` : *"He recognises what he's seeing. He has seen this before, under different circumstances."* → keyword `"distrust"` (via B3 si nécessaire) → `expr_12_distrust_guarded`.

### Note sur B3 pour SCN_004_S1
Le champ `emotion_intent` ne contient pas de keyword direct. Après N1, ajouter `"distrust"` dans `emotion_intent` :
> *"He recognises what he's seeing. He has seen this before, under different circumstances. Distrust."*

### Statut
- [ ] `primary_character` modifié : `"nara"` → `"elian"`
- [ ] `emotion_intent` SCN_004_S1 : ajout `"distrust"` (inclus dans B3)
- [ ] Dry-run : SCN_004_S1 (elian) confirme `expr_12_distrust_guarded`

---

## IMG — 🔴 BLOQUANT — Génération 10 master plates location refs

**Script :** `production/gen_location_refs.py`
**Coût :** 10 × $0.03 = **$0.30** (FLUX.2 Pro)
**Shots bloqués :** SCN_001_S1, SCN_001_S2, SCN_005_S1, SCN_007_S1, SCN_010_S2, SCN_011_S6 + backup SCN_003_S1

### Lieux à générer

| location_key | seed | Scènes |
|---|---|---|
| `ext_outer_wall_night` | 11 | SCN_001 |
| `int_transit_corridor_night` | 22 | SCN_002 |
| `int_pressure_valve_chamber_night` | 33 | SCN_003 |
| `int_voss_apartment_night` | 44 | SCN_004 |
| `int_civic_atrium_morning` | 55 | SCN_005 |
| `int_black_market_sublevel_day` | 66 | SCN_006 |
| `int_security_ops_center_day` | 77 | SCN_007 |
| `int_service_spine_night` | 88 | SCN_008, SCN_010 |
| `int_observation_chamber` | 99 | SCN_009 |
| `int_voss_apartment_predawn` | 121 | SCN_011 |

### Commande
```powershell
venv\Scripts\Activate.ps1 ; python production/gen_location_refs.py --execute
```

### Post-génération : validation
```powershell
Get-ChildItem production/location_refs -Filter "*_master.png" | Measure-Object | Select-Object Count
# Attendu : Count = 10
```

### Statut
- [ ] GO utilisateur reçu
- [ ] Génération exécutée
- [ ] 10 fichiers `*_master.png` confirmés
- [ ] Dry-run global : env shots montrent bien la location ref dans la colonne `CHAR REF`

---

## Dry-run de validation final

Après toutes les corrections (B1 + B2 + B3 + T1 + T2 + N1 + IMG) :

```powershell
venv\Scripts\Activate.ps1 ; python _tools/dry_run_prompts.py 2>&1 | Select-String "CHAR REF|angle_00_front_neutral"
```

**Critères de succès :**
- Aucun shot avec `primary_character` non-null sur `angle_00_front_neutral` (sauf shots réellement neutres)
- Les 7 env shots montrent `[location_ref]` ou `[master plate]` dans leur ligne CHAR REF
- SCN_003_S2 → `expr_09_exhaustion_deep`
- SCN_005_S2 → `expr_05_contempt_cold` (vale)
- SCN_006_S1 → `expr_11_calculation_cold` (mira)
- SCN_009_S2 → `expr_08_surprise_flash`
- SCN_011_S1 → `expr_09_exhaustion_deep`

---

## Tableau de bord

| ID | Sévérité | Statut | Fichier |
|---|---|---|---|
| B1 | 🔴 BLOQUANT | ⬜ à faire | `pipeline/shot_pipeline_v4.py` |
| B2 | 🔴 BLOQUANT | ⬜ à faire | `pipeline/shot_pipeline_v4.py` |
| B3 | 🟠 MAJEUR | ⬜ à faire | `production/storyboard.json` |
| T1 | 🟡 MODÉRÉ | ⬜ à faire | `pipeline/shot_pipeline_v4.py` |
| T2 | 🟡 MODÉRÉ | ⬜ à faire | `pipeline/shot_pipeline_v4.py` |
| N1 | 🟡 MODÉRÉ | ⬜ à faire | `production/storyboard.json` |
| IMG | 🔴 BLOQUANT | ⬜ à faire | `gen_location_refs.py --execute` |

**Shots correctement configurés avant corrections :** ~20/35 (57 %)
**Shots correctement configurés après corrections :** 35/35 (100 %)
