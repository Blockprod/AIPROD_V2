# AUDIT PIPELINE — AIPROD_V2 — 2026-04-21

**Périmètre** : pipeline rule-based (Pass1→Pass4), couche LLM (StoryExtractor, LLMRouter, StoryValidator), pipeline production (CharacterPrepass → StoryboardGenerator → VideoSequencer → AudioSynchronizer → EpisodeScheduler), continuité (PromptEnricher, LocationRegistry, PropRegistry).  
**Baseline** : commit `42f99d7` — 278 tests, 0 erreurs mypy, 0 erreurs ruff.  
**Auditeur** : GitHub Copilot (Claude Sonnet 4.6)

---

## Résumé exécutif

Le pipeline est structurellement solide. Les contrats IR entre passes sont définis via des `TypedDict` mypy-validated (`RawScene`, `VisualScene`, `ShotDict`) ce qui garantit une couverture statique complète. La couche LLM route correctement sur `LLMRouter` et le fallback rule-based est fonctionnel. Le pipeline production (image → vidéo → audio) respecte les contrats de données.

**6 problèmes identifiés** : 0 critique, 2 majeurs (🟠), 4 mineurs (🟡).  
Les 2 problèmes majeurs sont : (1) une déduplication agressive dans `extract_all()` susceptible d'éliminer des scènes valides sur des textes longs, et (2) l'alias `compile_output` qui inverse l'ordre des arguments par rapport à `compile_episode`.

---

## BLOC 1 — Contrats inter-passes (IR)

### Pass1 → Pass2 — ✅ CONFORME

| Clé émise par Pass1 (RawScene) | Attendue par Pass2 | Statut |
|---|---|---|
| `scene_id` | `.get("scene_id")` | ✅ |
| `characters` | `.get("characters", [])` | ✅ |
| `location` | `.get("location", "Unknown")` | ✅ |
| `time_of_day` | `.get("time_of_day")` | ✅ |
| `raw_text` | direct access `s["raw_text"]` | ✅ |

Détails :
- Format `scene_id` : `f"SCN_{index + 1:03d}"` → "SCN_001", "SCN_002" … ✅
- `location` défaut : `"Unknown"` (majuscule confirmée dans `_detect_location()`) ✅
- `time_of_day` : `Optional[str]`, `None` si non détecté ✅

### Pass2 → Pass3 — ✅ FONCTIONNEL (asymétrie documentée)

| Clé émise par Pass2 (VisualScene) | Attendue par Pass3 | Statut |
|---|---|---|
| `scene_id` | `scene.get("scene_id", "")` | ✅ |
| `characters` | `scene.get("characters", [])` | ✅ |
| `location` | `scene.get("location", "Unknown")` | ✅ |
| `time_of_day` | non utilisé en Pass3 | ✅ |
| `visual_actions` | `scene.get("visual_actions", [])` | ✅ |
| `dialogues` | non utilisé directement en Pass3 | ✅ |
| `emotion` | `scene.get("emotion", "neutral")` | ✅ |
| `pacing` | `scene.get("pacing", "medium")` | 🟡 `NotRequired` — absent voie rules-based |
| `time_of_day_visual` | `scene.get("time_of_day_visual", "day")` | 🟡 `NotRequired` — absent voie rules-based |
| `dominant_sound` | `scene.get("dominant_sound", "dialogue")` | 🟡 `NotRequired` — absent voie rules-based |

**Design gap** : `pacing`, `time_of_day_visual`, `dominant_sound` sont émis uniquement par la voie LLM (via `Normalizer.normalize()`). Sur la voie rules-based (Pass1 → Pass2), ces champs ne sont jamais produits. Pass3 utilise `.get()` avec valeurs par défaut — comportement fonctionnel, mais tous les shots rule-based auront systématiquement `pacing="medium"`, `time_of_day_visual="day"`, `dominant_sound="dialogue"` indépendamment du contenu. Documenté par `NotRequired` dans `intermediate.py`. *(voir P01)*

### Pass3 → Pass4 — ✅ CONFORME

| Clé émise par Pass3 (ShotDict) | Attendue par Pass4 (Shot model) | Statut |
|---|---|---|
| `shot_id` | `Shot.shot_id` | ✅ |
| `scene_id` | `Shot.scene_id` | ✅ |
| `prompt` | `Shot.prompt` | ✅ |
| `duration_sec` | `Shot.duration_sec`, validé [3, 8] | ✅ |
| `emotion` | `Shot.emotion` | ✅ |
| `shot_type` | `Shot.shot_type`, validé via `_VALID_SHOT_TYPES` | ✅ |
| `camera_movement` | `Shot.camera_movement`, validé via `_VALID_CAMERA_MOVEMENTS` | ✅ |
| `metadata` | `Shot.metadata = {}` (défaut si absent) | ✅ |

