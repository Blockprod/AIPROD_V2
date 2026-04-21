---
title: Plan d'action — Pipeline Quality v1
source: analyse_technique_p3_p4_p5_2026-04-21
creation: 2026-04-21 à 15:54
last_updated: 2026-04-21 à 15:54
status: active
phase: PQ (Post-P5)
prerequis: post_production_v1_plan.md complété (2026-04-21) — 124/124 tests
tests_avant: 124
tests_apres_cible: 148+
---

# PLAN D'ACTION — PIPELINE QUALITY v1 — 2026-04-21

**Étapes totales** : 6

| ID | Priorité | Gap | Phase | Fichier(s) impactés |
|---|---|---|---|---|
| PQ-01 | 🔴 Critique | Cohérence inter-shots (même personnage) | P3 | `image_gen/` |
| PQ-02 | 🔴 Critique | Sync audio/vidéo réelle (durée TTS ≠ duration_hint) | P5 | `post_prod/` |
| PQ-03 | 🟡 Important | last_frame chaining entre shots consécutifs | P4 | `video_gen/` |
| PQ-04 | 🟡 Important | Router intelligent (Runway vs Kling selon duration) | P4 | `video_gen/` |
| PQ-05 | 🟢 Nice-to-have | SSML pour contrôle du rythme vocal (pauses dramatiques) | P5 | `post_prod/` |
| PQ-06 | 🟢 Nice-to-have | FFmpegExporter comme 6ème composant P5 | P5 | `post_prod/` |

---

## PQ-01 ⏳ — Cohérence inter-shots (même personnage) — P3

### Problème
`StoryboardGenerator` génère chaque image indépendamment. Un personnage peut changer
de visage, de vêtements ou de morphologie entre le shot 1 et le shot 8 d'une même scène.

### Solution : `CharacterConsistencyMixin` + `base_image_url` dans `ImageRequest`

**Nouveau champ dans `ImageRequest` :**
```python
class ImageRequest(BaseModel):
    ...
    reference_image_url: str = ""   # URL d'une image de référence du personnage (IP-Adapter)
```

**Nouveau composant : `CharacterImageRegistry`**
```python
class CharacterImageRegistry:
    """Conserve la première image générée pour chaque personnage connu."""

    def __init__(self) -> None:
        self._registry: dict[str, str] = {}   # character_name → image_url

    def register(self, character: str, image_url: str) -> None:
        if character not in self._registry:
            self._registry[character] = image_url

    def get_reference(self, character: str) -> str:
        return self._registry.get(character, "")
```

**Intégration dans `StoryboardGenerator.build_requests()` :**
```python
# Pour chaque shot :
# 1. Identifier le personnage principal (scene.characters[0] si présent)
# 2. Consulter CharacterImageRegistry
# 3. Si référence disponible → passer en reference_image_url
# 4. Après génération → enregistrer la première image du personnage
```

**Fichiers à modifier :**
- `aiprod_adaptation/image_gen/image_request.py` — ajouter `reference_image_url: str = ""`
- `aiprod_adaptation/image_gen/storyboard.py` — intégrer `CharacterImageRegistry`

**Fichier à créer :**
- `aiprod_adaptation/image_gen/character_image_registry.py`

**Tests à ajouter** (`test_image_gen.py` → `TestCharacterImageRegistry`) :
```
test_registry_stores_first_image_for_character
test_registry_does_not_overwrite_existing_character
test_registry_returns_empty_for_unknown_character
test_storyboard_passes_reference_to_second_shot_same_character
```

---

## PQ-02 ⏳ — Sync audio/vidéo réelle (durée TTS ≠ duration_hint) — P5

### Problème
`AudioSynchronizer` construit la timeline avec `duration_hint_sec` (valeur du shot, ex: 4s).
La TTS ElevenLabs peut produire un audio de 6.3s. Le clip vidéo de 4s et l'audio de 6.3s
seront désynchronisés en export.

