Parfait. Voici le système complet.

---

## Règles spécifiques aux lieux dans Flux 1.1 Pro Ultra

Trois différences clés par rapport aux portraits de personnages :

**Ratio 16:9 obligatoire.** Un lieu de référence doit correspondre au cadre cinématographique final. Pas de 4:5.

**Pas de personnage dans le frame.** L'image de référence de lieu doit être vide de tout sujet humain — sinon Runway References va locker le personnage parasite en même temps que le décor.

**Trois angles minimum par lieu.** Wide establishing shot, medium environmental, close detail. Ces trois images constituent la "bible visuelle" du lieu pour Runway.

---

## La méthode : 7 blocs structurés pour les lieux

```
[TYPE DE LIEU + NOM] → [ARCHITECTURE PRÉCISE] → [ÉTAT + DÉGRADATION] 
→ [HEURE + CONDITIONS ATMOSPHÉRIQUES] → [ÉCLAIRAGE CINÉMATOGRAPHIQUE] 
→ [CAMÉRA + OPTIQUE] → [PALETTE + AMBIANCE]
```

---

## Le prompt maître — 3 angles de référence

---

### ANGLE 1 — Establishing shot (wide, vue d'ensemble)

```
Photorealistic cinematic wide establishing shot of [NOM DU LIEU], 
a [DESCRIPTION ARCHITECTURALE PRÉCISE : type de bâtiment, matériaux, époque, état], 
located in a dense dystopian urban environment, [ANNÉE OU ÉPOQUE IMPLICITE].

[DÉTAILS ARCHITECTURAUX DISTINCTIFS : éléments signature du lieu, 
structures spécifiques, enseignes, infrastructures visibles].
No people, no moving subjects, completely empty scene.

[HEURE DU JOUR : pre-dawn / overcast midday / golden hour / night] atmosphere, 
[CONDITIONS MÉTÉO : light rain on pavement / heavy smog layer / clear cold air / steam from vents].

Cinematic lighting: [SOURCE PRINCIPALE : massive industrial overhead sodium lamps / 
neon signage spill / overcast diffused skylight / moonlight through pollution haze], 
[SOURCE SECONDAIRE : distant city glow on horizon / practical lights inside windows / 
emergency lighting strips]. 
[PALETTE COLORIMÉTRIQUE : desaturated teal and amber / cold blue and orange / 
muted olive and rust].

Shot on ARRI Alexa 35, Cooke Anamorphic 32mm T2.3 lens, 
anamorphic bokeh on background lights, slight lens breathing visible, 
horizontal anamorphic flares on practical light sources.
Ground-level camera placement, eye-level horizon, rule of thirds composition.

Photorealistic production design reference, 
no CGI look, no game engine aesthetic, no concept art stylization, 
documentary realism applied to fiction, production-ready background plate quality.
```

---

### ANGLE 2 — Medium environmental (vue intermédiaire, détails lisibles)

```
Photorealistic cinematic medium shot of [MÊME LIEU, ZONE SPÉCIFIQUE : 
entrée principale / couloir latéral / place centrale / niveau inférieur],
same architectural identity as establishing reference, 
identical atmospheric conditions, identical time of day.

Focus on [DÉTAIL ARCHITECTURAL SIGNATURE : texture des murs, 
grilles métalliques, tuyauteries, affichages numériques défaillants, 
végétation envahissante, traces d'occupation humaine sans présence humaine].
No people, no moving subjects.

Same lighting setup as wide reference, 
camera slightly lower to emphasize verticality and scale, 
50mm equivalent lens, minimal depth of field compression.

Same color palette, same film stock simulation, 
consistent with establishing shot reference — same world, same light, same moment.
Production reference quality, environment bible entry.
```

---

### ANGLE 3 — Close detail (texture signature, élément iconique)

```
Photorealistic extreme close-up of [ÉLÉMENT ICONIQUE DU LIEU : 
texture de mur spécifique, enseigne dégradée, sol caractéristique, 
détail mécanique ou organique distinctif],
from [NOM DU LIEU], consistent with wide and medium reference images.

Same atmospheric conditions, same lighting direction and color temperature.
No people, no moving subjects.

Shot on ARRI Alexa 35, 100mm macro lens, razor-thin depth of field, 
subject sharp, background completely dissolved.

This image serves as texture and detail reference for production design continuity.
```

---

## Exemple concret pour District Zero

Si ton lieu principal est une zone industrielle abandonnée reconvertie en marché noir :

```
Photorealistic cinematic wide establishing shot of The Undergrid, 
a massive decommissioned electrical substation converted into a sprawling underground market, 
brutalist concrete structure from the 1970s now covered in decades of grime, 
unauthorized metal additions, layers of spray-painted signage in multiple languages, 
exposed high-voltage infrastructure repurposed as structural support.
Corrugated metal vendor stalls built against original transformer housings, 
tangle of illegal power lines overhead forming a dense canopy, 
cracked concrete floor with decades of oil stains and standing water in low points.
No people, no moving subjects, completely empty scene.

Pre-dawn atmosphere, light drizzle creating reflective wet surfaces, 
thin ground-level fog trapped under the metal canopy, 
cold air visible as breath condensation on surfaces.

Cinematic lighting: sodium vapor industrial lamps casting deep amber pools interrupted by 
shadow, blue-white LED strips on vendor stalls creating harsh contrast zones, 
distant emergency red lighting at exits bleeding into fog.
Palette: desaturated amber and cold teal with rust accents, 
deep crushed blacks in shadow areas.

Shot on ARRI Alexa 35, Cooke Anamorphic 32mm T2.3 lens, 
anamorphic horizontal flares on sodium lamps, ground-level camera placement.

Photorealistic production design reference, no CGI aesthetic, 
documentary realism applied to fiction, production-ready background plate quality.
```

---

## Paramètres techniques

| Paramètre | Valeur |
|---|---|
| Aspect ratio | **16:9** obligatoire |
| Raw mode | **ON** |
| Prompt enhance | **OFF** |
| Seed | **Fixe par lieu** — même seed pour les 3 angles |

---

## Ce que tu ajoutes dans `character_registry.json`

Renomme-le `production_registry.json` et ajoute un bloc `locations` :

```json
{
  "characters": { ... },
  "locations": {
    "the_undergrid": {
      "description_canonique": "...",
      "seed": 0000,
      "prompt_wide": "...",
      "prompt_medium": "...",
      "prompt_detail": "...",
      "refs": {
        "wide": "assets/refs/locations/undergrid_wide.png",
        "medium": "assets/refs/locations/undergrid_medium.png",
        "detail": "assets/refs/locations/undergrid_detail.png"
      },
      "palette": "desaturated amber / cold teal / rust",
      "time_of_day": "pre-dawn",
      "weather": "light drizzle"
    }
  }
}
```

Ce fichier devient la bible de production d'AIPROD_SERIES — chaque appel Runway References le consulte pour passer les bonnes images au bon adapter.