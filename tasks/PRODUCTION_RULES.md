---
type: production-rules
projet: AIPROD_V2 — District Zero (et toute série future)
creation: 2026-04-27 à 19:11
statut: RÈGLES ABSOLUES — jamais dérogées
---

# RÈGLES DE PRODUCTION — AIPROD_V2

> Ces règles s'appliquent à **toute la série**, à chaque épisode, à chaque shot,
> à chaque session de génération. Elles sont codifiées dans le pipeline et dans
> le `reference_pack.json`. Toute dérogation doit être explicitement documentée.

---

## RÈGLE #0 — BIBLE VISUELLE DE LA SÉRIE

> Source de vérité absolue : `preproduction/district_zero/reference_pack.json` → `style_block`

```
Photorealistic cinematic quality, ARRI Alexa 35, anamorphic lens, 4K hyperrealistic.
Color grading: desaturated teal and steel-blue dominant, selective warm amber highlights
in practical sources. No oversaturation, no fantasy glow, no HDR clipping.
Natural grain texture, corroded metal surfaces, wet concrete, humid air with visible
light particles. Lighting logic: practical sources only (halogen cage lights, neon,
water reflections, emergency strips). Naturally contrasted chiaroscuro.
```

**Ce style_block est immuable pour toute la série.** Toute modification doit être
validée par le DA et versionnée dans le reference_pack.json.

---

---

## RÈGLE #1 — LA MISE AU POINT D'INTENTION ("Focus Check")

> Inspirée de la technique cinéma : avant de cadrer, le focus puller zoome au maximum
> sur le point d'intention, effectue la mise au point, puis revient au cadre de départ.
> **Cette règle s'applique à TOUT sujet d'intention, avec ou sans personnage.**

### Principe

Pour chaque élément visuel qui doit être reconnaissable et cohérent tout au long
d'une série, un **prepass dédié** doit être effectué AVANT toute génération de shot :

1. **Zoom** — Générer une image canonique du sujet seul, au maximum de détail
2. **Mise au point** — Extraire / valider l'identité visuelle exacte (masque RGBA ou référence URL)
3. **Dézoom** — Utiliser cette référence verrouillée dans chaque shot où le sujet apparaît

### Application par catégorie de sujet

| Sujet | Prepass | Mécanisme pipeline | Statut |
|-------|---------|-------------------|--------|
| **Personnage (visage)** | Portrait canonique → suppression fond → masque RGBA | `CharacterPrepass` → `generate_edit` | ✅ Implémenté |
| **Lieu / décor** | Image canonique du lieu vide → URL de référence | `LocationPrepass` → `reference_image_url` | ⏳ À implémenter |
| **Objet-clé** (arme, artefact, véhicule) | Image canonique de l'objet seul | `PropPrepass` → `reference_image_url` | ⏳ À implémenter |

### Règles d'application strictes

- **Jamais de shot payant sans prepass validé** pour tout sujet d'intention présent dans le shot
- Le `--dry-run` doit toujours afficher la liste des prepasses résolus ET des prepasses manquants
- Un prepass manquant sur un sujet d'intention = WARNING obligatoire dans le dry-run
- Un prepass manquant sur un personnage avec `--remove-background` = **ERREUR BLOQUANTE** (exit 1)
- Le prepass est toujours lancé dans le **même run** que les shots pour éviter la dérive d'identité entre sessions

### Analogie complète

```
Cinéma                          Pipeline AIPROD
─────────────────────────────   ─────────────────────────────────────────
Zoom max sur le visage       →  CharacterPrepass : portrait canonique
Bague de MAP parfaite        →  rembg : extraction du visage (masque RGBA)
Mise au point verrouillée    →  register_rgba() : identité verrouillée en mémoire
Dézoom → cadre de travail    →  generate_edit() : sujet net incrusté dans la scène
```

---

## RÈGLE #2 — DRY-RUN OBLIGATOIRE AVANT TOUT RUN PAYANT

Tout run impliquant un adapter payant (image, vidéo, audio) **doit** être précédé
d'un `--dry-run` validé :

