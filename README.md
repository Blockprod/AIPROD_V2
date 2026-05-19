# AIPROD ADAPTATION ENGINE v2 — District Zero EP01

AIPROD Adaptation Engine v2 est un compilateur cinématographique complet écrit en Python qui transforme un texte brut (roman, script, synopsis) en une chaîne de production audiovisuelle bout-en-bout. Le système couvre l'intégralité du pipeline : compilation narrative déterministe en représentation intermédiaire structurée (IR), enrichissement LLM optionnel (Claude / Gemini / router adaptatif), cohérence globale de l'épisode, moteur de règles de tournage, calcul de faisabilité shot-level, contraintes de référence visuelle (VisualBible), suivi de saison multi-épisodes, génération d'images et de vidéos via adaptateurs externes (Runway, Flux, DALL·E, Kling, Seedance…), post-production NLE (manifest, EDL, cue-sheet audio), et métriques de qualité broadcast calibrées sur les cibles Netflix. Le noyau reste strictement déterministe — même entrée, même sortie au niveau byte — et ne dépend d'aucune API externe obligatoire. L'IR (`AIPRODOutput`, Pydantic v2) constitue le contrat central entre toutes les couches et peut être exporté dans cinq formats de livraison (EDL JSON, Resolve Timeline, audio cue-sheet, batch generation manifest, season report).

**Projet actif : District Zero EP01** — série dystopique 11 scènes, 35 shots, 3 480 frames @ 24 fps (2 min 25 s). 5 personnages lockés (Nara, Mira, Elian, Vale, Rook), 10 lieux DOP-grade générés (FLUX 1.1 Pro Ultra, seeds fixes, 3840×2160).

---

## Architecture