`Shot.shot_type` accepte exactement : `"wide"`, `"medium"`, `"close_up"`, `"pov"` — correspondance parfaite avec `SHOT_TYPE_RULES` + fallback `"medium"`. ✅  
`Shot.camera_movement` accepte : `"static"`, `"follow"`, `"pan"` — correspondance avec `CAMERA_MOTION_VERBS`. ✅

---

## BLOC 1b — Contrats couche LLM

### engine.py → StoryExtractor — ✅ CONFORME

```python
# engine.py:60
scenes_llm = StoryExtractor().extract_all(effective_llm, text, _budget)
```

- Signature : `extract_all(self, llm: LLMAdapter, text: str, budget: ProductionBudget) → list[VisualScene]` ✅
- `budget.max_chars_per_chunk` utilisé dans `split_into_chunks(text, budget.max_chars_per_chunk)` ✅
- `prior_summary` transmis entre chunks successifs : `f"Last scenes: {locations}."` ✅
- Prompt LLM contient `f"- Maximum {budget.max_scenes} scenes for this sequence\n"` ✅
- Fallback silencieux si `scenes_llm == []` → voie rule-based activée (NullLLMAdapter / CI) ✅

**Observation** : path single-chunk appelle `extract_chunk(llm, chunks[0], budget)` sans `prior_summary=""` explicite. OK (valeur par défaut), mais asymétrique avec le path multi-chunks. *(voir P05)*

### LLMRouter — ✅ CONFORME

- Hérite `LLMAdapter` : `class LLMRouter(LLMAdapter)` ✅
- Implémente `generate_json(prompt)` et `generate_text(prompt)` ✅
- Clé de routage : `len(prompt) // 4` (estimation tokens) vs `token_threshold=80_000` (≈320K chars) ✅
- Routage : ≤80K tokens → primary_llm ; >80K tokens → fallback_llm ✅

### StoryValidator — ✅ CONFORME

- Filtre uniquement (score ≥ threshold=0.5), sans mutation des données ✅
- Score : `1.0 - 0.25 × nb_issues` ✅
- Règles de disqualification : location manquante/unknown, aucune action filmable, pensées internes, action impossible, >2 personnages, émotion invalide ✅
- `engine.py:82` : `if not scenes_pass2: raise ValueError("StoryValidator: no filmable scenes...")` — préfixe non conforme à la convention "PASS N:" *(voir P06)*

### Normalizer — ✅ CONFORME

- Normalise les clés `actions`/`visual_actions` (alias backward-compat) ✅
- Injecte `pacing`, `time_of_day_visual`, `dominant_sound` uniquement si valeur valide (via frozensets) ✅
- `characters[:2]` — respecte la limite max_2_characters avant Pass3 ✅

### StoryExtractor — déduplication cross-chunks — ⚠️ P03

```python
# story_extractor.py
key = (scene["location"], (scene["characters"] or [""])[0])
if key not in seen:
    seen.add(key)
    all_scenes.append(scene)
```

Clé de déduplication : `(location, first_character)`. Sur des textes longs multi-chunks, deux scènes distinctes dans des chunks différents mais ayant même location et même premier personnage seront considérées comme doublons — la seconde sera silencieusement ignorée. *(voir P03)*

---

## BLOC 1c — Contrats pipeline production

### CharacterPrepass → StoryboardGenerator — ✅ CONFORME

```python
storyboard = StoryboardGenerator(
    adapter=image_adapter,
    prepass_registry=prepass_result.registry,
).generate(output)
```

- `prepass_result.registry` : `CharacterImageRegistry` transmis comme `prepass_registry` ✅
- `CharacterImageRegistry.get_reference(char)` retourne `""` (chaîne vide) si absent — jamais `None` ✅
- `ImageRequest.reference_image_url = ""` accepte la chaîne vide ✅

### StoryboardGenerator → VideoSequencer — ✅ CONFORME

| Champ StoryboardOutput | Usage VideoSequencer | Statut |
|---|---|---|
| `.frames: List[ShotStoryboardFrame]` | itéré dans `build_requests()` | ✅ |
| `frame.shot_id` | `VideoRequest.shot_id` | ✅ |
| `frame.image_url` | `VideoRequest.image_url` | ✅ |
| `frame.scene_id` | `VideoRequest.scene_id` | ✅ |

