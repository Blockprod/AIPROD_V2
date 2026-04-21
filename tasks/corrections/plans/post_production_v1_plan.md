---
title: Plan d'action — Post-production v1
source: plan_global_revise.md
creation: 2026-04-21 à 15:12
last_updated: 2026-04-21 à 15:18
status: completed
phase: P5
corrections_totales: 6 (P1:2 P2:2 P3:2)
prerequis: video_generation_v1_plan.md complété (2026-04-21) — 108/108 tests
tests_avant: 108
tests_apres_cible: 124+
tests_apres_reel: 124
---

# PLAN D'ACTION — POST-PRODUCTION v1 — 2026-04-21

**Étapes totales** : 6 (P1:2 · P2:2 · P3:2)

---

## Contexte

P4 produit un `VideoOutput` : une liste de clips vidéo (un par shot).
P5 ajoute la **piste audio** (voix/narration via TTS) et construit la
**timeline finale** : chaque shot → video_url + audio_url + start_sec.
Résultat : un `ProductionOutput` prêt pour un outil d'export 4K (FFmpeg, DaVinci, Premiere).

---

## Architecture cible

```
VideoOutput + AIPRODOutput (dialogues, durations)
        ↓
[PP-01] AudioRequest + AudioResult + ProductionOutput (modèles)
        ↓
[PP-02] AudioAdapter ABC + NullAudioAdapter
        ↓
[PP-03] ElevenLabsAdapter + OpenAITTSAdapter (prod, exclus CI)
        ↓
[PP-04] AudioSynchronizer — sync audio+video → timeline ordonnée
        ↓
[PP-05] run_pipeline_full() — pipeline complet en 1 appel
[PP-06] __init__.py exports
```

**Fichiers à créer :**
```
aiprod_adaptation/
  post_prod/
    __init__.py
    audio_request.py      ← PP-01
    audio_adapter.py      ← PP-02
    elevenlabs_adapter.py ← PP-03
    openai_tts_adapter.py ← PP-03
    audio_synchronizer.py ← PP-04
  tests/
    test_post_prod.py     ← PP-05/06
```
**Fichier à modifier :** `aiprod_adaptation/core/engine.py` — PP-05

---

## PP-01 ✅ FAIT (2026-04-21 à 15:18) — Modèles de données

```python
class AudioRequest(BaseModel):
    shot_id: str; scene_id: str; text: str
    voice_id: str = "default"; language: str = "en"
    duration_hint_sec: int = 4

class AudioResult(BaseModel):
    shot_id: str; audio_url: str; audio_b64: str = ""
    duration_sec: int; model_used: str; latency_ms: int

class TimelineClip(BaseModel):
    shot_id: str; scene_id: str
    video_url: str; audio_url: str
    duration_sec: int; start_sec: int

class ProductionOutput(BaseModel):
    title: str; timeline: List[TimelineClip]
    total_duration_sec: int
    resolution: str = "3840x2160"  # 4K
    fps: int = 24
```

**Tests** — `TestAudioRequest` :
```
test_audio_request_default_voice_id
test_audio_request_default_language
test_production_output_total_duration_sum
test_timeline_clip_start_sec_cumulative
```

---

## PP-02 ✅ FAIT (2026-04-21 à 15:18) — `AudioAdapter` ABC + `NullAudioAdapter`

```python
class NullAudioAdapter(AudioAdapter):
    MODEL_NAME = "null"
    def generate(self, request: AudioRequest) -> AudioResult:
        return AudioResult(
            shot_id=request.shot_id,
            audio_url=f"null://audio/{request.shot_id}.mp3",
            duration_sec=request.duration_hint_sec,
            model_used=self.MODEL_NAME, latency_ms=0,
        )
```

**Tests** — `TestNullAudioAdapter` :
```
test_null_adapter_returns_audio_result
test_null_adapter_is_deterministic
test_null_adapter_shot_id_preserved
```

---

## PP-03 ✅ FAIT (2026-04-21 à 15:18) — `ElevenLabsAdapter` + `OpenAITTSAdapter` (prod, exclus CI)

**ElevenLabsAdapter** : ElevenLabs TTS API — `ELEVENLABS_API_KEY`
**OpenAITTSAdapter** : OpenAI TTS (`tts-1-hd`) — `OPENAI_API_KEY`

Exclusion mypy :
```toml
"aiprod_adaptation/post_prod/elevenlabs_adapter\\.py",
"aiprod_adaptation/post_prod/openai_tts_adapter\\.py",
```

---

## PP-04 ✅ FAIT (2026-04-21 à 15:18) — `AudioSynchronizer`

Prend `VideoOutput` + `AIPRODOutput` + `AudioAdapter`.
Construit la timeline ordonnée avec `start_sec` cumulatif.
Dialogue présent → `text = dialogue[0]` ; sinon → texte du `prompt`.

```python
class AudioSynchronizer:
    def build_requests(self, video, output) -> List[AudioRequest]: ...
    def generate(self, video, output) -> tuple[List[AudioResult], ProductionOutput]: ...
```

**Tests** — `TestAudioSynchronizer` :
```
test_synchronizer_one_audio_per_shot
test_synchronizer_start_sec_cumulative
test_synchronizer_total_duration_sum
test_synchronizer_is_deterministic
test_synchronizer_title_preserved
test_synchronizer_error_does_not_crash
```

---

## PP-05 ✅ FAIT (2026-04-21 à 15:18) — `run_pipeline_full()` dans `engine.py`

```python
def run_pipeline_full(
    text, title, episode_id="EP01",
    llm=None, character_descriptions=None,
    image_adapter=None, image_base_seed=None,
    video_adapter=None,
    audio_adapter=None,
) -> tuple[AIPRODOutput, StoryboardOutput|None, VideoOutput|None, ProductionOutput|None]:
```

**Tests** — `TestRunPipelineFull` :
```
test_full_pipeline_null_adapters      # tous NullAdapters → ProductionOutput non None
test_full_pipeline_no_audio_adapter   # audio_adapter=None → production is None
test_full_pipeline_output_unchanged   # AIPRODOutput identique sans adapters
```

---

## PP-06 ✅ FAIT (2026-04-21 à 15:18) — `__init__.py` exports

```python
from aiprod_adaptation.post_prod.audio_adapter import AudioAdapter, NullAudioAdapter
from aiprod_adaptation.post_prod.audio_request import AudioRequest, AudioResult, ProductionOutput, TimelineClip
from aiprod_adaptation.post_prod.audio_synchronizer import AudioSynchronizer
__all__ = [...]
```

---

## Validation finale

```bash
ruff check aiprod_adaptation/
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/image_gen/ aiprod_adaptation/video_gen/ aiprod_adaptation/post_prod/ --strict
pytest aiprod_adaptation/tests/ -v --tb=short -m "not integration"
```

Cibles : 124+ tests · ruff 0 · mypy strict 0