### Solution : `audio_duration_sec` réel dans `AudioResult` + recalcul timeline

**Champ à utiliser :** `AudioResult.duration_sec` doit refléter la durée **réelle** de l'audio
produit, pas `duration_hint_sec`.

**Nouveau utilitaire : `audio_duration_from_b64()`**
```python
def audio_duration_from_b64(audio_b64: str, mime: str = "audio/mpeg") -> int:
    """Décode le b64, parse les frames MP3, retourne la durée en secondes arrondie."""
    import base64, math
    from mutagen.mp3 import MP3
    from io import BytesIO
    raw = base64.b64decode(audio_b64)
    duration_f = MP3(BytesIO(raw)).info.length
    return max(1, math.ceil(duration_f))
```

**Intégration dans `AudioSynchronizer.generate()` :**
```python
# Après génération de chaque AudioResult :
# - Si audio_b64 non vide → calculer duration_sec réelle via audio_duration_from_b64()
# - Mettre à jour result.duration_sec avant de construire la timeline
# - start_sec cumulatif calculé sur les durées réelles
```

**Règle de sync vidéo/audio :**
```
Si duration_audio > duration_video  → noter le delta dans TimelineClip.metadata (pour FFmpeg -t)
Si duration_audio < duration_video  → padding silence (silence_padding_sec = duration_video - duration_audio)
```

**Nouveau champ dans `TimelineClip` :**
```python
class TimelineClip(BaseModel):
    ...
    audio_duration_sec: int = 0    # durée réelle de l'audio (0 = non mesuré)
    silence_padding_sec: int = 0   # silence à ajouter si audio < vidéo
```

**Fichiers à modifier :**
- `aiprod_adaptation/post_prod/audio_request.py` — ajouter `audio_duration_sec` + `silence_padding_sec` à `TimelineClip`
- `aiprod_adaptation/post_prod/audio_synchronizer.py` — intégrer `audio_duration_from_b64()` + recalcul

**Fichier à créer :**
- `aiprod_adaptation/post_prod/audio_utils.py` — `audio_duration_from_b64()` (facultatif si mutagen absent → fallback sur `duration_hint_sec`)

**Dépendance optionnelle :** `mutagen` (graceful fallback si absent)

**Tests à ajouter** (`test_post_prod.py` → `TestAudioDurationSync`) :
```
test_timeline_clip_has_audio_duration_field
test_timeline_clip_silence_padding_when_audio_shorter
test_synchronizer_uses_real_duration_when_available
test_audio_utils_fallback_without_mutagen
```

---

## PQ-03 ⏳ — last_frame chaining entre shots consécutifs — P4

### Problème
Chaque `VideoRequest` est généré depuis l'image fixe du storyboard. Entre le shot N et le
shot N+1, il y a une rupture visuelle (lumière, position personnage, angle).

### Solution : `last_frame_url` dans `VideoRequest` + `VideoClipResult`

**Nouveau champ dans `VideoClipResult` :**
```python
class VideoClipResult(BaseModel):
    ...
    last_frame_url: str = ""   # URL de la dernière frame du clip (fournie par le modèle ou extraite)
```

**Nouveau champ dans `VideoRequest` :**
```python
class VideoRequest(BaseModel):
    ...
    last_frame_hint_url: str = ""  # last_frame du clip précédent → passé au modèle pour continuité
```

**Intégration dans `VideoSequencer.build_requests()` :**
```python
# Pour chaque shot à partir du 2ème :
# - Si clips_so_far[i-1].last_frame_url non vide
# - ET shot.scene_id == shot_précédent.scene_id (même scène, pas de coupe)
# → passer en last_frame_hint_url
```

**Condition de chaining :** même `scene_id` seulement — ne pas chaîner entre scènes
différentes (coupe voulue).

**Fichiers à modifier :**
- `aiprod_adaptation/video_gen/video_request.py` — ajouter `last_frame_hint_url` + `last_frame_url`
- `aiprod_adaptation/video_gen/video_sequencer.py` — intégrer le chaining dans `build_requests()` + `generate()`