### VideoSequencer → AudioSynchronizer — ✅ CONFORME

| Champ VideoOutput | Usage AudioSynchronizer | Statut |
|---|---|---|
| `.clips: List[VideoClipResult]` | itéré dans `build_requests()` et pour `clip_by_shot` | ✅ |
| `clip.shot_id` | clé du dictionnaire `clip_by_shot` | ✅ |
| `clip.video_url` | `TimelineClip.video_url` | ✅ |
| `clip.duration_sec` | `video_dur` pour calcul silence_padding | ✅ |
| `clip.latency_ms` | non utilisé pour audio latency | ✅ |

`TimelineClip.latency_ms = audio.latency_ms` — correctement alimenté depuis l'audio ✅

### EpisodeScheduler — métriques latence — ✅ CONFORME

```python
metrics.image_latency_ms += sum(f.latency_ms for f in storyboard.frames)
metrics.total_latency_ms += metrics.image_latency_ms

metrics.video_latency_ms += sum(c.latency_ms for c in video.clips)
metrics.total_latency_ms += metrics.video_latency_ms

metrics.audio_latency_ms += sum(c.latency_ms for c in production.timeline)
metrics.total_latency_ms += metrics.audio_latency_ms
```

Pas de double-comptage : chaque stage ajoute sa propre latence une seule fois à `total_latency_ms`. ✅

### PromptEnricher / LocationRegistry / PropRegistry — ✅ CONFORMES

- `location_registry.get_prompt_hint(location)` retourne `""` si location inconnue ✅  
  Format si trouvé : `"LOCATION CONTEXT: {description}. Lighting: {lighting_hint}."` ✅
- `prop_registry.get_prompt_hint(shot_id)` retourne `""` si aucun prop pertinent ✅  
  Format si trouvé : `"PROPS IN SCENE: {desc1} held by {char}, {desc2}."` ✅
- `sorted(registry.keys())` dans `_enrich_prompt` → déterminisme garanti ✅
- `sorted(relevant, key=lambda p: p.name)` dans PropRegistry → déterminisme garanti ✅

---

## BLOC 2 — Gardes et gestion d'erreurs

| Pass | Condition gardée | Exception | Préfixe | Statut |
|---|---|---|---|---|
| Pass1 | `raw_text` vide ou whitespace-only | `ValueError` | "PASS 1:" | ✅ |
| Pass1 | segmentation → 0 scènes | `ValueError` | "PASS 1:" | ✅ |
| Pass2 | `scenes` liste vide | `ValueError` | "PASS 2:" | ✅ |
| Pass3 | `scenes` liste vide | `ValueError` | "PASS 3:" | ✅ |
| Pass3 | `visual_actions` vide pour une scène | `ValueError` | "PASS 3:" | ✅ |
| Pass3 | atomisation → 0 shots | `ValueError` | "PASS 3:" | ✅ |
| Pass4 | `title` vide | `ValueError` | "PASS 4:" | ✅ |
| Pass4 | `scenes` liste vide | `ValueError` | "PASS 4:" | ✅ |
| Pass4 | `shots` liste vide | `ValueError` | "PASS 4:" | ✅ |
| Pass4 | `shot.scene_id` référence inconnue | `ValueError` | "PASS 4:" | ✅ |
| Pass4 | `ValidationError` Pydantic | `ValueError(str(exc))` | — | ✅ |
| engine.py | StoryValidator → 0 scènes filmables | `ValueError` | "StoryValidator:" | 🟡 P06 |

