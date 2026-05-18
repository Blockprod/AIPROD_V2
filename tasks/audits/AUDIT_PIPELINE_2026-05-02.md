---
type: audit
projet: AIPROD_V2 — District Zero EP01
creation: 2026-05-02 à 13:51
auditeur: DT senior / DA
statut: RÉFÉRENCE — lire avant toute session de génération
---

# AUDIT TECHNIQUE & ARTISTIQUE — AIPROD_V2
## District Zero EP01 — Diagnostic de production

> Mandat : identifier avec précision chirurgicale pourquoi les images générées
> manquent de cohérence narrative, de précision visuelle et de niveau studio.
> Basé sur lecture intégrale du repo au 2026-05-02.

---

## VERDICT GLOBAL

Le pipeline EP01 (`pipeline/shot_pipeline.py` + `production/gen_shots.py`) est
**Nara-only par construction**. Les masters lieux sont excellents architecturalement.
L'intention artistique écrite dans `storyboard.json` est de niveau professionnel.
Le problème est systémique : **l'intention ne survit pas à la chaîne de transformation**.
Quatre ruptures de transmission identifiées ci-dessous, par ordre de criticité décroissant.

---

## AXE 1 — PIPELINE

### PROBLÈME 1.1 — Le pipeline P2 est hardcodé pour Nara. Tous les autres personnages obtiennent son visage.

**Fichier** : `pipeline/shot_pipeline.py`, ligne 69

```python
LOCKED_NARA_CANONICAL = (
    "Female protagonist of a dystopian survival thriller. "
    "Late 20s, fine balanced features, elegant defined jawline..."
)
```

**Fichier** : `pipeline/shot_pipeline.py`, fonction `build_p1_prompt()`

```python
"subject": {
    "action": p.subject_action,
    "costume": LOCKED_NARA_CANONICAL,   # ← hardcodé, identique pour TOUS les personnages
},
```

**Impact** : Quand `gen_shots.py` génère un shot de Vale, Elian, Mira ou Rook en P1,
le `costume` injecté dans le prompt décrit Nara (femme, 20s, traits fins, tactical vest).
En P2 (face inpainting), la référence image du personnage correct est utilisée mais
le prompt P2 `build_p2_prompt()` mentionne explicitement "Nara Voss" et son LOCKED_CANONICAL.
**Le modèle est en contradiction directe entre sa ref image et son prompt textuel.**
Résultat : compromis instable → traits de Nara qui contaminent les autres personnages.

**Correction** : `SceneP1Params` doit accepter un `character_canonical: str` injecté depuis
`characters.json` par `gen_shots.py`. `build_p2_prompt()` doit recevoir le canonical
du personnage concerné, pas un literal Nara.

---

### PROBLÈME 1.2 — Les shots environnement sont une copie statique du master plate. Aucune variation compositionnelle.

**Fichier** : `production/gen_shots.py`, lignes 120-127

```python
# Shot environnement seulement — copie du master plate lieu (déjà généré en Phase B)
import shutil
location_ref = ROOT / f"production/location_refs/{shot['location_key']}_master.png"
...
shutil.copy2(str(location_ref), str(out_path))
```

**Impact** : `SCN_001_SHOT_001` (ultra_wide, tripod bas, searchbeam gauche→droite) et
`SCN_001_SHOT_002` (medium, Dutch tilt 3°, searchbeam traversant) reçoivent **la même image**.
Le storyboard décrit deux intentions visuelles distinctes. Le pipeline les aplati en une.
La composition, le tilt, le mouvement du searchbeam : aucun de ces éléments ne survit.

**Correction** : Les shots environnement doivent être générés depuis `refs_angles_prompts`
de `locations.json` (already written, already DOP-grade) en utilisant l'angle approprié
(`wide` / `medium` / `detail`) plutôt que copier le master. Le master est une référence,
pas un livrable de shot.

---

### PROBLÈME 1.3 — La seed est fixée par scène, pas par shot. Le décor est cohérent mais les re-runs ne le sont pas.

**Fichier** : `production/gen_shots.py`, ligne 88

```python
params = build_scene_params(shot, scene_cfg, location, grade)
```

**Fichier** : `production/locations.json` — chaque lieu a une seed unique (`"seed": 22`)