**Tests à ajouter** (`test_video_gen.py` → `TestLastFrameChaining`) :
```
test_first_shot_has_no_last_frame_hint
test_second_shot_same_scene_gets_last_frame_hint
test_shots_different_scenes_not_chained
test_empty_last_frame_url_does_not_chain
```

---

## PQ-04 ⏳ — Router intelligent (Runway vs Kling selon duration) — P4

### Problème
Runway Gen-3 est optimal pour les shots courts (≤5s) mais limité à 10s.
Kling v2 gère jusqu'à 30s avec meilleur camera control pour les plans larges.
Actuellement, un seul adapter est passé — pas de routing.

### Solution : `SmartVideoRouter`

```python
class SmartVideoRouter(VideoAdapter):
    """
    Route vers runway_adapter si duration_sec <= threshold, sinon vers kling_adapter.
    Threshold configurable (défaut : 5s).
    """

    def __init__(
        self,
        runway_adapter: VideoAdapter,
        kling_adapter: VideoAdapter,
        threshold_sec: int = 5,
    ) -> None:
        self._runway = runway_adapter
        self._kling = kling_adapter
        self._threshold = threshold_sec

    def generate(self, request: VideoRequest) -> VideoClipResult:
        if request.duration_sec <= self._threshold:
            return self._runway.generate(request)
        return self._kling.generate(request)
```

**Fichier à créer :**
- `aiprod_adaptation/video_gen/smart_video_router.py`

**Fichier à modifier :**
- `aiprod_adaptation/video_gen/__init__.py` — exporter `SmartVideoRouter`

**Tests à ajouter** (`test_video_gen.py` → `TestSmartVideoRouter`) :
```
test_router_uses_runway_for_short_shot
test_router_uses_kling_for_long_shot
test_router_threshold_boundary_uses_runway
test_router_threshold_boundary_plus1_uses_kling
test_router_custom_threshold
```

---

## PQ-05 ⏳ — SSML pour contrôle du rythme vocal — P5

### Problème
Les dialogues dramatiques (scènes de tension, révélations) nécessitent des pauses, une
emphase et un débit contrôlé. La TTS plain-text produit une narration monotone.

### Solution : `SSMLBuilder`

```python
class SSMLBuilder:
    """Construit un wrapper SSML adapté à l'émotion du shot."""

    _EMOTION_PARAMS: dict[str, dict[str, str]] = {
        "fear":      {"rate": "slow",   "pitch": "low",    "break_ms": "500"},
        "joy":       {"rate": "medium", "pitch": "high",   "break_ms": "200"},
        "sadness":   {"rate": "slow",   "pitch": "low",    "break_ms": "400"},
        "anger":     {"rate": "fast",   "pitch": "medium", "break_ms": "100"},
        "neutral":   {"rate": "medium", "pitch": "medium", "break_ms": "300"},
        "suspense":  {"rate": "slow",   "pitch": "low",    "break_ms": "700"},
    }

    def build(self, text: str, emotion: str) -> str:
        params = self._EMOTION_PARAMS.get(emotion, self._EMOTION_PARAMS["neutral"])
        return (
            f'<speak>'
            f'<prosody rate="{params["rate"]}" pitch="{params["pitch"]}">'
            f'{text}'
            f'<break time="{params["break_ms"]}ms"/>'
            f'</prosody>'
            f'</speak>'
        )
```

**Intégration dans `AudioSynchronizer.build_requests()` :**
```python
# Si ssml_enabled=True (param du constructeur) :
# → passer SSMLBuilder().build(text, shot.emotion) comme `text` de l'AudioRequest
# Compatibilité : ElevenLabs et Azure TTS supportent SSML ; OpenAI TTS ne le supporte pas
```

**Nouveau champ dans `AudioRequest` :**
```python
class AudioRequest(BaseModel):
    ...
    ssml: bool = False   # True si text contient du SSML (pour les adapters compatibles)
```