- Vérifier : `Prepass resolved` non vide si `--remove-background`
- Vérifier : zéro ligne `ERROR` ou `SKIPPED` non intentionnel
- Vérifier : estimation de coût cohérente avec le budget disponible
- Lire la ligne `DRY-RUN OK` avant de retirer `--dry-run`

---

## RÈGLE #3 — COHÉRENCE QUALITÉ INTRA-ÉPISODE

Tous les shots d'un même épisode doivent être générés avec la **même qualité** :
- `OPENAI_IMAGE_QUALITY` : valeur identique pour tous les runs du même épisode
- Si un run partiel a été fait à une qualité donnée (ex: `high`), les runs de
  complétion **doivent** utiliser la même valeur
- Documenter la qualité utilisée dans le nom du dossier de sortie si différente
  du standard de la série

---

## RÈGLE #4 — JAMAIS RÉGÉNÉRER UN SHOT VALIDÉ

Un shot validé par le directeur artistique (DA) est **définitif** :
- Le marquer explicitement `NEVER REGENERATE` dans les notes de session
- Ne jamais l'inclure dans un `--shot-id` de re-run
- En cas de re-run de scène complète, exclure explicitement les shots validés

---

## RÈGLE #5 — UN SEUL RUN GROUPÉ PAR SESSION

Pour économiser les prepasses (chaque run repaie les N personnages) :
- Grouper tous les shots manquants d'un même épisode dans **un seul run**
- Ne jamais lancer des runs scène par scène si les scènes partagent des personnages
- Exception : si les scènes ont des personnages entièrement disjoints

---

---

## RÈGLE #6 — FORMAT & RAPPORT D'ASPECT

- **Format de la série** : anamorphique **2.39:1** (cinémascope) — immuable
- **Caméra de référence** : ARRI Alexa 35 LF + optiques Cooke S7i anamorphiques
- **Résolution de génération** : 1536×1024 (paysage) pour tous les plans sauf portraits
- **Portraits** (close-up, extreme close-up) : 1024×1536 ou 1024×1024 selon sujet
- **Jamais** de format 16:9 (1.77:1) ou carré pour les plans de production

---

## RÈGLE #7 — BALANCE DES BLANCS & TEMPÉRATURE COULEUR

Deux registres coexistent dans la série — jamais de mélange dans un même shot :

| Registre | Température | Usage | Exemples de lieux |
|----------|-------------|-------|-------------------|
| **Froid dominant** | 4 000–5 500 K | Espace extérieur, institutions, surveillance | Seawall, Civic Atrium, Ops Center |
| **Chaud accent** | 2 200–3 200 K | Sources pratiques isolées dans l'obscurité | Cage bulbs, lampes salon, néons ambrés |

- **Règle absolue** : le froid domine toujours — le chaud est un accent, jamais la base
- **Jamais** de light mix indifférencié (tout chaud ou tout neutre = interdit)
- En portrait : tonalité froide sur le fond + lumière pratique chaude sur le sujet = règle d'or
- Codifié dans le style_block : `"selective warm amber highlights in practical sources"`

---

## RÈGLE #8 — ÉTALONNAGE & COLORIMÉTRIE

Palette chromatique verrouillée pour toute la série :

| Canal | Valeur | Description |
|-------|--------|-------------|
| **Dominante** | Teal + Steel-blue désaturé | Ombres et tons moyens |
| **Accent chaud** | Amber + Orange sombre | Sources pratiques uniquement |
| **Interdits absolus** | Vert vif, rouge vif, rose, cyan saturé | Hors brief DA |
| **Saturation** | Réduite (-20 à -35%) | Réalisme dystopique, fatigue visuelle |
| **Contraste** | Chiaroscuro naturel | Pas de HDR clipping, pas de lift excessif |
| **Noirs** | Profonds mais non écrasés | Détail conservé dans les ombres |
| **Hautes lumières** | Jamais clippées | No HDR glow, no fantasy bloom |

- Codifié : `"desaturated teal and steel-blue dominant, selective warm amber highlights"`
- `"No oversaturation, no fantasy glow, no HDR clipping"`
- En pipeline : le `style_block` est injecté dans **100% des prompts** via le `style_token`

---

## RÈGLE #9 — ÉCLAIRAGE (LIGHTING)

