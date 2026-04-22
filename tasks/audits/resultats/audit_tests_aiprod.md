---
type: audit
dimension: tests
projet: AIPROD_V2
baseline: 278 tests · 0 failing · commit 42f99d7
creation: 2026-04-22 à 10:18
---

# AUDIT TESTS — AIPROD_V2 — 2026-04-22

## Résumé exécutif

**Baseline** : 278 tests, 0 failing (post-session master corrections)  
**Coverage globale** : 92 % (3668 stmts, 292 manquants)  
**Score** : 🟡 — 0🔴 · 1🟠 · 7🟡

Points forts :
- 10 fichiers de test, bon découpage par couche fonctionnelle
- Déterminisme byte-level vérifié (test dédié)
- Stubs déterministes (NullImageAdapter / NullVideoAdapter / NullAudioAdapter) utilisés systématiquement
- Tests de régression structurels (schéma Pydantic, ValueError, guards)

Points faibles :
- `cli.py` à 73 % : branches `--output-format csv/json-flat`, `_load_image_adapter("flux"/"replicate")`, `_load_video_adapter("smart")` non couvertes
- `pass4_compile.py` à 82 % : branches ValidationError non atteignables directement via pass4 (couverture acceptable)
- `audio_utils.py` à 67 % : branche mutagen réelle (lignes 28-33) non couverte — justifié (mutagen optionnel en CI)
- `CostReport.to_summary_str()` jamais appelé dans les tests
- `pass3_shots.py` : cas `scene avec 0 visual_actions` → `ValueError` non testé directement via `simplify_shots()`
- `StoryValidator.validate_all()` → liste vide non testée via engine (edge case : toutes les scènes filtrées)
- `EpisodeScheduler` : aucun test avec `AIPRODOutput` vide (0 scènes / 0 shots)

---

## BLOC 1 — Inventaire des tests par fichier

### test_pipeline.py — 55 tests ✅

| Classe | Tests | Ce qui est testé |
|---|---|---|
| `TestEmptyInput` | 8 | segment(""), segment(" "), transform_visuals([]), atomize_shots([]), compile_output empty scenes/shots/title, run_pipeline("") |
| `TestMultiLocation` | 3 | 2 scènes produites sur texte multi-lieux, scene_ids uniques et ordonnés, location capturée |
| `TestTimeJump` | 2 | Phrase temporelle crée nouvelle scène, phrases détectées |
| `TestInternalThoughts` | 4 | Pensée → action physique, phrase non-pensée inchangée, dialogues préservés, nom abstrait remplacé |
| `TestDeterminism` | 2 | model_dump identique ×2, JSON byte-identical ×2 |
| `TestInvalidDuration` | 6 | duration<3 → ValueError, duration>8 → ValueError, bornes 3 et 8 valides, Shot rejecte direct, shot→scene inconnue |
| `TestFullPipeline` | 9 | AIPRODOutput retourné, episode EP01, durations valides, scene_ids référencés, title préservé, ≥1 scène, ≥1 shot, pas de pensée dans visual_actions |
| `TestRealText` | 1 | Texte littéraire réel sans crash |
| `TestShotStructure` | 5 | shot_type valide, camera_movement valide, prompt sans préfixe shot_type, shot_type invalide → ValueError, camera_movement invalide → ValueError |
| `TestProductionBudget` | 6 | valeurs par défaut, factory for_short, factory for_episode_45, shots_estimate, pipeline accepte budget, budget None → défaut |
| `TestVisualSceneEnrichment` | 5 | pacing fast → duration ≤5, pacing slow → duration ≥5, time_of_day_visual injecté, dominant_sound=silence, pacing manquant → medium |
| `TestMultiEpisode` | 5 | compile 2 épisodes, shot_ids uniques, scene_ids uniques, episode_ids distincts, total shots couvre tous épisodes |

### test_adaptation.py — 47 tests ✅

