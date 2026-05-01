---
title: "Plan d'action - Audit IR & Maturite Conceptuelle"
creation: 2026-04-23 à 16:05
source_audit: tasks/audits/resultats/audit_ir_maturity_aiprod.md
baseline_commit: ab9bb76
corrections_totales: 6
p1_count: 2
p2_count: 3
p3_count: 1
---

# PLAN D'ACTION - AUDIT IR & MATURITE CONCEPTUELLE - 2026-04-23

**Source** : `tasks/audits/resultats/audit_ir_maturity_aiprod.md`
**Genere le** : 2026-04-23 à 16:05
**Corrections totales** : 6 (P1:2 · P2:3 · P3:1)

---

## Resume

Le repo est solide sur le plan executable (`374 passed, 4 deselected`, Ruff vert) et le coeur rules reste un vrai compilateur deterministe en 4 passes. Le blocage principal n'est plus la correction technique de surface, mais le fait que le sens visuel reste encore porte par `VisualScene.visual_actions` et `Shot.prompt` au lieu d'un IR d'action de premier rang. Le chemin critique est donc net : introduire un modele d'action type, en faire la source unique des requests backend, puis stabiliser les entites et la continuite longue avant de resserrer les contrats residuels.

**Cible post-corrections :**
- `pytest aiprod_adaptation/tests/ -q --tb=short` : 374 passed, 4 deselected
- determinisme du chemin rules : preserve
- `mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py --strict` : 0 erreur
- `ruff check .` : 0 erreur
- `python main.py --input aiprod_adaptation/examples/sample.txt --title Sample 2>$null | python -m json.tool` : JSON valide
- aucun `# type: ignore` dans le codebase
- contrats explicites entre mode compilateur deterministic et mode generatif optionnel

---

## Corrections P1 - CRITIQUE

### [IR-01] - Introduire un vrai IR d'action type entre Pass 2, Pass 3 et le schema final
**Priorite** : P1
**Severite** : 🔴
**Fichier** : `aiprod_adaptation/models/intermediate.py:30`, `aiprod_adaptation/models/intermediate.py:48`, `aiprod_adaptation/core/pass2_visual.py:178`, `aiprod_adaptation/core/pass3_shots.py:124`, `aiprod_adaptation/core/pass3_shots.py:143`, `aiprod_adaptation/models/schema.py:19`, `aiprod_adaptation/core/pass4_compile.py:16`
**Probleme** : `VisualScene.visual_actions` reste `list[str]`, `ShotDict.prompt` reste le porteur central du sens et Pass 3 atomise encore les actions a partir de ponctuation/phrases. Le systeme compile donc proprement une representation encore textualisee au lieu d'un evenement cinematographique typable.
**Action** : Ajouter un payload d'action structure au niveau scene et shot (par exemple `subject_id`, `action_type`, `target`, `modifiers`, `location_id`, `camera_intent`), le produire des Pass 2, le consommer dans Pass 3, puis le valider dans le schema final et Pass 4. `prompt` doit devenir un derive de compatibilite, pas la source primaire.
**Tests impactes** : `aiprod_adaptation/tests/test_pipeline.py`, `aiprod_adaptation/tests/test_adaptation.py`, `aiprod_adaptation/tests/test_comparison.py`, `aiprod_adaptation/tests/test_image_gen.py`, `aiprod_adaptation/tests/test_video_gen.py`, `aiprod_adaptation/tests/test_post_prod.py` ; ajouter des tests cibles pour la preservation de l'action structuree a travers les 4 passes.
**Risque** : Eleve - changement du contrat central inter-passes et de la forme du modele compile.

---

### [IR-02] - Sortir les backends du couplage au texte libre
**Priorite** : P1
**Severite** : 🔴
**Fichier** : `aiprod_adaptation/image_gen/image_request.py:6`, `aiprod_adaptation/image_gen/image_request.py:9`, `aiprod_adaptation/image_gen/storyboard.py:32`, `aiprod_adaptation/image_gen/storyboard.py:91`, `aiprod_adaptation/core/continuity/prompt_enricher.py:14`, `aiprod_adaptation/core/continuity/prompt_enricher.py:52`, `aiprod_adaptation/video_gen/video_request.py:6`, `aiprod_adaptation/video_gen/video_request.py:10`, `aiprod_adaptation/video_gen/video_sequencer.py:21`, `aiprod_adaptation/video_gen/video_sequencer.py:55`, `aiprod_adaptation/post_prod/audio_request.py:10`, `aiprod_adaptation/post_prod/audio_request.py:15`, `aiprod_adaptation/post_prod/audio_synchronizer.py:39`, `aiprod_adaptation/post_prod/audio_synchronizer.py:77`
**Probleme** : `ImageRequest.prompt`, `VideoRequest.prompt` et `AudioRequest.text` restent les payloads principaux des couches aval. Les backends consomment donc encore des phrases enrichies et non des champs structures directement exploitables, ce qui force du re-parsing ou une dependance permanente au texte.
**Action** : Introduire des requests backend structurees porteuses d'entites, d'actions, d'intention camera et d'etat de continuite. Conserver `prompt`/`text` comme sorties derivees calculees a la frontiere adapter/provider quand un backend en a besoin, pas dans le coeur pipeline.
**Tests impactes** : `aiprod_adaptation/tests/test_image_gen.py`, `aiprod_adaptation/tests/test_video_gen.py`, `aiprod_adaptation/tests/test_post_prod.py`, `aiprod_adaptation/tests/test_scheduling.py`, `aiprod_adaptation/tests/test_io.py` ; ajouter des tests qui verrouillent la construction deterministe des requests structurees et la generation du prompt de compatibilite.
**Risque** : Eleve - touche les contrats entre IR, generateurs et adapters externes.

