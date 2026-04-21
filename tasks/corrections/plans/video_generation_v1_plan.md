---
title: Plan d'action — Video Generation Connector v1
source: plan_global_revise.md
creation: 2026-04-21 à 15:08
last_updated: 2026-04-21 à 15:11
status: completed
phase: P4
corrections_totales: 6 (P1:2 P2:2 P3:2)
prerequis: image_generation_v1_plan.md complété (2026-04-21) — 92/92 tests
tests_avant: 92
tests_apres_cible: 108+
tests_apres_reel: 108
---

# PLAN D'ACTION — VIDEO GENERATION CONNECTOR v1 — 2026-04-21

**Étapes totales** : 6 (P1:2 · P2:2 · P3:2)

---

## Contexte

P3 produit un `StoryboardOutput` : une image par shot.
P4 prend chaque image + le prompt associé et génère un **clip vidéo** (image-to-video).
Résultat : une séquence de clips synchronisés avec les durées de shots.

Modèles cibles : **Runway Gen-3 Alpha** et **Kling v1.5** (image-to-video).

Pattern : identique à `ImageAdapter` — ABC + NullAdapter (CI) + adapters prod exclus mypy.

---

## Architecture cible

```
StoryboardOutput  +  AIPRODOutput (durées shots)
        ↓
[VG-01] VideoRequest — 1 par shot (image_url + prompt + duration_sec)
        ↓
[VG-02] VideoAdapter ABC + NullVideoAdapter
        ↓
[VG-03] RunwayAdapter + KlingAdapter (prod, exclus CI)
        ↓
[VG-04] VideoSequencer — orchestre N appels shot→clip
        ↓
[VG-05] VideoOutput — résultat final (List[VideoClipResult])
        ↓
[VG-05] run_pipeline_with_video() dans engine.py
[VG-06] __init__.py exports
```

**Fichiers à créer :**

```
aiprod_adaptation/
  video_gen/
    __init__.py
    video_request.py     ← VG-01
    video_adapter.py     ← VG-02
    runway_adapter.py    ← VG-03
    kling_adapter.py     ← VG-03
    video_sequencer.py   ← VG-04
  tests/
    test_video_gen.py    ← VG-05/06
```

**Fichier à modifier :** `aiprod_adaptation/core/engine.py` — VG-05

---

## Modèle de données

```python
class VideoRequest(BaseModel):
    shot_id:      str
    scene_id:     str
    image_url:    str          # depuis ImageResult
    prompt:       str          # depuis Shot.prompt
    duration_sec: int          # depuis Shot.duration_sec (3–8)
    motion_score: float = 5.0  # 1.0 (quasi-statique) → 10.0 (très animé)
    seed:         int | None = None

class VideoClipResult(BaseModel):
    shot_id:    str
    video_url:  str
    duration_sec: int
    model_used: str
    latency_ms: int

class VideoOutput(BaseModel):
    title:       str
    clips:       List[VideoClipResult]
    total_shots: int
    generated:   int
```

---

## VG-01 ✅ FAIT (2026-04-21 à 15:11) — `VideoRequest` + `VideoClipResult` + `VideoOutput`

**Fichier** : `aiprod_adaptation/video_gen/video_request.py`

**Tests** — `TestVideoRequest` :
```
test_video_request_default_motion_score     # motion_score=5.0
test_video_request_duration_preserved       # duration_sec transmis
test_video_output_generated_lte_total       # generated <= total_shots
```

---

## VG-02 ✅ FAIT (2026-04-21 à 15:11) — `VideoAdapter` ABC + `NullVideoAdapter`

**Fichier** : `aiprod_adaptation/video_gen/video_adapter.py`

```python
class NullVideoAdapter(VideoAdapter):
    MODEL_NAME = "null"
    def generate(self, request: VideoRequest) -> VideoClipResult:
        return VideoClipResult(
            shot_id=request.shot_id,
            video_url=f"null://clips/{request.shot_id}.mp4",
            duration_sec=request.duration_sec,
            model_used=self.MODEL_NAME,
            latency_ms=0,
        )
```

**Tests** — `TestNullVideoAdapter` :
```
test_null_adapter_returns_video_clip_result
test_null_adapter_is_deterministic
test_null_adapter_shot_id_preserved
```

---

## VG-03 ✅ FAIT (2026-04-21 à 15:11) — `RunwayAdapter` + `KlingAdapter` (prod, exclus CI)

**RunwayAdapter** : Runway Gen-3 Alpha Turbo image-to-video  
Env var : `RUNWAY_API_TOKEN`

**KlingAdapter** : Kling v1.5 image-to-video  
Env var : `KLING_API_KEY` + `KLING_API_SECRET`

Exclusion mypy :
```toml
"aiprod_adaptation/video_gen/runway_adapter\\.py",
"aiprod_adaptation/video_gen/kling_adapter\\.py",
```

---

## VG-04 ✅ FAIT (2026-04-21 à 15:11) — `VideoSequencer`

**Fichier** : `aiprod_adaptation/video_gen/video_sequencer.py`

Prend `StoryboardOutput` + `AIPRODOutput` (pour `duration_sec`).
Gère les erreurs sans crasher (même pattern que `StoryboardGenerator`).

```python
class VideoSequencer:
    def build_requests(self, storyboard, output) -> List[VideoRequest]: ...
    def generate(self, storyboard, output) -> VideoOutput: ...
```

**Tests** — `TestVideoSequencer` :
```
test_sequencer_generates_one_clip_per_shot
test_sequencer_is_deterministic
test_sequencer_title_preserved
test_sequencer_generated_count_correct
test_sequencer_build_requests_count
test_sequencer_error_does_not_crash
```

---

## VG-05 ✅ FAIT (2026-04-21 à 15:11) — `run_pipeline_with_video()` dans `engine.py`

Nouvelle fonction (pas de breaking change) :

```python
def run_pipeline_with_video(
    text, title, episode_id="EP01",
    llm=None, character_descriptions=None,
    image_adapter=None, image_base_seed=None,
    video_adapter=None,
) -> tuple[AIPRODOutput, StoryboardOutput | None, VideoOutput | None]:
    output, storyboard = run_pipeline_with_images(...)
    video: VideoOutput | None = None
    if video_adapter is not None and storyboard is not None:
        video = VideoSequencer(video_adapter).generate(storyboard, output)
    return output, storyboard, video
```

**Tests** — `TestRunPipelineWithVideo` :
```
test_run_with_video_null_adapters         # NullImage + NullVideo → video non None
test_run_with_video_no_video_adapter      # video_adapter=None → video is None
test_run_with_video_no_image_adapter      # image_adapter=None → storyboard None, video None
```

---

## VG-06 ✅ FAIT (2026-04-21 à 15:11) — `__init__.py` exports

```python
from aiprod_adaptation.video_gen.video_adapter import VideoAdapter, NullVideoAdapter
from aiprod_adaptation.video_gen.video_request import VideoRequest, VideoClipResult, VideoOutput
from aiprod_adaptation.video_gen.video_sequencer import VideoSequencer
__all__ = [...]
```

---

## Validation finale

```bash
ruff check aiprod_adaptation/
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/image_gen/ aiprod_adaptation/video_gen/ --strict
pytest aiprod_adaptation/tests/ -v --tb=short -m "not integration"
```

Cibles : 108+ tests · ruff 0 · mypy strict 0 · `run_pipeline()` inchangé