| Classe | Tests | Ce qui est testé |
|---|---|---|
| `TestInputClassifier` | 3 | novel → "novel", "INT." → "script", "FADE IN:" → "script" |
| `TestNullLLMAdapter` | 2 | retourne dict, déterministe |
| `TestScriptParser` | 5 | 1 scène parsée, caractère extrait, action → visual_actions, scènes ordonnées, script vide → [] |
| `TestStoryExtractorDeterminism` | 2 | NullLLM → list, déterministe ×2 |
| `TestEngineRouting` | 3 | novel → rule fallback, script → output, null adapter byte-identical |
| `TestStoryExtractor` | 5 | retourne list, fallback sur LLM vide, 1 appel LLM, respecte max_scenes, prior_summary injecté |
| `TestStoryValidator` | 8 | score 1.0, location manquante, pensée interne, action impossible, trop de perso, émotion invalide, validate_all filtre, validate_all retourne tout valide |
| `TestLLMRouter` | 5 | claude pour court, gemini pour long, boundary, threshold custom, null adapters 2 chemins |
| `TestSplitIntoChunks` | 6 | max_chars respecté, découpe aux frontières, paragraphe tronqué, texte vide → [], extract_all = extract (1 chunk), extract_all multi-chunks prior_summary |
| `TestProductionBudgetChunk` | 4 | max_chars_per_chunk défaut, episode_45 plus grand, extract_all respecte budget, frozen dataclass immuable |
| `TestLLMRouterCompleteness` | 4 | extract_all appelé pas extract, budget transmis, LLMRouter is LLMAdapter, engine utilise extract_all |

### test_image_gen.py — 46 tests ✅

| Classe | Tests | Ce qui est testé |
|---|---|---|
| `TestImageRequest` | 4 | valeurs par défaut, steps invalide → ValueError, guidance invalide → ValueError, generated_count |
| `TestNullImageAdapter` | 3 | retourne ImageResult, déterministe, shot_id préservé |
| `TestStoryboardGenerator` | 6 | 1 résultat/shot, déterministe, title préservé, generated_count, build_requests_count, erreur adapter ne crash pas |
| `TestRunPipelineWithImages` | 3 | null adapter, pas d'adapter, output inchangé |
| `TestCharacterImageRegistry` | 4 | stocke 1ère image, pas d'écrasement, "" pour inconnu, référence injectée au 2ème shot |
| `TestCharacterImageRegistryCanonical` | 4 | stocke canonical_prompt, pas d'écrasement, prompt injecté, pas de canonical → pas de crash |
| `TestStyleToken` | 3 | défaut injecté partout, custom override, chaîne vide acceptée |
| `TestCharacterSheetRegistry` | 6 | register/get, pas d'écrasement, all_sheets retourne list, prepass génère 1 image/sheet, idempotent, erreur ne crash pas |
| `TestShotStoryboardFrame` | 4 | prompt_used présent, seed_used présent, style_token sur output, frames_count |
| `TestCheckpointStore` | 5 | has() après save(), get() retourne frame, storyboard saute cached, reprend depuis checkpoint partiel, fichier persiste et recharge |
| `TestCharacterPrepass` | 4 | 1 image/personnage, popule registry, gère échec adapter, storyboard utilise prepass registry |

### test_video_gen.py — 32 tests ✅

| Classe | Tests | Ce qui est testé |
|---|---|---|
| `TestVideoRequest` | 4 | motion_score défaut, duration préservée, generated ≤ total, motion_score invalide → ValueError |
| `TestNullVideoAdapter` | 3 | retourne VideoClipResult, déterministe, shot_id préservé |
| `TestVideoSequencer` | 6 | 1 clip/shot, déterministe, title préservé, generated_count, build_requests, erreur ne crash pas |
| `TestRunPipelineWithVideo` | 3 | null adapters, pas de video adapter, pas de image adapter |
| `TestLastFrameChaining` | 4 | 1er shot sans last_frame, scènes différentes non chaînées, URL vide non chaînée, champ last_frame_url existe |
| `TestSmartVideoRouter` | 5 | runway pour court, kling pour long, boundary runway, boundary+1 kling, threshold custom |
| `TestStoryboardToVideoIntegration` | 4 | VideoRequest a image_url, build_requests image_url depuis storyboard, image_url injectée, frames = requests |
| `TestSmartVideoRouterInterface` | 3 | implements VideoAdapter, route short → runway, route long → kling |

### test_post_prod.py — 29 tests ✅