- **Sources exclusivement pratiques** : lampes cage halogène, néons, réflexions d'eau,
  bandes d'urgence, écrans de contrôle — jamais de lumière "studio" artificielle
- **Logique lumineuse narrative** : la lumière justifie toujours son existence dans le décor
- **Chiaroscuro naturellement contrasté** : zones d'ombre importantes, pas de fill light uniforme
- **Particules atmosphériques** : air humide visible, particules dans les faisceaux lumineux
- Codifié : `"motivated practical lighting only"` dans le `DEFAULT_STYLE_TOKEN`
- Codifié : `"Lighting logic: practical sources only (halogen cage lights, neon, water reflections,
  emergency strips). Naturally contrasted chiaroscuro."` dans le style_block

**Par registre de plan** :
- Portrait close-up : Kodak Portra 400, f/2.0, bokeh arrière — lumière douce sur visage
- Plan large extérieur nuit : contrejour froid + halos de projecteurs dans la brume
- Plan large intérieur : sources isolées dans l'obscurité, vanishing point lumineux

---

## RÈGLE #10 — CADRAGE & COMPOSITION

Référence : `_SHOT_TYPE_LABELS` dans `storyboard.py` + directives IR par shot

| Type | Label | Règle de composition |
|------|-------|---------------------|
| `extreme_wide` | Extreme wide establishing | Sujet <10% hauteur cadre, environnement dominant |
| `wide` | Wide establishing | Sujet 25–40% hauteur cadre, règle des tiers |
| `medium` | Medium shot | Sujet cadré mi-cuisse à crown, contexte visible |
| `over_shoulder` | Over-shoulder | Épaule premier plan floue, visage sujet net |
| `close_up` | Close-up portrait | Épaules à crown, visage occupant 60–80% |
| `extreme_close_up` | Extreme close-up | Yeux–menton uniquement, détail peau visible |
| `insert` | Insert detail | Objet seul, macro, fond non-identifiable |

**Règles universelles** :
- Règle des tiers : sujet jamais centré sauf effet de domination/isolation intentionnel
- Format anamorphique 2.39:1 : exploiter l'espace horizontal — bannir la composition "TV"
- Profondeur de champ : toujours motivée par le sujet d'intention (cf. Règle #1)
- **Jamais** de composition "clipart" ou symétrie parfaite non intentionnelle

---

## RÈGLE #11 — PROFONDEUR DE CHAMP

| Type de plan | Ouverture | Profondeur | Effet |
|--------------|-----------|------------|-------|
| Portrait ECU / CU | f/1.4–f/2.0 | Très faible | Bokeh, isolation totale du visage |
| Portrait MS | f/2.8–f/4.0 | Faible | Sujet net, fond lisible flou |
| Plan large intérieur | f/5.6–f/8.0 | Moyenne | Avant-plan et milieu nets |
| Establishing wide | f/8.0–f/11 | Profonde | Tout l'environnement net |

- En portrait : `"shallow depth of field f/2.0, soft bokeh background"` — codifié `_PORTRAIT_FOOTER`
- En establishing : `"deep depth of field, f/8.0"` — codifié dans les métadonnées IR
- **Jamais** de "tout net" sur un plan de dialogue (interdit : f/16 en portrait)

---

## RÈGLE #12 — TEXTURE & GRAIN

- **Grain film** obligatoire sur tout shot : `"film emulsion grain"` dans le style_token
- **Texture naturelle de peau** : pores visibles, micro-imperfections, subsurface scattering
  — `"natural skin texture with visible pores, subsurface scattering"`
- **Surfaces décor** : métal corrodé, béton humide, bois vieilli — texture matière prioritaire
  — `"corroded metal surfaces, wet concrete"` dans le style_block
- **Jamais** : peau lissée, surface plastique, rendu CGI propre, over-sharpening

---

## RÈGLE #13 — MOUVEMENT DE CAMÉRA

Valeurs autorisées dans l'IR (`camera_movement`) et leur usage :

| Mouvement | Usage narratif |
|-----------|---------------|
| `static` | Tension, contemplation, pouvoir institutionnel |
| `slow_push` | Révélation progressive, menace qui approche |
| `pull_back` | Isolement du personnage, monde qui s'élargit |
| `pan` | Découverte de l'espace, suivi d'action latérale |
| `tilt_up` / `tilt_down` | Échelle monumentale, abaissement/élévation symbolique |
| `handheld` | Urgence, chaos, point de vue subjectif sous pression |

