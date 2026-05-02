---
creation: 2026-05-02 à 15:35
source: tasks/audits/AUDIT_GLOBAL_2026-05-02.md
statut: en attente — 0/14 corrections appliquées
---

# Plan de corrections — Post-audit global
**District Zero EP01 · 2026-05-02**

---

## Légende priorité
- 🔴 BLOQUANT — ne pas lancer de run payant avant résolution
- 🟠 HAUTE — impact visuel ou fiabilité direct
- 🟡 NORMALE — qualité incrémentale
- ⚪ BASSE — post-EP01

---

## BLOC A — Prérequis absolus avant run payant (🔴 BLOQUANT)

| # | Axe | Fichier · ligne | Impact réel | Action | Statut |
|---|-----|----------------|-------------|--------|--------|
| A-1 | Visuel | `production/gen_location_refs.py` ligne 43 | 10 masters lieux générés avec JSON dégradé → tous les shots P1 commencent d'un état cassé | Vérifier que `--ultra` appelle `build_master_prompt_dop()` puis lancer le retake. Coût : $0.60 | ⏳ |
| A-2 | Tests | `pipeline/` — fichier inexistant | Corrections 1.1 + 2.3 + 4.2 sans test de non-régression → une modif future recrée la régression en silence | Créer `pipeline/test_shot_pipeline.py` : struct prompt P1, canonical default Nara, canonical Vale ≠ Nara | ⏳ |
| A-3 | Tests | `production/tests/` — fichier inexistant | `gen_shots.py` (script principal EP01) non testé | Créer `production/tests/test_gen_shots.py` : `build_scene_params()` priorité `lighting_context`, dry-run sans appel API | ⏳ |
| A-4 | Continuité | `production/dashboard.json` ligne 34 | `SCN_010` (poursuite = scène la plus critique) sans master plate | Lancer `gen_location_refs.py --loc int_service_spine_night` avec seed 110. Mettre à jour `master_plate_path` dans `dashboard.json` | ⏳ |

---

## BLOC B — Corrections de fond (🟠 HAUTE)

