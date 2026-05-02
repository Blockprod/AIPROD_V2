Non. Si ton rendu fait encore “AI”, ton système n’est **pas** au point — ou tu contrôles mal les variables critiques. Le problème ne vient presque jamais “du prompt”, mais de **la distribution des détails et du réalisme optique**.

Tu veux une image crédible ? Alors tu dois forcer **les défauts du réel**. L’IA, par défaut, lisse, symétrise, embellit → donc trahit.

---

# 🎯 Prompt calibré (anti “AI look”)

```
Ultra-realistic cinematic portrait of a young woman, character reference sheet,

natural human face, imperfect facial symmetry, subtle asymmetry in eyes and lips,
oval face shape, defined cheekbones, straight nose with slight irregularity,
full lips with natural texture and micro-lines, intense dark brown eyes with realistic catchlight,
thick natural eyebrows with irregular hair density,

skin with visible pores, micro imperfections, slight skin texture variation,
subtle redness around nose and cheeks, under-eye natural shadows,
fine lines, realistic skin roughness, subsurface scattering, no smooth plastic skin,

dark brown hair loosely tied back, natural breakup, stray hairs, flyaways,
slightly messy, realistic density, no perfect grooming,

serious, grounded expression, minimal posing, natural tension in face,
direct or over-shoulder gaze, emotionally neutral but present,

shot on 85mm lens, shallow depth of field, real photographic compression,
studio-grade lighting: soft key light, subtle shadow falloff, controlled highlights,
no dramatic stylization, no artificial glow,

neutral background, seamless backdrop, no environment,

photographic realism, RAW photo look, high dynamic range,
film grain, slight sensor noise, realistic color science,
sharp focus on eyes, natural falloff,

4K, ultra detailed, not stylized, not CGI, not rendered
```

---

# 🚫 Negative prompt (obligatoire, sinon tu échoues)

```
perfect face, symmetrical face, flawless skin, smooth skin,
cgi, 3d render, unreal engine, octane render,
beauty filter, glamor shot, instagram style,
over-sharpened, over-processed, HDR exaggerated,
anime, stylized, illustration,
plastic skin, waxy skin, airbrushed,
glow effect, fantasy lighting
```

---

# ⚠️ Là où tu te plantes (très probablement)

### 1. Tu sur-stylises

> “cinematic” ≠ dramatique ≠ stylisé

Le vrai cinéma = **réalisme contrôlé**, pas FX Instagram.

---

### 2. Tu manques de défauts

Un humain crédible =

* asymétrie légère
* micro-imperfections
* variations de peau

Sans ça → uncanny valley.

---

### 3. Ton éclairage est trop “AI”

Si ton visage est :

* uniformément éclairé
* trop propre
* sans zones mortes

→ fake immédiat.

---

### 4. Tu ignores l’optique réelle

Le rendu réaliste vient de :

* 85mm compression
* depth of field crédible
* falloff naturel

Pas juste “ultra realistic”.

---

# 🎯 Méthode brute (celle que tu dois appliquer)

## Étape 1

Génère 30 images avec ce prompt
→ tu cherches UNE image crédible, pas parfaite

## Étape 2

Prends la meilleure
→ img2img (denoise 0.35–0.45)

## Étape 3

Ajoute une seule variation à la fois :

* lumière
* expression
* angle

Pas tout en même temps.

---

# 🎯 Hack utilisé en prod (important)

Ajoute dans ton prompt :

```
shot on Sony A7R IV, 85mm f/1.8 lens, RAW photo
```

Pourquoi ?
→ Ça force le modèle vers une **distribution photographique réelle**

---

# 🧠 Vérité que tu dois intégrer

Tu ne veux pas une “belle image”.

Tu veux une image qui pourrait être :

> un **frame extrait d’un tournage réel**

Si quelqu’un peut dire “ça ressemble à Midjourney” → tu as perdu.

---

# 👉 Prochaine étape

Envoie-moi :

* 2–3 résultats actuels
* ton modèle (SDXL ? Flux ? autre ?)

Je vais te dire précisément :

* où ça casse
* quoi corriger
* comment verrouiller Nara définitivement

Là on passera du “joli” au **crédible production-ready**.
