---
title: Plan d'action — Production Completeness v1
source: bilan_conceptuel_2026-04-21_post_SO
creation: 2026-04-21 à 18:17
last_updated: 2026-04-21 à 18:17
status: active
phase: PC (Production Completeness — combler les lacunes des 5 axes à < 100%)
prerequis: scale_orchestration_v1_plan.md complété (2026-04-21) — 247/247 tests
tests_avant: 247
tests_apres_cible: 310+
---

# PLAN D'ACTION — PRODUCTION COMPLETENESS v1 — 2026-04-21

**Objectif** : porter tous les axes à 100% en comblant les 5 lacunes conceptuelles identifiées après la session Scale & Orchestration.

| Axe | Avant | Cible |
|---|---|---|
| CONTINUITÉ | 67% | 100% |
| IMAGE GEN | 90% | 100% |
| VIDEO GEN | 75% | 100% |
| AUDIO / POST-PROD | 67% | 100% |
| SCHEDULER / METRICS | 67% | 100% |
| ADAPTATION LLM | 90% | 100% |

---

## Table des étapes

| ID | Priorité | Action | Axe | Fichier(s) impactés |
|---|---|---|---|---|
| PC-01 | 🔴 Critique | FFmpeg muxing — `FfmpegExporter.export()` lit `ProductionOutput`, produit un fichier vidéo réel | AUDIO/POST | `post_prod/ffmpeg_exporter.py` |
| PC-02 | 🔴 Critique | Character prepass — pipeline `CharacterPrepass` : génère une image de référence par personnage avant la storyboard | IMAGE | `image_gen/character_prepass.py` (NEW), `image_gen/storyboard.py` |
| PC-03 | 🟠 Important | CLI adapters de prod — `--image-adapter`, `--video-adapter`, `--audio-adapter` dans `aiprod pipeline` et `aiprod storyboard` | VIDEO + CLI | `aiprod_adaptation/cli.py` |
| PC-04 | 🟠 Important | Continuité lieu/prop — `LocationRegistry` + `PropRegistry` pour tracker cohérence cross-shots | CONTINUITÉ | `core/continuity/location_registry.py` (NEW), `core/continuity/prop_registry.py` (NEW), `core/continuity/prompt_enricher.py` |
| PC-05 | 🟠 Important | SmartVideoRouter intégration CLI — brancher `smart_video_router.py` dans le CLI et dans `EpisodeScheduler` | VIDEO | `video_gen/smart_video_router.py`, `core/scheduling/episode_scheduler.py` |
| PC-06 | 🟡 Nice-to-have | Audio latency tracking — exposer `latency_ms` dans `TimelineClip`, le remonter dans `RunMetrics.audio_latency_ms` | SCHEDULER | `post_prod/audio_request.py`, `post_prod/audio_synchronizer.py`, `core/scheduling/episode_scheduler.py` |
| PC-07 | 🟡 Nice-to-have | Observabilité prod — `CostReport` par run : tokens LLM, appels API image/vidéo/audio, coût estimé | METRICS | `core/cost_report.py` (NEW), `core/run_metrics.py`, `core/scheduling/episode_scheduler.py` |
| PC-08 | 🟡 Nice-to-have | LLM adapter completeness — vérification que `LlmRouter` passe bien `prior_summary` et `budget` cross-adapter | ADAPTATION | `core/adaptation/llm_router.py`, `core/adaptation/story_extractor.py` |

---

## État des lieux — ce qui existe déjà (247 tests, commit 87e2595)

