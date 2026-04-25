---
title: Bilan global — AIPROD_V2
source: état réel du repo au 2026-04-23 après clôture routeur
creation: 2026-04-23 à 13:54
last_updated: 2026-04-23 à 13:54
status: current-state
phase: global
validation: 363 passed, 4 deselected · ruff clean · mypy strict clean
---

# BILAN GLOBAL — AIPROD_V2 — 2026-04-23

## Résumé exécutif

AIPROD_V2 n'est plus un prototype exploratoire. Le concept central est déjà prouvé par le code :

1. un pipeline narratif déterministe en 4 passes ;
2. une IR cinématographique typée et exploitable ;
3. une branche LLM réelle avec extraction, validation et routage ;
4. des connecteurs image, vidéo et audio ;
5. une CLI utilisable pour pipeline, comparaison et scheduling ;
6. un routeur LLM désormais observable, configurable et validé sur cas réel.

Le projet est donc en fin de v1 technique. La majorité des briques conceptuelles sont livrées. Le travail restant relève surtout de la consolidation globale, de l'alignement documentation/audit, et de quelques chantiers d'industrialisation encore partiels.

---

## État réel du concept

### Ce que le concept démontre déjà

- texte brut vers scènes visuelles structurées ;
- scènes vers shots atomiques déterministes ;
- compilation typée vers `AIPRODOutput` ;
- enrichissement continuité personnages / lieux / props ;
- génération de storyboard image ;
- séquencement vidéo ;
- synchronisation audio / timeline de production ;
- comparaison rules vs LLM sur cas réel ;
- routage intelligent Claude/Gemini avec observabilité locale.

### Ce que cela signifie

Le concept "compilateur narratif vers pipeline cinématique" est validé techniquement. La question n'est plus "est-ce que l'idée marche ?" mais "qu'est-ce qu'il reste à solidifier pour en faire un système de production local cohérent de bout en bout ?"

---

## État des grands axes

| Axe | État réel | Commentaire |
|---|---|---|
| IR déterministe 4 passes | livré | coeur stable, typé, validé |
| adaptation / story engine | livré | extraction, validation, chunking, budget |
| backends IR / exports | livré | JSON, CSV, JSON flat, IO disque |
| continuité | livré | registres personnages / lieux / props opérationnels |
| image generation | livré | adapters + storyboard + checkpoint + prepass |
| video generation | livré | adapters + smart router + sequencer |
| audio / post-production | livré | synchronisation et `ProductionOutput` présents |
| scheduling | livré mais perfectible | orchestre image → vidéo → audio avec métriques de base |
| LLM router | livré et clôturé | plan dédié fermé, validation réelle chapter1 faite |
| observabilité globale | partielle | traces routeur solides, coût USD encore incomplet |
| documentation globale | partielle | README bon, audits/plans globaux partiellement obsolètes |

---

## Plans déjà clos

Les plans suivants sont explicitement marqués `completed` et sont globalement cohérents avec l'état du code :

- `adaptation_layer_v1_plan.md`
- `ir_maturity_v3_plan.md`
- `pipeline_quality_v1_plan.md`
- `backends_ir_plan.md`
- `image_generation_v1_plan.md`
- `video_generation_v1_plan.md`
- `post_production_v1_plan.md`
- `continuity_engine_v1_plan.md`
- `story_engine_v1_plan.md`
- `storyboard_coherence_v1_plan.md`
- `production_completeness_v1_plan.md`
- `production_ready_plan.md`
- `llm_router_endgame_plan.md`

Conclusion : le repo a déjà parcouru une grande partie du chemin conceptuel prévu dans les plans v1.

---

## Documents devenus partiellement obsolètes

### `scale_orchestration_v1_plan.md`

Ce plan est encore marqué `active`, mais plusieurs items qu'il présente comme manquants sont déjà livrés dans le code :

- `split_into_chunks()` et `extract_all()` ;
- `max_chars_per_chunk` dans `ProductionBudget` ;
- persistance JSON via `core/io.py` ;
- CLI `aiprod` avec `pipeline`, `storyboard`, `schedule`, `compare` ;
- checkpoint storyboard ;
- `EpisodeScheduler` ;
- couverture de tests dédiée (`test_io.py`, `test_scheduling.py`, etc.).

Ce plan doit donc être rebaseliné plutôt qu'exécuté tel quel.

### `audit_master_aiprod.md`

