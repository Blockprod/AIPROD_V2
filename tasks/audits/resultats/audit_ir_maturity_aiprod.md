---
type: audit
audit: IR & Maturite Conceptuelle
projet: AIPROD_V2
date: 2026-04-23
heure: 15:53
auditeur: GitHub Copilot (GPT-5.4)
statut: complet
baseline_tests: 374 passed, 4 deselected
baseline_ruff: All checks passed
---

# AUDIT - IR & MATURITE CONCEPTUELLE
## AIPROD ADAPTATION ENGINE v2

---

## Niveau de maturite conceptuelle actuel

**3.5 / 5**

Ce n'est plus un jouet. Ce n'est pas encore un compilateur narratif de grade production.

Le systeme a un vrai coeur de compilation deterministe en 4 passes, des contrats inter-passes explicites, une validation stricte, une branche LLM normalisee vers le meme IR, un comparateur rules vs LLM, et un scheduler de production image/video/audio. C'est deja une base serieuse.

Le plafond actuel est clair: le systeme reste semantiquement porte par du texte libre a deux endroits critiques, `VisualScene.visual_actions` et `Shot.prompt`. Tant que le coeur de l'action reste encode comme phrase et non comme structure typable consommable directement par les backends, l'IR reste incomplet.

---

## 1. FACTUAL STATE (NO OPINION)

### Ce qui existe

**Pipeline coeur:**

| Pass | Fichier | Entree | Sortie | Contrat |
|---|---|---|---|---|
| 1 | `core/pass1_segment.py` | `str` | `list[RawScene]` | `TypedDict` |
| 2 | `core/pass2_visual.py` | `list[RawScene]` | `list[VisualScene]` | `TypedDict` |
| 3 | `core/pass3_shots.py` | `list[VisualScene]` | `list[ShotDict]` | `TypedDict` |
| 4 | `core/pass4_compile.py` | scenes + shots + title | `AIPRODOutput` | Pydantic v2 |

**IR intermediaire:**

- `RawScene`: `scene_id`, `characters`, `location`, `time_of_day`, `raw_text`
- `VisualScene`: `scene_id`, `characters`, `location`, `time_of_day`, `visual_actions`, `dialogues`, `emotion`, plus enrichissements optionnels `pacing`, `time_of_day_visual`, `dominant_sound`
- `ShotDict`: `shot_id`, `scene_id`, `prompt`, `duration_sec`, `emotion`, `shot_type`, `camera_movement`, `metadata`

**IR compile final:**

- `Scene`, `Shot`, `Episode`, `AIPRODOutput` dans `models/schema.py`
- validation Pydantic directe sur `duration_sec`, `shot_type`, `camera_movement`
- validation referentielle `scene_id` dans `pass4_compile.py`

**Branche adaptation LLM:**

- `StoryExtractor` impose un schema JSON de production et chunk le texte long
- `Normalizer` convertit la sortie LLM en `VisualScene`
- `StoryValidator` filtre les scenes non filmables avant Pass 3
- `LLMRouter`, adapters Claude/Gemini, trace exportable et compare CLI existent

**Couches aval:**

- storyboard image
- sequencement video
- synchronisation audio
- scheduler global avec `RunMetrics` et `CostReport`
- comparateur rules vs LLM avec diffs structures et alignement heuristique de scenes

**CLI et points d'entree:**

- `aiprod pipeline`
- `aiprod storyboard`
- `aiprod schedule`
- `aiprod compare`
- `main.py` expose aussi le pipeline direct

**Tests et baseline actuelle:**

- 11 fichiers de tests actifs sous `aiprod_adaptation/tests/`
- `pytest aiprod_adaptation/tests/ -q --tb=short` -> `374 passed, 4 deselected`
- `ruff check .` -> vert

### Ce qui est deterministe vs non deterministe

**Deterministe:**

- Pass 1 a Pass 4 sur chemin rules/null
- validation Pydantic
- comparaison structurelle rules vs LLM
- enrichissement de continuite
- scheduler comme orchestration de donnees
- routeur comme logique de decision locale, a entree et etat process donnes

**Non deterministe ou externe:**

- extraction LLM Claude/Gemini
- generation image/video/audio via adapters reels
- disponibilite provider et reponses upstream

Conclusion factuelle: le coeur compilateur rules est deterministe. Le repo dans son ensemble ne l'est plus, parce qu'il integre volontairement des branches LLM et generatives externes.

### Ce qui est strictement implemente vs loose

**Strict:**

