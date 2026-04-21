---
type: audit
audit: IR & Maturité Conceptuelle
projet: AIPROD_V2
date: 2026-04-21
heure: 12:30
auditeur: GitHub Copilot (Claude Sonnet 4.6)
statut: complet
---

# AUDIT — IR & MATURITÉ CONCEPTUELLE
## AIPROD ADAPTATION ENGINE v2

---

## 1. FACTUAL STATE (NO OPINION)

### Ce qui existe

**Passes implémentées :**

| Pass | Fichier | Entrée | Sortie | Type contrat |
|---|---|---|---|---|
| 1 | `pass1_segment.py` | `str` | `List[RawScene]` | TypedDict strict |
| 2 | `pass2_visual.py` | `List[RawScene]` | `List[VisualScene]` | TypedDict strict |
| 3 | `pass3_shots.py` | `List[VisualScene]` | `List[ShotDict]` | TypedDict strict |
| 4 | `pass4_compile.py` | title + scenes + shots | `AIPRODOutput` | Pydantic v2 |

**Modèles IR (`intermediate.py`) :**
- `RawScene` : `scene_id, characters, location, time_of_day, raw_text`
- `VisualScene` : `scene_id, characters, location, time_of_day, visual_actions, dialogues, emotion`
- `ShotDict` : `shot_id, scene_id, prompt, duration_sec, emotion, shot_type, camera_movement, metadata (NotRequired)`

**Modèles finaux (`schema.py`) :**
- `Shot` : 8 champs dont `shot_type: str = "medium"` et `camera_movement: str = "static"`
- `Scene`, `Episode`, `AIPRODOutput` : hiérarchie Pydantic v2 complète

**Règles centralisées (`core/rules/`) :**
- `segmentation_rules.py` : `LOCATION_PHRASES`, `TIME_PHRASES`
- `emotion_rules.py` : `EMOTION_RULES` (5 émotions), `_INTERNAL_THOUGHT_WORDS`
- `duration_rules.py` : `_MOTION_VERBS`, `_INTERACTION_VERBS`, `_PERCEPTION_VERBS`
- `cinematography_rules.py` : `SHOT_TYPE_RULES` (4 types), `CAMERA_MOVEMENT_*_KEYWORDS`

**Backends (`backends/`) :**
- `CsvExport` : 8 colonnes
- `JsonFlatExport` : liste plate de shots
- `BackendBase` : interface abstraite

**Tests :**
- `test_pipeline.py` : 36 tests, 9 classes
- `test_backends.py` : 6 tests, 2 classes
- Total : **42 tests**

**CI :** GitHub Actions — ruff + mypy strict + pytest sur push `main`

### Ce qui est déterministe

Tout. Aucun `random`, `datetime.now()`, `uuid4`, `set()` pour l'ordre, `sorted()` implicite. `test_json_byte_identical` le prouve.

### Ce qui est strictement implémenté vs loosement défini

**Strict :**
- Contrats inter-passes via TypedDict (mypy les valide)
- Règles duration : base + 4 conditions booléennes + clamp [3,8]
- Règles shot_type : ordered priority list, first match wins
- Règles camera_movement : hiérarchie motion > interaction > static
- Validation finale Pydantic : ValueError si duration hors [3,8]

**Loose (imprécis) :**
- `_atomize_action()` : split sur `", "` est fragile — dépend du format exact de la visual_action entrante
- `_extract_proper_nouns()` : heuristique positionnelle (token i>0 + majuscule) — pas un vrai POS tagger
- Segmentation par "changement de catégorie d'action entre paragraphes" : la condition `prev_category != category` est implémentée mais rarement déclenchée en pratique (la majorité des scènes vient des triggers location/time)
- `emotion` dans `VisualScene` est calculée une fois pour la scène entière — pas par shot

---

## 2. GAP ANALYSIS (CRITICAL)

### Gaps architecturaux

**GAP-1 : Absence de représentation structurée de l'action**

