---
title: Plan de corrections — Audit shots EP01
creation: 2026-05-08 à 15:13
status: en_cours
priorite_max: bloquant
---

# Plan de corrections — Audit shots EP01
## District Zero — Phase C pré-génération

---

## Vue d'ensemble

5 défauts identifiés lors de l'audit de pré-génération des 35 shots EP01.
2 défauts critiques (bloquants — aucun shot ne peut être lancé avant correction).
2 défauts majeurs (narratifs — doivent être résolus avant validation finale).
1 défaut modéré (amélioration optionnelle mais recommandée).

```
BLOCAGE PHASE C : OUI
Corrections bloquantes restantes : 2
Corrections narratives restantes : 2
Améliorations optionnelles : 2
```

---

## PRIORITÉ 1 — BLOQUANT (avant tout lancement)

### CORRECTION C1 — Réécriture de `_build_stylization_prompt()`

**Fichier cible :** `pipeline/shot_pipeline_v4.py`
**Fonction :** `_build_stylization_prompt()`

**Problème :**
La fonction n'utilise que 5 des 10 champs disponibles dans le storyboard. Elle ignore les
signaux les plus forts pour un modèle de diffusion (référence DOP, composition, eyeline).
De plus l'ordre des tokens est contre-productif : les modèles de diffusion pondèrent lourdement
les premiers tokens — or le prompt commence par `action_brief` (narratif) alors qu'il devrait
commencer par les signaux techniques forts.

**Champs actuellement utilisés :**
- `action_brief` ✓
- `lighting_context` ✓
- `emotion_intent` ✓
- `material_state` ✓
- `camera_spec` ✓

**Champs absents à injecter :**
- `reference_exact` → signal DOP maximal (Seedream comprend "Deakins", "Lubezki", "Blade Runner 2049")
- `composition` → mise en scène non transmise (ex : "Seawall lower third, skyline upper 65%")
- `eyeline` → direction de regard des personnages
- `camera_movement` → `follow_handheld_fast` vs `static` (encode la texture du plan)
- `off_frame_tension` → contexte de tension hors-cadre (optionnel, injecter si non-null)
- `state_override` → état physique des personnages (wet, soaked, tremor) — CRITIQUE SCN_011

**Ordre cible des tokens :**
```
1. reference_exact (traduit en vocabulaire photographique)
2. shot_type_label + camera_spec (signal technique)
3. composition (mise en scène)
4. eyeline (si non-null)
5. lighting_context
6. material_state
7. action_brief (narratif)
8. emotion_intent
9. state_override (si non-null)
10. off_frame_tension (si non-null)
```

**Fins de prompt à supprimer :**
- ❌ `"No AI artefacts. No distorted anatomy."` → formulations négatives inefficaces
- ❌ `"Photorealistic cinematic"` → formule générique dégradante déjà éliminée des scripts personnages

**Fins de prompt de remplacement (vocabulaire cinématographique) :**
- ✅ `"Anamorphic 2.39:1. Lens flare characteristics. Film grain visible at ISO push."`
- ✅ `"Shot on 35mm anamorphic. Optical aberrations retained. Deep focus."`
- ✅ `"Practical light sources dominant. Motivated shadows."`
(choisir selon `camera_spec` et `lighting_context`)

**Règle d'injection `scene_axis` :**
Lire `scenes_axis[scene_id]` dans le storyboard et injecter la direction comme contrainte
d'eyeline/mouvement quand non-null :
- SCN_010 : `"Sprint direction left-to-right. Nara escaping screen-left."`
- SCN_011 ↔ SCN_004 : `"Apartment axis identical to SCN_004. Camera north-west."`

**Validation :** Générer 1 shot test en dry-run, afficher le prompt complet, valider avant --execute.

---

### CORRECTION C2 — `_resolve_char_ref()` : pointer vers Phase B

**Fichier cible :** `pipeline/shot_pipeline_v4.py`
**Fonction :** `_resolve_char_ref()`

