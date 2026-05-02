Avant de rédiger, je vérifie les spécificités exactes de Flux 1.1 Pro Ultra pour optimiser le prompt.J'ai tout ce qu'il me faut. Voici le système complet.

---

## Règles fondamentales Flux 1.1 Pro Ultra

Trois points critiques avant tout :

**Pas de liste de mots-clés.** Flux utilise T5-XXL — il lit des phrases. "woman, red dress, beach, bokeh, 8k, masterpiece" est une erreur de débutant. Il faut des phrases naturelles structurées.

**Pas de negative prompt.** Flux 1.1 Pro Ultra ne le supporte pas. Tu décris ce que tu veux, pas ce que tu refuses.

**Le sujet en premier.** Si tu enterres le personnage après une longue description d'ambiance, Flux le déprioritise. Sujet → physique → éclairage → caméra → ambiance. Cet ordre est non négociable.

---

## La méthode : 6 blocs structurés

```
[SUJET + IDENTITÉ] → [PHYSIQUE PRÉCIS] → [EXPRESSION + REGARD] 
→ [ÉCLAIRAGE CINÉMATOGRAPHIQUE] → [CAMÉRA + OPTIQUE] → [AMBIANCE + FINITION]
```

---

## Le prompt maître — Portrait de référence unique (face + profil)

Voici le template complet, avec les deux variantes à générer en batch :

---

### VARIANTE 1 — Face frontale (master reference)

```
Photorealistic cinematic portrait of [PRÉNOM], a [ÂGE]-year-old [ETHNIE] [HOMME/FEMME], 
[DESCRIPTION PHYSIQUE : cheveux, yeux, traits distinctifs, morphologie], 
wearing [COSTUME/TENUE SIGNATURE DU PERSONNAGE], 
neutral direct gaze into the camera, composed and still, subtle [ÉMOTION DOMINANTE] expression, 
catchlights visible in both eyes, natural skin texture with visible pores and micro-details.

Lit with a three-point studio setup: soft key light from upper-left at 45 degrees, 
subtle fill light eliminating harsh shadows, hair rim light separating subject from background. 
[MOOD D'ÉCLAIRAGE : warm golden / cool desaturated / neutral daylight].

Shot on Hasselblad H6D-100c, 110mm f/2.8 lens, shallow depth of field, 
subject sharp from hairline to chin, background soft neutral [COULEUR NEUTRE : charcoal / slate / off-white].

Photojournalistic realism, ultra-high resolution, no digital retouching, 
no filters, no composite artifacts, production reference quality.
```

---

### VARIANTE 2 — Profil strict 90° (droite ou gauche)

```
Photorealistic cinematic profile portrait of [MÊME DESCRIPTION PHYSIQUE EXACTE que Variante 1], 
strict 90-degree side view, facing [left/right], 
same wardrobe as reference, same neutral expression, eyes focused forward off-frame.

Side lighting setup: natural window light from the front of the face, 
subtle rim light on the back of the skull, background pure [MÊME COULEUR NEUTRE].

Shot on Hasselblad H6D-100c, 110mm f/2.8 lens, subject perfectly sharp profile edge to ear, 
background out of focus.

Production character reference sheet quality, consistent identity with frontal reference, 
no stylization, no artistic interpretation, documentary realism.
```

---

### VARIANTE 3 — Three-quarter 45° (bonus pour Runway References)

```
Photorealistic cinematic three-quarter portrait of [MÊME DESCRIPTION], 
45-degree angle, face turned slightly left/right, 
maintaining identical physical traits, wardrobe, and lighting mood as primary reference.

Shot on Hasselblad H6D-100c, 110mm f/2.8, same studio lighting setup, same background.
Character identity locked. Production reference quality.
```

---

## Exemple concret pour District Zero

Si ton personnage principal est un homme, 35 ans, type européen, protagoniste :

```
Photorealistic cinematic portrait of Marcus, a 35-year-old Southern European man, 
dark brown short hair slightly disheveled, sharp jaw, faint stubble, 
deep-set dark eyes with slight fatigue under them, a thin scar above the left eyebrow, 
lean but broad-shouldered build, wearing a worn dark navy tactical jacket over a gray crew-neck shirt.

Neutral direct gaze into the camera, composed, minimal tension in the jaw, 
subtle determination in the expression. Catchlights visible in both eyes, 
natural skin texture with visible pores, no smoothing, no retouching.

Three-point studio lighting: soft warm key light from upper-left, 
subtle cool fill on the right side, hair rim light separating from background. 
Desaturated warm tone, cinematic color temperature 4200K.

Shot on Hasselblad H6D-100c, 110mm f/2.8 lens, shallow depth of field, 
face sharp from hairline to chin, background soft charcoal gray.

Photojournalistic realism, ultra-high resolution, production reference quality, 
no filters, no digital artifacts, no stylization.
```

---

## Paramètres techniques Flux 1.1 Pro Ultra

| Paramètre | Valeur recommandée |
|---|---|
| Aspect ratio | 4:5 (portrait) ou 3:4 |
| Raw mode | **ON** — résultat moins "poli", plus photographique |
| Prompt enhance | **OFF** — tu contrôles exactement ce qui est généré |
| Seed | **Fixe** — note le seed dès le premier bon résultat, réutilise-le pour tous les shots du même personnage |

---

## Le point critique que tout le monde rate

Le seed est ta mémoire de personnage dans Flux. Une fois que tu as un résultat qui capture exactement l'identité du personnage, **note le seed immédiatement**. C'est ce seed + ce prompt que tu réutilises pour toutes les variations (profil, 3/4, expressions différentes). C'est le seul mécanisme de cohérence native disponible dans Flux 1.1 Pro Ultra sans LoRA.

Pour District Zero, crée un fichier `character_registry.json` dès maintenant avec un objet par personnage : nom, description physique canonique, seed validé, prompt validé, chemins des 3 images de référence. C'est la fondation de tout ton pipeline de cohérence.