---
title: Plan d'action — Scale & Orchestration v1
source: bilan_conceptuel_2026-04-21
creation: 2026-04-21 à 17:48
last_updated: 2026-04-21 à 17:48
status: active
phase: SO (Scale & Orchestration — P6 + gaps fonctionnels)
prerequis: storyboard_coherence_v1_plan.md complété (2026-04-21) — 200/200 tests
tests_avant: 200
tests_apres_cible: 238+
---

# PLAN D'ACTION — SCALE & ORCHESTRATION v1 — 2026-04-21

**Étapes totales** : 8

| ID | Priorité | Action | Phase | Fichier(s) impactés |
|---|---|---|---|---|
| SO-01 | 🔴 Critique | Implémenter `split_into_chunks()` + boucle de chunking dans `StoryExtractor` | P6 | `core/adaptation/story_extractor.py` |
| SO-02 | 🔴 Critique | Ajouter `max_chars_per_chunk` à `ProductionBudget` et enforcer dans le chunking | P6 | `core/production_budget.py`, `core/adaptation/story_extractor.py` |
| SO-03 | 🔴 Critique | Persistance JSON — `save_output()` / `load_output()` pour tous les IRs | FX | `core/io.py` (NEW) |
| SO-04 | 🟠 Important | `EpisodeScheduler` — orchestrateur séquentiel image + vidéo + audio | P6 | `core/scheduling/episode_scheduler.py` (NEW) |
| SO-05 | 🟠 Important | CLI — commande `aiprod` avec `pipeline` et `storyboard` sous-commandes | FX | `aiprod_adaptation/cli.py` (NEW) |
| SO-06 | 🟠 Important | Checkpoint/reprise dans `StoryboardGenerator` — sauter les shots déjà générés | FX | `image_gen/storyboard.py`, `image_gen/checkpoint.py` (NEW) |
| SO-07 | 🟡 Nice-to-have | Tests multi-épisodes — valider la compilation et les exports sur N > 1 épisodes | FX | `tests/test_pipeline.py`, `tests/test_backends.py` |
| SO-08 | 🟡 Nice-to-have | `RunMetrics` — tracking latency/cost agrégé par run de génération | FX | `core/run_metrics.py` (NEW) |

---

## État des lieux — ce qui existe déjà (200 tests, commit 70bce13)

### ✅ Ce qui est en place
- `StoryExtractor.extract_chunk()` — **alias** de `extract()`, signature P6-compatible avec `prior_summary`
- `ProductionBudget.chunk_size: int = 20` — taille en nombre de scènes, pas en tokens/chars
- `AIPRODOutput` / `Episode` / `Scene` / `Shot` — tous Pydantic v2 → `model_dump()` / `model_dump_json()` disponibles nativement
- `StoryboardOutput`, `VideoOutput`, `ProductionOutput` — tous Pydantic v2

### ❌ Ce qui manque / est cassé
- Aucune fonction de découpage texte → `extract_chunk()` reçoit toujours le roman **entier**
- `ProductionBudget` n'a pas de `max_chars_per_chunk` — `chunk_size` est en nombre de scènes (heuristique non reliable)
- Pas de sauvegarde sur disque des IRs (`AIPRODOutput`, `StoryboardOutput`, etc.)
- Pas d'interface CLI — usage = code Python direct uniquement
- Pas de checkpoint : si `StoryboardGenerator` plante au shot 47/80, tout est perdu
- 0 test sur un `AIPRODOutput` avec `len(episodes) > 1` malgré le support dans le modèle
- Pas de collecte de latency/cost au niveau run complet

---

## SO-01 ⏳ — `split_into_chunks()` + boucle de chunking dans `StoryExtractor`

### Problème
`extract_chunk()` existe mais ne **fait rien de plus** que `extract()` : le texte entier est passé au LLM en un seul appel. Pour un roman de 100K chars, on dépasse le context window et le LLM tronque silencieusement.

### Solution
Ajouter une fonction `split_into_chunks()` standalone (découpages aux sauts de paragraphes), puis une méthode `extract_all()` qui boucle en passant un résumé glissant (`prior_summary`) entre chaque chunk.

### Contrat attendu