| Classe | Tests | Ce qui est testé |
|---|---|---|
| `TestAudioRequest` | 4 | voice_id défaut, language défaut, total_duration sum, duration_hint invalide → ValueError |
| `TestNullAudioAdapter` | 3 | retourne AudioResult, déterministe, shot_id préservé |
| `TestAudioSynchronizer` | 6 | 1 audio/shot, start_sec cumulatif, total_duration sum, déterministe, title préservé, erreur ne crash pas |
| `TestRunPipelineFull` | 3 | null adapters, pas d'audio adapter, output inchangé |
| `TestAudioDurationSync` | 4 | champ audio_duration, silence_padding si audio plus court, durée réelle quand disponible, audio_utils fallback sans mutagen |
| `TestSSMLBuilder` | 5 | balises `<speak>`, fear → rate slow, joy → pitch high, émotion inconnue → neutral, ssml flag défaut False |
| `TestFFmpegExporter` | 4 | raise si ffmpeg absent, commande correcte, résolution respectée, fps respecté |

### test_scheduling.py — 21 tests ✅

| Classe | Tests | Ce qui est testé |
|---|---|---|
| `TestEpisodeScheduler` | 6 | retourne SchedulerResult, frames = shots, clips = frames, timeline = clips, image_url propagées, metrics présentes |
| `TestRunMetrics` | 7 | success_rate 100%, partiel, 0 demandé, average_latency, latency 0 generated, shots_requested = total, shots_generated = storyboard.generated |
| `TestAudioLatency` | 4 | champ latency_ms, synchronizer popule latency, audio_latency=0 avec null, total_latency inclut toutes étapes |
| `TestCostReport` | 4 | valeurs par défaut=0, total_cost somme, merge somme, run_metrics a cost alimenté |

### test_continuity.py — 24 tests ✅

| Classe | Tests | Ce qui est testé |
|---|---|---|
| `TestCharacterRegistry` | 5 | extrait tous perso, déduplique, tracks toutes scènes, output vide → vide, enrich_from_text |
| `TestEmotionArcTracker` | 5 | all shots en ordre, 1er shot sans previous, transition abrupte détectée, transition douce acceptée, get_warnings retourne messages |
| `TestPromptEnricher` | 4 | injecte description, skip description vide, déterministe, n'altère pas l'input |
| `TestEngineWithContinuity` | 2 | sans continuity inchangé, avec descriptions enrichit prompts |
| `TestLocationRegistry` | 3 | construit depuis output, prompt_hint contient nom, inconnue → vide |
| `TestPropRegistry` | 3 | register/retrieve, get_active_props, prompt_hint contient prop |
| `TestPromptEnricherWithLocationAndProp` | 2 | injecte location_hint, injecte prop_hint |

### test_cli.py — 9 tests ✅

| Classe | Tests | Ce qui est testé |
|---|---|---|
| `TestCLIParser` | 3 | help sans crash, missing --input → nonzero, missing --title → nonzero |
| `TestCLIPipeline` | 2 | pipeline → JSON valide, storyboard lit output JSON |
| `TestCLIAdapters` | 4 | image_adapter null par défaut, nom invalide → nonzero, cmd_schedule → JSON scheduler, schedule sauve storyboard+video+production |

### test_backends.py — 9 tests ✅

| Classe | Tests | Ce qui est testé |
|---|---|---|
| `TestCsvExport` | 3 | header CSV, row_count, déterministe |
| `TestJsonFlatExport` | 3 | liste JSON, episode_id présent, déterministe |
| `TestMultiEpisodeBackends` | 3 | CSV tous épisodes, JSON flat tous épisodes, deux episode_ids présents |

### test_io.py — 6 tests ✅

| Classe | Tests | Ce qui est testé |
|---|---|---|
| `TestSaveLoadOutput` | 3 | round-trip, crée dossiers parents, JSON invalide → ValidationError |
| `TestSaveLoadStoryboard` | 1 | round-trip |
| `TestSaveLoadVideo` | 1 | round-trip |
| `TestSaveLoadProduction` | 1 | round-trip |

**Total : 278 tests — tous passants ✅**

---

## BLOC 2 — Couverture par module

### Couverture complète (100 %) ✅
`backends/base.py`, `backends/csv_export.py`, `backends/json_flat_export.py`,  
`core/adaptation/classifier.py`, `core/adaptation/llm_adapter.py`, `core/adaptation/llm_router.py`,  
`core/adaptation/script_parser.py`, `core/adaptation/story_validator.py`,  
`core/continuity/*` (emotion_arc, location_registry, prop_registry),  
`core/io.py`, `core/production_budget.py`, `core/run_metrics.py`, `core/rules/*`,  
`image_gen/character_image_registry.py`, `image_gen/character_sheet.py`,  
`image_gen/image_adapter.py`, `models/intermediate.py`,  
`post_prod/audio_adapter.py`, `post_prod/ssml_builder.py`,  
`video_gen/smart_video_router.py`, `video_gen/video_adapter.py`