Le champ central de `ShotDict` reste `prompt: str` — une chaîne de texte libre.
Il n'existe pas de décomposition `subject / verb / object / modifier`.
Exemple actuel :
```
"prompt": "John walked quickly through the busy streets, in the city."
```
Un vrai IR cinématographique exposerait :
```
"subject": "John",
"action": "walk",
"modifier": "quickly",
"object": None,
"setting": "city streets"
```
Sans cette structure, aucun moteur de rendu ne peut consommer ce champ sans re-parser le texte.

**GAP-2 : `shot_type` et `camera_movement` ne couvrent pas tous les cas**

`shot_type` = "medium" par défaut pour ~60–70% des shots (tout ce qui ne déclenche pas pov/close_up/wide). Aucune règle ne distingue un two-shot d'un single. Le champ existe mais sa granularité est faible.

`camera_movement` ne reconnaît pas : zoom, crane, dolly, tracking. Trois valeurs pour un espace cinématographique qui en nécessite au moins 8.

**GAP-3 : Couplage implicite entre `prompt` et les champs structurés**

`prompt` est construit à partir du texte brut de l'action, indépendamment de `shot_type` et `camera_movement`. Ces trois champs ne forment pas un tout cohérent : on peut avoir `shot_type="wide"` et un prompt qui décrit un geste facial. Il n'y a pas de validation croisée.

**GAP-4 : Contrat faible sur `visual_actions`**

`VisualScene.visual_actions: List[str]` est une liste de chaînes libres. Aucun schéma ne contraint leur format. Pass 3 reçoit n'importe quelle chaîne et fait de son mieux. Une action comme `"fidgets, paces, bites lip"` (produite par Pass 2 pour "nervous") sera atomisée en 3 shots distincts — c'est intentionnel mais non documenté comme contrat.

**GAP-5 : Pas de concept de "séquence"**

`Episode` contient `scenes` + `shots` comme deux listes parallèles et non liées structurellement. Il n'y a pas de garantie qu'un shot référence une scène existante (sauf le test `test_shot_scene_ids_reference_known_scenes`). C'est un test, pas un invariant du modèle.

**GAP-6 : `emotion` de scène ≠ émotion de shot**

Chaque shot hérite de l'émotion de sa scène parente (copiée telle quelle). Il n'y a pas de modulation d'émotion au niveau shot — tous les shots d'une scène "nervous" ont `emotion="nervous"`, même un shot de type "wide" de course qui serait plus "urgent" que "nervous".

### Risques de non-déterminisme cachés

- `_extract_proper_nouns()` dans Pass 1 : l'ordre de détection dépend de `sentence.split()` sur le texte source → déterministe tant que le texte l'est.
- `_atomize_action()` : split sur `", "` — déterministe mais dépendant du format exact produit par Pass 2 (pas garanti stable si Pass 2 change).

---

## 3. PASS-BY-PASS EVALUATION

### Pass 1 — Segmentation

**Correctness : 7/10**

Le mécanisme de segmentation fonctionne pour les cas couverts par les listes `LOCATION_PHRASES` / `TIME_PHRASES`. Il échoue pour des changements de lieu implicites (métaphores, pronoms anaphoriques, ellipses).

**Déterminisme : 9/10**

Entièrement déterministe. Risque marginal : `re.split(r"\n{2,}", ...)` produit des résultats différents selon les fins de ligne (CRLF vs LF) — géré en pratique car le test `test_real_text_no_crash` tourne.

**Clarté des règles : 8/10**

`LOCATION_PHRASES` et `TIME_PHRASES` dans `segmentation_rules.py` sont explicites. La règle "changement de catégorie d'action" est implémentée mais son déclenchement réel est difficile à prédire sans exécuter.

**Failure modes :**
- Texte sans double newline → une seule scène pour tout le texte
- Lieu détecté par sous-chaîne partielle : `"in the car"` peut matcher `"in the "` et capturer `"car"` comme location valide
- Noms propres en milieu de phrase en position i=0 (début de phrase) sont ignorés

**Scalability :**
- O(n) en paragraphes, O(k) en phrases par paragraphe — pas de problème jusqu'à ~10 000 mots. Au-delà, le scan linéaire des listes de verbes par phrase devient lent.

---