```
aiprod_adaptation/
├── core/
│   ├── pass1_segment.py         — PASS 1 : Segmentation (text → List[RawScene])
│   ├── pass2_visual.py          — PASS 2 : Visual transform (thoughts → physical actions)
│   ├── pass3_shots.py           — PASS 3 : Shot atomization (scenes → List[ShotDict])
│   ├── pass4_compile.py         — PASS 4 : Compile + validate (→ AIPRODOutput)
│   ├── engine.py                — run_pipeline() / process_narrative_with_reference()
│   ├── io.py                    — load_output() / save_output()
│   ├── visual_bible.py          — VisualBible: per-character/location anchor store
│   ├── quality_gate.py          — broadcast quality gate helper
│   ├── run_metrics.py           — lightweight CLI-side metrics helper
│   ├── comparison.py            — rules vs LLM diff utilities
│   ├── cost_report.py           — token & API cost estimation
│   ├── production_budget.py     — shot-level budget model
│   │
│   ├── rules/                   — deterministic rule tables
│   │   ├── segmentation_rules.py
│   │   ├── segmentation_rules_v3.py
│   │   ├── emotion_rules.py
│   │   ├── duration_rules.py
│   │   ├── cinematography_rules.py
│   │   ├── cinematography_rules_v3.py
│   │   ├── visual_transformation_rules_v3.py
│   │   ├── body_language_rules.py
│   │   ├── dop_style_rules.py
│   │   ├── pass4_coherence_rules.py
│   │   └── verb_categories.py
│   │
│   ├── global_coherence/        — PASS 4 enrichment layer
│   │   ├── consistency_checker.py   — R01 shot-type vs feasibility correction
│   │   ├── pacing_analyzer.py       — PacingProfile computation
│   │   ├── prompt_finalizer.py      — R05–R09 prompt enrichment
│   │   │                              (R07/R08 VisualBible; R09 Kontext preservation clause)
│   │   └── __init__.py
│   │
│   ├── rule_engine/             — cinematic rule enforcement
│   │   ├── models.py                — CinematicRule, RuleViolation, RuleEngineReport
│   │   ├── builtin_rules.py         — CHR-01…CHR-N built-in rules
│   │   ├── evaluator.py             — RuleEvaluator
│   │   ├── conflict_resolver.py     — hard/soft conflict resolution
│   │   └── __init__.py
│   │
│   ├── feasibility/             — shot feasibility scoring
│   │   ├── engine.py                — FeasibilityEngine (0–100 score per shot)
│   │   └── __init__.py
│   │
│   ├── reference_constraints/   — VisualBible invariant extraction
│   │   ├── models.py                — ReferenceInvariants, ColorSwatch
│   │   ├── extractor.py             — ReferenceConstraintsExtractor
│   │   └── __init__.py
│   │
│   ├── reference_image/         — reference image quality analysis
│   │   ├── models.py
│   │   ├── extractor.py
│   │   ├── quality_gate.py
│   │   └── __init__.py
│   │
│   ├── continuity/              — cross-shot continuity tracking
│   │   ├── character_registry.py
│   │   ├── location_registry.py
│   │   ├── prop_registry.py
│   │   ├── emotion_arc.py
│   │   ├── prompt_enricher.py
│   │   └── __init__.py
│   │
│   ├── season/                  — multi-episode season tracking
│   │   ├── models.py                — AIPRODSeason, SeasonCoherenceMetrics
│   │   ├── tracker.py               — SeasonTracker
│   │   └── __init__.py
│   │
│   ├── metrics/                 — broadcast quality KPIs (Sprint 9)
│   │   ├── models.py                — ShotMetrics, EpisodeMetrics, SeasonMetrics
│   │   │                              + 7 NETFLIX_TARGET_* constants
│   │   ├── engine.py                — MetricsEngine (6 KPIs + OSCS)
│   │   └── __init__.py
│   │
│   ├── postproduction/          — NLE manifest generation (Sprint 9)
│   │   ├── _timecode.py             — frames_to_timecode / timecode_to_frames (SMPTE)
│   │   ├── models.py                — AudioCue, ContinuityNote, TimelineClip,
│   │   │                              PostProductionManifest
│   │   ├── audio_directives.py      — AudioDirectivesBuilder (tone → cue_type + mood)
│   │   ├── continuity.py            — ContinuityBuilder (establishing/lighting/color)
│   │   ├── timeline.py              — TimelineBuilder (transitions + SMPTE timecodes)
│   │   └── __init__.py              — build_manifest_for_episode(clock=…) (clock injectable for deterministic testing)
│   │
│   ├── exports/                 — delivery format serializers (Sprint 9)
│   │   ├── edl_json.py              — export_edl_json()
│   │   ├── resolve_timeline.py      — export_resolve_timeline() (OTIO-inspired)
│   │   ├── audio_cue_sheet.py       — export_audio_cue_sheet()
│   │   ├── batch_generation.py      — export_batch_generation()
│   │   ├── season_report.py         — export_season_report()
│   │   └── __init__.py
│   │
│   ├── adaptation/              — LLM adapters & story extraction
│   │   ├── llm_adapter.py           — LLMAdapter base interface
│   │   ├── claude_adapter.py        — Anthropic Claude adapter
│   │   ├── gemini_adapter.py        — Google Gemini adapter
│   │   ├── llm_router.py            — adaptive provider router
│   │   ├── story_extractor.py       — chunked narrative → IR via LLM
│   │   ├── story_validator.py       — schema validation of LLM output
│   │   ├── script_parser.py         — screenplay format parser
│   │   ├── normalizer.py            — output normalizer
│   │   └── classifier.py            — scene/shot classifier
│   │
│   └── scheduling/              — generation run scheduling
│       ├── episode_scheduler.py     — EpisodeScheduler (image + video + audio)
│       └── __init__.py
│
├── models/
│   ├── schema.py                — Scene / Shot / Episode / AIPRODOutput /
│   │                              RuleEngineReport / AIPRODSeason (Pydantic v2)
│   └── intermediate.py          — RawScene / VisualScene / ShotDict (TypedDict)
│
├── backends/
│   ├── base.py                  — BackendBase (abstract export interface)
│   ├── csv_export.py            — CsvExport (one row per shot)
│   └── json_flat_export.py      — JsonFlatExport (flat array)
│
├── image_gen/                   — image generation adapters
│   ├── image_adapter.py         — ImageAdapter base
│   ├── openai_image_adapter.py  — DALL·E / GPT Image 2 adapter
│   ├── flux_adapter.py          — Flux adapter (A1111 + IP-Adapter)
│   ├── comfyui_adapter.py       — ComfyUIAdapter base (workflow JSON + polling)
│   │                              + make_xlabs_ipadapter_adapter() factory
│   ├── flux_kontext_adapter.py  — FluxKontextAdapter (Kontext Dev, background-swap)
│   ├── runway_image_adapter.py  — Runway image adapter
│   ├── replicate_adapter.py     — generic Replicate adapter (FLUX Ultra, ESRGAN upscale)
│   ├── huggingface_image_adapter.py — HuggingFace Inference API (FLUX.1-schnell, free tier)
│   ├── ideogram_image_adapter.py — Ideogram v3 adapter
│   ├── seedream_adapter.py      — Seedream 4.5 adapter (Replicate, $0.04/image)
│   ├── meshy_adapter.py         — Meshy 3D asset generation adapter
│   ├── tripo3d_adapter.py       — Tripo3D API adapter (mesh from image)
│   ├── triposg_adapter.py       — TripoSG local adapter (triposg/ third_party)
│   ├── character_sheet.py       — character reference sheet builder
│   ├── character_prepass.py     — pre-pass character image generation
│   ├── character_image_registry.py
│   ├── character_mask.py        — background removal + edit mask (remove_background, build_edit_mask)
│   ├── reference_pack.py        — reference image packing
│   ├── storyboard.py            — storyboard assembly (+ kontext_adapter param)
│   ├── image_request.py
│   ├── checkpoint.py
│   └── __init__.py
│
├── video_gen/                   — video generation adapters
│   ├── video_adapter.py         — VideoAdapter base
│   ├── runway_adapter.py        — Runway Gen-3/4/Aleph adapter
│   │                              (i2v: gen4_turbo/gen4.5/gen3a_turbo;
│   │                               v2v: gen4_aleph with character references;
│   │                               Gen3aTurbo: last_frame continuity via prompt_image list)
│   ├── runway_prompt_formatter.py — format_runway_prompt() motion prompt builder
│   │                              (14 camera movements → Runway i2v instructions,
│   │                               anti-cut clause, sequential timestamps)
│   ├── kling_adapter.py         — Kling adapter (kling-v3, camera_type: professional)
│   ├── seedance_adapter.py      — Seedance 2.0 adapter (bytedance/seedance-2.0 via Replicate)
│   │                              character_reference_urls → reference_images (jusqu'à 9 refs)
│   │                              generate_audio=False, 720p, $0.18/sec
│   ├── smart_video_router.py    — SmartVideoRouter 3 branches :
│   │                              character_reference_urls → Seedance 2.0
│   │                              ≤5s sans perso → Runway
│   │                              >5s sans perso → Kling 3.0
│   ├── video_sequencer.py       — clip stitching sequencer
│   │                              (propagates character_reference_urls from storyboard)
│   ├── video_request.py         — VideoRequest + character_reference_urls field
│   └── __init__.py
│
├── post_prod/                   — audio & video post adapters
│   ├── audio_adapter.py         — AudioAdapter abstract interface + NullAudioAdapter
│   ├── elevenlabs_adapter.py    — ElevenLabs TTS (cloud)
│   ├── openai_tts_adapter.py    — OpenAI TTS (cloud)
│   ├── runway_tts_adapter.py    — Runway audio (cloud)
│   ├── f5tts_adapter.py         — F5-TTS local (flow-matching, clonage vocal, $0.00)
│   │                              F5TTSAdapter + generate_to_file() ; auto-detect CUDA
│   ├── audiocraft_adapter.py    — Meta AudioCraft local ($0.00)
│   │                              MusicGenAdapter (musicgen-stereo-large)
│   │                              AudioGenAdapter (audiogen-medium, SFX)
│   │                              make_local_audio_adapter("musicgen"|"audiogen")
│   ├── audio_synchronizer.py
│   ├── ssml_builder.py
│   ├── audio_utils.py
│   ├── audio_request.py
│   ├── ffmpeg_exporter.py       — FFmpeg timeline export
│   └── __init__.py
│
├── tests/                       — 998 tests, 0 failures
│   ├── test_pipeline.py
│   ├── test_backends.py
│   ├── test_cli.py
│   ├── test_comparison.py
│   ├── test_io.py
│   ├── test_adaptation.py
│   ├── test_continuity.py
│   ├── test_scheduling.py
│   ├── test_image_gen.py
│   ├── test_video_gen.py
│   ├── test_post_prod.py
│   ├── test_rule_engine.py
│   ├── test_reference_image.py
│   ├── test_pass1_cinematic.py
│   ├── test_pass2_cinematic.py
│   ├── test_pass3_cinematic.py
│   ├── test_pass4_cinematic.py
│   ├── test_cinematic_integration.py
│   ├── test_sprint9.py          — metrics + postprod + exports (68 tests)│   ├── test_consistency.py      — AssetRegistry, ColorManager, ContinuityChecker, AudioNormalizer│   ├── test_video_sequencer.py  — VideoSequencer propagation + Aleph routing (3 tests)
│   ├── test_runway_prompt_formatter.py — motion prompt + anti-cut + R09 (9 tests)
│   └── test_comfyui_adapter.py  — ComfyUIAdapter + FluxKontext (4 tests)
│
└── examples/
    ├── sample.txt               — minimal narrative input (smoke test baseline)
    └── chapter1.txt             — rich input (4 characters, 3+ locations, dialogues)

production/
├── characters.json              — 5 personnages lockés (Nara, Mira, Elian, Vale, Rook)
│                                  canonical complet · portrait_brief DOP · seed fixe · validated_date
├── locations.json               — 10 lieux · seeds 11→121 · canonical · lighting_brief · dop_ref
│                                  colour (dominant/accent/blacks) · camera spec · ref_image path
├── storyboard.json              — 35 shots EP01 · axes 180° par scène · shot_type · camera_spec
│                                  composition · action_brief · lighting_context · emotion_intent
│                                  12 emotion_intent augmentés (B3) · primary_character DOP-grade (N1)
├── grade.json                   — look transversal épisode (palette Roger Deakins · interdits · DOP refs)
├── shot_animations.json         — config caméra + animations Blender par shot (fov_mm, clip_start…)
├── metrics_v4.jsonl             — log des métriques qualité par run (SSIM · ArcFace · luminance)
│
├── gen_location_refs.py         — Génère master plates lieux (FLUX 1.1 Pro Ultra, 3840×2160)
│                                  _MASTER_COMPOSITIONS : compositions dédiées text-to-image pur
│                                  _strip_black_bands() : suppression automatique letterbox
│                                  CLI : --loc · --ultra · --gpt2 · --local · --dry-run
│                                  --local : FLUX.1-schnell local via diffusers ($0.00, 4 steps)
├── gen_location_angles.py       — Génères wide/medium/detail par lieu via FLUX Ultra + Redux
│                                  _sanitize_canonical() : supprime toute présence humaine du prompt
│                                  _precision_master() : 7 paramètres photographiques (IRE/µm/Kelvin)
│                                  _creative_composition() : 30 compositions narratives (10 lieux × 3 angles)
├── gen_location_coverage.py     — Planches multi-angles coverage (wide/medium/detail, $0.20/lieu)
│
├── gen_character_refs.py        — Génère portraits de référence par personnage (Phase A)
├── gen_character_faces.py       — Corpus Phase B : 7 angles + 14 expressions par personnage
│                                  Modèle : Seedream 4.5 ($0.04/image) · 5 chars × 21 = 105 fichiers
│                                  Nomenclature : angle_NN_*.png / expr_NN_*.png
├── gen_character_bodies.py      — Corpus Phase B : 8 turnarounds + 7 poses par personnage
│                                  Modèle : Seedream 4.5 ($0.04/image) · 5 chars × 15 = 75 fichiers
│                                  Nomenclature : turn_NN_*.png / pose_NN_*.png
├── gen_character_sheets.py      — Planches multi-angles V4 (character sheets, $1.60/char)
├── gen_character_meshes.py      — Meshes 3D TripoSG V4 depuis character sheets
├── gen_metahuman_rigs.py        — Import FBX MetaHuman UE5 → Blender (nettoyage rig + export .blend)
│
├── gen_shots.py                 — Orchestrateur Phase A (Replicate FLUX/Seedream)
├── gen_shots_v4.py              — Orchestrateur Phase C · 35 shots · --backend replicate|comfyui|null
│                                  Budget alert $250 · dry-run obligatoire · coût Replicate $139.20
├── gen_assembly.py              — Assembly rough cut
├── gen_3d_assets.py             — Génère assets 3D lieux via Meshy (depuis location_sheets/)
│
├── quality_gate_v4.py           — Quality gate shot-level broadcast
│                                  SSIM inter-frames ≥ 0.85 · ArcFace identité ≥ 0.85
│                                  Luminance std ≤ 15.0 · log → metrics_v4.jsonl
├── benchmark_characters.py      — Validation ArcFace des références personnages
├── dashboard.py / dashboard.json
├── run.py                       — CLI unifié production
│
├── character_faces/             — Corpus Phase B visages (5 slugs × 21 = 105 PNG)
│   └── {slug}/                    nara/ mira/ elian/ vale/ rook/
├── character_bodies/            — Corpus Phase B corps (5 slugs × 15 = 75 PNG)
│   └── {slug}/                    nara/ mira/ elian/ vale/ rook/
├── character_refs/              — Phase A portraits lockés par personnage
├── location_refs/               — 10 master plates (10 PNG 3840×2160, seeds déterministes)
├── assets_3d/                   — Assets 3D générés (Meshy / TripoSG)
├── metahumans/                  — FBX MetaHuman UE5 + statuts JSON
└── shots/                       — Shots générés Phase A
```

