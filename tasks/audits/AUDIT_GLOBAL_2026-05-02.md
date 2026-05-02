---
creation: 2026-05-02 à 15:30
type: audit-global
axes: architecture · qualité-visuelle · continuité · prompts · tests · roadmap
rôle: CTO + Directeur Artistique + Producteur Exécutif
statut: verdict de production — zéro validation de confort
---

# AUDIT GLOBAL — AIPROD_V2 / District Zero EP01
**2026-05-02 · Post-corrections pipeline (4/5 appliquées)**

---

## AXE 1 — ARCHITECTURE CODE

### 1.A — Dualité de pipeline non réconciliée ⚠ CRITIQUE

**Problème** : Deux pipelines cohabitent sans passerelle.  
- `aiprod_adaptation/` = moteur générique text→IR→shots (Pass 1-4, `engine.py`, 1072 tests)  
- `pipeline/shot_pipeline.py` + `production/` = pipeline EP01 artisanal (Replicate API directe, zéro intégration avec le moteur générique)

Les deux n'échangent pas de données. Le `storyboard.json` EP01 a été écrit à la main, pas produit par Pass 1-3. Le moteur générique ne sait pas que EP01 existe. EP01 ne peut pas bénéficier des améliorations de Pass 3 (continuity flags, 180° guard, beat_type routing).

**Impact** : Toute amélioration du moteur générique (`cinematography_rules_v3.py`, `dop_style_rules.py`, `visual_bible.py`) n'atteint jamais la production réelle. On maintient deux stacks en parallèle indéfiniment.

**Action** : Définir `production/storyboard.json` comme le format cible de Pass 4 pour EP01. Ajouter un script `production/compile_ep01.py` qui exécute Pass 1-4 sur `district_zero_ep01.fountain` et valide le résultat contre `storyboard.json`. Pas une refonte — un pont.

---

### 1.B — `dashboard.py` : rechargement JSON à chaque appel

**Fichier** : `production/dashboard.py` — `_load()` ligne 8  
**Problème** : Chaque appel à `load_character()`, `load_location()`, `load_scene()` relit le fichier JSON depuis le disque. Dans `gen_shots.py`, chaque shot fait 2-3 appels → le storyboard (35 shots) provoque 70-100 lectures disque inutiles.  
**Impact** : Mineur en performance, mais symptomatique : aucun objet `ProductionState` centralisé. Si un fichier est corrompu pendant un run, les 30 premiers shots réussissent et les 5 suivants crashent silencieusement.  
**Action** : Charger tous les JSON une fois en tête de `run()` dans `gen_shots.py` (déjà fait pour `grade.json` et `storyboard`). Appliquer le même pattern à `locations.json` et `characters.json`.

---

### 1.C — `_load_env()` et `sys.path.insert` à chaque import

**Fichiers** : `production/gen_shots.py` ligne 17, `gen_location_refs.py`, `benchmark_characters.py`  
**Problème** : Chaque script production manipule `sys.path` manuellement. `_load_env()` n'est pas un singleton — si appelé deux fois, il relit le `.env`.  
**Impact** : Acceptable pour des scripts CLI ponctuels. Devient un problème si ces modules sont importés dans des tests ou dans un orchestrateur.  
**Action** : Consolider dans un `production/__init__.py` qui expose `bootstrap()` appelé une fois. Pas urgent — noter pour la prochaine session.

---

### 1.D — `SceneP1Params` sans validation explicite des champs critiques

**Fichier** : `pipeline/shot_pipeline.py` — `SceneP1Params` dataclass  
**Problème** : `character_canonical` peut être une chaîne vide, `seed` peut être 0, `composition` peut être `""`. Aucune validation à la construction. Un `SceneP1Params` invalide part en API sans signal d'erreur.  
**Impact** : Un shot Mira avec `canonical=""` part avec un prompt tronqué → résultat silencieusement dégradé, pas détecté avant de voir l'image.  
**Action** : Convertir en `pydantic.BaseModel` ou ajouter `__post_init__` avec assertions minimales sur les champs non vides.

---

### 1.E — `benchmark_characters.py` : auto-comparaison intra-image