**Impact** : `scene_cfg["seed"]` est la seed du lieu, passée identique à tous les shots
de la même scène. Correct pour la cohérence intra-scène. Mais si un shot individuel
est retaké (`--shot SCN_002_SHOT_003`), le modèle peut produire un décor légèrement
différent selon la charge GPU au moment du run (FLUX n'est pas 100% déterministe à
seed égale sur infra cloud). Sans seed **par shot**, chaque retake risque de casser
la continuité de décor.

**Correction** : Définir `shot_seed = scene_seed + shot_index` et passer ce seed à P1.
`storyboard.json` contient `"shot_id": "SCN_002_SHOT_001"` — l'index est extractible.

---

### PROBLÈME 1.4 — `LocationPrepass` est marqué `⏳ À implémenter` dans PRODUCTION_RULES.md mais les shots utilisent les master plates comme si le prepass était actif.

**Fichier** : `tasks/PRODUCTION_RULES.md`, tableau Règle #1

```
| Lieu / décor | Image canonique du lieu vide → URL de référence | LocationPrepass → reference_image_url | ⏳ À implémenter |
```

**Fichier** : `aiprod_adaptation/image_gen/storyboard.py`, `StoryboardGenerator.generate()`

```python
location_reference_url = (
    self._reference_pack.location_reference_url(location_key)
    if self._reference_pack is not None and location_key
    else ""
)
reference_url = char_registry.get_reference(primary_char) if primary_char else ""
if not reference_url:
    reference_url = location_reference_url   # ← utilisé en fallback
```

**Impact** : Le `ReferencePack` attend des `reference_image_urls` pour les lieux.
Ces URLs ne sont alimentées nulle part de façon systématique dans le pipeline EP01.
`gen_location_refs.py` génère les masters et les sauvegarde localement en PNG,
mais ne met pas à jour le `reference_pack.json` avec les URLs correspondantes.
Résultat : `location_reference_url()` retourne `""` → le fallback image vers
le master plate est silencieusement désactivé → **Redux / image-to-image ne s'active jamais
pour les lieux**.

**Correction** : Après `gen_location_refs.py`, un step automatique doit uploader
chaque PNG vers un CDN ou le passer en data URI et mettre à jour
`reference_pack.json["locations"][loc_key]["reference_image_urls"]`.

---

## AXE 2 — PROMPTS

### PROBLÈME 2.1 — `build_location_prompt()` sérialise un JSON dans une string. FLUX reçoit des accolades, des guillemets échappés et des virgules.

**Fichier** : `production/gen_location_refs.py`, `build_location_prompt()`

```python
return (
    f'{{"location_canonical": "{loc["canonical"]}", '
    f'"lighting_brief": "{loc["lighting_brief"]}", '
    ...
)
```

**Impact** : Le prompt envoyé à FLUX contient littéralement
`{"location_canonical": "Narrow maintenance corridor...", "lighting_brief": "Key: single cage tungsten..."}`.
FLUX T5-XXL est un encodeur de langage naturel. Il ne parse pas le JSON — il encode
les tokens `{`, `"`, `:`, `}` comme n'importe quel autre token.
Des études empiriques (BFL, ComfyUI community) montrent que les tokens de ponctuation
JSON fragmentent le champ d'attention et réduisent la cohérence de génération.
Les prompts sont plus efficaces en prose continue.

Le `build_master_prompt_dop()` récent (refactoré cette session) est correct :
prose continue, structure narrative. `build_location_prompt()` (utilisé en fallback
et en test) est cassé sur ce point.

**Correction** : Réécrire `build_location_prompt()` en prose continue sur le modèle
de `build_master_prompt_dop()`. Supprimer les f-strings JSON.

---

### PROBLÈME 2.2 — `_condense_location()` dans `storyboard.py` tronque à 5 segments et strip les tokens techniques. Les infos DOP qui resteraient survivantes sont les premières victimes.

**Fichier** : `aiprod_adaptation/image_gen/storyboard.py`, `_condense_location()`

```python
parts = [p.strip() for p in stripped.split(",") if p.strip() and len(p.strip()) > 4]
return ", ".join(parts[:5]).strip().strip(",").strip()
```

**Impact** : Le `location_prompt` de `ReferencePack` peut contenir 300 mots de brief
DOP-grade (`"Key: single cage tungsten work lamp at vanishing point 30m ahead — 2850K,
500W, generating circular warm glow..."`) — tout cela est tronqué à 5 segments CSV.
Ce qui passe : les 5 premiers tokens après split par virgule, c'est-à-dire les mots
en début de description. Ce qui saute : températures Kelvin, IRE, ratios, DOP ref,
anamorphic notes. Le modèle reçoit un résumé de supermarché à la place d'un brief de
gaffer.