---

## Corrections P2 - IMPORTANT

### [IR-03] - Stabiliser les entites et le graphe scene -> beat -> shot
**Priorite** : P2
**Severite** : 🟠
**Fichier** : `aiprod_adaptation/models/intermediate.py:21`, `aiprod_adaptation/models/intermediate.py:30`, `aiprod_adaptation/models/schema.py:9`, `aiprod_adaptation/models/schema.py:19`, `aiprod_adaptation/models/schema.py:57`, `aiprod_adaptation/core/pass4_compile.py:16`, `aiprod_adaptation/core/continuity/character_registry.py:15`, `aiprod_adaptation/core/continuity/location_registry.py:24`, `aiprod_adaptation/core/comparison.py:97`, `aiprod_adaptation/core/comparison.py:282`
**Probleme** : `Episode` garde `scenes` et `shots` comme listes paralleles, les personnages et lieux restent surtout manipules comme chaines, et les registries de continuite n'alimentent pas encore un graphe de references de premier rang. Le systeme tient la coherence minimale, mais pas une structure narrative/cinematographique riche.
**Action** : Introduire des IDs stables d'entites (characters, locations, props) et une relation explicite scene/beat/shot dans les modeles intermediaires et finaux. Reutiliser `CharacterRegistry` et `LocationRegistry` comme fondation du graphe compile plutot que comme utilitaires adjacents.
**Tests impactes** : `aiprod_adaptation/tests/test_pipeline.py`, `aiprod_adaptation/tests/test_continuity.py`, `aiprod_adaptation/tests/test_comparison.py`, `aiprod_adaptation/tests/test_adaptation.py` ; ajouter des tests de validation referentielle pour IDs d'entites, beats et rattachement scene -> shots.
**Risque** : Moyen a eleve - evolution de schema large, mais tres localisee sur les contrats de donnees.

---

### [IR-04] - Remplacer la memoire inter-chunks textuelle par une continuite structuree
**Priorite** : P2
**Severite** : 🟠
**Fichier** : `aiprod_adaptation/core/adaptation/story_extractor.py:14`, `aiprod_adaptation/core/adaptation/story_extractor.py:55`, `aiprod_adaptation/core/adaptation/story_extractor.py:103`, `aiprod_adaptation/core/adaptation/story_extractor.py:156`, `aiprod_adaptation/core/adaptation/story_extractor.py:178`, `aiprod_adaptation/core/adaptation/normalizer.py:13`, `aiprod_adaptation/core/continuity/character_registry.py:15`, `aiprod_adaptation/core/continuity/location_registry.py:24`
**Probleme** : La memoire longue narration repose encore sur `Last scenes: <locations>.`, donc sur un resume pauvre qui ignore etat des personnages, objectifs en cours et dernieres actions critiques. La branche LLM peut tenir des volumes moyens, mais pas une continuite narrative profonde a grande echelle.
**Action** : Remplacer le `prior_summary` textuel par un snapshot structure de continuite (entites actives, lieux, objectifs non resolus, dernieres actions significatives), l'injecter dans l'extraction LLM et le normalizer, puis valider sa coherence en aval.
**Tests impactes** : `aiprod_adaptation/tests/test_adaptation.py`, `aiprod_adaptation/tests/test_continuity.py`, `aiprod_adaptation/tests/test_pipeline.py` ; ajouter des fixtures multi-chunks avec retour de personnages et changements de lieux pour verrouiller la memoire structuree.
**Risque** : Moyen - modifie la qualite des sorties LLM et les hypothese de continuite, sans casser le coeur rules.

---