- **Interdit** : drone shot, steadicam fluide sur scène intime, zoom optique comme substitut de découpe
- Pour la génération image : le mouvement est codifié dans le prompt (`camera_intent`)
  — pour la vidéo (Runway) : transmis comme `camera_motion` dans le `VideoRequest`

---

## RÈGLE #14 — RACCORDS & CONTINUITÉ VISUELLE

- **Raccord sur le regard** : direction du regard conservée entre deux plans en dialogue
- **Raccord de lumière** : même température de source entre plans du même lieu/moment
- **Raccord de costume** : tenue identique dans les scènes continues (géré par Règle #1)
- **Raccord de décor** : même état du décor (géré par Location Prepass — Règle #1 ⏳)
- **180° rule** : ne jamais couper l'axe en dialogue (interdit dans le découpage IR)
- En pipeline : `last_frame_url` dans `VideoClipResult` assure le chaînage inter-shots vidéo

---

## RÈGLE #15 — SON & AMBIANCE SONORE

Chaque shot porte un `dominant_sound` dans les métadonnées IR — il dicte la génération audio :

| Valeur | Type ambiance | Adapter recommandé |
|--------|---------------|-------------------|
| `ambient` | Environnement pur, pas de dialogue | ElevenLabs SFX / silence |
| `dialogue` | Voix de personnage au premier plan | ElevenLabs TTS avec SSML |
| `action` | Son d'impact, mouvement intense | SFX layer |
| `music` | Musique diégétique ou extra-diégétique | Réservé post-prod |

- **Voix** : ton et rythme SSML dictés par `emotion` du shot + `beat_type` de la scène
- **Jamais** de musique générée par IA sans validation DA (risque de tonalité incohérente)
- Silence intentionnel = valeur narrative — ne pas combler systématiquement

---

## ÉVOLUTION DE LA RÈGLE #1 — ROADMAP

### Location Prepass (à venir)
Pour chaque lieu clé de la série, générer une image canonique vide (sans personnage)
qui servira de référence pour tous les shots dans ce lieu :
- Input : `location.canonical_prompt` depuis `reference_pack.json`
- Output : URL stockée dans `LocationImageRegistry`
- Usage : injecté comme `reference_image_url` dans tous les shots avec ce `location_id`

### Prop Prepass (à venir)
Pour les objets narratifs importants (ex: le badge de Nara, l'arme de Vale) :
- Même mécanique que le character prepass
- Déclenché si `prop_id` présent dans le shot et entrée dans le reference pack

---

## TABLEAU DE BORD DES RÈGLES

| # | Règle | Statut pipeline |
|---|-------|----------------|
| R0 | Bible visuelle (style_block) | ✅ `reference_pack.json` |
| R1 | Focus Check / Prepass d'intention | ✅ personnages · ⏳ lieux · ⏳ props |
| R2 | Dry-run obligatoire | ✅ `--dry-run` pre-flight |
| R3 | Cohérence qualité intra-épisode | ✅ `OPENAI_IMAGE_QUALITY` |
| R4 | Shot validé = NEVER REGENERATE | ✅ convention manuelle |
| R5 | Run groupé par session | ✅ convention manuelle |
| R6 | Format 2.39:1 anamorphique | ✅ `_openai_image_size()` |
| R7 | Balance des blancs | ✅ style_block + prompts lieux |
| R8 | Étalonnage / Colorimétrie | ✅ style_block |
| R9 | Éclairage pratique uniquement | ✅ style_token + prompts lieux |
| R10 | Cadrage / Composition | ✅ `_SHOT_TYPE_LABELS` + IR |
| R11 | Profondeur de champ | ✅ `_PORTRAIT_FOOTER` + IR metadata |
| R12 | Texture & Grain | ✅ style_token |
| R13 | Mouvement de caméra | ✅ IR `camera_movement` |
| R14 | Raccords & Continuité | ✅ partiel (`last_frame_url`) · ⏳ location |
| R15 | Son & Ambiance | ✅ IR `dominant_sound` + SSML |