### Pass 2 — Visual Rewrite

**Correctness : 6/10**

La transformation émotion → action visuelle fonctionne pour les 5 émotions codées. Le problème : une phrase comme `"She was terrified of her future"` déclenche `scared` → `"trembles, takes backward steps, eyes widen"`. Ce remplacement est correct mais **perd le sujet** ("She") et produit une action sans référence au personnage. La `visual_action` résultante est anonyme.

**Déterminisme : 10/10**

Aucun risque. Règles purement booléennes.

**Clarté des règles : 9/10**

`EMOTION_RULES` est lisible et maintenable. Les 5 émotions couvrent les cas courants.

**Failure modes :**
- Texte sans émotion reconnaissable → toutes les phrases passent en "neutral", aucune transformation → `emotion="neutral"` pour la scène entière
- Multi-émotions dans une scène : seule la **première** match (dans `_detect_emotion_in_text`) définit l'émotion de toute la scène

**Scalability :**
- O(n × k) où n = phrases, k = émotions × mots-clés. Non bloquant.

---

### Pass 3 — Shot Atomization

**Correctness : 7/10**

La décomposition fonctionne. `_atomize_action()` sur `", "` est fragile : une action comme `"She opens the door, steps inside, and looks around"` donnera 3 parts dont `"and looks around"` — le `"and"` résiduel est un artefact.

`shot_type` et `camera_movement` sont déterministes mais à faible granularité (voir GAP-2).

`prompt` = texte brut sans contexte cinématographique structuré. Il est dérivé de l'action, pas des champs IR.

**Déterminisme : 9/10**

Entièrement déterministe. Risque : si `visual_actions` contient des chaînes avec `", "` internes à des noms propres (ex: `"New York, Manhattan"`), l'atomisation incorrecte pourrait produire des shots sans sens.

**Clarté des règles : 7/10**

`cinematography_rules.py` est propre. Le problème est l'absence de documentation sur les cas limites de `_atomize_action()`.

**Failure modes :**
- `visual_actions` vide pour une scène → `ValueError` (correctement géré)
- Action = chaîne vide après split → skippée silencieusement (condition `if not part.strip()`)
- Numérotation des shots : `shot_num` repart à 1 pour chaque scène → collisions d'ID impossibles car préfixé par `scene_id`

**Scalability :**
- Scène avec 50 visual_actions → 50+ shots dans un seul épisode. Aucun cap. Aucune validation de cohérence entre nombre de scènes et nombre de shots.

---

### Pass 4 — Compilation

**Correctness : 9/10**

Validation Pydantic stricte. `ValueError` systématique. Vérification explicite de la durée [3,8] **avant** la validation Pydantic (ce qui est correct car Pydantic ne contraint pas `duration_sec` via validator).

**Déterminisme : 10/10**

Aucun risque. Assemblage pur.

**Clarté des règles : 9/10**

Code lisible, guards explicites, alias backward-compat propre.

**Failure modes :**
- Un shot avec `scene_id` référençant une scène inexistante → **accepté silencieusement**. Pass 4 ne valide pas la cohérence référentielle shots ↔ scenes.
- `Shot.shot_type` et `Shot.camera_movement` ont des défauts (`"medium"`, `"static"`) → un dict passé sans ces champs ne lève pas d'erreur, ce qui peut masquer un bug de Pass 3.

**Scalability :**
- `[Scene(**s) for s in scenes]` : O(n). Non bloquant.

---

## 4. IR EVALUATION

### Verdict : **B — Semi-structured pipeline**

**Justification point par point :**

**Argument pour "prompt generator" (A) :**
- Le champ `prompt: str` est la valeur centrale consommée par les backends actuels (CSV, JSON flat)
- `prompt` ne peut pas être re-parsé par un moteur de rendu sans NLP
- Aucun décomposition `subject/verb/object` → impossible de générer une image sans re-interpréter le texte

**Argument contre "true IR" (C) :**
- Un vrai IR de compilateur (ex: LLVM IR, AST) est **indépendant de toute représentation textuelle**. Ici, `prompt` est une repr textuelle couplée à la logique.
- Un vrai IR ciné exposerait au minimum : `subject_id`, `action_type (enum)`, `object_id`, `framing (enum)`, `movement (enum)`, `duration_ms`. Tous typés, aucun free text.