`stories/district_zero_ep01.fountain` — script source EP01  
`tasks/` — METHODE_PRODUCTION_IA_2026.md · PRODUCTION_RULES.md · WORKFLOW.md  

```
pipeline/
├── shot_pipeline.py     — VERROUILLÉ v2 (2026-04-30) · LOCKED_MODEL flux-2-pro · LOCKED_COST $0.03+$0.05
│                          SceneP1Params · build_p1_prompt() · build_p2_prompt() · _download() · ArcFace
├── shot_pipeline_v4.py  — Pipeline Phase C production · StylizationBackend ABC
│                          ReplicateBackend   : jagilley/controlnet-normal ($0.04/frame)
│                          ComfyUIBackend     : SD1.5 + ControlNet Normal + IP-Adapter (local, $0.00)
│                            upload /image · normals EXR (→ normalbae) · polling /history
│                            Modèles : v1-5-pruned-emaonly · control_v11p_sd15_normalbae
│                                      ip-adapter-plus_sd15 · CLIP-ViT-H-14
│                          NullStylizationBackend : CI stub
│                          _build_stylization_prompt() : 12 tokens ordonnés (DOP → émotion)
│                          _resolve_char_ref() : 3 niveaux (corps/expressions/angle)
│                          _emotion_matches() : word-boundary + négation
├── blender_render.py    — Rendu Blender Cycles headless
│                          Outputs : frames/frame_{N:04d}.png · depth/depth_{N:04d}.exr
│                                    normals/normals_{N:04d}.exr
│                          Entrée  : shot_animations.json (fov_mm, clip_start…)
├── video_pipeline.py    — frames PNG → clips MP4/MOV via FFmpeg
│                          frames_to_clip()       : H.264 CRF18 yuv420p (1080p)
│                          frames_to_clip_hevc()  : HEVC 4K HDR10 10-bit · BT.2020 · SMPTE ST 2084
│                                                   Lanczos4 1920→3840 · x265 HDR10 master display
│                          frames_to_prores()     : ProRes 422 HQ (~220 Mbps) mezzanine broadcast
│                          add_audio() · concat_clips() · process_shot()
└── assembly.py          — assemble_episode() : clips → master MP4 via FFmpeg concat
```

