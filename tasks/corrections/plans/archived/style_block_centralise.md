---
title: Style block centralisé dans reference_pack.json
creation: 2026-04-27 à 10:15
priority: low
status: completed
---

## Objectif

Centraliser le bloc stylistique commun (caméra, grain, tones, lumière) dans un champ unique `"style_block"` au niveau racine de `reference_pack.json`. Ce bloc doit être automatiquement concaténé à la fin de chaque prompt de personnage et de lieu lors de la génération, sans modifier les prompts existants.

Actuellement, les mentions `ARRI Alexa 35`, `chiaroscuro`, `4K hyperrealistic`, `cinematic quality` etc. sont dupliquées dans chaque prompt individuel. Si on veut changer le rendu global de la série (ex: passer à un étalonnage plus chaud, ou changer de style caméra), il faut modifier 11+ entrées à la main.

---

## Étape 1 — Ajouter `style_block` dans `reference_pack.json`

Ajouter un champ `"style_block"` au niveau racine du JSON, avant `"characters"` :

```json
{
  "style_block": "Photorealistic cinematic quality, ARRI Alexa 35, anamorphic lens, 4K hyperrealistic. Color grading: desaturated teal and steel-blue dominant, selective warm amber highlights in practical sources. No oversaturation, no fantasy glow, no HDR clipping. Natural grain texture, corroded metal surfaces, wet concrete, humid air with visible light particles. Lighting logic: practical sources only (halogen cage lights, neon, water reflections, emergency strips). Naturally contrasted chiaroscuro.",
  "characters": { ... },
  "locations": { ... }
}
```

Le bloc stylistique doit décrire uniquement ce qui est **global et invariant** : caméra, étalonnage, grain, logique lumière. Tout ce qui est spécifique à un personnage ou un lieu reste dans son propre prompt.

---

## Étape 2 — Nettoyer les prompts existants

Retirer de chaque prompt individuel les fragments déjà couverts par `style_block` :
- `4K hyperrealistic, cinematic quality, naturally contrasted chiaroscuro` → à supprimer des personnages
- `ARRI Alexa 35` → à supprimer des lieux
- `photorealistic cinematic` → à supprimer des lieux (déjà couvert)

**Ne pas supprimer** les éléments propres au lieu ou personnage (tones spécifiques, éclairage de scène, ambiance particulière).

---

## Étape 3 — Modifier `reference_pack.py` (ou l'équivalent dans la pipeline)

Dans le code qui construit le prompt final envoyé à FLUX, concatener :

```python
final_prompt = entry["prompt"].rstrip(" .,") + ". " + pack.get("style_block", "")
```

L'injection doit se faire :
- Pour les prompts de **personnages** dans `character_prepass.py` ou `replicate_adapter.py`
- Pour les prompts de **lieux** dans `_build_input()` de `replicate_adapter.py`

Le `style_block` est optionnel (`.get()` avec fallback vide) pour ne pas casser les tests existants.

---

## Étape 4 — Mettre à jour les tests

Vérifier que `test_image_gen.py` couvre le cas d'injection du `style_block` :
- Test : prompt final contient bien le style_block quand présent dans le pack
- Test : prompt final est inchangé quand `style_block` absent du pack (rétrocompatibilité)

---

## Étape 5 — Vérification visuelle (1 shot pilote)

Lancer un run sur `SCN_001_SHOT_001` uniquement pour vérifier que le prompt final assemblé est correct et que le rendu visuel est cohérent avec les runs validés.

**À demander confirmation avant le lancer.**

---

## Fichiers impactés

| Fichier | Action |
|---|---|
| `preproduction/district_zero/reference_pack.json` | Ajout `style_block` + nettoyage prompts |
| `aiprod_adaptation/image_gen/replicate_adapter.py` | Injection `style_block` dans `_build_input()` |
| `aiprod_adaptation/image_gen/character_prepass.py` | Injection `style_block` si applicable |
| `aiprod_adaptation/tests/test_image_gen.py` | 2 nouveaux tests |

---

## Critère de succès

- Un seul endroit à modifier pour changer le rendu global de la série
- 93 tests passent toujours après les changements
- Run pilote sur SCN_001 validé visuellement