**Argument pour "semi-structured" (B) — ce qui est vrai :**
- `shot_type` et `camera_movement` sont des champs structurés réels, typés, validés par mypy
- Les TypedDicts inter-passes définissent des contrats clairs et vérifiés statiquement
- Les règles sont centralisées, explicites et non-ambiguës dans leur application
- La hiérarchie `AIPRODOutput > Episode > Scene/Shot` est un IR de structure valide
- La distinction `scene_id` / `shot_id` avec format normalisé (`SCN_001_SHOT_001`) est une décision d'IR, pas de prompt engineering

**Conclusion :** Le système est à **~65% d'un vrai IR**. La structure existe. Le problème est que le contenu du `prompt` n'est pas décomposé — il reste une chaîne libre dérivée du texte source, ce qui rend le système dépendant d'un NLP aval pour toute utilisation sérieuse en rendu.

---

## 5. ARCHITECTURAL RISKS

### Couplage

**RISK-1 : `_atomize_action()` couplée au format de sortie de Pass 2**

Si Pass 2 change son format de `visual_actions` (ex: passe de `", "` comme séparateur à `"\n"`), Pass 3 casse silencieusement sans erreur. Aucun contrat ne définit le format interne des chaînes dans `List[str]`.

**RISK-2 : `prompt` couplé au texte brut**

`_build_prompt(action, location)` = `f"{clean}, in {location_str}."` — format hard-codé. Tout changement de format du prompt casse `test_json_byte_identical` et potentiellement les backends.

**RISK-3 : Listes de verbes dupliquées**

`_MOTION_VERBS` existe dans `duration_rules.py` ET dans `cinematography_rules.py` (`CAMERA_MOVEMENT_MOTION_KEYWORDS`). Les listes ne sont pas identiques. Un verbe ajouté dans l'une n'est pas automatiquement dans l'autre. Divergence garantie à terme.

### Extensibility limits

**LIMIT-1 : Ajouter un backend vidéo (Runway, Sora)**

Actuellement impossible sans NLP. `prompt` = texte libre. Un backend vidéo a besoin de : durée en frames (pas en secondes entières), type de transition, angle caméra, descripteur visuel de sujet. Rien de ça n'est dans l'IR.

**LIMIT-2 : Narratif long (roman entier)**

Pas de pagination, pas de limitation du nombre de scènes ou shots. Un roman de 80 000 mots produirait ~2 000 shots dans un seul objet en mémoire. Aucun streaming, aucun chunking.

**LIMIT-3 : Multi-épisodes**

`AIPRODOutput.episodes: List[Episode]` supporte structurellement plusieurs épisodes, mais `engine.run_pipeline()` crée toujours `episode_id="EP01"` par défaut. Pas de logique de découpage en épisodes.

### Technical debt

**DEBT-1 : `scene_id` référentielle non enforced**

`Shot.scene_id` devrait être une clé étrangère vers `Episode.scenes[*].scene_id`. Elle ne l'est pas. La seule vérification est dans le test, pas dans le modèle.

**DEBT-2 : `metadata: dict[str, Any]`**

`metadata` est un sac fourre-tout non typé dans `Shot` et `ShotDict`. Tout futur champ structuré sera tentant d'y mettre — et perdra les bénéfices de mypy strict.

**DEBT-3 : Alias backward-compat**

`atomize_shots = simplify_shots` et `compile_output = compile_episode` sont des aliases de backward-compat qui polluent l'API publique. À terme, ils créeront de la confusion sur quelle fonction utiliser.

---

## 6. MATURITY SCORE

### Overall : 6/10

Le système fonctionne, est testé, typé, et déterministe. Il manque la décomposition structurée de l'action, la validation référentielle, et la granularité cinématographique pour prétendre à plus.

### Determinism reliability : 9/10

Quasi-parfait. Le seul risque marginal est `_atomize_action()` sur des chaînes avec `", "` dans des noms propres composés. `test_json_byte_identical` valide le déterminisme de bout en bout.

