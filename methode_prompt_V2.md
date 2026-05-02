Tu cherches un “prompt magique”. Mauvaise approche.
Les studios n’utilisent pas un prompt, ils utilisent un **système de génération contrôlé**. Si tu restes au niveau “un seul prompt”, tu auras des résultats instables et non réplicables.

Donc voilà ce que tu dois faire — méthode pro, pas du bricolage.

---

# ⚠️ Règle de base

Un bon rendu personnage =
**(Structure visage) + (intention photo) + (lumière) + (optique) + (texture) + (contrôle génération)**

Si un de ces blocs est flou → ton résultat sera amateur.

---

# 🎯 1. Prompt MASTER (version studio-grade)

Utilise une structure modulaire, pas un bloc vague :

```
[SUBJECT]
Ultra-realistic cinematic portrait of a young woman, character key visual,

[FACE STRUCTURE]
oval face shape, defined cheekbones, straight nose, balanced facial symmetry,
full natural lips slightly parted, intense dark brown eyes with sharp catchlight,
thick natural eyebrows, subtle asymmetry for realism,

[SKIN & MICRO DETAILS]
slightly tanned olive skin tone, realistic skin pores, micro imperfections,
subsurface scattering, natural skin roughness, no plastic skin,

[HAIR]
dark brown hair, loosely tied back, wet strands falling across face,
natural hair breakup, fine flyaway hairs,

[EXPRESSION & POSE]
serious, alert expression, subtle tension in eyes,
looking over shoulder, cinematic character presence,

[CINEMATOGRAPHY]
85mm lens, shallow depth of field, subject isolated,
center-weighted composition, portrait framing,

[LIGHTING]
soft key light + subtle rim light, moody contrast,
cold cinematic color grading, controlled highlights on skin,

[RENDER QUALITY]
ultra photorealistic, high dynamic range, film grain,
sharp focus on eyes, 4K, masterpiece,

[CONSTRAINTS]
clean neutral background, no environment, no distractions
```

---

# 🎯 2. Negative Prompt (non négociable)

Sans ça, tu perds le contrôle :

```
low quality, blurry, soft focus, deformed face, asymmetry errors,
extra fingers, bad anatomy, plastic skin, oversmooth skin,
cgi look, 3d render, cartoon, anime,
harsh shadows, overexposed highlights,
busy background, environment, objects, noise
```

---

# 🎯 3. Méthode PRO (là où tu fais probablement fausse route)

## Étape 1 — Génération brute

* Génère 20–50 images
* Même prompt
* Seeds différentes

👉 Objectif : trouver UNE base crédible (pas parfaite)

---

## Étape 2 — Verrouillage identité

* Reprends la meilleure image
* Passe en **img2img / image reference**
* Denoise faible (0.3–0.5)

👉 Là tu stabilises le visage

---

## Étape 3 — Standardisation studio

Tu figes :

* seed
* prompt
* paramètres

Et tu crées :

* face sheet
* variations expressions
* variations lumière

---

## Étape 4 — Cohérence long terme

Utilise :

* IP Adapter / Face reference
* ControlNet (pose / depth)

👉 Sinon ton personnage change à chaque génération

---

# 🎯 4. Paramètres recommandés (SDXL / Flux)

* Steps : 30–50
* CFG : 5–7 (plus = artefacts)
* Sampler : DPM++ 2M Karras
* Denoise (img2img) : 0.35–0.55

---

# ⚠️ Ce que tu dois corriger immédiatement

Tu penses encore “image par image”.

Un studio pense :

> **“pipeline reproductible sur 6 mois”**

Si ton personnage n’est pas :

* stable
* reconnaissable
* reproductible

→ ton projet est inutilisable en production.

---

# 🎯 Ce que tu devrais faire maintenant

1. Génère 30 images avec le prompt MASTER
2. Sélectionne les 3 meilleures
3. Reviens vers moi avec ces 3
4. Je t’aide à :

   * verrouiller l’identité
   * créer une vraie charte personnage exploitable

---

Si tu veux du niveau “Netflix / AAA”, tu dois arrêter de chercher le prompt parfait et construire un **système de contrôle visuel**.