**Problème :**
Le pipeline pointe vers `production/character_refs/{slug}_ref.png` — les 5 images Phase A
(générées avant le corpus complet). Les 180 images du corpus Phase B (`character_faces/`,
`character_bodies/`) ne sont jamais utilisées.

**Correction principale :**
Pointer vers `production/character_faces/{slug}/angle_00_front_neutral.png` par défaut
(image canonique validée, seed verrouillé, œil corrects pour Mira et Rook).

**Amélioration (sélection par angle de shot) :**
Implémenter une logique de sélection d'angle basée sur `shot_type` :
```
shot_type contient "profile" ou "ots_*"      → angle_02_profile_left.png ou angle_03_profile_right.png
shot_type contient "ots_over_*"              → angle_04_three_quarter_left.png
shot_type = "cu_*" ou "ecu_*"               → angle_00_front_neutral.png
shot_type = "wide" ou "establishing"        → angle_00_front_neutral.png (ou body turnaround)
défaut                                       → angle_00_front_neutral.png
```

**Fallback :** Si l'image de Phase B n'existe pas → fallback vers `character_refs/{slug}_ref.png`
avec warning log.

**Validation :** Vérifier que les 5 slugs (nara, mira, elian, vale, rook) ont bien leur
`angle_00_front_neutral.png` dans `character_faces/`.

---

## PRIORITÉ 2 — NARRATIF (avant validation finale)

### CORRECTION N1 — Causalité Mira inversée (SCN_011_SHOT_005 ↔ SCN_006)

**Fichier cible :** `production/storyboard.json`
**Shot cible :** `SCN_011_SHOT_005`

**Problème :**
Dans SCN_011_SHOT_005 (épilogue), Elian dit à Nara :
> *"Go to the freight tunnels. Find the relay called Lantern. Ask for Mira Sol."*

Or dans SCN_006 (marché noir, chronologiquement AVANT SCN_011), Nara est déjà avec Mira Sol.
Le spectateur comprend que SCN_011_SHOT_005 est une instruction de première rencontre → causalité
inversée.

**Solution retenue (à choisir) :**

**Option A — Reformulation pour EP02 (minimale) :**
Modifier `action_brief` et/ou `audio_brief` de SCN_011_SHOT_005 pour qu'Elian fasse référence
à ce qui vient APRÈS, pas à la rencontre initiale :
> *"When this breaks open — and it will — go back to Mira. The Lantern relay. She'll know what to do with what you found."*

**Option B — Shot intermédiaire SCN_004.5 (structurelle) :**
Ajouter un shot entre SCN_004 et SCN_006 montrant Nara trouver Mira par elle-même
(à partir d'un indice d'Elian dans SCN_004, sans que le spectateur ait entendu le nom).
→ Plus lourd, réservé si réécriture narrative globale prévue.

**Recommandation :** Option A. Modifier uniquement les champs `action_brief` et `audio_brief`
de SCN_011_SHOT_005. Ne pas ajouter de shots (scope minimal).

---

### CORRECTION N2 — État physique Nara inexpliqué (SCN_010 → SCN_011)

**Fichier cible :** `production/storyboard.json`
**Shots cibles :** `SCN_010_SHOT_004` et `SCN_011_SHOT_001`

**Problème :**
- SCN_010_SHOT_004 : Nara passe sous une porte blindée qui se ferme. Tunnel souterrain sec,
  dust et béton. Aucune pluie.
- SCN_011_SHOT_001 `state_override` : *"Dark hair wet and plastered to neck and temples.
  Jacket soaked through at shoulders and back. Water drops catching blue light."*

Ellipse non expliquée — le spectateur ne sait pas d'où vient l'eau.

**Solution retenue (à choisir) :**

**Option A — Modifier SCN_010_SHOT_004 (pont narratif) :**
Ajouter à `state_override` ou `action_brief` de SCN_010_SHOT_004 une mention de sortie sous la
pluie : *"Nara slides under the descending blast door, emerges into a rain-soaked access shaft."*
Et modifier `location_key` si nécessaire pour indiquer que la sortie de tunnel est exposée à
l'extérieur.