### Architectural soundness : 6/10

La séparation core/backends est propre. Les TypedDicts inter-passes sont une bonne décision. Le problème est le couplage implicite entre les listes de verbes dupliquées et l'absence de validation référentielle shots ↔ scenes.

### IR quality : 5/10

`shot_type` et `camera_movement` sont des champs IR réels. Mais tant que `prompt` reste le champ principal et non une dérivation d'une représentation plus profonde, le système est à mi-chemin. Un IR digne de ce nom permettrait de reconstruire le `prompt` depuis les champs structurés — ce n'est pas encore le cas.

---

## 7. STRATEGIC NEXT STEPS

### #1 — Décomposer `visual_actions` en `VisualAction` typée **(impact : critique)**

Remplacer `visual_actions: List[str]` par `visual_actions: List[VisualAction]` où :

```python
class VisualAction(TypedDict):
    subject: str        # "John", "She", "The door"
    verb: str           # lemme normalisé : "walk", "open", "stare"
    object: NotRequired[str]   # "the briefcase", None
    modifier: NotRequired[str] # "quickly", "nervously"
```

Ce changement transforme le système de "semi-structured" à "vrai IR". Il est faisable sans NLP pour les cas simples (sujet = premier nom propre de la scène, verbe = premier verbe détecté, objet = remainder). C'est imparfait mais structuré.

### #2 — Unifier les listes de verbes **(impact : dette technique)**

Fusionner `_MOTION_VERBS` (duration_rules) et `CAMERA_MOVEMENT_MOTION_KEYWORDS` (cinematography_rules) en une seule source dans `verb_categories.py`. Les deux modules l'importent. Élimine la divergence garantie.

### #3 — Enforcer la référence `shot.scene_id → scene.scene_id` dans Pass 4 **(impact : correctness)**

Dans `compile_episode()`, ajouter :

```python
known_scene_ids = {s["scene_id"] for s in scenes}
for shot in shots:
    if shot["scene_id"] not in known_scene_ids:
        raise ValueError(f"PASS 4: shot '{shot['shot_id']}' references unknown scene '{shot['scene_id']}'")
```

Ce n'est pas un refactor — c'est combler un trou dans le contrat.

### #4 — Ajouter `camera_angle` comme champ structuré **(impact : IR quality)**

Valeurs : `"eye_level"` (défaut), `"low_angle"`, `"high_angle"`, `"overhead"`. Règles heuristiques simples : mots-clés `"looks down"`, `"towers over"`, `"bird's eye"`. Même pattern que `shot_type`. Amène l'IR de 3 → 4 champs cinématographiques structurés.

### #5 — Typer `Shot.shot_type` et `Shot.camera_movement` avec validation Pydantic **(impact : robustesse)**

Actuellement `str` avec défaut. Une valeur invalide (`"zoom"`, `"extreme_close"`) passe silencieusement. Ajouter un `field_validator` Pydantic :

```python
_VALID_SHOT_TYPES = {"wide", "medium", "close_up", "pov"}
_VALID_CAMERA_MOVEMENTS = {"static", "follow", "pan"}

@field_validator("shot_type")
@classmethod
def validate_shot_type(cls, v: str) -> str:
    if v not in _VALID_SHOT_TYPES:
        raise ValueError(f"Invalid shot_type: {v!r}")
    return v
```

Sans ça, la cohérence des valeurs n'est garantie que par les tests, pas par le modèle.

---

## 8. HARD VERDICT

> **"This is a promising prototype."**

Le système a une architecture saine, un déterminisme réel, et des contrats inter-passes vérifiés statiquement. Ce n'est pas du prompt engineering déguisé — les champs `shot_type` et `camera_movement` sont une décision d'IR légitime.

Mais il reste un prototype parce que le champ central de l'IR (`prompt`) est une chaîne libre non décomposée, que les listes de verbes divergent déjà entre modules, et qu'aucun backend réel de rendu ne peut consommer cet output sans re-parser le texte. Les 5 prochaines étapes sont claires et implémentables sans NLP.