---

## District Zero EP01 — État de production

### Personnages lockés

| Personnage | Slug | Rôle | Validé |
|---|---|---|---|
| Nara Voss | `nara` | Protagoniste | 2026-05-01 |
| Mira Sol | `mira` | Deuteragoniste | 2026-05-01 |
| Elian Voss | `elian` | Supporting | 2026-05-01 |
| Commander Sarin Vale | `vale` | Antagoniste secondaire | 2026-05-01 |
| Director Halden Rook | `rook` | Antagoniste principal | 2026-05-01 |

**Corpus Phase B** (génération Seedream 4.5 · $0.04/image) :
- `character_faces/{slug}/` — 7 angles + 14 expressions = **21 PNG × 5 = 105 fichiers**
- `character_bodies/{slug}/` — 8 turnarounds + 7 poses = **15 PNG × 5 = 75 fichiers**

### Master plates lieux (FLUX 1.1 Pro Ultra · raw=True · 16:9 · 3840×2160 · 10/10 générés)

| Lieu | Seed | Scènes | DOP référence |
|---|---|---|---|
| `ext_outer_wall_night` | 11 | SCN_001 | Roger Deakins / Blade Runner 2049 (2017) |
| `int_transit_corridor_night` | 22 | SCN_002 | Roger Deakins / Sicario (2015) |
| `int_pressure_valve_chamber_night` | 33 | SCN_003 | Denis Villeneuve / Arrival (2016) |
| `int_voss_apartment_night` | 44 | SCN_004 | Denis Villeneuve / Prisoners (2013) |
| `int_civic_atrium_morning` | 55 | SCN_005 | Roger Deakins / Skyfall (2012) |
| `int_black_market_sublevel_day` | 66 | SCN_006 | Denis Villeneuve / Blade Runner 2049 (2017) |
| `int_security_ops_center_day` | 77 | SCN_007 | David Fincher / The Social Network (2010) |
| `int_service_spine_night` | 88 | SCN_008/010 | Roger Deakins / Sicario (2015) |
| `int_observation_chamber` | 99 | SCN_009 | Alfonso Cuarón / Children of Men (2006) |
| `int_voss_apartment_predawn` | 121 | SCN_011 | Roger Deakins / No Country for Old Men (2007) |