```python
# core/adaptation/story_extractor.py

def split_into_chunks(text: str, max_chars: int = 8_000) -> list[str]:
    """
    Découpe le texte aux frontières de paragraphes (double newline).
    Garantit: len(chunk) <= max_chars.
    Si un paragraphe seul dépasse max_chars, il est tronqué à la dernière phrase.
    Retourne: liste de chunks non-vides.
    """

class StoryExtractor:
    def extract_all(
        self,
        llm: LLMAdapter,
        text: str,
        budget: ProductionBudget,
    ) -> list[VisualScene]:
        """
        Découpe text en chunks, appelle extract_chunk() sur chacun avec prior_summary cumulatif.
        Combine et déduplique (même scene_id) les scènes résultantes.
        Fallback: si 1 seul chunk, identique à extract().
        """
```

### Fichiers à modifier
- `core/adaptation/story_extractor.py` — ajouter `split_into_chunks()` (module-level) + `extract_all()`

### Tests à écrire (dans `test_adaptation.py`)
- `test_split_into_chunks_respects_max_chars` — aucun chunk ne dépasse `max_chars`
- `test_split_into_chunks_splits_at_paragraph_boundaries` — coupures sur `\n\n`
- `test_split_into_chunks_single_paragraph_truncated` — paragraphe > max_chars → tronqué
- `test_split_into_chunks_empty_text_returns_empty_list`
- `test_extract_all_single_chunk_equivalent_to_extract` — comportement identique si 1 chunk
- `test_extract_all_multiple_chunks_passes_prior_summary` — vérifie que `prior_summary` se propage

---

## SO-02 ⏳ — `max_chars_per_chunk` dans `ProductionBudget` + enforcement

### Problème
`ProductionBudget.chunk_size = 20` représente un nombre de scènes cible, pas un budget de tokens/chars. Il n'existe aucune contrainte qui empêche un appel LLM de recevoir 200K chars.

### Solution
Ajouter `max_chars_per_chunk: int = 8_000` à `ProductionBudget`, et que `split_into_chunks()` (SO-01) lise ce champ plutôt qu'une valeur hardcodée.

### Contrat attendu

```python
@dataclass(frozen=True)
class ProductionBudget:
    target_duration_sec: int = 180
    max_scenes: int = 12
    max_shots_per_scene: int = 6
    max_characters: int = 4
    chunk_size: int = 20
    max_chars_per_chunk: int = 8_000    # ← NOUVEAU

    @classmethod
    def for_short(cls) -> "ProductionBudget":
        return cls(target_duration_sec=180, max_scenes=12, max_characters=4)

    @classmethod
    def for_episode_45(cls) -> "ProductionBudget":
        return cls(
            target_duration_sec=2700,
            max_scenes=135,
            max_characters=6,
            chunk_size=20,
            max_chars_per_chunk=12_000,    # ← Gemini peut ingérer plus
        )
```

### Fichiers à modifier
- `core/production_budget.py` — ajouter `max_chars_per_chunk`
- `core/adaptation/story_extractor.py` — `split_into_chunks()` lit `budget.max_chars_per_chunk`

### Tests à écrire (dans `test_adaptation.py` ou `test_pipeline.py`)
- `test_budget_default_max_chars_per_chunk` — valeur par défaut = 8000
- `test_budget_for_episode_45_has_larger_chunk` — `for_episode_45().max_chars_per_chunk > 8_000`
- `test_extract_all_respects_budget_max_chars` — chunks issus de `extract_all` ≤ `budget.max_chars_per_chunk`
- `test_budget_frozen_dataclass_max_chars_immutable`

---

## SO-03 ⏳ — Persistance JSON — `save_output()` / `load_output()`

### Problème
`AIPRODOutput` est Pydantic v2 → `model_dump_json()` est gratuit. Mais il n'existe aucun utilitaire dans le projet pour écrire/lire ces IRs depuis le disque. Un run de 2h de génération produit des données éphémères perdues à la fin du script.

### Solution
Créer `core/io.py` avec des fonctions de persistance typées pour chacun des 4 IRs du pipeline.

### Contrat attendu