**Correction** : Pour les prompts de `reference_pack.json` qui sont déjà en prose
DOP-grade, `_condense_location()` doit passer en mode passthrough (ou limiter à
150 tokens, pas à 5 segments CSV arbitraires).

---

### PROBLÈME 2.3 — `_build_shot_prompt()` assemble les segments avec `" — "`. Pour les plans wide avec personnage, le modèle reçoit un label de framing suivi d'une description de personnage suivi d'un lieu — dans cet ordre.

**Fichier** : `aiprod_adaptation/image_gen/storyboard.py`, `_build_shot_prompt()`

```python
segments: list[str] = [framing]    # "Wide establishing shot"
if char:
    segments.append(char)           # description personnage
# ...
loc = _condense_location(...)
if loc:
    segments.append(loc)            # lieu en dernier
segments.append(_TECH_FOOTER)
```

**Impact** : Pour un plan `wide` avec Nara dans le corridor,
le modèle reçoit : `"Wide establishing shot — Female protagonist, late 20s..."`.
Pour FLUX (et T5-XXL en particulier), les tokens du début du prompt ont un poids
d'attention supérieur. La description du personnage prime sur la composition du plan.
Résultat prévisible : le modèle génère un portrait avec fond flou plutôt qu'un plan
large où le personnage est à 25% de la hauteur cadre.

Ce comportement est documenté dans `_NO_CHAR_SHOT_TYPES` (insert, wide, extreme_wide
→ char = "") mais le cas `medium` et `over_shoulder` ne l'applique pas.
Un plan `medium` avec personnage reçoit la description complète du personnage en
position 2 — avant le lieu.

**Correction** : Pour `medium` et `over_shoulder`, inverser l'ordre :
lieu → personnage → cadrage. La composition spatiale doit précéder l'identité.

---

### PROBLÈME 2.4 — Le `_PORTRAIT_FOOTER` est identique pour tous les personnages. Nara (cold blue industrial, Deakins/Sicario) et Vale (cold overhead, Fincher/Social Network) reçoivent le même footer `"Kodak Portra 400, f/2.0, soft bokeh"`.

**Fichier** : `aiprod_adaptation/image_gen/storyboard.py`, ligne 51

```python
_PORTRAIT_FOOTER = (
    "analog portrait photography, 35mm film, Kodak Portra 400, "
    "natural skin texture with visible pores, micro-imperfections, "
    "shallow depth of field f/2.0, soft bokeh background, film grain"
)
```

**Impact** : Vale doit être `"ARRI Alexa 35, 50mm T2.8, cold 6500K fluorescent,
9:1 ratio, Fincher/Social Network"`. Il reçoit du Kodak Portra 400 warm et du soft bokeh.
Ces deux intentions sont opposées. `characters.json` contient le `portrait_brief` correct
pour chaque personnage — mais `StoryboardGenerator.generate()` ne le lit pas.

**Correction** : Enrichir `ReferencePack` avec le `portrait_brief` de chaque personnage.
Dans `_build_shot_prompt()`, quand `is_portrait`, récupérer
`reference_pack.characters[primary_char].portrait_brief` et construire le footer
depuis `lighting + camera + dop_ref` du personnage concerné.

---

### PROBLÈME 2.5 — `build_p1_prompt()` génère du JSON stringifié envoyé à FLUX. Même problème que 2.1.

**Fichier** : `pipeline/shot_pipeline.py`, `build_p1_prompt()`

```python
doc = {
    "production_note": "...",
    "location": "...",
    "lighting_design": p.lighting_desc,
    ...
}
return json.dumps(doc)
```

**Impact** : FLUX 2 Pro reçoit un JSON sérialisé (~400 tokens de structure JSON).
**Ce format a été validé à 0.9378 ArcFace** — c'est le point positif, et il faut
le dire clairement. Le modèle semble tolérer ce format pour la cohérence de personnage.
Mais pour la précision d'éclairage et de composition (ce qui manque), le JSON
disperse l'attention. La prose structurée par paragraphes sémantiques est supérieure
pour les directives de lumière (validé par les prompts d'angles de `locations.json`
qui sont en prose et produisent de meilleurs détails architecturaux).

**Correction prioritaire** : Ne pas casser le score ArcFace en changeant le format P2.
En revanche, pour P1 (master décor), migrer vers la prose structurée type
`build_master_prompt_dop()` qui est déjà testée et plus performante sur les lieux.

---