**Fichier** : `production/benchmark_characters.py` ligne 63  
**Problème** : `_score_arcface(app, img, img)` compare une image à elle-même → score toujours 1.0. Ce n'est pas un benchmark ArcFace, c'est une vérification que le visage est détectable. Le vrai benchmark (score entre le shot généré et la référence) n'existe que dans `run_shot()` pendant la génération réelle.  
**Impact** : La commande "valider les portraits de référence" retourne 1.0 pour tous → aucune valeur diagnostique. Les portraits dégradés passent sans signal.  
**Action** : Remplacer par `_score_arcface(app, ref_img, canonical_img)` en comparant la ref existante contre `nara_hero_ref_01.png` comme baseline. Sinon supprimer la commande et documenter que le score ArcFace est mesuré à la génération.

---

## AXE 2 — QUALITÉ VISUELLE & ARTISTIQUE

### 2.A — P1 génère le personnage + le décor dans le même appel : erreur fondamentale de méthode

**Fichier** : `pipeline/shot_pipeline.py` — `build_p1_prompt()` ligne 126  
**Problème** : Le prompt P1 contient `"subject": {"action": ..., "costume": character_canonical}`. FLUX.2 Pro reçoit donc la description complète du personnage dans le master plate. La logique déclarée du pipeline est :
- P1 = master décor (seed fixe par scène → cohérence décor)
- P2 = face inpainting (injecter le personnage)

Mais P1 inclut le personnage. Résultat : le seed fixe de scène **pose le personnage dans le décor dès P1**, alors que la référence personnage n'est injectée qu'en P2. P2 fait du face inpainting sur un master qui a déjà halluciné le personnage selon le prompt textuel. La tension entre hallucination P1 et inpainting P2 est la source principale de drift anatomique.  
**Impact réel** : Le score ArcFace 0.9378 est excellent malgré ça — mais c'est Nara, dont le canonical est le plus précis du repo. Vale (4 lignes de canonical), Rook (5 lignes) vont drifter nettement plus.  
**Action corrective** : Retirer `"subject"` du prompt P1 pour les shots avec personnage. P1 = décor seul (seed fixe). P2 = personnage inpainté. C'est architecturalement plus propre et produira un décor plus stable. **Nécessite rebenchmark ArcFace Nara avant déploiement.**

---

### 2.B — La seed de scène est partagée entre TOUS les shots d'une scène

**Fichier** : `production/dashboard.json` + `gen_shots.py` ligne 42  
**Problème** : Tous les shots d'une scène utilisent la même seed P1 (SCN_002 = seed 22 pour SHOT_001, SHOT_002, SHOT_003). La seed fixe garantit la cohérence du décor entre shots, ce qui est le comportement voulu. Mais elle signifie aussi que le décor P1 est strictement identique quel que soit le `shot_type` (wide, close, medium). Le plan 32mm wide et le plan 50mm close de SCN_002 ont le même master plate background.  
**Impact** : Les plans wide et close d'une même scène ont le même arrière-plan non recadré → pas de profondeur de champ cohérente entre les shots d'une scène. Un close-up sur le wrist display devrait avoir le corridor en bokeh, pas une copie pixel-parfaite du wide.  
**Action** : Conserver la seed scène pour les plans wide et medium. Pour les plans close-up et extreme_close_up, dériver la seed : `shot_seed = scene_seed + shot_index`. Cela garantit cohérence de scène sur les plans larges et variété de bokeh sur les gros plans.

---

### 2.C — `build_location_prompt()` dans `gen_location_refs.py` : JSON stringifié (pré-existant, non corrigé)

**Fichier** : `production/gen_location_refs.py` ligne 43  
**Problème** : `build_location_prompt()` (ancienne fonction) sérialise un dict Python en JSON string et l'envoie comme prompt texte. T5-XXL encode les guillemets JSON, les deux-points et les accolades comme des tokens qui ne portent aucune information sémantique visuelle. La nouvelle fonction `build_master_prompt_dop()` corrige ça — mais les 10 masters n'ont pas encore été retournés.  
**Impact** : Les masters existants ont été générés avec le prompt JSON dégradé. Si un retake est lancé sans confirmer quelle fonction est appelée, le résultat peut être identique.  
**Action** : Vérifier que `--ultra` appelle `build_master_prompt_dop()`, pas `build_location_prompt()`. Retourner les 10 masters. Coût : $0.60.