- contrats `TypedDict` entre passes
- contraintes de duree de shot et enums de cinematographie au niveau modele final
- validation explicite des references `scene_id` a la compilation
- echec explicite sur `shot_id` inconnus dans les couches video et audio
- chunking texte et budget de production structures
- compare output structure et export JSON

**Loose:**

- `VisualScene.visual_actions` reste `list[str]`
- `Shot.prompt` reste le porteur central du sens visuel
- `Shot.metadata` reste un sac ouvert `dict[str, Any]`
- `Normalizer` fait de la coercition best-effort a partir de `dict[str, Any]`
- la memoire inter-chunks LLM se resume a `Last scenes: <locations>` sur les 3 dernieres scenes

---

## 2. GAP ANALYSIS (CRITICAL)

### Ecart entre vision cible et implementation reelle

La vision cible annonce un compilateur narratif a IR cinematographique. L'implementation reelle est un pipeline fortement structure, mais pas encore un vrai IR cinematographique integral.

### Gaps majeurs

**GAP-1 - Le contenu semantique central reste textuel**

Le coeur de l'action n'est pas encode comme structure exploitable. Il reste encode dans des phrases.

Exemple actuel:

```json
{
  "prompt": "Marcus runs quickly through the market street."
}
```

Un vrai IR devrait exposer quelque chose de cet ordre:

```json
{
  "subject_id": "char_marcus",
  "action_type": "run",
  "target": "market_street",
  "manner": "quickly",
  "framing": "wide",
  "movement": "follow"
}
```

Tant que `prompt` reste le payload principal consomme par les couches aval, les backends ne consomment pas un IR. Ils consomment une phrase enrichie.

**GAP-2 - `VisualScene` n'est pas une scene semantique, c'est une scene textualisee**

`visual_actions` est une liste de phrases, pas une liste d'evenements types. Le LLM est force de renvoyer des `actions: list[str]`, puis `Normalizer` les accepte comme telles. Le systeme normalise la forme, pas la semantique profonde.

**GAP-3 - Le modele compile final garde des listes paralleles, pas un graphe explicite**

`Episode` contient `scenes` et `shots` comme deux listes separees. C'est valide et exploitable, mais ce n'est pas encore un graphe narratif/cinematographique riche.

Il manque au minimum:

- des identifiants stables de personnages et lieux comme entites
- des references de shot vers subject/action/target typables
- une relation explicite `scene -> shots`
- une notion intermediaire de `sequence` ou `beat`

**GAP-4 - L'IR ne rend pas les backends independants du texte**

Les couches image/video/audio utilisent encore des requetes prompt-centriques:

- `ImageRequest.prompt`
- `VideoRequest.prompt`
- `AudioRequest.text`

Ajouter des backends plus intelligents obligera encore a reparser du texte, ou a enrichir massivement les requests. C'est le signe que l'IR n'a pas encore absorbe le sens necessaire.

**GAP-5 - Le chemin LLM viole la definition originelle du systeme**

La definition d'origine du projet etait: pas de LLM, pas d'API externe, transformations purement rule-based, determinisme byte-level. Le repo actuel depasse cette definition. Ce n'est pas forcement une erreur produit, mais c'est un fait architectural.

Le systeme reel est donc:

- un compilateur narratif deterministe sur chemin rules
- plus une branche d'adaptation generative optionnelle
- plus une pipeline de pre-production generative

Ce n'est plus strictement le systeme decrit dans l'intention initiale.

**GAP-6 - La memoire longue narration reste faible**

Le chunking LLM est propre, mais la continuite inter-chunks repose sur un resume pauvre: les 3 dernieres locations. Cela passera mal a grande echelle sur des romans longs, multi-intrigues, retours de personnages et changements d'enjeu.

**GAP-7 - `metadata` est un escape hatch utile, mais c'est aussi une fuite de design**

Le fait de loger `time_of_day_visual` et `dominant_sound` dans `metadata` montre que le modele a besoin d'enrichissements, mais n'a pas encore stabilise leur place dans l'IR shot-level.

### Ce qui est mieux que l'ancien etat

Il y a quand meme une progression conceptuelle nette par rapport a un simple prompt system:

- la sortie LLM est normalisee vers le meme `VisualScene`
- le coeur rules et la branche LLM convergent vers Pass 3 et Pass 4
- le comparateur rules vs LLM observe des deltas structurels, pas juste du texte
- le scheduler travaille sur un `AIPRODOutput` valide, pas sur du JSON libre

Le systeme n'est donc pas un enchaunement de prompts. C'est un pipeline semantiquement contraint, encore incomplet.