## AXE 3 — COHÉRENCE

### PROBLÈME 3.1 — La règle 180° est implémentée dans Pass 3 mais non vérifiée dans le pipeline de production. `storyboard.json` la documente mais `gen_shots.py` n'en sait rien.

**Fichier** : `production/storyboard.json`

```json
"SCN_010": {
  "axis": "Sprint direction: left-to-right away from pursuit",
  "note": "CRITICAL: maintain for chase logic. Nara always escaping screen-left."
}
```

**Fichier** : `aiprod_adaptation/core/pass3_shots.py`, `_apply_180_degree_guard()`

La garde 180° existe dans le moteur générique (Pass 3) mais **n'est pas appelée
par `gen_shots.py`**. `gen_shots.py` lit `storyboard.json` directement et génère
chaque shot de façon indépendante — sans mémoire des shots précédents, sans vérification
de l'axe.

**Impact** : Deux shots successifs de la même scène peuvent placer le personnage
à gauche et à droite du cadre de façon arbitraire. Dans une scène de poursuite
(SCN_010), inverser l'axe de fuite entre deux shots consécutifs détruit la lisibilité
du mouvement narratif.

**Correction** : `gen_shots.py` doit vérifier la direction du shot contre l'axe de
scène avant génération, ou au minimum logguer un WARNING si `camera_movement` implique
un changement de direction dans une scène `axis: CRITICAL`.

---

### PROBLÈME 3.2 — La seed est globale par lieu, pas par (lieu × shot_type). Un retake isolé peut produire une architecture légèrement différente.

**Déjà identifié en 1.3. Impact sur la cohérence** :

`SCN_004_SHOT_001` (medium_wide, chambre complète) et `SCN_004_SHOT_003` (close, table centrale)
ont la même seed de lieu (44). Si `SCN_004_SHOT_003` est retaké isolément, la géométrie
de la pièce peut dériver légèrement par rapport à `SHOT_001`. La table centrale peut
changer de position de quelques pixels — visible en montage.

**Correction** : Seed par shot = `location_seed + shot_index_in_scene`.
Stocker ce `shot_seed` dans `storyboard.json` ou le calculer de façon déterministe.

---

### PROBLÈME 3.3 — `ContinuityChecker` valide `reference_anchor_strength >= 0.8` mais cette valeur est calculée de façon binaire dans Pass 3 : 0.9 si `reference_location_id` est présent, 0.5 sinon.

**Fichier** : `aiprod_adaptation/core/pass3_shots.py`

```python
anchor_strength: float = 0.9 if reference_location_id else 0.5
```

**Impact** : La valeur 0.9 est attribuée dès que `reference_location_id` est non-nul —
**indépendamment de l'existence réelle d'une image de référence**. `ContinuityChecker`
valide cette valeur et passe le check B1. Mais si `LocationPrepass` n'a pas généré
l'image (cf. 1.4), la cohérence visuelle réelle est 0.5, pas 0.9. La métrique
est un mensonge structurel.

**Correction** : `anchor_strength` doit être calculé depuis `ReferencePack` —
`0.9` uniquement si `location_reference_url(ref_id) != ""`.

---

### PROBLÈME 3.4 — Les sons et le contexte audio du storyboard (`audio_brief`) ne sont reliés à aucun générateur audio dans le pipeline actuel.

**Fichier** : `production/storyboard.json`, `SCN_001_SHOT_001`

```json
"audio_brief": "Black water against concrete — low, constant, massive.
Searchbeam motor: faint mechanical rotation above. Wind across open water. No music."
```

**Fichier** : `tasks/METHODE_PRODUCTION_IA_2026.md`, section Sound Designer

Décrit la méthode (Stable Audio, ElevenLabs SFX) mais aucun adaptateur audio
n'est présent dans `aiprod_adaptation/`. Le champ `audio_brief` est lu et stocké
dans les ShotDict mais jamais consommé.

**Impact** : Le niveau sonore de la série est au niveau L0 (humain fait tout).
Les briefs audio sont parmi les meilleurs éléments du storyboard — précis,
atmosphériques, de niveau professionnel. Ils sont inutilisés.

**Correction** : Priorité basse par rapport aux problèmes 1.1-1.4, mais un
`audio_adapter.py` basé sur Stable Audio ou ElevenLabs SFX devrait être planifié.
Le `audio_brief` est prêt à être consommé.

---

## AXE 4 — ARTISTIQUE