```python
# core/io.py (NEW)
from pathlib import Path
from aiprod_adaptation.models.schema import AIPRODOutput
from aiprod_adaptation.image_gen.image_request import StoryboardOutput
from aiprod_adaptation.video_gen.video_request import VideoOutput
from aiprod_adaptation.post_prod.audio_request import ProductionOutput


def save_output(output: AIPRODOutput, path: Path | str) -> None:
    """Écrit AIPRODOutput en JSON (UTF-8, indenté). Crée les répertoires parents."""

def load_output(path: Path | str) -> AIPRODOutput:
    """Charge et valide un AIPRODOutput depuis un fichier JSON."""

def save_storyboard(sb: StoryboardOutput, path: Path | str) -> None: ...
def load_storyboard(path: Path | str) -> StoryboardOutput: ...

def save_video(vo: VideoOutput, path: Path | str) -> None: ...
def load_video(path: Path | str) -> VideoOutput: ...

def save_production(po: ProductionOutput, path: Path | str) -> None: ...
def load_production(path: Path | str) -> ProductionOutput: ...
```

### Fichiers à créer/modifier
- `core/io.py` (NEW) — 4 paires save/load
- `core/__init__.py` — exporter `save_output`, `load_output`

### Tests à écrire (nouveau `tests/test_io.py`)
- `test_save_load_output_roundtrip` — save → load → égal à l'original
- `test_save_load_storyboard_roundtrip`
- `test_save_load_video_roundtrip`
- `test_save_load_production_roundtrip`
- `test_load_output_invalid_json_raises_validation_error` — fichier corrompu → `ValidationError`

---

## SO-04 ⏳ — `EpisodeScheduler` — orchestrateur séquentiel image + vidéo + audio

### Problème
Pour produire un épisode complet, il faut actuellement appeler manuellement 3 générateurs dans l'ordre (`StoryboardGenerator` → `VideoSequencer` → `AudioSynchronizer`). Il n'y a aucun composant d'orchestration : erreur = tout recommencer.