---

### 2.D — `_condense_location()` tronque à 5 segments : détruit le DOP brief

**Fichier** : `aiprod_adaptation/image_gen/storyboard.py` ligne 137  
**Problème** : `parts[:5]` coupe les briefs de lieu après le 5ème token CSV. Un brief de lieu comme `"industrial corridor, wet concrete, halogen cage lights, 2700K orange key, 4:1 ratio, deep vanishing point, pipe clusters overhead, steam venting, no natural light"` perd tout ce qui est au-delà de `"2700K orange key"`. IRE, ratios, références DOP, textures — tout tronqué.  
**Impact** : Pour le moteur générique AIPROD, chaque shot de lieu est généré depuis 5 mots au lieu d'un brief complet. La qualité visuelle du moteur générique est structurellement plafonnée par cette ligne.  
**Action** : Remplacer `parts[:5]` par `parts[:12]` ou supprimer le cap et remplacer par un cap de longueur en caractères (`[:500]`).

---

### 2.E — Le `portrait_brief` maintenant injecté dans `StoryboardGenerator` n'est jamais passé en pratique

**Fichier** : `aiprod_adaptation/image_gen/storyboard.py` — `character_briefs` paramètre ajouté aujourd'hui  
**Problème** : Le paramètre `character_briefs` a été ajouté, mais aucun code dans `engine.py` ou `cli.py` ne le renseigne. `StoryboardGenerator` est instancié sans `character_briefs` dans tous les points d'entrée existants → `_get_portrait_footer()` retourne toujours `_PORTRAIT_FOOTER` générique.  
**Impact** : La correction 2.4 est structurellement correcte mais inerte. Le bricolage est fait — le branchement ne l'est pas.  
**Action** : Dans `engine.py`, `run_pipeline_with_images()`, charger `characters.json` et passer `character_briefs=characters_data` à `StoryboardGenerator`. 2 lignes de code.

---

## AXE 3 — COHÉRENCE NARRATIVE & CONTINUITÉ

### 3.A — Aucune continuité shot-à-shot dans le pipeline EP01

**Fichier** : `production/gen_shots.py` — boucle `for shot in shots_to_run`  
**Problème** : Chaque shot est généré de façon totalement indépendante. Il n'y a aucun mécanisme de :
- `last_frame_hint_url` (existant dans `VideoRequest` mais jamais utilisé en image)
- Position des personnages entre shots
- État de l'éclairage entre shots d'une même scène
- Cohérence de la prise de vue entre SHOT_001 et SHOT_002 de la même scène

En cinéma, le raccord s'assure que le personnage n'a pas changé de côté entre deux plans. Dans ce pipeline, SHOT_002 de SCN_002 (close sur le wrist display) peut avoir le personnage entré depuis la gauche alors que SHOT_001 (wide) le montre depuis la droite.  
**Impact** : Toutes les coupes dans l'épisode sont potentiellement des jump cuts non intentionnels. Les axes 180° documentés dans `storyboard.json` (`scenes_axis`) sont uniquement des commentaires — pas de garde en code.  
**Action** : Ajouter dans `gen_shots.py` un état `prev_shot_result` passé à P2 comme `last_frame_url`. Faible coût d'implémentation. Impact de continuité maximal.

---

### 3.B — `reference_anchor_strength` est calculé binaire, pas mesuré

**Fichier** : `aiprod_adaptation/core/pass3_shots.py` — `_compute_feasibility_score()`  
**Problème** : `anchor_strength = 0.9 if reference_location_id else 0.5`. C'est un flag masqué en float. La valeur 0.9 est assignée dès qu'un `reference_location_id` est présent, sans vérifier si l'image de référence du lieu existe réellement dans `reference_pack.json`. `LocationPrepass` est marqué `⏳ À implémenter` dans `PRODUCTION_RULES.md`.  
**Impact** : `ContinuityChecker.B1` valide `reference_anchor_strength >= 0.8` et passe sur tous les shots — mais le décor de référence n'a jamais été injecté. La validation est silencieusement mensongère.  
**Action** : Dans `pass3_shots.py`, résoudre réellement `reference_pack.location_reference_url(location_id)` avant d'assigner 0.9. Si l'URL est vide, assigner 0.5. Ce n'est pas `LocationPrepass` complet, mais ça rend le score honnête.