### PROBLÈME 4.1 — L'`emotion_intent` du storyboard (le registre dramatique du shot) n'est pas injecté dans le prompt de génération.

**Fichier** : `production/storyboard.json`, `SCN_002_SHOT_001`

```json
"emotion_intent": "Controlled competence in motion. This is her environment — she runs here, she knows this floor."
```

**Fichier** : `production/gen_shots.py`, `build_scene_params()`

```python
extra_notes=(
    f"Camera spec: {shot['camera_spec']}. Emotion: {shot['emotion_intent']}. "
    f"Character state: {state}."
),
```

L'`emotion_intent` est dans `extra_notes`. Dans `build_p1_prompt()`,
`extra_notes` est appendé à la fin du `"production_note"` — le champ JSON
le plus dilué du prompt. C'est la position d'attention la plus faible.

**Impact** : La distinction entre `SCN_002_SHOT_001` ("Controlled competence in motion")
et `SCN_002_SHOT_003` ("The choice. She could turn back. She doesn't.") est un nuance
dramatique de premier plan. Si les deux shots sont générés avec la même seed et le
même décor, seule l'intention émotionnelle les différencie. Cette intention est noyée
en queue de prompt.

**Correction** : L'`emotion_intent` doit être le **premier segment** du prompt P2
(face inpainting), pas une note de queue. Le modèle doit lire l'intention dramatique
avant la description technique. Structure recommandée :

```
[emotion_intent]. [subject_action]. [canonical]. [camera + technical].
```

---

### PROBLÈME 4.2 — Le `lighting_context` par shot du storyboard est ignoré au profit du `lighting_brief` de lieu générique.

**Fichier** : `production/storyboard.json`, `SCN_002_SHOT_002`

```json
"lighting_context": "Wrist display glow as key — amber-orange, from below.
Corridor cage lamp as backlight at distance. Face: display glow only."
```

**Fichier** : `production/gen_shots.py`, ligne 94

```python
p2_scene_env=location["lighting_brief"][:200],
```

`p2_scene_env` reçoit les 200 premiers caractères du `lighting_brief` du **lieu** —
le brief générique de la scène entière — pas le `lighting_context` **spécifique au shot**.

**Impact** : `SCN_002_SHOT_002` doit montrer uniquement la lumière de la montre OLED
comme source principale ("Face: display glow only"). Le `lighting_brief` du corridor
décrit la cage tungsten à 30m + les strips LED amber + le bounce froid du sol.
Le modèle reçoit une description de trois sources au lieu d'une. Il génère un éclairage
de corridor générique, pas l'intimité froide de la lueur ambrée d'une montre sur un visage
dans l'obscurité.

**Correction** : `p2_scene_env` doit consommer `shot["lighting_context"]` si disponible,
avec `location["lighting_brief"]` comme fallback uniquement.

---

### PROBLÈME 4.3 — La `composition` par shot du storyboard est injectée dans `extra_notes` mais pas dans le `composition` field de `SceneP1Params` qui lui est dédié.

**Fichier** : `production/gen_shots.py`, `build_scene_params()`

```python
SceneP1Params(
    ...
    composition=shot["composition"],   # ✓ correct — ce champ est utilisé
    ...
    extra_notes=(
        f"Camera spec: {shot['camera_spec']}. Emotion: {shot['emotion_intent']}..."
    ),
)
```

En réalité, `composition=shot["composition"]` est correct et présent. **Ce point est faux.**
La composition atterrit dans `build_p1_prompt()["composition"]` — champ dédié.
**Ceci est bon. Ne pas toucher.**

---

### PROBLÈME 4.4 — Les références DOP par scène (`dop_ref` de `locations.json`) sont génériques au lieu. Aucune référence DOP shot-spécifique n'est dans le pipeline.

**Fichier** : `production/locations.json`

```json
"dop_ref": "Roger Deakins / Sicario (2015) — sub-tunnel approach sequence"
```

Cette référence est identique pour tous les shots du corridor (`SCN_002_SHOT_001`,
`SHOT_002`, `SHOT_003`). Pourtant, ces trois shots ont des intentions visuelles
radicalement différentes :
- `SHOT_001` = travelling handheld dynamique → Sicario corridor est correct
- `SHOT_002` = insert montre, lumière seule → Fincher/Fight Club insert shots
- `SHOT_003` = silhouette threshold → Kubrick/2001 corridor geometry

Un seul DOP ref pour trois intentions distinctes produit des images tonalement uniformes
là où la variation est le propos.