### Solution
`EpisodeScheduler` orchestre les 3 couches séquentiellement pour un `AIPRODOutput`. Il est compatible avec le checkpoint SO-06 (si un IR est déjà présent sur disque, il saute l'étape).

### Contrat attendu

```python
# core/scheduling/episode_scheduler.py (NEW)
from __future__ import annotations
from dataclasses import dataclass
from aiprod_adaptation.models.schema import AIPRODOutput
from aiprod_adaptation.image_gen.image_request import StoryboardOutput
from aiprod_adaptation.video_gen.video_request import VideoOutput
from aiprod_adaptation.post_prod.audio_request import ProductionOutput


@dataclass
class SchedulerResult:
    storyboard: StoryboardOutput
    video: VideoOutput
    production: ProductionOutput


class EpisodeScheduler:
    def __init__(
        self,
        image_adapter: ImageAdapter,
        video_adapter: VideoAdapter,
        audio_adapter: AudioAdapter,
        base_seed: int = 42,
    ) -> None: ...

    def run(self, output: AIPRODOutput) -> SchedulerResult:
        """
        Enchaîne StoryboardGenerator → VideoSequencer → AudioSynchronizer.
        Retourne SchedulerResult avec les 3 IRs.
        """
```

### Fichiers à créer
- `core/scheduling/__init__.py` (NEW)
- `core/scheduling/episode_scheduler.py` (NEW)

### Tests à écrire (nouveau `tests/test_scheduling.py`)
- `test_scheduler_run_returns_scheduler_result`
- `test_scheduler_storyboard_frames_count_matches_shots`
- `test_scheduler_video_clips_count_matches_frames`
- `test_scheduler_production_timeline_count_matches_clips`
- `test_scheduler_result_image_urls_propagate_to_video`

---

## SO-05 ⏳ — CLI — commande `aiprod` avec sous-commandes

### Problème
Zéro interface utilisateur. Exécuter le pipeline = écrire du Python. Bloquant pour tout usage non-dev.

### Solution
CLI minimaliste via `argparse` (0 nouvelle dépendance) avec 2 sous-commandes :
- `aiprod pipeline` — texte → `AIPRODOutput` (JSON sur disque)
- `aiprod storyboard` — `AIPRODOutput` → `StoryboardOutput` (JSON sur disque)

### Contrat attendu

```
# Usage
aiprod pipeline --input roman.txt --title "Mon Roman" --output output.json
aiprod pipeline --input script.fountain --title "Mon Film" --output output.json [--format script]
aiprod storyboard --input output.json --output storyboard.json [--style-token "custom style"]
```

```python
# aiprod_adaptation/cli.py (NEW)
def build_parser() -> argparse.ArgumentParser: ...
def cmd_pipeline(args: argparse.Namespace) -> int: ...
def cmd_storyboard(args: argparse.Namespace) -> int: ...
def main() -> None: ...
```

**Entry point dans pyproject.toml :**
```toml
[project.scripts]
aiprod = "aiprod_adaptation.cli:main"
```

### Fichiers à créer/modifier
- `aiprod_adaptation/cli.py` (NEW)
- `pyproject.toml` — ajouter `[project.scripts]`

### Tests à écrire (nouveau `tests/test_cli.py`)
- `test_cli_pipeline_outputs_valid_json` — appel via `subprocess` ou `argparse` direct
- `test_cli_pipeline_missing_input_exits_nonzero`
- `test_cli_storyboard_reads_output_json`
- `test_cli_help_does_not_crash`

---

## SO-06 ⏳ — Checkpoint/reprise dans `StoryboardGenerator`

### Problème
Si `StoryboardGenerator.generate()` plante au shot 47/80 (timeout API, OOM, etc.), les 46 images déjà générées sont perdues — le prochain appel repart de zéro.

### Solution
`CheckpointStore` persistant (fichier JSON par run) : avant chaque appel adapter, on vérifie si `shot_id` est déjà dans le store. Après chaque succès, on sauvegarde. En cas de crash, le prochain `generate()` reprend là où il s'était arrêté.

### Contrat attendu

```python
# image_gen/checkpoint.py (NEW)
from pathlib import Path
from aiprod_adaptation.image_gen.image_request import ShotStoryboardFrame


class CheckpointStore:
    def __init__(self, path: Path | None = None) -> None:
        """path=None → store en mémoire (pour tests). path → fichier JSON."""

    def has(self, shot_id: str) -> bool: ...
    def save(self, frame: ShotStoryboardFrame) -> None: ...
    def get(self, shot_id: str) -> ShotStoryboardFrame | None: ...
    def all_cached(self) -> list[ShotStoryboardFrame]: ...


# image_gen/storyboard.py — modifier StoryboardGenerator.__init__
class StoryboardGenerator:
    def __init__(
        self,
        adapter: ImageAdapter,
        base_seed: int = 42,
        style_token: str = DEFAULT_STYLE_TOKEN,
        character_prompts: dict[str, str] | None = None,
        checkpoint: CheckpointStore | None = None,   # ← NOUVEAU
    ) -> None: ...
```

### Fichiers à créer/modifier
- `image_gen/checkpoint.py` (NEW)
- `image_gen/storyboard.py` — injecter `CheckpointStore` dans `generate()`
- `image_gen/__init__.py` — exporter `CheckpointStore`

### Tests à écrire (dans `test_image_gen.py`)
- `test_checkpoint_store_memory_has_after_save`
- `test_checkpoint_store_get_returns_frame`
- `test_storyboard_skips_cached_shots` — adapter.generate() non appelé pour shots déjà en cache
- `test_storyboard_resumes_from_partial_checkpoint` — 2/3 shots en cache → 1 seul appel adapter
- `test_checkpoint_store_file_persists_and_reloads` — save sur disque, recharger, `has()` = True

---

## SO-07 ⏳ — Tests multi-épisodes

### Problème
`AIPRODOutput.episodes: list[Episode]` supporte N épisodes, mais **tous les tests** compilent un output avec `len(episodes) == 1`. Les bugs multi-épisodes (index collision, export CSV incomplet, etc.) sont invisibles.

### Solution
Ajouter une fixture `_multi_episode_output()` et des tests dédiés dans `test_pipeline.py` et `test_backends.py`.

### Contrat attendu

```python
# Dans test_pipeline.py
def _multi_episode_output() -> AIPRODOutput:
    """Retourne un AIPRODOutput avec 2 épisodes distincts (6 scènes, 18 shots total)."""
    ...

class TestMultiEpisode:
    def test_compile_two_episodes(self) -> None: ...
    def test_shot_ids_unique_across_episodes(self) -> None: ...
    def test_scene_ids_unique_across_episodes(self) -> None: ...
    def test_csv_export_includes_all_episodes(self) -> None: ...
    def test_json_flat_export_includes_all_episodes(self) -> None: ...
```

### Fichiers à modifier
- `tests/test_pipeline.py` — ajouter `_multi_episode_output()` + `TestMultiEpisode`
- `tests/test_backends.py` — ajouter tests CSV/JSON multi-épisodes

### Tests à écrire
- `test_compile_two_episodes` — `len(output.episodes) == 2`
- `test_shot_ids_unique_across_episodes` — aucun `shot_id` en doublon entre épisodes
- `test_scene_ids_unique_across_episodes`
- `test_csv_export_includes_all_episodes` — nb lignes CSV = total shots des 2 épisodes
- `test_json_flat_export_includes_all_episodes`

---

## SO-08 ⏳ — `RunMetrics` — tracking latency/cost agrégé

### Problème
Aucun composant ne collecte les métriques d'un run complet (durée totale, coût estimé, shots générés vs échoués). Impossible de monitorer une production de 80 shots en cours.

### Solution
`RunMetrics` dataclass collecté par `EpisodeScheduler` (SO-04) et retourné dans `SchedulerResult`.

### Contrat attendu

```python
# core/run_metrics.py (NEW)
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class RunMetrics:
    shots_requested: int = 0
    shots_generated: int = 0
    shots_failed: int = 0
    total_latency_ms: int = 0
    image_latency_ms: int = 0
    video_latency_ms: int = 0
    audio_latency_ms: int = 0

    @property
    def success_rate(self) -> float:
        if self.shots_requested == 0:
            return 1.0
        return self.shots_generated / self.shots_requested

    @property
    def average_latency_ms(self) -> float:
        if self.shots_generated == 0:
            return 0.0
        return self.total_latency_ms / self.shots_generated
```

### Fichiers à créer/modifier
- `core/run_metrics.py` (NEW)
- `core/scheduling/episode_scheduler.py` (SO-04) — enrichir `SchedulerResult` avec `metrics: RunMetrics`
- `core/__init__.py` — exporter `RunMetrics`

### Tests à écrire (dans `tests/test_scheduling.py`)
- `test_run_metrics_success_rate_all_generated`
- `test_run_metrics_success_rate_partial_failure`
- `test_run_metrics_average_latency`
- `test_scheduler_result_has_metrics`

---

## Récapitulatif des tests attendus

| Étape | Fichier cible | Tests nouveaux |
|---|---|---|
| SO-01 | `test_adaptation.py` | +6 |
| SO-02 | `test_adaptation.py` ou `test_pipeline.py` | +4 |
| SO-03 | `tests/test_io.py` (NEW) | +5 |
| SO-04 | `tests/test_scheduling.py` (NEW) | +5 |
| SO-05 | `tests/test_cli.py` (NEW) | +4 |
| SO-06 | `test_image_gen.py` | +5 |
| SO-07 | `test_pipeline.py`, `test_backends.py` | +5 |
| SO-08 | `tests/test_scheduling.py` | +4 |
| **Total** | — | **+38** |

**Cible : 200 + 38 = 238 tests**

---

## Risques & points de vigilance

| Risque | Mitigation |
|---|---|
| `split_into_chunks()` coupe en milieu de dialogue | Couper uniquement sur `\n\n` (frontière de paragraphe) |
| `prior_summary` génère des doublons de scènes entre chunks | Dédupliquer par `(location, characters[:1])` dans `extract_all()` |
| `CheckpointStore` en fichier crée des effets de bord entre tests | `path=None` → store in-memory dans tous les tests |
| CLI argparse — tests difficiles à isoler | Passer `args` directement à `cmd_pipeline()`, ne pas tester via `sys.argv` |
| `EpisodeScheduler` dépend de 3 adapters → setup lourd | Utiliser les 3 `Null*Adapter` dans tous les tests |
| `RunMetrics` dans `SchedulerResult` casse l'API SO-04 si ajouté après | Inclure `metrics` dès la création de `SchedulerResult` dans SO-04 |

---

## Ordre d'exécution recommandé

```
SO-02 (budget max_chars) → SO-01 (split_into_chunks) → SO-03 (io.py)
    → SO-08 (RunMetrics) → SO-04 (EpisodeScheduler + metrics) → SO-06 (checkpoint)
    → SO-07 (multi-épisodes tests) → SO-05 (CLI)
```

Rationale :
- SO-02 avant SO-01 : `split_into_chunks()` lit `budget.max_chars_per_chunk`
- SO-08 avant SO-04 : `SchedulerResult` inclut `metrics` dès sa création
- SO-03 avant SO-05 : la CLI utilise `save_output()` / `load_output()`
- SO-07 en avant-dernier : tests de régression une fois la logique multi-épisodes stabilisée
- SO-05 (CLI) en dernier : surface externe, dépend de tout le reste