L'audit master reste utile comme photo historique, mais il est techniquement dépassé :

- il parle de `278 tests`, alors que l'état réel validé est `363 passed, 4 deselected` ;
- il signale l'absence de tests routeur, alors que le routeur est désormais fortement couvert ;
- il considère encore certains chantiers de scheduling/metrics comme plus ouverts qu'ils ne le sont réellement.

Il faut donc le considérer comme un audit de phase précédente, pas comme une photographie fidèle du repo actuel.

---

## Ce qui est réellement terminé

### 1. Le coeur produit

Le pipeline narratif principal est stable, typé et testé. C'est la partie la plus précieuse du projet, et elle est solide.

### 2. Le mode LLM n'est plus un appendice fragile

L'adaptation LLM existe avec des adapters réels, un validateur, un routeur, des politiques d'échec, des traces et une validation réelle sur `chapter1.txt`.

### 3. Les couches aval existent vraiment

Le projet ne s'arrête pas au JSON. Il sait déjà préparer storyboard, vidéo, audio et scheduling avec interfaces dédiées.

### 4. Le concept de comparaison est opérationnel

Le repo sait comparer rules vs LLM, générer des artefacts structurés et inspecter les écarts sur un cas narratif réel du repo.

---

## Ce qui reste réellement à faire

### P1 — Rebaseliner la vision globale

Le besoin le plus immédiat n'est pas un nouveau sous-système, mais une remise à plat documentaire :

1. refaire un audit master actuel ;
2. mettre à jour le plan `Scale & Orchestration` selon l'état réel ;
3. synchroniser les chiffres globaux de tests et de périmètre dans la documentation de pilotage.

### P2 — Compléter l'observabilité économique

`CostReport` existe, `RunMetrics` existe, et le scheduler remplit déjà les compteurs d'appels image/vidéo/audio. En revanche, les coûts USD réels et les tokens LLM ne sont pas encore véritablement remontés par les adapters.

Autrement dit : la structure d'observabilité est là, mais la partie "coût réel" reste partielle.

### P3 — Finaliser l'opérabilité bout en bout

`FFmpegExporter` existe et est testé, mais il n'est pas encore exposé comme surface CLI de haut niveau. Le pipeline sait produire les IRs de production ; la finition opérateur "dernier kilomètre" mérite encore d'être homogénéisée.

### P4 — Clarifier la prochaine priorité produit

Le repo a dépassé le stade où tout doit avancer en parallèle. La prochaine vraie décision doit être unique :

1. industrialisation / orchestration ;
2. qualité sémantique des sorties ;
3. observabilité / coûts / exploitation.

Sans ce choix, le risque est de diluer les prochaines sessions dans des micro-améliorations latérales.

---

## Risques résiduels identifiés

- documentation de pilotage en retard sur le code réel ;
- audits historiques encore utilisés comme référence implicite alors qu'ils sont datés ;
- `CostReport` encore insuffisant pour une lecture économique réelle ;
- dernière mile opérateur non totalement uniformisé autour d'une surface CLI unique.

---

## État de validation de référence

État validé au moment de ce bilan :

```text
363 passed, 4 deselected
ruff check .  -> clean
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py --strict -> clean
```

Validation réelle routeur disponible :

- `artifacts/chapter1-router-compare/compare.json`
- `artifacts/chapter1-router-compare/router_trace.json`
- `artifacts/chapter1-router-compare/compare_forced_chunks.json`
- `artifacts/chapter1-router-compare/router_trace_forced_chunks.json`

Le run multi-chunk forcé constitue la vraie preuve de continuité contextuelle observable pour le routeur.

---

## Conclusion stratégique

AIPROD_V2 a déjà réussi l'essentiel du pari conceptuel.

Le projet n'a plus besoin d'être "prouvé". Il a besoin d'être recentré, audité à nouveau, et aligné autour d'une prochaine étape unique. La meilleure lecture actuelle est donc :

- concept validé ;
- coeur logiciel solide ;
- router clôturé ;
- couches aval présentes ;
- reste à faire concentré sur la consolidation globale et la priorisation du prochain vrai lot.

---

## Recommandation de suite

Ordre recommandé pour la suite du projet :

1. refaire un audit master à jour ;
2. rebaseliner `scale_orchestration_v1_plan.md` ;
3. choisir un seul lot prioritaire pour la prochaine phase (`industrialisation`, `qualité de sortie`, ou `observabilité/coûts`).