**Correction** : Ajouter un champ `dop_ref_override` optionnel dans `storyboard.json`
par shot. Présent → prioritaire sur le DOP ref du lieu. Absent → fallback lieu.

---

### PROBLÈME 4.5 — Le `camera_spec` par shot n'est pas utilisé pour adapter le modèle ou le ratio d'aspect.

**Fichier** : `production/storyboard.json`

```json
"camera_spec": "50mm anamorphic, T2.8, ISO 1600, tripod"   (SCN_002_SHOT_002)
"camera_spec": "32mm anamorphic, T2.3, ISO 1600, handheld"  (SCN_002_SHOT_001)
```

**Fichier** : `production/gen_shots.py`

```python
extra_notes=(f"Camera spec: {shot['camera_spec']}...")
```

Le `camera_spec` est en `extra_notes`, position de faible attention. Plus critique :
**le changement de focale n'est pas traduit en changement de paramètre de génération**.
FLUX ne peut pas simuler la compression 50mm vs la distorsion 32mm par la mention
textuelle enfouie en extra_notes. Ces informations seraient plus utiles dans le
`production_note` en tête de prompt, et la profondeur de champ correspondante
(T2.8 = shallow, T2.3 à distance = medium) devrait être dans un champ dédié.

**Correction** : Déplacer `camera_spec` vers le champ `locked_camera` de `SceneP1Params`
(ou en premier segment de `production_note`) + dériver `depth_of_field` depuis l'ouverture.

---

## SYNTHÈSE — PRIORITÉS D'ACTION

| # | Problème | Impact | Effort | Priorité |
|---|----------|--------|--------|----------|
| 1.1 | Pipeline P2 Nara-only | Personnages Vale/Elian/Mira/Rook impossibles | M | **CRITIQUE** |
| 4.2 | `lighting_context` shot ignoré | Éclairage générique lieu vs intention shot | S | **HAUTE** |
| 2.3 | Ordre segments prompt wide+char | Portrait au lieu de plan large | S | **HAUTE** |
| 2.4 | `_PORTRAIT_FOOTER` générique | Style DOP personnage absent | S | **HAUTE** |
| 1.2 | Env shots = copie master plate | Shots 1 et 2 identiques dans SCN_001 | M | **HAUTE** |
| 4.1 | `emotion_intent` en queue prompt | Intention dramatique invisible | S | **MOYENNE** |
| 2.1 | JSON stringifié dans prompt | Attention fragmentée par ponctuation | S | **MOYENNE** |
| 1.4 | LocationPrepass non actif | Redux lieu désactivé silencieusement | L | **MOYENNE** |
| 1.3 | Seed scène pas par shot | Dérive décor sur retakes | S | **BASSE** |
| 3.3 | `anchor_strength` mensonge | Métrique CI faussement verte | S | **BASSE** |
| 4.4 | DOP ref générique au lieu | Tonalité uniforme intra-scène | S | **BASSE** |

**Effort** : S = < 2h | M = demi-journée | L = 2+ jours

---

## CE QUI EST BON — UNE FOIS, VITE

- `storyboard.json` : niveau professionnel. `action_brief`, `lighting_context`, `emotion_intent`,
  `audio_brief`, axes 180° par scène — c'est un vrai document de production, pas un template.
- `characters.json` : canonicals et `portrait_brief` de niveau studio. Chaque personnage
  a une identité visuelle distincte et précise.
- `locations.json` + `refs_angles_prompts` : les prompts d'angles (en prose, ~300 mots chacun)
  sont le modèle à suivre pour tous les prompts du pipeline. IRE, Kelvin, bokeh specs, DOP ref,
  anamorphic notes — tout y est.
- `grade.json` : correctement injecté dans `gen_shots.py` via `colour_desc`. Ce point est résolu.
- `LOCKED_NARA_CANONICAL` + score ArcFace 0.9378 : la méthode de prompt P2 fonctionne.
  Le problème est qu'elle ne s'applique qu'à un seul personnage.
- `_MASTER_COMPOSITIONS` (post-refactoring cette session) : correctement séparé des prompts Redux.

---

## PROCHAINE ÉTAPE RECOMMANDÉE

Implémenter **1.1** avant toute génération de shots multi-personnages :
extraire le `canonical` de `characters.json` par `char_id` dans `gen_shots.py`,
le passer à `SceneP1Params` et `build_p2_prompt()`. Coût : ~2h. Déblocage : Vale,
Elian, Mira, Rook peuvent être générés correctement pour la première fois.