### Couverture élevée (89–98 %) — lacunes mineures

| Module | % | Lignes manquantes | Analyse |
|---|---|---|---|
| `core/pass1_segment.py` | 95% | 112, 136, 187, 205, 236 | Branches `_action_category` sur verbes rares ; `_build_scene` cas `loc=None+time=None` en milieu de texte ; flush final sans nouvelle scène |
| `core/pass2_visual.py` | 91% | 75-78, 130 | `_transform_sentence` : branch émotion sans `visual_action` (return sentence) ; `transform_visuals` deprecated wrapper |
| `core/pass3_shots.py` | 97% | 147, 153, 180 | `_atomize_action` : action se terminant par `!`/`?` (testée seulement `.`) ; branch `shots` vide après atomization |
| `core/pass4_compile.py` | 82% | 57-58, 70-71, 75-76, 80-81 | `ValidationError` sur Scene, Shot, Episode, AIPRODOutput — atteignables seulement avec TypedDict malformé hors du pipeline normal |
| `core/adaptation/story_extractor.py` | 94% | 32-34, 143 | `split_into_chunks` : paragraphe tronqué à `last_dot` (ligne 34) ; `extract` avec `prior_summary` non-vide dans contexte multi-chunk |
| `core/adaptation/normalizer.py` | 89% | 37, 40, 43 | Champs `pacing`, `time_of_day_visual`, `dominant_sound` en dehors des valeurs enum → branche de rejection |
| `core/continuity/character_registry.py` | 96% | 23 | `enrich_from_text` avec description vide `""` pour un personnage connu |
| `core/continuity/prompt_enricher.py` | 97% | 72 | Branche location hint vide (`get_prompt_hint` → `""`) |
| `core/cost_report.py` | 95% | 42 | `to_summary_str()` jamais appelé dans les tests |
| `core/engine.py` | 95% | 77-78, 89, 130 | `logger.debug("pass1_start")` (2 branches) ; `logger.info("continuity_applied")` indirect via engine |
| `image_gen/checkpoint.py` | 89% | 19-20, 38 | Chargement depuis fichier avec JSON corrompu (exception silencieuse) ; `save()` avec `self._path is None` (path= None, branche non-write) |
| `image_gen/storyboard.py` | 89% | 91-96, 99, 113, 130 | Seed par défaut vs seed explicite ; branche `style_token` vide sur prepass ; injection `character_prompts` explicites |
| `image_gen/character_prepass.py` | 94% | 72-74 | `_unique_characters()` avec `AIPRODOutput` sans personnages (0 chars) → `generated=0, failed=0` |
| `models/schema.py` | 98% | 33 | Branche `Scene.characters = []` via Pydantic validator edge case |
| `post_prod/audio_request.py` | 98% | 67 | Champ `resolution` avec valeur non-défaut sur `ProductionOutput` |
| `post_prod/audio_synchronizer.py` | 98% | 31 | Branche erreur adapter dans synchronizer (silent fallback) |
| `post_prod/audio_utils.py` | 67% | 28-33 | **Branche mutagen installé** — import réel + décodage MP3 non couvert (mutagen non installé en CI) |
| `post_prod/ffmpeg_exporter.py` | 97% | 26 | Branche `--format` non-défaut sur export |
| `image_gen/image_request.py` | 96% | 23, 30 | Validateurs de champs `steps` et `guidance_scale` edge cases |
| `video_gen/video_request.py` | 97% | 21 | Validateur `motion_score` edge case |
| `video_gen/video_sequencer.py` | 97% | 61 | Branche erreur adapter silencieuse |

### Non couvert (0 %) — intentionnel (adapters réels, CI uniquement Null)

| Module | Raison |
|---|---|
| `core/adaptation/claude_adapter.py` | Requiert API key Claude — hors scope CI |
| `core/adaptation/gemini_adapter.py` | Requiert API key Gemini — hors scope CI |
| `image_gen/flux_adapter.py` | Requiert API Replicate/Flux |
| `image_gen/replicate_adapter.py` | Requiert API Replicate |
| `video_gen/kling_adapter.py` | Requiert API Kling |
| `video_gen/runway_adapter.py` | Requiert API Runway |
| `post_prod/elevenlabs_adapter.py` | Requiert API ElevenLabs |
| `post_prod/openai_tts_adapter.py` | Requiert API OpenAI |