---

### 3.C — Axes 180° du storyboard : commentaires, zéro garde de code

**Fichier** : `production/storyboard.json` — `scenes_axis`  
**Problème** : Les 11 axes de scène (dont SCN_010 "CRITICAL: maintain for chase logic") sont des métadonnées JSON jamais lues par `gen_shots.py`. La règle 180° la plus critique (la scène de course) n'a aucun mécanisme de validation dans le pipeline.  
**Impact** : Aucun signal d'erreur si deux shots consécutifs du même scène inversent la direction de course. L'editeur découvre les jump cuts en post-montage.  
**Action** : Ajouter une validation post-génération dans `gen_shots.py` : pour chaque scène avec `scenes_axis`, comparer la `composition` du shot courant contre celle du shot précédent et lever un warning si "left" devient "right" sans coupe justifiée.

---

### 3.D — SCN_010 manque son master plate

**Fichier** : `production/dashboard.json` ligne 34  
**Problème** : `"SCN_010": { "master_plate_path": null }`. SCN_010 est la scène de poursuite (le point dramatique le plus intense de l'épisode). Son lieu est `int_service_spine_night` — partagé avec SCN_008. Le master plate de SCN_010 est `null` alors que la course est le shot le plus critique à maîtriser.  
**Impact** : Tout shot avec personnage dans SCN_010 utilise la seed scène (110) mais sans master plate pré-généré. Le run démarre en aveugle.  
**Action** : Lancer `gen_location_refs.py --loc int_service_spine_night` avec seed 110 (la seed de SCN_010, pas la seed de SCN_008 qui est 88). Mettre à jour `dashboard.json`.

---

## AXE 4 — PROMPTS & INTENTION CRÉATIVE

### 4.A — `build_p1_prompt()` : JSON stringifié envoyé à T5-XXL

**Fichier** : `pipeline/shot_pipeline.py` ligne 131 — `return json.dumps(doc)`  
**Problème** : FLUX.2 Pro utilise T5-XXL comme encodeur texte. T5-XXL est entraîné sur du texte naturel, pas du JSON. Un prompt comme `{"production_note": "DISTRICT ZERO — Episode 01 — SCN_002..."}` est encodé token par token — les `{`, `"`, `:`, `}` consomment des slots d'attention sans apporter de signal sémantique. Un brief en prose de 200 mots au même token budget transmet plus d'information visuelle qu'un JSON de 200 tokens.  
**Impact** : Les prompts actuels sont techniquement corrects mais sous-optimaux. Le score ArcFace 0.9378 est atteint malgré ça, pas grâce à ça.  
**Action** : Écrire `build_p1_prompt_prose()` qui sérialise le même `SceneP1Params` en prose structurée (intro DOP → lieu → lumière → grade → composition → personnage — dans cet ordre). Benchmarker sur 3 shots Nara avant de switcher.

---

### 4.B — `emotion_intent` et `audio_brief` : présents dans `storyboard.json`, absents du prompt

**Fichier** : `production/gen_shots.py` ligne 45 — `extra_notes`  
**Problème** : `extra_notes` = `"Camera spec: {shot['camera_spec']}. Emotion: {shot['emotion_intent']}. Character state: {state}."`. L'`emotion_intent` est injecté en fin de `extra_notes`, qui se retrouve en fin de `production_note`, qui est la première clé d'un JSON — donc après les tokens de structure JSON → dans le segment où T5-XXL a l'attention la plus diffuse.  
L'`audio_brief` n'est pas injecté du tout. Or un audio brief comme `"Wrist display amber beep — once, twice, then gone"` contient une information de rythme dramatique directement exploitable pour l'image.  
**Impact** : L'intention dramatique la plus précise du storyboard (`emotion_intent`) est dans la zone de plus faible attention du modèle. C'est l'inverse de ce qu'un DA ferait.  
**Action** : Déplacer `emotion_intent` en première position du prompt P1, avant la description technique. Le modèle doit lire l'émotion avant de lire l'ARRI.

---

### 4.C — `colour_desc` : les hex codes ne sont pas lisibles par T5-XXL

**Fichier** : `production/gen_shots.py` ligne 33-39 — `build_scene_params()`  
**Problème** : `colour_desc` contient `"Dominant: #1C2B35. Accent: #B86010. Blacks: #05080A."`. T5-XXL n'associe pas `#1C2B35` à "dark teal-grey". Les hex codes sont sémantiquement opaques pour un encodeur texte.  
**Impact** : La couleur du grade est perdue. `grade.json` contient `"grade_intent"` en prose (Deakins, desaturated teals, crushed blacks) — qui lui est encodé. Les hex codes ajoutent du bruit sans signal.  
**Action** : Remplacer les hex codes par leurs équivalents prose. `#1C2B35` → "deep teal-steel dark". Ou tout simplement ne garder que `grade_intent` + `dop_ref` et supprimer les hex.

---

### 4.D — `style_block` dans `ReferencePack` jamais alimenté pour EP01

**Fichier** : `aiprod_adaptation/image_gen/reference_pack.py` — `style_block`  
**Problème** : `PRODUCTION_RULES.md` Règle #0 définit un `style_block` immuable pour la série. `reference_pack.json` n'existe pas dans `production/` — seulement dans `preproduction/district_zero/` (archive). Le moteur générique utilise `ReferencePack.style_block` pour concaténer le style à chaque prompt de personnage et de lieu. Pour EP01, ce mécanisme est mort-né.  
**Impact** : Le style_block de la série (ARRI, teal-steel, practicals only, no HDR) n'est pas systématiquement injecté dans le moteur générique pour EP01.  
**Action** : Créer `production/reference_pack.json` minimal avec `style_block` issu de `PRODUCTION_RULES.md` Règle #0, les 5 personnages et les 10 lieux avec `reference_image_urls` (après génération). C'est le pont entre le moteur générique et la production EP01.

---

## AXE 5 — TESTS & FIABILITÉ

### 5.A — Zéro test sur `pipeline/shot_pipeline.py`

**Constat** : 1072 tests couvrent le moteur générique. Zéro test ne couvre `pipeline/shot_pipeline.py` — le code qui génère réellement les images EP01.  
**Ce qui n'est pas testé** :
- `build_p1_prompt()` : structure du JSON, présence des champs obligatoires, que `character_canonical` est bien injecté
- `build_p2_prompt()` : que le nom du personnage et son canonical sont correctement formatés
- `SceneP1Params` : que les defaults sont sains, que `character_canonical` est `LOCKED_NARA_CANONICAL` par défaut
- `run_shot()` : aucun test de la logique d'orchestration (sans appel API réel — un mock Replicate suffit)  

**Impact** : La correction 1.1 (multi-perso) qu'on vient d'appliquer n'a aucun test de non-régression. Si quelqu'un modifie `build_p1_prompt()` demain, rien ne détecte la régression avant de voir les images.  
**Action** : Créer `pipeline/test_shot_pipeline.py` avec au minimum : test de la structure du prompt P1, test que `character_canonical` par défaut = `LOCKED_NARA_CANONICAL`, test que Vale reçoit son propre canonical.

---

### 5.B — Zéro test sur `production/gen_shots.py`

**Constat** : Même diagnostic que 5.A. Le script principal de génération EP01 n'est pas testé.  
**Ce qui n'est pas testé** :
- `build_scene_params()` : que `lighting_context` est prioritaire sur `lighting_brief` (correction 4.2)
- Dry-run : qu'il affiche le bon contenu sans appeler l'API
- Chargement des JSON : qu'une clé manquante lève une erreur lisible  

**Action** : Créer `production/tests/test_gen_shots.py` avec des mocks JSON et un mock `run_shot`. 30 lignes, 5 tests. Valeur élevée.

---

### 5.C — `test_continuity.py` ne teste pas les cas EP01 réels

**Fichier** : `aiprod_adaptation/tests/test_consistency.py`  
**Problème** : Les fixtures utilisent des scènes génériques (`"SCN_001"`, `"Nara scans the perimeter."`). Aucun test ne vérifie la règle 180° de SCN_010, la continuité de SCN_004 et SCN_011 (même appartement, même axe), ou le fait que SCN_010 n'a pas de master plate.  
**Impact** : La suite de tests valide la logique de `ContinuityChecker` en isolation — pas son comportement sur le contenu réel de l'épisode.  
**Action** : Ajouter un test d'intégration qui charge `storyboard.json` réel et valide les invariants EP01 documentés.

---

### 5.D — `benchmark_characters.py` : auto-score = 1.0 toujours (voir 1.E)

Score auto-comparaison `_score_arcface(app, img, img)` = 1.0 garanti. Aucune valeur diagnostique. Le seul vrai benchmark est `run_shot()` avec la vraie API. La suite de tests n'a aucun moyen de détecter un portrait dégradé sans appel API.

**Action** : Ajouter une commande `benchmark --cross` qui compare chaque portrait de référence existant contre la baseline `nara_hero_ref_01.png`. Score != 1.0 → information réelle.

---

### 5.E — Le pipeline peut casser silencieusement sur 4 scénarios non détectés

| Scénario | Signal actuel | Signal requis |
|----------|--------------|---------------|
| `character_canonical = ""` dans `SceneP1Params` | Aucun — prompt P1 valide sans le sujet | `ValueError` à la construction |
| `lighting_context` absent dans un shot → `None` → `[:200]` → `TypeError` | `AttributeError: 'NoneType' object has no attribute '__getitem__'` en production | Géré par `or location["lighting_brief"]` (déjà corrigé) mais pas testé |
| API Replicate retourne une URL vide | `_download("")` → `urllib.error.URLError` → exception non catchée → run partiel sans métrique | Try/catch + entry `"flag_retake": True` dans JSONL |
| Master plate d'un lieu manquant + shot env-only | `shutil.copy2` échoue silencieusement si `location_ref.exists() == False` → entry JSONL avec `result_1x: null` | Log WARNING + exit avec code non-zero si flag requis |

---

## AXE 6 — ROADMAP & PRIORITÉS

### 6.A — 3 choses à corriger immédiatement (impact maximal)

**1. Retourner les 10 masters lieux avec `build_master_prompt_dop()` ($0.60)**  
C'est le fondement de tout. P1 pose son décor à partir du master plate. Des masters générés avec du JSON sont des fondations cassées. Toutes les corrections de prompts sont inutiles si les masters restent du JSON de 2026-04-28. Cette action débloque immédiatement la qualité visuelle.  
Commande : `python production\gen_location_refs.py --ultra --dry-run` → vérifier → `python production\gen_location_refs.py --ultra`

**2. Créer `pipeline/test_shot_pipeline.py` + `production/tests/test_gen_shots.py`**  
Les corrections qu'on vient d'appliquer (1.1, 4.2, 2.3) n'ont aucun test de non-régression. Si quelqu'un modifie `SceneP1Params` dans 3 semaines, Vale recevra à nouveau le canonical de Nara et personne ne le saura. Avant le prochain run payant, écrire ces tests.

**3. Retirer `"subject"` du prompt P1 (correction 2.A)**  
P1 = décor pur. P2 = personnage pur. C'est l'architecture déclarée — l'implémenter vraiment. Cette modification seule réduit la tension entre P1 et P2 qui cause le drift anatomique sur les personnages non-Nara. Rebenchmark ArcFace Nara obligatoire après.

---

### 6.B — Quoi ignorer pour l'instant

- **`LocationPrepass` complet** : la vraie implémentation demande un mécanisme de prepass dédié. Le gain marginal vs le coût d'implémentation est faible tant que les masters ne sont pas générés avec `build_master_prompt_dop()`.
- **`_condense_location()` tronquée** : le moteur générique AIPROD n'est pas sur le chemin EP01 direct. Corriger après avoir livré EP01.
- **Pont `pass1-4` → `production/storyboard.json`** : architecture ambitieuse, non critique pour la livraison. Le storyboard manuel est de qualité studio — ne pas le sacrifier pour un pipeline automatisé non validé.
- **`dashboard.py` rechargements JSON** : performance négligeable sur 35 shots.

---

### 6.C — Le vrai goulot d'étranglement

Le pipeline EP01 a **deux blocages concrets** avant un épisode livrable :

**Blocage 1 — Masters lieux** (corrigeable en 1 run, $0.60)  
10 masters générés avec du JSON dégradé. Tout shot P1 s'appuie dessus. Aucune correction de prompt n'aide tant que ces images ne sont pas retournées.

**Blocage 2 — Personnages Vale, Elian, Mira, Rook** (corrigeable en 1 run, ~$0.20)  
Les portraits de référence existent pour Nara. Vale, Elian, Mira, Rook ont `ref_image` dans `characters.json` mais le score ArcFace n'a jamais été validé pour eux avec le nouveau pipeline multi-perso. Avant de générer les 35 shots EP01, générer 1 shot test par personnage secondaire et vérifier que le score ≥ 0.80.

Ce qui est prêt et solide :
- Le storyboard.json est de niveau studio (axes, emotion_intent, lighting_context, audio_brief)
- Le grade.json est complet et correctement injecté
- La correction multi-perso (1.1) est architecturalement propre
- Les 1072 tests du moteur générique passent
- Les seeds sont verrouillées et documentées

Ce qui manque pour livrer EP01 :
- 10 masters lieux retournés avec les bons prompts
- 1 shot test par personnage secondaire validé ArcFace
- Tests pipeline/shot_pipeline.py (avant tout run payant à grande échelle)

---

## VERDICT — 10 lignes

Le projet est sérieux. Le storyboard est meilleur que ce que la plupart des productions humaines produisent au stade EP01. Le moteur générique (1072 tests, Pass 1-4, `cinematography_rules_v3`, `visual_bible`) est une infrastructure solide et bien testée — mais elle tourne à vide sur EP01 parce que les deux stacks ne se parlent pas. La correction multi-perso d'aujourd'hui est la bonne architecture. Les masters lieux générés en JSON dégradé sont le seul vrai blocage de qualité visuelle immédiat. Le benchmark ArcFace `_score_arcface(img, img) = 1.0` est un mensonge de confort — le vrai score ne sera connu qu'après génération. L'absence totale de tests sur `pipeline/shot_pipeline.py` est le risque de régression le plus probable dans les prochaines sessions. Le projet est à 2 runs payants d'un premier épisode générable : les 10 masters lieux ($0.60) + les 4 personnages secondaires test ($0.32). Tout le reste est de la qualité incrémentale.

---

*Sources lues : `pipeline/shot_pipeline.py`, `production/gen_shots.py`, `production/gen_location_refs.py`, `production/benchmark_characters.py`, `production/dashboard.py`, `production/storyboard.json`, `production/grade.json`, `production/characters.json`, `production/dashboard.json`, `aiprod_adaptation/image_gen/storyboard.py`, `aiprod_adaptation/image_gen/reference_pack.py`, `aiprod_adaptation/image_gen/character_prepass.py`, `aiprod_adaptation/core/engine.py`, `aiprod_adaptation/core/pass1_segment.py`, `aiprod_adaptation/core/pass2_visual.py`, `aiprod_adaptation/core/pass3_shots.py`, `aiprod_adaptation/core/pass4_compile.py`, `aiprod_adaptation/core/visual_bible.py`, `aiprod_adaptation/core/quality_gate.py`, `aiprod_adaptation/core/run_metrics.py`, `aiprod_adaptation/core/rules/cinematography_rules_v3.py`, `aiprod_adaptation/core/rules/dop_style_rules.py`, `aiprod_adaptation/consistency/continuity_checker.py`, `aiprod_adaptation/consistency/color_manager.py`, `aiprod_adaptation/models/schema.py`, `aiprod_adaptation/video_gen/video_request.py`, `aiprod_adaptation/tests/test_consistency.py`, `aiprod_adaptation/tests/test_pass3_cinematic.py`, `aiprod_adaptation/tests/test_image_gen.py`, `tasks/PRODUCTION_RULES.md`, `tasks/lessons.md`*