---

## 3. PASS-BY-PASS EVALUATION

### Pass 1 - Segmentation

**Correctness: 7/10**

**Determinism robustness:** excellente sur le chemin rules. Aucun hasard, aucune heuristique instable dependante d'un ordre non maitrise.

**Clarity of rules:** bonne. Les regles de segmentation par paragraphes, lieu, temps et categorie d'action sont lisibles.

**Failure modes:**

- texte sans double saut de ligne -> scene unique trop grosse
- detection de lieu par sous-chaine fragile
- extraction des noms propres toujours heuristique, meme si meilleure qu'avant grace au pre-scan global

**Scalability limits:**

- lineaire et acceptable a taille moyenne
- precision semantique insuffisante pour recits tres longs, tres elliptiques ou litteraires

### Pass 2 - Visual Rewrite

**Correctness: 7/10**

**Determinism robustness:** excellente sur le chemin rules. Transformation pure, stable, explicable.

**Clarity of rules:** bonne. Regles emotionnelles, dialogues et suppression de pensee interne sont nettes.

**Failure modes:**

- emotion dominante calculee au niveau scene, pas au niveau shot
- `visual_actions` reste en phrases libres
- certaines transformations emotionnelles ecrasent encore de la specificite d'action
- la suppression de dialogues et speech tags reste basee sur regex et heuristiques de surface

**Scalability limits:**

- ne casse pas en volume
- plafonne vite en finesse narrative, car il ne construit pas de representation d'action plus profonde

### Pass 3 - Shot Atomization

**Correctness: 6/10**

**Determinism robustness:** bonne. Les regles de duree, cadrage et mouvement sont stables.

**Clarity of rules:** bonne cote cinematographie, moyenne cote atomisation.

**Failure modes:**

- `_atomize_action()` repose encore sur ponctuation et virgules
- `prompt` est derive d'une phrase, pas d'un evenement structure
- `shot_type` et `camera_movement` couvrent l'essentiel minimum, pas un vocabulaire cinema riche
- le coeur du sens reste encore dans `prompt`, pas dans les champs structures

**Scalability limits:**

- fonctionne sur petits et moyens volumes
- deviendra limitant des qu'il faudra exprimer blocking, subject focus, choreography, multi-agent actions, props critiques, transitions ou coverage reel

### Pass 4 - Compilation

**Correctness: 9/10**

**Determinism robustness:** excellente.

**Clarity of rules:** excellente. Les echecs sont clairs, les validations Pydantic sont directes, la coherence `scene_id` est enforcee.

**Failure modes:**

- le modele valide la forme plus que la richesse semantique
- la compilation n'eleve pas un texte libre en vrai IR; elle fige proprement un IR encore partiel

**Scalability limits:**

- bonne tenue en volume pour la forme
- pas de probleme algorithmique majeur
- la limite est conceptuelle, pas technique: l'objet compile reste trop textuel

---

## 4. IR EVALUATION (CORE PART)

### Reponse stricte

**B) Semi-structured pipeline**

### Pourquoi ce n'est pas A) Prompt generator

Parce qu'il existe de vrais contrats de donnees et une vraie compilation:

- `TypedDict` inter-passes
- `AIPRODOutput` Pydantic
- IDs de scenes et shots stables
- validations fortes sur duree et cinematographie
- convergence rules/LLM vers la meme structure
- comparaison structurelle des sorties

Un simple prompt generator ne fait pas ca.

### Pourquoi ce n'est pas C) True IR

Parce que les unites semantiques decisives ne sont pas encodees comme structures typeses de premier rang.

Ce qui manque a un vrai IR cinematographique:

- action typee
- sujet type
- cible/objet type
- entites personnages et lieux referencees par ID
- relation shot <-> beat <-> scene explicite
- instructions camera et blocking plus riches et independantes du texte
- independance reelle des backends vis-a-vis du prompt

### Verdict technique

Le systeme est un **pipeline semi-structure fort**, pas un prompt system, mais pas encore un IR cinematographique complet.

---

## 5. ARCHITECTURAL RISKS

### Coupling issues

**RISK-1 - Couplage persistant des backends au texte**

Les requests image/video/audio consomment encore du texte libre comme signal principal. Cela limite l'evolutivite et oblige a reparser ou sur-interpreter plus tard.

**RISK-2 - Couplage LLM vers schema faible en semantique**

Le LLM produit du JSON valide, mais ce JSON reste lui-meme textualise. Le schema encadre la forme de retour, pas la structure profonde de l'action.