Ces modules sont correctement isolés (0 % coverage en CI = attendu).

### cli.py — 73 % 🟠

**Lignes non couvertes** : 33-36, 42-51, 57-60, 135-136, 138-139, 185-195, 199

- **Lignes 33-36** : `_load_image_adapter("flux")` et `_load_image_adapter("replicate")` — chemin importlib non testé
- **Lignes 42-51** : `_load_video_adapter("smart")`, `_load_video_adapter("runway")`, `_load_video_adapter("kling")` — adapteurs non-null non testés
- **Lignes 57-60** : `_load_audio_adapter("elevenlabs")` et `_load_audio_adapter("openai")`
- **Lignes 135-136, 138-139** : `cmd_pipeline` avec `--output-format csv` et `--output-format json-flat` non testés
- **Lignes 185-195** : `cmd_schedule` avec formats de sortie alternatifs ; chemin d'écriture `metrics.json`
- **Ligne 199** : `main()` appelé directement via `if __name__ == "__main__"`

---

## BLOC 3 — Qualité des fixtures

### Format des données de test

- ✅ `test_pipeline.py` : les `RawScene` et `VisualScene` de classe utilisent `cast(RawScene, {...})` et `cast(VisualScene, {...})` — format conforme à pass1/pass2
- ✅ `test_pipeline.py` : les `ShotDict` ont les champs requis par pass4 (shot_id, scene_id, prompt, duration_sec, emotion, shot_type, camera_movement)
- ✅ `test_scheduling.py` : utilise exclusivement `NullImageAdapter`, `NullVideoAdapter`, `NullAudioAdapter`
- ✅ Les scènes de test VisualScene ont `visual_actions` non vides (requis par pass3)
- ✅ Les dialogues sont préservés dans les fixtures VisualScene

### Dépendances entre tests