### [IR-05] - Assumer explicitement les deux modes du projet: compilateur deterministic et adaptation generative
**Priorite** : P2
**Severite** : 🟠
**Fichier** : `aiprod_adaptation/core/engine.py:44`, `aiprod_adaptation/core/engine.py:112`, `aiprod_adaptation/core/engine.py:150`, `aiprod_adaptation/core/engine.py:181`, `aiprod_adaptation/cli.py:302`, `aiprod_adaptation/cli.py:359`, `aiprod_adaptation/cli.py:437`, `main.py:121`, `main.py:127`
**Probleme** : Le repo contient deja un coeur compilateur deterministic et une branche generative optionnelle, mais cette double identite reste implicite dans l'orchestration. Les garanties de determinisme, de dependances requises et de comportement utilisateur restent donc floues.
**Action** : Introduire une frontiere explicite de mode dans l'engine, la CLI et la documentation operative: mode compilateur rules avec garanties fortes, et mode adaptation/generation avec dependances externes et garanties distinctes. Verrouiller cette separation jusque dans les points d'entree `aiprod` et `main.py`.
**Tests impactes** : `aiprod_adaptation/tests/test_cli.py`, `aiprod_adaptation/tests/test_pipeline.py`, `aiprod_adaptation/tests/test_scheduling.py` ; ajouter des tests de selection de mode, de `require_llm` et de garde sur les dependances providers.
**Risque** : Moyen - change la surface publique et la lisibilite produit, mais pas l'algorithme coeur.

---

## Corrections P3 - MINEUR

### [IR-06] - Fermer la fuite de design via `metadata` et verrouiller le contrat residuel
**Priorite** : P3
**Severite** : 🟡
**Fichier** : `aiprod_adaptation/models/intermediate.py:57`, `aiprod_adaptation/models/schema.py:27`, `aiprod_adaptation/core/pass3_shots.py:143`, `aiprod_adaptation/core/comparison.py:395`
**Probleme** : `metadata` reste une soupape utile, mais c'est aussi la voie par laquelle des informations semantiques critiques peuvent continuer a s'echapper hors du modele type. Si ce champ reste ouvert sans garde, l'IR semblera stable alors qu'il se fragmentera silencieusement.
**Action** : Geler `metadata` a un role de compatibilite transitoire, promouvoir tout champ recurrent critique dans les modeles types, et etendre la comparaison/tests pour faire echouer toute semantique importante stockee uniquement dans `metadata`.
**Tests impactes** : `aiprod_adaptation/tests/test_pipeline.py`, `aiprod_adaptation/tests/test_comparison.py`, `aiprod_adaptation/tests/test_adaptation.py` ; ajouter des tests contractuels sur les champs autorises dans `metadata`.
**Risque** : Faible a moyen - resserre le contrat sans refonte algorithmique majeure.

---

## Ordre d'execution recommande

1. **IR-01** - Introduire un vrai IR d'action type entre Pass 2, Pass 3 et le schema final
2. **IR-02** - Sortir les backends du couplage au texte libre
3. **IR-03** - Stabiliser les entites et le graphe scene -> beat -> shot
4. **IR-04** - Remplacer la memoire inter-chunks textuelle par une continuite structuree
5. **IR-05** - Assumer explicitement les deux modes du projet: compilateur deterministic et adaptation generative
6. **IR-06** - Fermer la fuite de design via `metadata` et verrouiller le contrat residuel

**Rationale ordre :** `IR-01` traite la cause racine du plafond de maturite. `IR-02` doit suivre immediatement pour que les couches image/video/audio consomment enfin l'IR au lieu de phrases. `IR-03` ajoute ensuite les references stables dont l'action structuree a besoin pour devenir un vrai graphe. `IR-04` devient alors beaucoup plus robuste, car la memoire inter-chunks peut transporter des entites et actions de premier rang. `IR-05` clarifie enfin les garanties produit et runtime une fois les contrats de donnees stabilises. `IR-06` vient en dernier pour fermer proprement les echappements residuels sans figer trop tot un mauvais modele.

---

## Validation finale

```powershell
venv\Scripts\Activate.ps1

# Validation globale
pytest aiprod_adaptation/tests/ -q --tb=short
ruff check .
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py --strict
python main.py --input aiprod_adaptation/examples/sample.txt --title Sample 2>$null | python -m json.tool > $null

# Validation ciblee sur les surfaces touchees
pytest aiprod_adaptation/tests/test_pipeline.py -q --tb=short
pytest aiprod_adaptation/tests/test_adaptation.py -q --tb=short
pytest aiprod_adaptation/tests/test_continuity.py -q --tb=short
pytest aiprod_adaptation/tests/test_comparison.py -q --tb=short
pytest aiprod_adaptation/tests/test_image_gen.py -q --tb=short
pytest aiprod_adaptation/tests/test_video_gen.py -q --tb=short
pytest aiprod_adaptation/tests/test_post_prod.py -q --tb=short
pytest aiprod_adaptation/tests/test_scheduling.py -q --tb=short
pytest aiprod_adaptation/tests/test_cli.py -q --tb=short
```

**Resultat attendu :** base toujours verte, chemin rules toujours deterministe, IR d'action devenu la source primaire du sens, requests backend derivees de l'IR, et frontiere explicite entre compilation deterministic et adaptation generative.