| # | Axe | Fichier · ligne | Impact réel | Action | Statut |
|---|-----|----------------|-------------|--------|--------|
| B-1 | Visuel | `pipeline/shot_pipeline.py` — `build_p1_prompt()` dict | Personnage inclus dans le prompt P1 alors que l'archi déclare "P1 = décor pur" → drift anatomique P2 sur Vale/Rook | Retirer la clé `"subject"` du JSON P1 pour les shots avec personnage. Ajouter paramètre `include_subject: bool = False`. Rebenchmark ArcFace Nara obligatoire après. | ⏳ |
| B-2 | Prompts | `production/gen_shots.py` — `extra_notes` ligne 45 | `emotion_intent` injecté en dernière position (zone d'attention T5 la plus faible) | Déplacer `emotion_intent` en première position du prompt P1. Il doit précéder la description technique. | ⏳ |
| B-3 | Architecture | `aiprod_adaptation/image_gen/storyboard.py` — `engine.py` | `character_briefs` ajouté à `StoryboardGenerator` mais jamais passé par `engine.py` → correction 2.4 inerte | Dans `engine.py` / `run_pipeline_with_images()`, charger `characters.json` et passer `character_briefs=` à `StoryboardGenerator`. 2 lignes. | ⏳ |
| B-4 | Continuité | `aiprod_adaptation/core/pass3_shots.py` — `_compute_feasibility_score()` | `anchor_strength = 0.9` assigné si `reference_location_id` présent, sans vérifier que l'image existe réellement → `ContinuityChecker.B1` valide un score mensonger | Résoudre `reference_pack.location_reference_url(location_id)` avant d'assigner 0.9. Si URL vide → 0.5. | ⏳ |
| B-5 | Architecture | `pipeline/shot_pipeline.py` — `SceneP1Params` dataclass | `character_canonical=""` ou `seed=0` → prompt dégradé sans signal d'erreur | Ajouter `__post_init__` avec `assert` sur les champs non vides critiques (`character_canonical`, `scene_id`). | ⏳ |
| B-6 | Continuité | `production/gen_shots.py` — boucle shots | Chaque shot généré de façon totalement indépendante → zéro continuité intra-scène | Ajouter état `prev_shot_result` dans la boucle et passer l'URL du dernier frame à P2 comme `last_frame_url` | ⏳ |

---

## BLOC C — Qualité incrémentale (🟡 NORMALE)

| # | Axe | Fichier · ligne | Impact réel | Action | Statut |
|---|-----|----------------|-------------|--------|--------|
| C-1 | Prompts | `pipeline/shot_pipeline.py` ligne 131 | `json.dumps()` → tokens `:`, `{`, `"` consomment attention T5 sans signal visuel | Écrire `build_p1_prompt_prose()` : même data en prose structurée (DOP → lieu → lumière → grade → compo → perso). Benchmarker sur 3 shots avant switch. | ⏳ |
| C-2 | Prompts | `production/gen_shots.py` ligne 33-39 | Hex codes `#1C2B35` → sémantiquement opaques pour T5-XXL | Remplacer hex par leur équivalent prose ou supprimer au profit de `grade_intent` + `dop_ref` uniquement. | ⏳ |
| C-3 | Visuel | `aiprod_adaptation/image_gen/storyboard.py` ligne 137 | `parts[:5]` tronque les briefs de lieu → IRE, Kelvin, ratios DOP perdus dans le moteur générique | Remplacer `parts[:5]` par `parts[:12]` ou cap `[:500]` en caractères. | ⏳ |
| C-4 | Continuité | `production/storyboard.json` — `scenes_axis` | Axes 180° documentés mais aucun code ne les valide à la génération | Ajouter validation post-génération dans `gen_shots.py` : comparer `composition` entre shots consécutifs d'une scène. Warning si "left" → "right" sans coupe. | ⏳ |
| C-5 | Tests | `production/benchmark_characters.py` ligne 63 | `_score_arcface(app, img, img)` = 1.0 garanti → zéro valeur diagnostique | Ajouter `--cross` qui compare chaque ref contre la baseline `nara_hero_ref_01.png`. Documenter que le vrai score est mesuré à la génération. | ⏳ |
| C-6 | Architecture | `production/gen_shots.py` — boucle top-level | JSON rechargés potentiellement plusieurs fois ; crash sur JSON corrompu mi-run sans message lisible | Charger `characters.json` + `locations.json` une seule fois en tête de `run()`. Ajouter `try/except` avec message explicite sur lecture JSON. | ⏳ |

---

## BLOC D — Post-EP01 (⚪ BASSE)

| # | Axe | Description | Action |
|---|-----|-------------|--------|
| D-1 | Architecture | Deux pipelines non connectés (moteur générique AIPROD ↔ pipeline EP01) | Créer `production/compile_ep01.py` : exécuter Pass 1-4 sur `district_zero_ep01.fountain` et valider le résultat contre `storyboard.json` |
| D-2 | Architecture | `production/reference_pack.json` inexistant → `style_block` de la série non injecté dans le moteur générique | Créer `production/reference_pack.json` minimal avec `style_block` + 5 personnages + 10 lieux |
| D-3 | Architecture | `production/__init__.py` — pas de `bootstrap()` centralisé | Consolider `_load_env()` + `sys.path.insert` dans `production/__init__.py` exposant `bootstrap()` appelé une fois |
| D-4 | Tests | `test_consistency.py` : fixtures génériques, pas les cas EP01 réels | Ajouter test d'intégration qui charge `storyboard.json` réel et valide les invariants EP01 (SCN_010 axis, SCN_004 continuité) |
| D-5 | Visuel | `VideoRequest.last_frame_hint_url` et `character_reference_urls` existent mais jamais alimentés | Implémenter dans `gen_shots.py` l'alimentation de `last_frame_hint_url` pour le futur pipeline vidéo |

---

## Ordre d'exécution recommandé

```
Session 1 (maintenant, avant run payant) :
  → A-2 : test_shot_pipeline.py
  → A-3 : test_gen_shots.py
  → B-5 : __post_init__ SceneP1Params
  → Committer les corrections déjà appliquées + les nouveaux tests
  → CI verte → GO pour les runs payants

Session 2 (premier run payant) :
  → A-1 : retake 10 masters lieux ($0.60)
  → A-4 : master plate SCN_010
  → Valider masters humainement avec le DA

Session 3 (validation personnages) :
  → B-1 : retirer "subject" de P1 + rebenchmark ArcFace Nara
  → 1 shot test par personnage secondaire (Vale, Elian, Mira, Rook) — ~$0.32
  → Score ArcFace ≥ 0.80 validé → GO pour les 35 shots

Session 4 (run 35 shots EP01) :
  → B-2 : déplacer emotion_intent en premier
  → B-3 : brancher character_briefs dans engine.py
  → B-6 : last_frame_url intra-scène
  → Run 35 shots EP01 complet (~$2.80)
```

---

## Règles absolues (rappel)

- Jamais d'appel API sans GO explicite
- ArcFace Nara ≥ 0.9378 avant tout shot réel après correction B-1
- Pas de `# type: ignore`
- `SCN_010` ne génère pas de shot tant que `master_plate_path != null`