### Future extensibility limits

**RISK-3 - Long narratives**

Le chunking actuel resout le volume brut, pas la memoire narrative profonde. Les resumes inter-chunks par seules locations vont casser sur recits longs avec arcs croises.

**RISK-4 - Multiple scenes and multi-agent staging**

Le systeme sait gerer plusieurs scenes. Il sait beaucoup moins bien exprimer plusieurs agents dans la meme action, ou une choregraphie complexe, sans retomber dans la phrase libre.

**RISK-5 - Video backends richer than prompt-in/pixels-out**

Si un backend video demande un vrai schema de mouvement, de sujet, de trajectoire, de lensing ou de continuity state, l'IR actuel sera trop pauvre.

### Hidden technical debt

**RISK-6 - `metadata` comme soupape permanente**

Si de plus en plus d'informations critiques migrent dans `metadata`, le modele semblera stable alors qu'il se fragmente.

**RISK-7 - Double identite du projet**

Le projet raconte encore partiellement une histoire de compilateur deterministic pur, alors que le repo reel contient aussi une vraie branche generative externe. Si cette dualite n'est pas explicitee comme deux modes distincts, la lecture produit restera confuse.

---

## 6. MATURITY SCORE

### Overall score: 7/10

Le coeur est solide, teste, valide, deterministic sur son chemin rules, et deja utile. Le 7 vient de la robustesse d'ensemble et de la convergence rules/LLM/scheduler. Il ne va pas plus haut parce que la semantique d'action n'est pas encore structuree comme IR de premier rang.

### Determinism reliability: 9/10

Le coeur rules est tres fort. Les tests et les regles le montrent. Le point retire n'est pas sur le coeur, mais sur le fait que le repo global inclut maintenant des branches provider externes non deterministes.

### Architectural soundness: 8/10

Le decoupage modulaire, les contrats, la validation et la CLI sont bons. La vraie faiblesse n'est pas un mauvais decoupage; c'est un IR semantiquement trop mince pour les ambitions cinema long terme.

### IR quality: 6/10

Le systeme a une vraie ossature d'IR. Mais il n'a pas encore internalise les evenements, les entites et les relations comme structures consommables directement par tous les backends. Tant que `prompt` et `visual_actions` restent le coeur du sens, la qualite IR plafonne.

---

## 7. STRATEGIC NEXT STEPS (NON-NEGOTIABLE)

### TOP 5 highest impact changes

**1. Introduire un vrai IR d'action typable**

Ajouter une representation shot-level et scene-level avec au minimum `subject_id`, `action_type`, `target`, `modifiers`, `location_id`, `camera_intent`. Tant que cette couche n'existe pas, le projet restera un pipeline semi-structure.

**2. Sortir `prompt` du role de payload principal**

Faire du prompt un derive de l'IR, pas l'inverse. Les requests image/video/audio doivent pouvoir etre construites depuis des champs structures, puis seulement rendues en texte si un provider en a besoin.

**3. Stabiliser les entites et references**

Introduire de vrais IDs d'entites pour personnages, lieux, props et, idealement, beats/sequences. Les scenes et shots doivent se rattacher a ces entites de maniere explicite.

**4. Separer explicitement le mode compilateur deterministic du mode adaptation generative**

Le repo a deja les deux. Il faut maintenant l'assumer architecturalement: un coeur compilateur rule-based, et une couche d'adaptation/generation optionnelle. Sans cette frontiere, l'identite technique du projet restera floue.

**5. Remplacer la memoire LLM inter-chunks par une continuite structuree**

Le resume `Last scenes: <locations>` n'est pas une memoire narrative. Il faut une representation compacte des entites, lieux, objectifs et dernieres actions critiques pour passer a l'echelle sur les longues narrations.

---

## 8. HARD VERDICT

**This is a solid compiler foundation**

Le mot important est `foundation`.

Le coeur compilateur est reel.
Le determinisme rules est reel.
Les contrats sont reels.
La validation est reelle.

Mais l'IR cinema final n'est pas encore complet. Le systeme ne doit pas etre vendu comme un vrai IR cinematographique plein tant que l'action, les entites et les relations restent principalement encapsulees dans des phrases.

---

## Conclusion brute

Le projet a depasse le stade du prototype bricole et a depasse le stade du prompt engineering pur.

Il est deja un compilateur narratif credible au niveau structurel.

Il n'est pas encore un compilateur narratif mature au niveau semantique.

Le prochain saut n'est pas cosmetique. Il faut faire entrer l'action dans le modele.