### Pipeline vidéo (SmartVideoRouter)

```
character_reference_urls présents  →  Seedance 2.0  ($0.18/sec, 720p, cohérence personnage)
≤ 5s sans personnage               →  Runway Gen-4  (i2v qualité)
> 5s sans personnage               →  Kling 3.0     (kling-v3, camera_type: professional)
```

### Phase C — Stylisation frame-par-frame (en attente GO)

| | Cloud (Replicate) | Local (ComfyUI) |
|---|---|---|
| Modèle | `jagilley/controlnet-normal` (SD1.5) | SD1.5 + ControlNet Normal + IP-Adapter |
| Coût | **$139.20** (3 480 frames × $0.04) | **$0.00** |
| Pré-requis | `REPLICATE_API_TOKEN` | ComfyUI sur localhost:8188 · RTX ≥ 12 GB VRAM |

```powershell
# Dry-run (aucun appel API)
python production/gen_shots_v4.py --all --backend replicate --dry-run

# Phase C — cloud (GO DA requis)
python production/gen_shots_v4.py --all --backend replicate --execute

# Phase C — local ComfyUI (gratuit)
python production/gen_shots_v4.py --all --backend comfyui --execute
```

**ComfyUI — modèles requis** (`ComfyUI/models/`) :
- `checkpoints/v1-5-pruned-emaonly.safetensors`
- `controlnet/control_v11p_sd15_normalbae.safetensors`
- `ipadapter/ip-adapter-plus_sd15.safetensors`
- `clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors`
- Extension : [ComfyUI-IPAdapter-plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus)

### Phase C — Audio local (F5-TTS + AudioCraft)

```python
from aiprod_adaptation.post_prod.f5tts_adapter import F5TTSAdapter
from aiprod_adaptation.post_prod.audiocraft_adapter import make_local_audio_adapter

# TTS vocal (clonage voix)
tts = F5TTSAdapter(ref_audio="production/audio/voice_refs/nara_ref.wav")
result = tts.generate(AudioRequest(shot_id="SCN_001_SHOT_001", text="..."))

# Score cinématique (MusicGen stereo large)
music = make_local_audio_adapter("musicgen", duration=10.0)

# SFX (AudioGen medium)
sfx = make_local_audio_adapter("audiogen", duration=5.0)
```

### Phase 3 — Vidéo broadcast 4K HDR10 (post-MSI Vector 17)

```python
from pipeline.video_pipeline import frames_to_clip_hevc, frames_to_prores

# HEVC 4K HDR10 10-bit (BT.2020 · SMPTE ST 2084 · 1000 nits)
frames_to_clip_hevc(frames_dir, upscale_4k=True, crf=18)

# ProRes 422 HQ mezzanine (~220 Mbps) pour grade DaVinci Resolve
frames_to_prores(frames_dir, profile=3)
```

### Règles de production absolues