**Option B — Modifier SCN_011_SHOT_001 (logique d'exertion) :**
Remplacer `state_override` dans SCN_011_SHOT_001 :
- ❌ `"Dark hair wet and plastered to neck and temples. Jacket soaked through at shoulders and back."`
- ✅ `"Hair dark with sweat, strands plastered to temples. Jacket collar damp, shoulders dusty from tunnel concrete. Breathing still rapid."`

Supprime la contrainte de pluie non justifiée tout en maintenant l'intensité physique.

**Recommandation :** Option B si on ne veut pas ajouter de shot. Option A si la pluie a une
valeur symbolique (purification, début du monde extérieur). Décision éditoriale.

---

## PRIORITÉ 3 — OPTIONNEL (amélioration)

### AMÉLIORATION A1 — Ellipse Vale SCN_005 → SCN_007

**Fichier cible :** `production/storyboard.json`
**Problème :**
- SCN_005_SHOT_002 : Vale → "Put her under passive watch"
- SCN_007_SHOT_002 : Vale → "Don't stop her" (instrumentalisation active)

Aucun shot intermédiaire ne montre Vale recevoir l'information qui provoque ce basculement.
La psychologie de Vale reste opaque entre ces deux décisions.

**Options :**

**Option A — Shot intermédiaire ops center (Vale seul) :**
Ajouter SCN_006.5 : Vale dans l'ops center, receive d'un rapport sur ce que Nara vient de
faire dans le marché (avec Mira). Réaction froide, calcul visible. → il *choisit* de la laisser aller.
Enrichit Vale comme antagoniste actif (pas réactif).

**Option B — Modification du `audio_brief` SCN_007_SHOT_002 :**
Ajouter une ligne implicite qui suggère que Vale a déjà tout prévu :
> *"Don't stop her. We let the infection spread — then we contain it all at once."*
La décision paraît alors délibérément planifiée depuis le début, pas un revirement.

**Recommandation :** Option B (zéro shot supplémentaire). Option A si EP02 développe Vale.

---

### AMÉLIORATION A2 — Cohérence palette chromatique arc narratif

**Fichier cible :** `pipeline/shot_pipeline_v4.py` + `production/storyboard.json`
**Problème :**
L'arc émotionnel Dread → Discovery → Confrontation → Revelation → Pursuit → Collapse est
tracé dans les `lighting_context` individuels mais aucun système n'encode les contraintes
de palette au niveau de l'arc global (ex : SCN_001-003 cold dead blue, SCN_006 amber tungsten,
SCN_009-010 cyan screens, SCN_011 retour cold predawn blue).

**Correction :** Ajouter un champ `arc_palette` par scène dans `scenes_axis` ou créer une
lookup table dans `_build_stylization_prompt()` qui mappe `scene_id` → palette constraint suffix.
Cette contrainte de palette viendrait s'ajouter à la fin du prompt après `lighting_context`.

---

## RÉSUMÉ EXÉCUTIF

| # | Type | Fichier | Statut |
|---|---|---|---|
| C1 | Critique | `pipeline/shot_pipeline_v4.py` → `_build_stylization_prompt()` | ⬜ À faire |
| C2 | Critique | `pipeline/shot_pipeline_v4.py` → `_resolve_char_ref()` | ⬜ À faire |
| N1 | Majeur | `production/storyboard.json` → SCN_011_SHOT_005 | ⬜ En attente décision |
| N2 | Majeur | `production/storyboard.json` → SCN_010_SHOT_004 ou SCN_011_SHOT_001 | ⬜ En attente décision |
| A1 | Optionnel | `production/storyboard.json` → Vale SCN_005/007 | ⬜ Optionnel |
| A2 | Optionnel | `pipeline/shot_pipeline_v4.py` + storyboard | ⬜ Optionnel |

**Ordre d'exécution recommandé :**
1. C2 (rapide — changement de path uniquement)
2. C1 (réécriture fonction — 1-2h)
3. N1 + N2 (décision éditoriale requise)
4. A1 + A2 (si scope étendu validé)

**Condition de déblocage Phase C :** C1 + C2 complétés et validés par dry-run.
