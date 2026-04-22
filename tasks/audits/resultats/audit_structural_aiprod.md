# AUDIT STRUCTUREL — AIPROD_V2 — 2026-04-21

**Périmètre** : 68 modules — core/ · core/adaptation/ · core/continuity/ · core/rules/ · core/scheduling/ · image_gen/ · video_gen/ · post_prod/ · backends/ · models/ · cli.py  
**Baseline** : commit `42f99d7` + corrections PA-01→PA-08 (278 tests, 0 mypy, 0 ruff)  
**Auditeur** : GitHub Copilot (Claude Sonnet 4.6)

---

## Résumé exécutif

L'architecture d'AIPROD_V2 est globalement saine. Les trois pipelines (IR rule-based, LLM, production) sont bien séparés. Les interfaces adapter (LLM, Image, Video, Audio) suivent un pattern cohérent ABC + NullAdapter. Les imports runtime dans `engine.py` évitent les dépendances circulaires. Les contrats IR sont typés via `TypedDict` (mypy-validated).

**8 problèmes identifiés** : 0 critique (🔴), 1 majeur (🟠), 7 mineurs (🟡).  
Le problème majeur est un couplage de détail d'implémentation entre `character_prepass.py` et `storyboard.py` (import de `DEFAULT_STYLE_TOKEN`). Les problèmes mineurs concernent principalement du dead code résiduel et trois `# type: ignore` dans `cli.py`.

---

## BLOC 1 — Pipeline réel

### PIPELINE IR (voie rule-based)

```
text
 └─► InputClassifier().classify() → "novel"           [core/adaptation/classifier.py]
      └─► segment(text) → list[RawScene]               [core/pass1_segment.py]
           └─► visual_rewrite(scenes) → list[VisualScene]  [core/pass2_visual.py]
                └─► StoryValidator().validate_all()     [core/adaptation/story_validator.py]
                     └─► simplify_shots(scenes) → list[ShotDict]  [core/pass3_shots.py]
                          └─► compile_episode(scenes, shots, title) → AIPRODOutput  [core/pass4_compile.py]
```

| Passe | Fichier | Fonction | Entrée | Sortie |
|---|---|---|---|---|
| Input classification | `core/adaptation/classifier.py` | `InputClassifier.classify()` | `str` | `"novel"` \| `"script"` |
| Pass 1 | `core/pass1_segment.py` | `segment()` | `str` | `list[RawScene]` |
| Pass 2 | `core/pass2_visual.py` | `visual_rewrite()` | `list[RawScene]` | `list[VisualScene]` |
| Validation | `core/adaptation/story_validator.py` | `StoryValidator.validate_all()` | `list[VisualScene]` | `list[VisualScene]` (filtré) |
| Pass 3 | `core/pass3_shots.py` | `simplify_shots()` | `list[VisualScene]` | `list[ShotDict]` |
| Pass 4 | `core/pass4_compile.py` | `compile_episode()` | `list[VisualScene], list[ShotDict], str` | `AIPRODOutput` |

### PIPELINE LLM

```
text
 └─► InputClassifier().classify() → "novel"
      └─► StoryExtractor().extract_all(llm, text, budget) → list[VisualScene]
           │  (chunks → extract_chunk() × N → Normalizer().normalize() → list[VisualScene])
           └─► StoryValidator().validate_all()
                └─► simplify_shots() → list[ShotDict]
                     └─► compile_episode() → AIPRODOutput
```