### ✅ Ce qui est en place
- `ProductionOutput` complète : timeline avec `start_sec`, `video_url`, `audio_url`, `silence_padding_sec`
- `CharacterSheetRegistry` + `CharacterImageRegistry` : stockent `canonical_prompt` + première URL par personnage
- `CheckpointStore` : sauvegarde/reprise JSON pour les shots storyboard
- `RunMetrics` : `shots_requested`, `shots_generated`, `shots_failed`, `image_latency_ms`, `video_latency_ms`
- `EpisodeScheduler` : run séquentiel image → vidéo → audio + metrics image + vidéo
- `SmartVideoRouter` : logique de routing Runway/Kling existante (`≤5 sec → Runway, >5 sec → Kling`)
- `AudioSynchronizer.generate()` retourne `(List[AudioResult], ProductionOutput)` — latences accessibles dans `AudioResult`
- `ffmpeg_exporter.py` : fichier présent mais corps vide (stub)
- `LlmRouter` : routing Claude/Gemini par taille de prompt
- `NullImageAdapter`, `NullVideoAdapter`, `NullAudioAdapter` : stubs CI fonctionnels
- Prod adapters : `FluxAdapter`, `ReplicateAdapter`, `RunwayAdapter`, `KlingAdapter`, `ElevenLabsAdapter`, `OpenAITTSAdapter` — implémentés mais non exposés en CLI

### ❌ Ce qui manque / est cassé
- `ffmpeg_exporter.py` : corps vide — `ProductionOutput` n'est jamais rendue en fichier vidéo
- Pas de prepass "character sheet" : le 1er shot d'un personnage sert de référence non contrôlée
- CLI : 0 option `--image-adapter` / `--video-adapter` — adapters de prod inutilisables sans code Python
- `LocationRegistry` et `PropRegistry` : inexistants — `prompt_enricher.py` n'injecte que les personnages
- `SmartVideoRouter` : non intégré dans `EpisodeScheduler` (hardcodé sur `NullVideoAdapter`)
- `TimelineClip` n'a pas de champ `latency_ms` → `RunMetrics.audio_latency_ms` reste toujours à 0
- Aucun `CostReport` : pas de tracking des coûts API (tokens, appels, euros estimés)
- `LlmRouter` ne passe pas `budget` ni `prior_summary` lors du routage multi-adapter

---

## PC-01 ⏳ — FFmpeg muxing

### Problème
`FfmpegExporter` existe (`post_prod/ffmpeg_exporter.py`) mais son corps est vide. La `ProductionOutput` contient une timeline complète (`video_url`, `audio_url`, `start_sec`) mais rien ne la convertit en fichier vidéo réel.

### Solution
Implémenter `FfmpegExporter.export(production: ProductionOutput, output_path: Path) -> Path` :
1. Pour chaque `TimelineClip` : télécharger (si URL distante) ou utiliser le chemin local
2. Construire un filtre `concat` ffmpeg pour assembler vidéo + audio avec les timecodes exacts
3. Retourner le chemin du fichier produit

### Contrat attendu

```python
# post_prod/ffmpeg_exporter.py

from pathlib import Path
from aiprod_adaptation.post_prod.audio_request import ProductionOutput

class FfmpegExporter:
    def __init__(self, ffmpeg_bin: str = "ffmpeg", working_dir: Path | None = None) -> None:
        ...

    def export(self, production: ProductionOutput, output_path: Path) -> Path:
        """
        Assemble les clips vidéo + audio de production.timeline en un fichier MP4.
        Utilise ffmpeg concat filter.
        Retourne output_path (créé ou écrasé).
        Lève RuntimeError si ffmpeg n'est pas disponible.
        """
        ...

    def is_available(self) -> bool:
        """Retourne True si ffmpeg est installé et accessible."""
        ...
```

### Fichiers à modifier
- `post_prod/ffmpeg_exporter.py` — implémenter le corps
- `aiprod_adaptation/cli.py` — ajouter commande `aiprod mux --input production.json --output video.mp4`