**Observation** : La guard de Pass2 ne couvre pas le cas où une scène individuelle a `raw_text = ""` (possible si l'appelant bypass Pass1 et injecte des scènes manuellement). Cette scène produirait `visual_actions=[]`, ce qui déclencherait l'erreur en Pass3. Erreur correctement propagée, mais différée d'une passe. *(voir P02)*

---

## BLOC 3 — Logique de transformation

### Pass1 — Segmentation

- Découpage : `re.split(r"\n{2,}", raw_text)` → paragraphes ✅
- Conditions de nouvelle scène : changement de location, de time_of_day, ou de catégorie d'action entre paragraphes ✅
- `_extract_proper_nouns` : liste avec déduplication manuelle (pas de set) → ordre d'insertion préservé ✅
- `_EXCLUDE_WORDS` : `frozenset` — pas d'itération de set ✅

### Pass2 — Réécriture visuelle

- `EMOTION_RULES` : 5 entrées (angry, scared, sad, happy, nervous) + fallback "neutral" ✅
- `_INTERNAL_THOUGHT_WORDS` dans `emotion_rules.py` : 6 mots `["thought", "wondered", "realized", "remembered", "imagined", "believed"]`
- `_INTERNAL_THOUGHT_WORDS` dans `story_validator.py` : 9 mots (+ `"felt"`, `"knew"`, `"hoped"`) ✅ **Asymétrie** *(voir P04)*
- `_DIALOGUE_RE = r'"([^"]*)"'` : capture uniquement guillemets droits doubles *(voir P07)*
- Alias `transform_visuals = visual_rewrite` ✅

### Pass3 — Décomposition en shots

- Format `shot_id` : `f"{scene_id}_SHOT_{shot_num:03d}"` avec compteur par scène (reset à 1) ✅
- Duration : base=3, +1 si verb_motion, +1 si verb_interaction, +1 si verb_perception, +1 si `len(action.split()) > 10`, clamp[3, 8] ✅
- Modificateur pacing : `"fast"` → `min(dur, 5)` ; `"slow"` → `max(dur, 5)` ✅
- `SHOT_TYPE_RULES` : `pov` > `close_up` > `wide` > fallback `"medium"` (premier match gagne) ✅
- Alias `atomize_shots = simplify_shots` ✅

### Pass4 — Compilation

- Ordre de validation : title → scenes → shots → intégrité shot.scene_id → Pydantic scenes → duration [3,8] → Pydantic shots → Pydantic episode → Pydantic output ✅
- `compile_episode(scenes, shots, title, episode_id="EP01")` : ordre d'arguments correct ✅
- Alias `compile_output(title, scenes, shots, episode_id)` → réinversé vers `compile_episode(scenes, shots, title, episode_id)` — 🟠 **ordre inversé entre l'alias et la fonction cible** *(voir P08)*

---

## BLOC 4 — Déterminisme

| Composant | Vecteur de non-déterminisme potentiel | Statut |
|---|---|---|
| Pass1–Pass4 | `random`, `uuid`, `shuffle`, `datetime.now()` | ✅ Absent |
| `_extract_proper_nouns` | Déduplication par liste (pas set) | ✅ Ordre préservé |
| `extract_all()` | `seen: set[tuple]` — test d'appartenance uniquement, `all_scenes: list` | ✅ Ordre déterministe |
| `PromptEnricher._enrich_prompt` | `sorted(registry.keys())` explicite | ✅ |
| `PropRegistry.get_prompt_hint` | `sorted(relevant, key=lambda p: p.name)` | ✅ |
| `CharacterImageRegistry.known_characters()` | `list(self._registry.keys())` — ordre insertion (Python 3.7+) | 🟡 Non trié, mais stable pour même input |
| `StoryValidator.validate_all()` | Itère `self._rules` (list ordonnée) | ✅ |
| `SHOT_TYPE_RULES`, `EMOTION_RULES` | List ordonnée, premier match gagne | ✅ |
| `_EXCLUDE_WORDS`, `_VALID_PACING` etc. | `frozenset` — test d'appartenance uniquement | ✅ |

Aucune source d'aléa identifiée dans le chemin d'exécution principal. ✅

---

## Problèmes identifiés

| ID | Sévérité | Bloc | Fichier:ligne | Description |
|---|---|---|---|---|
| P01 | 🟡 mineure | Bloc 1 / Pass2→Pass3 | `models/intermediate.py:38-40` | `pacing`, `time_of_day_visual`, `dominant_sound` définis `NotRequired` dans `VisualScene` mais jamais produits par la voie rules-based (Pass1→Pass2). Sur cette voie, tous les shots héritent des valeurs par défaut ("medium"/"day"/"dialogue") indépendamment du contenu réel. |
| P02 | 🟡 mineure | Bloc 2 / Pass2 | `core/pass2_visual.py` | Aucune garde sur `raw_text=""` au niveau d'une scène individuelle. Une scène avec `raw_text=""` produit `visual_actions=[]`, erreur différée en Pass3 (comportement acceptable mais non documenté). |
| P03 | 🟠 majeure | Bloc 1b / StoryExtractor | `core/adaptation/story_extractor.py:168-175` | Déduplication cross-chunks par clé `(location, first_character)` trop agressive : deux scènes distinctes de même lieu avec même premier personnage dans des chunks différents → la seconde est silencieusement ignorée. Sur des textes longs, ce comportement peut supprimer des scènes valides sans avertissement. |
| P04 | 🟡 mineure | Bloc 3 / Pass2 | `core/rules/emotion_rules.py:45` vs `core/adaptation/story_validator.py:21` | Asymétrie des listes `_INTERNAL_THOUGHT_WORDS` : 6 entrées dans `emotion_rules.py` (utilisé par Pass2), 9 dans `story_validator.py` (+ `"felt"`, `"knew"`, `"hoped"`). Les phrases avec ces 3 verbes ne sont pas filtrées par Pass2 et peuvent aboutir dans `visual_actions`. |
| P05 | 🟡 mineure | Bloc 1b / LLM | `core/adaptation/story_extractor.py:171` | Path single-chunk : `extract_chunk(llm, chunks[0], budget)` appelé sans `prior_summary=""` explicite. Fonctionnel (valeur par défaut), mais asymétrique avec le path multi-chunks qui passe explicitement `prior_summary`. |
| P06 | 🟡 mineure | Bloc 2 / engine | `core/engine.py:82` | Guard StoryValidator ne respecte pas la convention de préfixe "PASS N:" : `raise ValueError("StoryValidator: no filmable scenes...")` — préfixe hétérogène avec les autres gardes. |
| P07 | 🟡 mineure | Bloc 3 / Pass2 | `core/pass2_visual.py` | `_DIALOGUE_RE = r'"([^"]*)"'` capture uniquement les guillemets droits doubles ASCII. Les guillemets typographiques `"..."` (U+201C / U+201D), fréquents dans les romans, ne sont pas capturés — les dialogues en guillemets courbes ne seront pas extraits. |
| P08 | 🟠 majeure | Bloc 3 / Pass4 | `core/pass4_compile.py:169` | Alias `compile_output(title, scenes, shots, episode_id)` inverse l'ordre des 3 premiers arguments par rapport à `compile_episode(scenes, shots, title, episode_id)`. L'alias ré-mappe correctement les arguments en interne, mais un appelant qui compare les deux signatures peut faire un appel positionnel erroné en croyant que les ordres sont identiques. Risque de régression silencieuse. |

---

## Recommandations prioritaires

### 🟠 P03 — Déduplication cross-chunks agressive (story_extractor.py)

**Recommandation** : Remplacer la déduplication par `(location, first_character)` par une déduplication basée sur le contenu textuel (hash court du `raw_text`) ou supprimer complètement la déduplication cross-chunks (la validation se fait en aval par StoryValidator).

```python
# Option : hash du contenu
key = hash(scene.get("raw_text", "")[:200])
```

Priorité : haute — risque de données manquantes sur des épisodes longs sans aucun signal d'erreur.

### 🟠 P08 — Inversion d'arguments dans compile_output (pass4_compile.py)

**Recommandation** : Aligner la signature de l'alias avec la fonction cible, ou ajouter un `DeprecationWarning` explicite avec la note sur l'inversion d'ordre.

```python
# Documenter l'inversion de façon visible
def compile_output(
    title: str,           # ← ATTENTION : ordre différent de compile_episode
    scenes: ...,
    shots: ...,
    episode_id: str = "EP01"
) -> AIPRODOutput:
    """Deprecated. NOTE: argument order differs from compile_episode."""
    import warnings
    warnings.warn("compile_output is deprecated. Use compile_episode().", DeprecationWarning, stacklevel=2)
    return compile_episode(scenes, shots, title, episode_id)
```

### 🟡 P04 — Synchroniser _INTERNAL_THOUGHT_WORDS (emotion_rules.py)

Ajouter `"felt"`, `"knew"`, `"hoped"` à la liste dans `emotion_rules.py` pour alignement avec `story_validator.py`.

### 🟡 P07 — Étendre _DIALOGUE_RE aux guillemets typographiques (pass2_visual.py)

```python
_DIALOGUE_RE = re.compile(r'["\u201C]([^"\u201D]*)["\u201D]')
```

### 🟡 P01 — Documenter l'asymétrie voie rules-based / voie LLM

Ajouter un commentaire dans `pass3_shots.py` expliquant que `pacing`/`time_of_day_visual`/`dominant_sound` n'ont de valeur réelle que sur la voie LLM, pour prévenir les mainteneurs futurs.

---

*Rapport généré automatiquement à partir de l'analyse statique du code source — commit `42f99d7`.*