| Composant | Fichier | Rôle |
|---|---|---|
| `StoryExtractor` | `core/adaptation/story_extractor.py` | Chunking + LLM + Normalizer |
| `Normalizer` | `core/adaptation/normalizer.py` | dict[Any] → list[VisualScene] |
| `LLMRouter` | `core/adaptation/llm_router.py` | Route sur estimation tokens (len//4 vs 80K) |
| `ClaudeAdapter` | `core/adaptation/claude_adapter.py` | Anthropic API → dict |
| `GeminiAdapter` | `core/adaptation/gemini_adapter.py` | Google Generative AI → dict |

### PIPELINE SCRIPT (entrée screenplay)

```
text
 └─► InputClassifier().classify() → "script"
      └─► ScriptParser().parse(text) → list[VisualScene]   [core/adaptation/script_parser.py]
           └─► StoryValidator().validate_all()
                └─► simplify_shots() → list[ShotDict]
                     └─► compile_episode() → AIPRODOutput
```

`ScriptParser` produit directement des `VisualScene` (bypass de Pass1+Pass2).

### PIPELINE PRODUCTION

```
AIPRODOutput
 └─► EpisodeScheduler.run()                          [core/scheduling/episode_scheduler.py]
      ├─► CharacterPrepass.run(output)               [image_gen/character_prepass.py]
      │    └─► CharacterPrepassResult {registry: CharacterImageRegistry}
      ├─► StoryboardGenerator(prepass_registry=...).generate(output)  [image_gen/storyboard.py]
      │    └─► StoryboardOutput {frames: list[ShotStoryboardFrame]}
      ├─► VideoSequencer(adapter).generate(storyboard, output)        [video_gen/video_sequencer.py]
      │    └─► VideoOutput {clips: list[VideoClipResult]}
      └─► AudioSynchronizer(adapter).generate(video, output)          [post_prod/audio_synchronizer.py]
           └─► (list[AudioResult], ProductionOutput {timeline: list[TimelineClip]})
               └─► SchedulerResult {storyboard, video, production, metrics: RunMetrics}
```

| Composant | Fichier | Entrée | Sortie |
|---|---|---|---|
| `CharacterPrepass` | `image_gen/character_prepass.py` | `AIPRODOutput` | `CharacterPrepassResult` |
| `CharacterImageRegistry` | `image_gen/character_image_registry.py` | — | registre `name → image_url` |
| `StoryboardGenerator` | `image_gen/storyboard.py` | `AIPRODOutput` | `StoryboardOutput` |
| `VideoSequencer` | `video_gen/video_sequencer.py` | `StoryboardOutput, AIPRODOutput` | `VideoOutput` |
| `AudioSynchronizer` | `post_prod/audio_synchronizer.py` | `VideoOutput, AIPRODOutput` | `(list[AudioResult], ProductionOutput)` |
| `RunMetrics` | `core/run_metrics.py` | — | métriques latence + coût |

**Continuité optionnelle** (activée si `character_descriptions` passé à `run_pipeline`) :
```
AIPRODOutput
 └─► CharacterRegistry().build() + enrich_from_text()  [core/continuity/character_registry.py]
 └─► EmotionArcTracker().track()                        [core/continuity/emotion_arc.py]
 └─► PromptEnricher().enrich()                          [core/continuity/prompt_enricher.py]
      └─► AIPRODOutput (enrichi)
```

---

## BLOC 2 — Séparation des responsabilités

### Violations et observations

**engine.py — orchestrateur multi-responsabilités** *(acceptable)*  
`run_pipeline()` assume trois rôles : (1) classification d'entrée + routing LLM/rules/script, (2) passage des 4 passes + validation, (3) injection de continuité optionnelle (`character_descriptions`, lignes 88–96). Ce dernier rôle est fonctionnellement distinct et alourdit la signature. *(voir S06)*

**novel_pipe.py — module entier deprecated**  
`core/adaptation/novel_pipe.py` contient 4 fonctions (`extract_scenes`, `make_cinematic`, `to_screenplay`, `run_novel_pipe`). `run_novel_pipe()` lève un `DeprecationWarning`. Aucune de ces fonctions n'est appelée depuis `engine.py` ou `cli.py` — uniquement depuis `test_adaptation.py` (2 tests legacy). *(voir S02)*

**storyboard.py — méthode hors responsabilité principale**  
`StoryboardGenerator.prepass_character_sheets()` (ligne 59) opère sur un `CharacterSheetRegistry` qui n'est pas la responsabilité principale de `StoryboardGenerator`. Cette méthode n'est pas invoquée dans le pipeline de production (`EpisodeScheduler`, `cli.py`, `engine.py`) — uniquement dans 3 tests. *(voir S03)*

**Passes IR — SRP respecté** ✅  
- Pass1 : segmentation uniquement  
- Pass2 : réécriture visuelle uniquement  
- Pass3 : atomisation en shots uniquement  
- Pass4 : compilation + validation Pydantic uniquement  
Aucune logique de transformation dans la compilation, aucune validation dans les passes de transformation.

**Adapters — SRP respecté** ✅  
Chaque adapter (Claude, Gemini, Flux, Replicate, Runway, Kling, ElevenLabs, OpenAI TTS) est un fichier dédié, un seul rôle.

**Aliases backward-compat** ✅  
- `compile_output` (pass4_compile.py:76) : `DeprecationWarning` + remapping d'ordre explicite ✅  
- `atomize_shots = simplify_shots` (pass3_shots.py:185) : alias simple sans `DeprecationWarning`, utilisé dans `test_pipeline.py:22` ⚠️  
- `transform_visuals = visual_rewrite` (pass2_visual.py:166) : alias simple sans `DeprecationWarning`, utilisé dans `test_pipeline.py:21` ⚠️  

*(voir S07)*

---

## BLOC 3 — Couplage inter-modules

### Imports top-level vs. runtime

| Fichier | Pattern | Évaluation |
|---|---|---|
| `engine.py` | Tous imports dans le corps de fonction (sauf `AIPRODOutput`, `structlog`) | ✅ Pattern optimal — aucun import heavy au module-level |
| `cli.py` | Interfaces adapter importées top-level (lignes 7–9), adapters prod via `importlib` | ✅ Interfaces légères — OK |
| `episode_scheduler.py` | Top-level pour tous ses composants | ⚠️ Import lourd au module-level — acceptable car module de coordination |

### Couplage character_prepass.py → storyboard.py

```python
# character_prepass.py:14
from aiprod_adaptation.image_gen.storyboard import DEFAULT_STYLE_TOKEN
```

`DEFAULT_STYLE_TOKEN` est une constante de style (`"cinematic storyboard..."`) dont `character_prepass.py` a besoin pour sa valeur par défaut, mais qui est définie dans `storyboard.py`. Pas de cycle (storyboard.py importe `CharacterImageRegistry`, pas `character_prepass`), mais un couplage de détail d'implémentation. *(voir S01)*

### Dépendances circulaires potentielles

Aucune dépendance circulaire effective. Le découplage adopté (storyboard.py accepte `CharacterImageRegistry` en paramètre, pas `CharacterPrepassResult`) est correct. L'import `DEFAULT_STYLE_TOKEN` est le seul lien inverse.

### Aliases backward-compat — dette

`atomize_shots` et `transform_visuals` sont des assignations simples sans `DeprecationWarning`, contrairement à `compile_output`. Incohérence de traitement entre les trois aliases. *(voir S07)*

### `# type: ignore` dans le code de production

3 occurrences dans `cli.py` lignes 35, 50, 59 — sur le retour de `cls()` depuis `importlib`. Résolution possible via `typing.cast()`. *(voir S05)*

### Adapters prod — import lazy ✅

`FluxAdapter`, `ReplicateAdapter`, `RunwayAdapter`, `KlingAdapter`, `ElevenLabsAdapter`, `OpenAITTSAdapter` : tous chargés via `importlib.import_module()` dans `_load_*_adapter()`. Aucun import heavy au démarrage de `cli.py`. `SmartVideoRouter` : import direct (ligne 44) mais sans dépendance externe lourde — acceptable.

---

## BLOC 4 — Architecture globale

### Inventaire des packages — 68 modules

| Package | Modules | Statut |
|---|---|---|
| `core/` | engine, io, pass1–4, production_budget, run_metrics, cost_report | ✅ Tous actifs |
| `core/adaptation/` | classifier, claude, gemini, llm_adapter, llm_router, normalizer, novel_pipe, script_parser, story_extractor, story_validator | ⚠️ novel_pipe deprecated |
| `core/continuity/` | character_registry, emotion_arc, location_registry, prompt_enricher, prop_registry | ✅ Utilisés (chemin optionnel) |
| `core/rules/` | cinematography, duration, emotion, segmentation, verb_categories | ✅ Sources-of-truth bien isolées |
| `core/scheduling/` | episode_scheduler | ✅ Actif |
| `image_gen/` | character_image_registry, character_prepass, character_sheet, checkpoint, flux, image_adapter, image_request, replicate, storyboard | ⚠️ prepass_character_sheets() dead dans pipeline |
| `video_gen/` | kling, runway, smart_video_router, video_adapter, video_request, video_sequencer | ✅ Tous actifs |
| `post_prod/` | audio_adapter, audio_request, audio_synchronizer, audio_utils, elevenlabs, ffmpeg_exporter, openai_tts, ssml_builder | ✅ Tous actifs |
| `backends/` | base, csv_export, json_flat_export | ⚠️ Non exposés via CLI |
| `models/` | intermediate, schema | ✅ Contrats IR bien définis |
| `cli.py` | pipeline · storyboard · schedule | ✅ 3 commandes |

### Modules présents mais non actifs dans le pipeline principal

| Module | Situation |
|---|---|
| `core/adaptation/novel_pipe.py` | Deprecated, non appelé hors tests (2 tests legacy) |
| `image_gen/storyboard.py:prepass_character_sheets()` | Méthode non appelée dans pipeline prod |
| `backends/csv_export.py`, `backends/json_flat_export.py` | Fonctionnels, testés, mais sans point d'entrée CLI |

### core/__init__.py — API publique

Exporte correctement : `CostReport`, `ProductionBudget`, `RunMetrics`, `save_output`, `load_output`, `save_storyboard`, `load_storyboard`, `save_video`, `load_video`, `save_production`, `load_production`.  
**Non exportés** depuis `core/__init__.py` : `run_pipeline`, `run_pipeline_with_images`, `compile_episode`. Ces fonctions sont uniquement importables directement depuis leurs modules — cohérent avec une API orientée données.

### duration_rules.py — module documentation uniquement

`core/rules/duration_rules.py` ne contient que des docstrings/commentaires (pas de code exécutable). Son rôle est documentaire — les règles réelles sont dans `verb_categories.py` et utilisées dans `pass3_shots.py`. *(voir S08)*

---

## Problèmes identifiés

| ID | Sévérité | Fichier:ligne | Description |
|---|---|---|---|
| S01 | 🟠 | `image_gen/character_prepass.py:14` | Import de `DEFAULT_STYLE_TOKEN` depuis `storyboard.py` — couplage entre deux modules de même package. `DEFAULT_STYLE_TOKEN` devrait être définie dans un module de constantes partagé (ex: `image_gen/constants.py` ou inline dans chaque module). |
| S02 | 🟡 | `core/adaptation/novel_pipe.py:55` | Module entier deprecated. `run_novel_pipe()` n'est plus appelé depuis le code de production. 4 fonctions orphelines. 2 tests legacy dans `test_adaptation.py`. Devrait être supprimé ou marqué explicitement `# DEAD CODE — scheduled for removal`. |
| S03 | 🟡 | `image_gen/storyboard.py:59` | `prepass_character_sheets()` opère sur `CharacterSheetRegistry` mais n'est appelée dans aucun chemin de production (`engine.py`, `cli.py`, `episode_scheduler.py`). Hors responsabilité principale de `StoryboardGenerator`. Uniquement présente dans 3 tests. |
| S04 | 🟡 | `backends/csv_export.py`, `backends/json_flat_export.py` | Les backends CSV et JSON-flat sont fonctionnels et testés (9 tests) mais aucune commande CLI ne les invoque. `cmd_pipeline` utilise `save_output()` (JSON Pydantic). Les backends sont inaccessibles à l'utilisateur final sans code Python. |
| S05 | 🟡 | `cli.py:35,50,59` | `# type: ignore[no-any-return]` sur les 3 retours `cls()` dans `_load_*_adapter()`. Résolvable par `typing.cast(ImageAdapter, cls())` (resp. VideoAdapter, AudioAdapter). Viole la règle projet "Aucun # type: ignore". |
| S06 | 🟡 | `core/engine.py:88-96` | Injection de continuité optionnelle (`CharacterRegistry` + `EmotionArcTracker` + `PromptEnricher`) inlined dans `run_pipeline()`. Responsabilité mixte (pipeline + enrichissement). Candidat à extraction en `run_pipeline_with_continuity()` ou via un paramètre `enrichers: list[...]`. |
| S07 | 🟡 | `core/pass3_shots.py:185`, `core/pass2_visual.py:166` | Aliases `atomize_shots` et `transform_visuals` sans `DeprecationWarning`, contrairement à `compile_output` (pass4_compile.py:76) qui en a un. Traitement incohérent des trois aliases backward-compat. |
| S08 | 🟡 | `core/rules/duration_rules.py` | Fichier contenant uniquement des commentaires (pas de code exécutable). Rôle purement documentaire — devrait être un fichier `.md` ou un docstring dans `pass3_shots.py`, pas un module Python importable. |

---

## Recommandations prioritaires

### 🟠 S01 — Extraire DEFAULT_STYLE_TOKEN (character_prepass.py)

Déplacer la constante dans un module partagé, ou la dupliquer dans chaque module consommateur (constante simple) :

```python
# image_gen/character_prepass.py — option simple
_DEFAULT_STYLE_TOKEN = (
    "cinematic storyboard, 16:9 aspect ratio, film grain, anamorphic lens, color graded"
)
```

Cela supprime le couplage `character_prepass` → `storyboard` sans aucun impact fonctionnel.

### 🟡 S05 — Éliminer les # type: ignore dans cli.py

```python
import typing

def _load_image_adapter(name: str) -> ImageAdapter:
    if name == "null":
        return NullImageAdapter()
    import importlib
    module_path, class_name = _IMAGE_ADAPTERS[name].split(":")
    cls = getattr(importlib.import_module(module_path), class_name)
    return typing.cast(ImageAdapter, cls())
```

### 🟡 S07 — Ajouter DeprecationWarning aux aliases restants

```python
# pass3_shots.py
import warnings
def atomize_shots(scenes: List[VisualScene]) -> List[ShotDict]:
    """Deprecated. Use simplify_shots()."""
    warnings.warn("atomize_shots() is deprecated. Use simplify_shots().", DeprecationWarning, stacklevel=2)
    return simplify_shots(scenes)

# pass2_visual.py — idem pour transform_visuals
```

### 🟡 S02 — Marquer novel_pipe.py explicitement

Ajouter en tête de `novel_pipe.py` :
```python
# DEAD CODE — deprecated since StoryExtractor (commit 87e2595).
# Scheduled for removal. Kept only for test_adaptation.py legacy tests.
```

---

*Rapport généré depuis l'analyse statique du code source — baseline commit `42f99d7` + corrections PA-01→PA-08.*