### Tests attendus (fichier : `tests/test_post_prod.py`)
- `test_ffmpeg_exporter_is_available_returns_bool` — vérifie que `is_available()` retourne un bool sans planter
- `test_ffmpeg_exporter_raises_if_unavailable` — mock ffmpeg absent → `RuntimeError`
- `test_ffmpeg_exporter_builds_correct_concat_args` — vérifie les arguments ffmpeg construits (sans vraiment l'exécuter)
- `test_ffmpeg_exporter_creates_output_file` — test d'intégration marqué `@pytest.mark.integration`

---

## PC-02 ⏳ — Character prepass

### Problème
`CharacterSheetRegistry` stocke des `CharacterSheet` (canonical_prompt + seed), mais il n'existe pas de pipeline qui :
1. Collecte tous les personnages d'un `AIPRODOutput`
2. Génère une image de référence dédiée pour chacun (1 appel `ImageAdapter` par personnage)
3. Enregistre ces images dans `CharacterImageRegistry` avant que `StoryboardGenerator` commence

Sans ce prepass, la première image d'un personnage dans n'importe quel shot sert de référence, ce qui est non contrôlé.

### Solution
Créer `CharacterPrepass` :

```python
# image_gen/character_prepass.py

from dataclasses import dataclass
from aiprod_adaptation.image_gen.character_sheet import CharacterSheetRegistry
from aiprod_adaptation.image_gen.character_image_registry import CharacterImageRegistry
from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.models.schema import AIPRODOutput

@dataclass
class CharacterPrepassResult:
    generated: int          # nombre de personnages dont l'image a été générée
    failed: int             # erreurs éventuelles
    registry: CharacterImageRegistry  # registry peuplée

class CharacterPrepass:
    def __init__(
        self,
        adapter: ImageAdapter,
        sheet_registry: CharacterSheetRegistry | None = None,
        base_seed: int = 0,
    ) -> None: ...

    def run(self, output: AIPRODOutput) -> CharacterPrepassResult:
        """
        1. Extrait tous les personnages uniques de output
        2. Pour chaque personnage : ImageRequest avec canonical_prompt du CharacterSheet (ou nom si absent)
        3. Stocke le résultat dans CharacterImageRegistry
        4. Retourne CharacterPrepassResult
        """
        ...
```

Brancher dans `StoryboardGenerator.__init__` : `prepass_result: CharacterPrepassResult | None = None`
→ si fourni, initialiser `self._char_registry` avec `prepass_result.registry`.

### Fichiers à modifier
- `image_gen/character_prepass.py` (NEW)
- `image_gen/storyboard.py` — accepter `prepass_result` en paramètre d'init
- `image_gen/__init__.py` — exporter `CharacterPrepass`, `CharacterPrepassResult`
- `core/scheduling/episode_scheduler.py` — exécuter le prepass avant `StoryboardGenerator.generate()`

### Tests attendus (fichier : `tests/test_image_gen.py`)
- `test_character_prepass_generates_one_image_per_character`
- `test_character_prepass_populates_registry`
- `test_character_prepass_handles_adapter_failure_gracefully`
- `test_storyboard_generator_uses_prepass_registry`

---

## PC-03 ⏳ — CLI adapters de prod

### Problème
`aiprod pipeline` et `aiprod storyboard` utilisent systématiquement `NullImageAdapter`, `NullVideoAdapter`, `NullAudioAdapter`. Les adapters de production (`FluxAdapter`, `ReplicateAdapter`, `RunwayAdapter`, `KlingAdapter`, `ElevenLabsAdapter`, `OpenAITTSAdapter`) ne sont utilisables qu'en Python direct.

### Solution
Ajouter des options `--image-adapter`, `--video-adapter`, `--audio-adapter` aux sous-commandes CLI, avec un registre d'adapters :

```python
# cli.py — ajouts

IMAGE_ADAPTERS: dict[str, Callable[[], ImageAdapter]] = {
    "null":       lambda: NullImageAdapter(),
    "flux":       lambda: FluxAdapter(),        # lit FLUX_API_URL
    "replicate":  lambda: ReplicateAdapter(),   # lit REPLICATE_API_TOKEN
}

VIDEO_ADAPTERS: dict[str, Callable[[], VideoAdapter]] = {
    "null":   lambda: NullVideoAdapter(),
    "runway": lambda: RunwayAdapter(),          # lit RUNWAY_API_TOKEN
    "kling":  lambda: KlingAdapter(),           # lit KLING_API_KEY + KLING_API_SECRET
    "smart":  lambda: SmartVideoRouter(),       # auto-routing Runway/Kling
}

AUDIO_ADAPTERS: dict[str, Callable[[], AudioAdapter]] = {
    "null":       lambda: NullAudioAdapter(),
    "elevenlabs": lambda: ElevenLabsAdapter(),  # lit ELEVENLABS_API_KEY
    "openai":     lambda: OpenAITTSAdapter(),   # lit OPENAI_API_KEY
}
```

Commandes enrichies :
```bash
aiprod pipeline --input ch.txt --title "EP1" --output ir.json
aiprod storyboard --input ir.json --output sb.json --image-adapter replicate
aiprod schedule --input ir.json --output result/ \
    --image-adapter flux \
    --video-adapter smart \
    --audio-adapter elevenlabs
```

Nouvelle sous-commande `schedule` qui appelle `EpisodeScheduler` avec les adapters sélectionnés.

### Fichiers à modifier
- `aiprod_adaptation/cli.py` — ajouter `--image-adapter`, `--video-adapter`, `--audio-adapter` + commande `schedule`
- `core/scheduling/episode_scheduler.py` — accepter `VideoAdapter` générique (déjà le cas via interface)

### Tests attendus (fichier : `tests/test_cli.py`)
- `test_cli_image_adapter_null_is_default`
- `test_cli_image_adapter_invalid_name_exits_nonzero`
- `test_cli_schedule_command_outputs_scheduler_result_json`
- `test_cli_schedule_saves_storyboard_video_production_files`

---

## PC-04 ⏳ — Continuité lieu/prop

### Problème
`prompt_enricher.py` injecte uniquement les descriptions de personnages. Il n'y a aucun tracking de :
- **Lieux** : la couleur des murs, l'éclairage, les objets de décor doivent être cohérents entre tous les shots d'une même scène
- **Props** : un objet tenu par un personnage au shot N doit apparaître au shot N+1 s'il n'est pas posé

### Solution

```python
# core/continuity/location_registry.py (NEW)

@dataclass
class LocationProfile:
    location_id: str      # normalisé (lower, strip)
    description: str      # issu du 1er VisualScene avec ce lieu
    lighting_hint: str    # extrait de time_of_day_visual ou dominant_sound
    first_seen_scene: str

class LocationRegistry:
    def build_from_output(self, output: AIPRODOutput) -> "LocationRegistry": ...
    def get_prompt_hint(self, location: str) -> str: ...
    # → "LOCATION CONTEXT: {description}. Lighting: {lighting_hint}."
```

```python
# core/continuity/prop_registry.py (NEW)

@dataclass
class PropEntry:
    name: str
    held_by: str | None   # personnage portant l'objet
    last_seen_shot: str
    description: str

class PropRegistry:
    def register(self, prop: str, held_by: str | None, shot_id: str) -> None: ...
    def get_active_props_for_character(self, character: str) -> list[PropEntry]: ...
    def get_prompt_hint(self, shot_id: str) -> str: ...
    # → "PROPS IN SCENE: {name} held by {held_by}."
```

Brancher dans `prompt_enricher.py` : injecter les hints lieu + props après les hints personnage.

### Fichiers à modifier
- `core/continuity/location_registry.py` (NEW)
- `core/continuity/prop_registry.py` (NEW)
- `core/continuity/__init__.py` — exporter les deux
- `core/continuity/prompt_enricher.py` — accepter `location_registry` et `prop_registry` optionnels

### Tests attendus (fichier : `tests/test_continuity.py`)
- `test_location_registry_builds_from_output`
- `test_location_registry_get_prompt_hint_contains_location_name`
- `test_prop_registry_register_and_retrieve`
- `test_prop_registry_get_active_props_for_character`
- `test_prompt_enricher_injects_location_hint`
- `test_prompt_enricher_injects_prop_hint`

---

## PC-05 ⏳ — SmartVideoRouter intégration

### Problème
`SmartVideoRouter` (routing automatique Runway ≤5 sec / Kling >5 sec) existe dans `video_gen/smart_video_router.py` mais :
1. N'est pas intégré dans `EpisodeScheduler` (qui reçoit un `VideoAdapter` générique mais ne propose pas de routage automatique)
2. N'est pas exposé dans le CLI (PC-03 l'expose, mais PC-05 l'intègre réellement)

### Solution
Vérifier que `SmartVideoRouter` implémente correctement `VideoAdapter` et brancher l'option `--video-adapter smart` dans CLI.
Intégrer dans `EpisodeScheduler` le support implicite : si `video_adapter` est une instance de `SmartVideoRouter`, pas de traitement spécial nécessaire (polymorphisme).

Corriger si `SmartVideoRouter.generate()` ne respecte pas la signature `VideoAdapter.generate(request: VideoRequest) -> VideoClipResult`.

### Fichiers à modifier
- `video_gen/smart_video_router.py` — vérifier/corriger l'implémentation de l'interface `VideoAdapter`
- `video_gen/__init__.py` — exporter `SmartVideoRouter`
- `aiprod_adaptation/cli.py` — référencé dans PC-03 (dépendance)

### Tests attendus (fichier : `tests/test_video_gen.py`)
- `test_smart_video_router_routes_short_clip_to_runway`
- `test_smart_video_router_routes_long_clip_to_kling`
- `test_smart_video_router_implements_video_adapter_interface`

---

## PC-06 ⏳ — Audio latency tracking

### Problème
`RunMetrics.audio_latency_ms` reste toujours à 0 car `TimelineClip` ne stocke pas `latency_ms`. Les `AudioResult` objets contiennent bien `latency_ms` mais ne sont pas remontés dans `EpisodeScheduler`.

### Solution
1. Ajouter `latency_ms: int = 0` à `TimelineClip` (optionnel, ne casse pas la rétrocompatibilité)
2. Dans `AudioSynchronizer.generate()` : peupler `TimelineClip.latency_ms` depuis `AudioResult.latency_ms`
3. Dans `EpisodeScheduler.run()` : sommer `clip.latency_ms` pour `metrics.audio_latency_ms`

### Contrat

```python
# post_prod/audio_request.py — ajout dans TimelineClip
@dataclass
class TimelineClip(BaseModel):
    ...
    latency_ms: int = 0  # durée de l'appel audio en ms (0 si non mesuré)
```

### Fichiers à modifier
- `post_prod/audio_request.py` — ajouter `latency_ms: int = 0` à `TimelineClip`
- `post_prod/audio_synchronizer.py` — peupler `latency_ms` dans le clip
- `core/scheduling/episode_scheduler.py` — sommer pour `metrics.audio_latency_ms`

### Tests attendus (fichier : `tests/test_scheduling.py`)
- `test_timeline_clip_has_latency_ms_field`
- `test_audio_synchronizer_populates_latency_ms`
- `test_scheduler_metrics_audio_latency_is_nonzero_with_real_adapter` — marqué `@pytest.mark.integration`
- `test_scheduler_metrics_audio_latency_zero_with_null_adapter`

---

## PC-07 ⏳ — CostReport

### Problème
`RunMetrics` capture les latences mais pas les coûts. Il n'existe aucun mécanisme pour :
- Compter les tokens LLM consommés (Claude, Gemini)
- Compter les appels API image/vidéo/audio
- Estimer un coût en euros/dollars
- Agréger ces coûts sur plusieurs épisodes

### Solution

```python
# core/cost_report.py (NEW)

from dataclasses import dataclass, field

@dataclass
class CostReport:
    llm_tokens_input: int = 0
    llm_tokens_output: int = 0
    image_api_calls: int = 0
    video_api_calls: int = 0
    audio_api_calls: int = 0

    # Coûts estimés en USD (tarifs configurables)
    llm_cost_usd: float = 0.0
    image_cost_usd: float = 0.0
    video_cost_usd: float = 0.0
    audio_cost_usd: float = 0.0

    @property
    def total_cost_usd(self) -> float: ...

    def merge(self, other: "CostReport") -> "CostReport":
        """Fusionne deux rapports (cross-épisode)."""
        ...

    def to_summary_str(self) -> str:
        """Rapport lisible : tokens, appels, coût total."""
        ...
```

Intégrer dans `RunMetrics` : `cost: CostReport = field(default_factory=CostReport)`.
Les adapters de prod (Claude, Replicate, etc.) renseignent les compteurs via un mécanisme de callback ou d'enrichissement de résultat.

### Fichiers à modifier
- `core/cost_report.py` (NEW)
- `core/run_metrics.py` — ajouter `cost: CostReport`
- `core/__init__.py` — exporter `CostReport`

### Tests attendus (fichier : `tests/test_scheduling.py` ou `tests/test_cost_report.py` NEW)
- `test_cost_report_total_cost_is_sum_of_components`
- `test_cost_report_merge_accumulates_all_fields`
- `test_cost_report_to_summary_str_contains_total`
- `test_run_metrics_has_cost_report_field`

---

## PC-08 ⏳ — LLM adapter completeness

### Problème
`LlmRouter` fait le routing Claude/Gemini mais :
1. Ne passe pas `budget` au `StoryExtractor` lors du routage (perd les contraintes `max_chars_per_chunk`)
2. Ne garantit pas que `prior_summary` est transmis correctement en cas de chunking cross-adapter

### Solution
Vérifier dans `llm_router.py` que l'interface de dispatch appelle bien `extractor.extract_all(llm, text, budget)` et non `extractor.extract(llm, text, budget)`.
Ajouter un test d'intégration qui vérifie que le router préserve le budget et le prior_summary.

### Fichiers à modifier
- `core/adaptation/llm_router.py` — audit et correction si nécessaire
- `core/adaptation/story_extractor.py` — si `extract_all` n'est pas appelé depuis le router

### Tests attendus (fichier : `tests/test_adaptation.py`)
- `test_llm_router_calls_extract_all_not_extract`
- `test_llm_router_passes_budget_to_extractor`
- `test_llm_router_preserves_prior_summary_across_chunks`

---

## Ordre d'exécution recommandé

```
PC-06  (audio latency)        — 1 fichier, 4 tests, risque = 0
PC-02  (character prepass)    — fondation pour cohérence image
PC-04  (lieu/prop registry)   — compléter la continuité
PC-05  (SmartVideoRouter)     — vérification/correction interface
PC-08  (LLM completeness)     — audit + correction
PC-03  (CLI adapters)         — expose tout ce qui précède
PC-07  (CostReport)           — observabilité, dernier car dépend des adapters
PC-01  (FFmpeg muxing)        — livrable final visible, nécessite ffmpeg installé
```

---

## Critères de succès

- `ruff check aiprod_adaptation/` → 0 erreur
- `mypy aiprod_adaptation/core/ ... --strict` → 0 erreur
- `pytest aiprod_adaptation/tests/ -q --tb=short -m "not integration"` → 310+ passed, 0 failed
- Toutes les barres de progression à 100% :

```
[COMPILATEUR IR]          ████████████  100%
[ADAPTATION LLM]          ████████████  100%
[CONTINUITÉ]              ████████████  100%
[IMAGE GEN]               ████████████  100%
[VIDEO GEN]               ████████████  100%
[AUDIO / POST-PROD]       ████████████  100%
[SCHEDULER / METRICS]     ████████████  100%
[CLI / IO]                ████████████  100%
[EXPORT BACKENDS]         ████████████  100%
[TESTS]                   ████████████  310+ tests, 0 rouge
```