- ✅ Aucun état global mutable partagé entre classes de test
- ✅ Les helpers `_output()`, `_scheduler()` en module-level dans `test_scheduling.py` sont des fonctions (recréent l'état à chaque appel) — pas de pollution de cache
- ✅ `_storyboard_and_output()` dans `test_video_gen.py` est une fonction — pas un singleton
- ⚠️ `test_image_gen.py::TestCheckpointStore::test_checkpoint_store_file_persists_and_reloads` utilise `tmp_path` (fixture pytest) — correct
- ✅ Les fixtures de classe (`_BASE_SCENE`, `_THOUGHT_SCENE`) dans `test_pipeline.py` sont des `ClassVar` typées immuables — pas de risque de mutation inter-test

### Fixtures de classe vs pytest.fixture

- ✅ Utilisation cohérente : les tests simples utilisent des attributs de classe ou des helpers de module
- ✅ `test_image_gen.py` utilise `tmp_path` (pytest fixture) uniquement pour les tests fichier — correct
- ✅ `test_cli.py` utilise `tempfile.TemporaryDirectory()` comme context manager — correct, mais `tmp_path` serait plus idiomatique
- 🟡 `test_post_prod.py` : `setup_method` dans `TestSSMLBuilder` — pattern valide mais `tmp_path` + `@pytest.fixture` serait plus standard pour une infrastructure plus lourde

### CharacterPrepass avec 0 personnages

- test_image_gen.py:line~416 : `test_character_prepass_handles_adapter_failure_gracefully` teste le cas adapter échoue mais **avec** des personnages
- ⚠️ Cas `_unique_characters()` → `[]` (output sans personnages) : `character_prepass.py` lignes 72-74 non couvertes. Le test manque pour `AIPRODOutput` où toutes les scènes ont `characters=[]`

---

## BLOC 4 — Cas limites manquants

### Pipeline IR (test_pipeline.py)

| Cas limite | État | Priorité |
|---|---|---|
| `segment("")` → ValueError "PASS 1" | ✅ `TestEmptyInput::test_pass1_empty_string` | — |
| `segment("   \n ")` → ValueError | ✅ `TestEmptyInput::test_pass1_whitespace_only` | — |
| `simplify_shots([])` → ValueError | ✅ `TestEmptyInput::test_pass3_empty_list` | — |
| `compile_episode([], shots, "T")` → ValueError | ✅ `TestEmptyInput::test_pass4_empty_scenes` | — |
| `compile_episode(scenes, [], "T")` → ValueError | ✅ `TestEmptyInput::test_pass4_empty_shots` | — |
| `compile_episode(scenes, shots, "")` → ValueError | ✅ `TestEmptyInput::test_pass4_empty_title` | — |
| Scène avec `visual_actions=[]` → `simplify_shots()` | ❌ MANQUANT | 🟡 |
| Titre avec uniquement des espaces `"   "` → ValueError | ❌ MANQUANT | 🟡 |
| Scène avec `None` dans `characters` list | ❌ MANQUANT | 🟡 |
| Texte avec guillemets/apostrophes → no crash | ❌ MANQUANT | 🟡 |
| `segment` sur texte à 1 paragraphe (0 scène) → ValueError "PASS 1: segmentation" | À VÉRIFIER (comportement ligne 236 pass1) | 🟡 |

### Couche LLM (test_adaptation.py)

| Cas limite | État | Priorité |
|---|---|---|
| `extract_all` texte vide → `[]` | ✅ indirect via `split_into_chunks("")` → `[]` → `extract_all` retourne `[]` | — |
| `StoryValidator.validate_all()` → `[]` (toutes scènes filtrées) | ✅ `TestStoryValidator::test_validate_all_filters_below_threshold` | — |
| `LLMRouter` avec les deux adapters levant exception | ❌ MANQUANT | 🟡 |
| `ProductionBudget(max_scenes=0)` → comportement | ❌ MANQUANT — À VÉRIFIER (0 injecté dans le prompt LLM) | 🟡 |
| `run_pipeline` → StoryValidator retourne `[]` → ValueError levée | ❌ MANQUANT | 🟠 |

### Pipeline production (test_scheduling.py / test_image_gen.py)

| Cas limite | État | Priorité |
|---|---|---|
| `EpisodeScheduler.run()` avec output → 0 shots | ❌ MANQUANT | 🟡 |
| `CharacterPrepass.run()` avec output → 0 personnages | ❌ MANQUANT — lignes 72-74 non couvertes | 🟡 |
| `AudioSynchronizer.generate()` avec VideoOutput.clips=[] | ❌ MANQUANT | 🟡 |
| `CharacterPrepass` adapter échouant sur TOUS les shots (result.failed == total) | ⚠️ testé partiellement — `test_character_prepass_handles_adapter_failure_gracefully` teste 1 personnage avec échec | 🟡 |

### CLI (test_cli.py)

| Cas limite | État | Priorité |
|---|---|---|
| `cmd_pipeline` avec `--output-format csv` | ❌ MANQUANT | 🟡 |
| `cmd_pipeline` avec `--output-format json-flat` | ❌ MANQUANT | 🟡 |
| `cmd_schedule` avec dossier output inexistant → créé automatiquement | ⚠️ Couvert implicitement via `test_cli_schedule_saves_*` avec tempdir | — |
| `_load_image_adapter("flux")` → ImportError (module manquant) | ❌ MANQUANT | 🟡 |
| `cmd_pipeline` avec fichier input inexistant → FileNotFoundError propagée | ❌ MANQUANT | 🟡 |

### CostReport

| Cas limite | État | Priorité |
|---|---|---|
| `CostReport.to_summary_str()` format correct | ❌ MANQUANT — ligne 42 non couverte | 🟡 |
| `CostReport().merge(CostReport())` → élément neutre | ❌ MANQUANT | 🟡 |
| `metrics.cost` alimenté après `EpisodeScheduler.run()` | ✅ `TestCostReport::test_run_metrics_has_cost_field` | — |

---

## BLOC 5 — Déterminisme byte-level

### test_rule_pipeline_byte_identical — `test_pipeline.py:196`

```python
def test_rule_pipeline_byte_identical(self) -> None:
    import json
    out1 = run_pipeline(self._SAMPLE, "Test Title")
    out2 = run_pipeline(self._SAMPLE, "Test Title")
    assert json.dumps(out1.model_dump(), sort_keys=False) == \
           json.dumps(out2.model_dump(), sort_keys=False)
```

- ✅ **Existe et passe** dans la baseline 278 tests
- ✅ Vérifie l'**identité byte-for-byte** du JSON sérialisé (comparaison de chaînes)
- ✅ `sort_keys=False` garantit que l'ordre d'insertion Pydantic est testé (pas de tri artificiel)
- ✅ Deux appels indépendants sans état partagé
- ⚠️ **Périmètre limité au path rule-based** (`NullLLMAdapter` → fallback rules). Le commentaire dans le test l'explicite : "Le novel pipe LLM réel est non-déterministe par nature." — acceptable.
- ✅ Invariants vérifiés par grep (session précédente) : aucun `random`, `uuid`, `shuffle`, `datetime.now()` dans `core/`

### Conclusion BLOC 5

Le test de déterminisme est **correct et suffisant** pour le path déterministe (CI). La non-déterminisme du LLM réel est un non-problème architecturalement acceptable.

---

## Problèmes identifiés

| ID | Sévérité | Localisation | Description |
|---|---|---|---|
| TA01 | 🟠 | `cli.py` — 73% | `--output-format csv/json-flat` non testés ; `_load_image/video/audio_adapter(non-null)` non couverts |
| TA02 | 🟡 | `test_pipeline.py` — manquant | `simplify_shots()` avec scène `visual_actions=[]` → ValueError non testée directement |
| TA03 | 🟡 | `test_pipeline.py` — manquant | `compile_episode(scenes, shots, "   ")` (titre espaces) → ValueError non testée |
| TA04 | 🟡 | `test_adaptation.py` — manquant | `run_pipeline` où `StoryValidator` filtre toutes les scènes → ValueError "StoryValidator produced no filmable scenes" |
| TA05 | 🟡 | `test_scheduling.py` — manquant | `EpisodeScheduler.run()` avec `AIPRODOutput` à 0 shots (edge case) |
| TA06 | 🟡 | `test_image_gen.py` — manquant | `CharacterPrepass.run()` avec output sans personnages (`characters=[]` sur toutes scènes) |
| TA07 | 🟡 | `test_scheduling.py` — manquant | `CostReport.to_summary_str()` format non testé |
| TA08 | 🟡 | `test_post_prod.py` — manquant | `AudioSynchronizer.generate()` avec `VideoOutput.clips=[]` → comportement non testé |

---

## Tests manquants recommandés

```python
# TA01 — cli.py --output-format (test_cli.py)
def test_cli_pipeline_csv_output() -> None:
    # cmd_pipeline avec args.output_format = "csv"
    ...
def test_cli_pipeline_json_flat_output() -> None:
    # cmd_pipeline avec args.output_format = "json-flat"
    ...

# TA02 — simplify_shots scène vide (test_pipeline.py)
def test_pass3_scene_with_empty_visual_actions_raises() -> None:
    scene = cast(VisualScene, {..., "visual_actions": []})
    with pytest.raises(ValueError, match="PASS 3"):
        simplify_shots([scene])

# TA03 — titre espaces (test_pipeline.py)
def test_pass4_whitespace_only_title_raises() -> None:
    with pytest.raises(ValueError, match="PASS 4"):
        compile_episode([_BASE_SCENE], [_shot], "   ")

# TA04 — StoryValidator → liste vide → ValueError engine (test_adaptation.py)
def test_engine_story_validator_filters_all_scenes_raises() -> None:
    # Texte générant des scènes toutes invalides (score < 0.5)
    ...

# TA05 — EpisodeScheduler edge case (test_scheduling.py)
# N/A — AIPRODOutput sans shots ne peut pas être construit valide par Pydantic

# TA06 — CharacterPrepass sans personnages (test_image_gen.py)
def test_character_prepass_handles_output_with_no_characters() -> None:
    # AIPRODOutput avec characters=[] sur toutes scènes
    result = CharacterPrepass(NullImageAdapter(), base_seed=0).run(output_no_chars)
    assert result.generated == 0
    assert result.failed == 0

# TA07 — CostReport.to_summary_str() (test_scheduling.py)
def test_cost_report_to_summary_str_format() -> None:
    c = CostReport(image_api_calls=3, video_api_calls=2, audio_api_calls=5)
    s = c.to_summary_str()
    assert "Image: 3 calls" in s
    assert "Video: 2 calls" in s
    assert "Total: $0.0000" in s

# TA08 — AudioSynchronizer avec clips vides (test_post_prod.py)
def test_audio_synchronizer_with_empty_video_output() -> None:
    from aiprod_adaptation.video_gen.video_request import VideoOutput
    empty_video = VideoOutput(title="T", clips=[], total=0, generated=0, failed=0)
    results, production = AudioSynchronizer(NullAudioAdapter()).generate(empty_video, _output())
    assert production.timeline == []
```