**Fichier à créer :**
- `aiprod_adaptation/post_prod/ssml_builder.py`

**Fichiers à modifier :**
- `aiprod_adaptation/post_prod/audio_request.py` — ajouter `ssml: bool = False`
- `aiprod_adaptation/post_prod/audio_synchronizer.py` — paramètre `ssml_enabled`

**Tests à ajouter** (`test_post_prod.py` → `TestSSMLBuilder`) :
```
test_ssml_wraps_text_in_speak_tags
test_ssml_fear_uses_slow_rate
test_ssml_joy_uses_high_pitch
test_ssml_unknown_emotion_falls_back_to_neutral
test_audio_request_ssml_flag_default_false
```

---

## PQ-06 ⏳ — FFmpegExporter comme 6ème composant P5 — P5

### Problème
`ProductionOutput` contient une timeline complète mais aucun code ne produit le fichier
vidéo final. L'export 4K est la dernière étape manquante du pipeline.

### Solution : `FFmpegExporter`

```python
class FFmpegExporter:
    """
    Assemble les clips vidéo + audio de la timeline en un fichier MP4 final.
    Requiert ffmpeg installé et accessible dans le PATH.
    """

    def __init__(
        self,
        output_path: str,
        ffmpeg_bin: str = "ffmpeg",
        loglevel: str = "error",
    ) -> None:
        self._output_path = output_path
        self._ffmpeg_bin = ffmpeg_bin
        self._loglevel = loglevel

    def export(self, production: ProductionOutput) -> str:
        """
        Génère le fichier MP4 final.
        Retourne le chemin absolu du fichier produit.
        """
        # 1. Pour chaque clip : ffmpeg -i video -i audio -shortest → clip_N.mp4
        # 2. Générer filelist.txt pour la concaténation
        # 3. ffmpeg -f concat → output_path (résolution production.resolution, fps production.fps)
        # 4. Retourner output_path
        ...
```

**Fichier à créer :**
- `aiprod_adaptation/post_prod/ffmpeg_exporter.py`

**Fichier à modifier :**
- `aiprod_adaptation/post_prod/__init__.py` — exporter `FFmpegExporter`

**Tests à ajouter** (`test_post_prod.py` → `TestFFmpegExporter`) :
```
test_exporter_builds_correct_command_args   # mock subprocess, vérifier les args
test_exporter_raises_if_ffmpeg_not_found    # FileNotFoundError si bin absent
test_exporter_respects_resolution_from_production
test_exporter_respects_fps_from_production
```

**Note :** `FFmpegExporter` est un composant optionnel — `run_pipeline_full()` ne
l'appelle pas automatiquement. L'appelant doit l'instancier et appeler `.export()` manuellement.

---

## Ordre d'exécution recommandé

```
PQ-01 (P3, critique) → PQ-02 (P5, critique) → PQ-03 (P4) → PQ-04 (P4) → PQ-05 (P5) → PQ-06 (P5)
```

Les étapes PQ-03 et PQ-04 peuvent être parallélisées (même module `video_gen/`, fichiers distincts).
Les étapes PQ-05 et PQ-06 peuvent être parallélisées (même module `post_prod/`, fichiers distincts).

---

## Validation finale

```bash
ruff check aiprod_adaptation/
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ \
     aiprod_adaptation/image_gen/ aiprod_adaptation/video_gen/ aiprod_adaptation/post_prod/ --strict
pytest aiprod_adaptation/tests/ -v --tb=short -m "not integration"
```

Cibles : **148+ tests** · ruff 0 · mypy strict 0

| Étape | +tests | Total cumulé |
|---|---|---|
| PQ-01 | +4 | 128 |
| PQ-02 | +4 | 132 |
| PQ-03 | +4 | 136 |
| PQ-04 | +5 | 141 |
| PQ-05 | +5 | 146 |
| PQ-06 | +4 | 150 |