- **Jamais de régénération sans GO explicite** — dry-run obligatoire avant tout run payant
- **Empty location rule** — aucun personnage dans les masters lieux
- **No text/signage** — aucun texte lisible sur aucune surface. Ne pas mentionner un concept interdit, même en négatif (T5-XXL l'active quand même) — reformuler sans évoquer le concept.
- **Shot validé = définitif** — jamais régénéré sans décision DA explicite
- **No `# type: ignore`** — toutes les erreurs de type résolues explicitement

---

- Python 3.11+
- pydantic >= 2.0
- structlog >= 21.0
- anthropic, google-generativeai *(optionnel — requis pour les adaptateurs LLM)*
- ffmpeg *(requis pour `video_pipeline`, `ffmpeg_exporter`, `assembly`)*

**Pipeline local (optionnel — Phase C/2/3) :**
- `torch` + `diffusers` + `transformers` + `accelerate` — FLUX.1-schnell local (`gen_location_refs.py --local`)
- `f5-tts` + `soundfile` — TTS vocal local (`f5tts_adapter.py`)
- `audiocraft` + `torchaudio` — score + SFX local (`audiocraft_adapter.py`)
- `opencv-python` (`cv2`) — conversion EXR depth/normals → PNG pour ComfyUI
- ComfyUI + RTX ≥ 12 GB VRAM — backend stylisation local

---

## Installation

```bash
# Create and activate the virtual environment
py -3.11 -m venv venv
venv\Scripts\activate      # Windows PowerShell

# Install dependencies (with dev extras)
pip install -e ".[dev]"
```

---

## Usage

```bash
# ── Core pipeline ──────────────────────────────────────────────────────────

# Run the deterministic pipeline on a narrative text file
python main.py --input aiprod_adaptation/examples/sample.txt

# With a custom title and episode ID
python main.py --input chapter.txt --title "Episode 1" --episode-id EP01

# Write output to a file instead of stdout
python main.py --input chapter.txt --output output.json

# Export as CSV or flat JSON
python main.py --input chapter.txt --output output.csv --format csv
python main.py --input chapter.txt --output output.json --format json-flat

# Full help
python main.py --help

# ── LLM-enhanced pipeline ──────────────────────────────────────────────────

# Compare rules vs LLM on the same input via the packaged CLI
aiprod compare --input aiprod_adaptation/examples/chapter1.txt --title "Chapter 1"

# Also persist the rules and LLM JSON outputs used by the comparison
aiprod compare --input aiprod_adaptation/examples/chapter1.txt --title "Chapter 1" \
  --output compare.txt --rules-output rules.json --llm-output llm.json

# Emit the comparison summary itself as structured JSON
aiprod compare --input aiprod_adaptation/examples/chapter1.txt --title "Chapter 1" \
  --output compare.json --output-format json

# Force router to prefer Gemini on short prompts for one invocation
aiprod pipeline --input aiprod_adaptation/examples/chapter1.txt --title "Chapter 1" \
  --output output.json --llm-adapter router --router-short-provider gemini --require-llm

# Persist the router decision trace alongside the pipeline output
aiprod pipeline --input aiprod_adaptation/examples/chapter1.txt --title "Chapter 1" \
  --output output.json --llm-adapter router --router-trace-output router-trace.json --require-llm

# Force a real multi-chunk router run on chapter1 and persist the full trace history
aiprod compare --input aiprod_adaptation/examples/chapter1.txt --title "Chapter 1" \
  --llm-adapter router --output compare.json --output-format json \
  --rules-output rules.json --llm-output llm.json \
  --router-trace-output router-trace.json --max-chars-per-chunk 500

# ── Quality metrics (Sprint 9) ─────────────────────────────────────────────

# Compute broadcast quality KPIs from a compiled IR and write to JSON
aiprod metrics --input output.json --output metrics.json

# Print metrics to stdout (omit --output)
aiprod metrics --input output.json

# ── Delivery exports (Sprint 9) ────────────────────────────────────────────

# Export as EDL JSON (broadcast record timecodes, SMPTE HH:MM:SS:FF)
aiprod export --input output.json --format edl --output delivery/cut.edl.json

# Export as DaVinci Resolve timeline (OTIO-inspired, V1 + A1 tracks)
aiprod export --input output.json --format resolve --output delivery/timeline.json

# Export audio cue sheet (Q001…QN, mood, BPM, SFX descriptors)
aiprod export --input output.json --format audio-cue --output delivery/cues.json

# Export AI generation batch manifest (Runway / Flux / Kling)
aiprod export --input output.json --format batch --output delivery/batch.json \
  --adapter-target runway

# Export season coherence report (multi-episode, Netflix KPIs)
aiprod export --input ep01.json --format season-report --output season_report.json \
  --season-id S01 --series-title "District Zero"

# ── Media generation & scheduling ─────────────────────────────────────────

aiprod schedule --input output.json --output out/run \
  --image-adapter runway --video-adapter runway --audio-adapter elevenlabs
```

## Story Workflow

Recommended end-to-end production workflow:

```bash
# 1. Start from the reusable template
copy stories/story_template.txt stories/my_new_story.txt

# 2. Edit stories/my_new_story.txt with your own synopsis, script, or chapter

# 3. Compile the story into AIPROD IR
aiprod pipeline --input stories/my_new_story.txt --title "My New Story" \
  --output out/my_new_story_ir.json \
  --llm-adapter router --pipeline-mode generative --require-llm

# 4. Compute quality metrics and verify broadcast gate
aiprod metrics --input out/my_new_story_ir.json --output out/my_new_story_metrics.json

# 5. Export delivery manifests
aiprod export --input out/my_new_story_ir.json --format resolve \
  --output out/my_new_story_timeline.json
aiprod export --input out/my_new_story_ir.json --format batch \
  --output out/my_new_story_batch.json --adapter-target runway

# 6. Generate media from that compiled story
aiprod schedule --input out/my_new_story_ir.json --output out/my_new_story_run \
  --image-adapter runway --video-adapter runway --audio-adapter elevenlabs
```

Practical rule:
- one file per story; change `--input`, `--title`, and `--output` for each new video project

Optional LLM environment knobs:
- `GEMINI_MODEL` — overrides the primary Gemini model (default `gemini-2.5-flash`)
- `GEMINI_FALLBACK_MODELS` — comma-separated Gemini fallback models tried on transient failures
- `LLM_ROUTER_SHORT_PROVIDER` — preferred short-text provider for `router` (`claude` by default, `gemini` also supported)
- `LLM_ROUTER_PROVIDER_COOLDOWN_SEC` — how long the router avoids retrying a failed provider (default `300`)
- `LLM_ROUTER_PROVIDER_MAX_COOLDOWN_SEC` — caps adaptive backoff after repeated failures (default `2400`)
- `LLM_ROUTER_AUTH_QUARANTINE_SEC` — quarantine duration for authentication failures
- `LLM_ROUTER_QUOTA_QUARANTINE_SEC` — quarantine duration for quota and billing failures

Optional router CLI knobs:
- `--router-short-provider claude|gemini` — overrides the short-text router preference for the current invocation
- `--router-trace-output PATH` — writes the router decision trace JSON for `pipeline`, `compare`, or `main.py`
- `--max-chars-per-chunk N` — overrides the StoryExtractor chunk size (useful to force multi-chunk validation on short inputs)
- `--output-format json` *(compare only)* — writes comparison summary as structured JSON instead of plain text

Router behaviour notes:
- prompts containing `CONTEXT FROM PREVIOUS SCENES:` are treated as continuity-heavy and are routed to Gemini first, even when short
- router failures are classified (`transient`, `rate_limit`, `auth`, `quota`, `schema`, `unknown`) so cooldown and quarantine differ by failure type
- when router trace export is enabled, the JSON contains `trace_history` for the run and `last_trace` for quick inspection

Output format:
- `json` (default) — pretty-printed `AIPRODOutput` with nested episodes/scenes/shots
- `csv` — one row per shot: `episode_id, scene_id, shot_id, shot_type, camera_movement, prompt, duration_sec, emotion`
- `json-flat` — flat JSON array, one object per shot

---

## Running Tests

```bash
pytest aiprod_adaptation/tests/ -q
```

**1072 passed, 4 deselected** across 23 test modules:

| Module | Tests | Coverage |
|---|---|---|
| `test_pipeline.py` | 39 | 4 passes, determinism, smoke |
| `test_backends.py` | 6 | CSV + JSON flat export |
| `test_cli.py` | ~30 | all CLI subcommands |
| `test_comparison.py` | ~20 | rules vs LLM diff |
| `test_io.py` | ~12 | load/save round-trip |
| `test_adaptation.py` | ~30 | LLM adapters + router |
| `test_continuity.py` | ~30 | character/location/prop registries |
| `test_scheduling.py` | ~20 | EpisodeScheduler |
| `test_consistency.py` | ~30 | AssetRegistry, ColorManager, ContinuityChecker, AudioNormalizer |
| `test_image_gen.py` | ~45 | image adapters + storyboard + HuggingFace |
| `test_video_gen.py` | ~30 | video adapters + sequencer |
| `test_post_prod.py` | ~30 | TTS + FFmpeg exporter |
| `test_rule_engine.py` | ~40 | built-in rules + conflict resolver |
| `test_reference_image.py` | ~20 | reference quality gate |
| `test_pass1/2/3/4_cinematic.py` | ~160 | per-pass cinematic rules |
| `test_cinematic_integration.py` | ~400 | end-to-end integration |
| `test_sprint9.py` | 68 | metrics + postprod NLE + exports |
| `test_video_sequencer.py` | 3 | ref propagation + Aleph routing |
| `test_runway_prompt_formatter.py` | 9 | motion prompts + anti-cut + R09 |
| `test_comfyui_adapter.py` | 4 | ComfyUIAdapter + FluxKontextAdapter |

---

## Development — Lint Sequence

```bash
# 1. Style and imports
ruff check aiprod_adaptation/

# 2. Static type checking — core / models / backends / CLI (strict)
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ \
     aiprod_adaptation/cli.py main.py --strict

# 2b. Static type checking — adapters (ignore missing stubs)
mypy aiprod_adaptation/image_gen/ aiprod_adaptation/post_prod/ aiprod_adaptation/video_gen/ \
     --ignore-missing-imports

# 3. Tests
pytest aiprod_adaptation/tests/ -q
```

All four commands must pass before any commit.

---

## Pipeline Passes

| Pass | File | Input | Output |
|------|------|-------|--------|
| 1 | `pass1_segment.py` | `str` raw text | `List[RawScene]` |
| 2 | `pass2_visual.py` | `List[RawScene]` | `List[VisualScene]` |
| 3 | `pass3_shots.py` | `List[VisualScene]` | `List[ShotDict]` |
| 4 | `pass4_compile.py` | title + scenes + shots | `AIPRODOutput` (Pydantic v2) |

Pass 4 also runs the following enrichment sub-passes in order:

1. **ConsistencyChecker** (R01) — downgrades non-static camera to `static` when feasibility < 40
2. **RuleEvaluator** (CHR-N rules) — evaluates all cinematic rules and produces `RuleEngineReport`
3. **ConflictResolver** — resolves hard/soft rule conflicts
4. **PacingAnalyzer** — builds `PacingProfile` (total duration, mean shot duration, pacing label)
5. **PromptFinalizer** (R07/R08) — enriches prompts with character and location fragments from `VisualBible`

---

## Broadcast Quality Metrics

`aiprod metrics` computes 6 KPIs per episode and aggregates them into an `overall_episode_quality` (OEQ). All KPIs are in [0, 1].

| KPI | Formula | Netflix target |
|---|---|---|
| `reference_quality_score` (RQS) | $\sum_i(\text{anchor}_i \times \text{FS}_i/100 \times d_i) / \sum d_i$ | ≥ 0.75 |
| `visual_consistency_score` (VCS) | `ConsistencyReport.consistency_score` (Pass 4 output) | ≥ 0.85 |
| `feasibility_score` (FS) | $\overline{\text{feasibility\_score}}/100$ | ≥ 0.72 |
| `cinematic_richness_score` (CRS) | $0.40 \cdot \frac{\text{distinct\_types}}{11} + 0.30 \cdot \frac{\text{distinct\_movements}}{16} + 0.30 \cdot \Delta\text{beat}$ | ≥ 0.55 |
| `continuity_accuracy` (CA) | $1 - \frac{\text{establishing violations}}{\text{multi-shot scenes}}$ | ≥ 0.80 |
| `conflict_resolution_accuracy` (CRA) | $1 - \frac{\text{hard\_conflicts\_resolved}}{\text{rules\_evaluated}}$ | ≥ 0.92 |
| **OEQ** | $0.25\cdot\text{VCS} + 0.20\cdot\text{FS} + 0.20\cdot\text{CRS} + 0.15\cdot\text{CA} + 0.10\cdot\text{CRA} + 0.10\cdot\text{RQS}$ | **≥ 0.78** |

`passes_broadcast_gate()` returns `True` only when all 6 individual KPIs meet their respective targets.

Season-level OSCS (Overall Season Coherence Score) weights episodes by shot count for VCS and CA, and uses arithmetic means for the other four KPIs.

---

## Post-Production Exports

| Command | Format | Description |
|---|---|---|
| `--format edl` | EDL JSON | SMPTE record timecodes (01:00:00:00 start), transition tags |
| `--format resolve` | Resolve Timeline JSON | OTIO-inspired, V1 video track + A1 audio track |
| `--format audio-cue` | Audio Cue Sheet JSON | Q001…QN, cue_type, mood, BPM hint, SFX descriptor |
| `--format batch` | Batch Generation JSON | Per-shot generation params, motion intensity, reference anchors |
| `--format season-report` | Season Report JSON | Season KPIs, per-episode breakdown, broadcast gate, recommendations |

All timecodes follow SMPTE `HH:MM:SS:FF` format at the configured FPS (default 24.0).

---

## Shot IR Fields

Each `Shot` in the output carries structured cinematic fields:

| Field | Type | Values | Description |
|---|---|---|---|
| `shot_id` | `str` | `S001`… | Unique identifier |
| `scene_id` | `str` | `SC01`… | Parent scene identifier |
| `shot_type` | `str` | `wide` · `extreme_wide` · `medium` · `close_up` · `extreme_close_up` · `pov` · `two_shot` · `insert` · `cutaway` · `aerial` · `dutch_angle` | Framing type, derived from action verbs |
| `camera_movement` | `str` | `static` · `follow` · `pan` · `tilt` · `dolly_in` · `dolly_out` · `tracking` · `handheld` · `crane_up` · `crane_down` · `steadicam` · `whip_pan` · `rack_focus` · `zoom_in` · `zoom_out` · `aerial_descent` | Camera behaviour |
| `prompt` | `str` | free text | Visual description without any prefix |
| `duration_sec` | `int` | 3–8 | Duration clamped to [3, 8] |
| `emotion` | `str` | — | Dominant emotion of the parent scene |
| `feasibility_score` | `int` | 0–100 | Shot production feasibility (100 = fully achievable) |
| `reference_anchor_strength` | `float` | 0.0–1.0 | Adherence confidence to VisualBible reference |
| `lighting_directives` | `str \| None` | — | DOP lighting instructions |
| `composition_description` | `str \| None` | — | Framing and composition notes |
| `metadata` | `dict` | — | Extensible bag: `emotional_beat_index`, `color_grade_hint`, `dominant_sound`… |

---

## Cinematography Rules (deterministic)

**`shot_type` — first match wins (v3 rules, 11 types):**

| Rule | Trigger |
|---|---|
| `extreme_close_up` | extreme facial detail words |
| `close_up` | facial words: smile, frown, jaw, eyes, stare, glare… |
| `extreme_wide` | panoramic / establishing keywords |
| `wide` | motion words: walk, run, move, approach, rush… |
| `pov` | `pov`, `point of view` |
| `two_shot` | two characters facing / together |
| `insert` | object / detail insert words |
| `cutaway` | reaction / cutaway keywords |
| `aerial` | aerial / overhead keywords |
| `dutch_angle` | dutch / tilted angle keywords |
| `medium` | fallback (default) |

**`camera_movement` (16 values):**

| Value | Condition |
|---|---|
| `follow` | motion verb present |
| `pan` | interaction verb, no motion |
| `dolly_in` | approach + emphasis keywords |
| `tracking` | sustained parallel motion |
| `handheld` | unstable / tension keywords |
| `crane_up` / `crane_down` | vertical reveal / descend keywords |
| `whip_pan` | fast cut / transition keywords |
| `rack_focus` | focus shift keywords |
| `zoom_in` / `zoom_out` | explicit zoom keywords |
| `tilt` | vertical pan keywords |
| `steadicam` | smooth walk-and-talk keywords |
| `aerial_descent` | drone descent keywords |
| `static` | default |

---

## Absolute Invariants

- Fully deterministic core: same input → identical output (byte-level)
- No randomness, no LLMs, no external APIs, no datetime, no hashing for ordering in core passes
- Raises `ValueError` on any validation failure — never silently corrects or ignores
- All lists preserve strict input order
- No sets, no implicit sorting in core
- Core never imports from backends, image_gen, video_gen, or post_prod
- No `# type: ignore` anywhere in the codebase — all type errors are resolved explicitly
- Pydantic v2 throughout — mutations use `model_copy(update=...)`, never direct attribute assignment on validated models

---

## Emotion → Physical Action Mapping

| Emotion | Observable Action |
|---------|-------------------|
| angry | clenches fists, jaw tightens, steps forward aggressively |
| scared | trembles, takes backward steps, eyes widen |
| sad | lowers head, moves slowly, shoulders slumped |
| happy | smiles broadly, moves with energy, gestures openly |
| nervous | fidgets, paces, bites lip |

---

## Shot Duration Rules (deterministic)

- Base = 3 seconds
- +1 s if motion verb present
- +1 s if interaction verb present
- +1 s if perception verb present
- +1 s if action description > 10 words
- Clamped to [3, 8]
