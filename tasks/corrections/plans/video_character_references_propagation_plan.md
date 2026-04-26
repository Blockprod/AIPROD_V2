---
title: Cohérence visuelle & qualité vidéo — pipeline end-to-end
creation: 2026-04-26 à 11:30
status: ready
priority: P1
---

# Plan — Cohérence visuelle & qualité vidéo — pipeline end-to-end

## Vue d'ensemble

Ce plan couvre trois phases d'amélioration indépendantes mais complémentaires,
classées par impact/effort croissant.

| Phase | Périmètre | Effort | Impact |
|---|---|---|---|
| **1 — Références & routing** | Propagation ReferencePack→VideoRequest, correction Aleph, last_frame | Faible | Critique |
| **2 — Qualité prompt vidéo** | RunwayPromptFormatter, timestamps, anti-cut, R09 Kontext | Faible | Critique |
| **3 — Backend ComfyUI local** | ComfyUIAdapter, FluxKontext, XLabs IP-Adapter | Moyen | Élevé |

---

# PHASE 1 — Références visuelles & routing Runway

## Diagnostic réel (SDK 4.12.0 inspecté)

**`image_to_video.create` (Gen4_turbo, Gen4.5) — aucun paramètre `references`.**
La signature réelle du SDK ne le supporte pas. Seuls champs disponibles :
`prompt_image`, `prompt_text`, `seed`, `ratio`, `content_moderation`.

**`video_to_video.create` (Gen4_aleph) — HAS `references`**,
mais Aleph est video-to-video : il prend `video_uri` (vidéo source) en entrée
et la transforme. Ce n'est pas un remplacement de `image_to_video`.

**`RunwayAdapter` actuel** : `gen4_aleph` est dans la table de coûts mais
appelle `client.image_to_video.create` — ce qui est incorrect. Aleph utilise
`client.video_to_video.create`.

### État réel des capacités de character lock par modèle

| Modèle | Endpoint SDK | `references` supporté | Usage |
|---|---|---|---|
| `gen4_turbo` | `image_to_video.create` | **NON** | i2v — pas de lock nativement |
| `gen4.5` | `image_to_video.create` | **NON** | i2v — pas de lock nativement |
| `gen4_aleph` | `video_to_video.create` | **OUI** | v2v — transforme une vidéo source |
| `gen3a_turbo` | `image_to_video.create` | **NON** | i2v classique |

---

## Problème réel du pipeline

`ShotStoryboardFrame.reference_image_url` est rempli par `StoryboardGenerator`
mais n'est jamais propagé à `VideoRequest`. Ce gap reste à corriger
indépendamment de la question des `references` Runway.

De plus, `RunwayAdapter` a deux bugs silencieux :
1. `gen4_aleph` appelle `image_to_video.create` → **crash à l'exécution**
   (Aleph n'est pas dans la liste des modèles valides pour ce endpoint).
2. `last_frame_hint_url` est dans `VideoRequest` mais jamais transmis à l'API.

---

## Ce qui est faisable maintenant

### Voie A — `prompt_image` comme liste (continuité first/last frame)

`image_to_video.create` accepte `prompt_image` soit comme URL string
(première frame), soit comme `Iterable[{position, uri}]`.
Gen3aTurbo supporte `position: "first" | "last"` — permet de passer
la dernière frame du clip précédent comme contrainte de sortie.
Gen4_turbo supporte uniquement `position: "first"`.

C'est le seul mécanisme de référence visuelle exposé par l'API pour Gen4_turbo.
Le `last_frame_hint_url` déjà dans `VideoRequest` peut être passé via ce
mécanisme sur Gen3aTurbo.

### Voie B — Corriger `gen4_aleph` dans `RunwayAdapter`

Aleph doit utiliser `client.video_to_video.create` avec :
- `video_uri` : URL de la vidéo source (clip précédent)
- `prompt_text` : description du shot suivant
- `references` : `[{type: "image", uri: "url_perso"}]`

C'est le seul modèle Runway qui supporte nativement le character lock par
référence image + continuité vidéo. C'est une brique haute valeur.

---

## Fichiers touchés — Phase 1

| Fichier | Modification |
|---|---|
| `aiprod_adaptation/video_gen/video_request.py` | Ajouter `character_reference_urls` |
| `aiprod_adaptation/video_gen/video_sequencer.py` | Propager `frame.reference_image_url` |
| `aiprod_adaptation/video_gen/runway_adapter.py` | Corriger Aleph (v2v) + `last_frame_hint_url` |
| `aiprod_adaptation/tests/test_video_sequencer.py` | Tests de non-régression |

---

## Étape P1-1 — `video_request.py` : ajouter le champ

```python
class VideoRequest(BaseModel):
    shot_id: str
    scene_id: str
    image_url: str
    prompt: str
    action: ActionSpec | None = None
    duration_sec: int
    motion_score: float = 5.0
    seed: int | None = None
    last_frame_hint_url: str = ""
    character_reference_urls: list[str] = []  # utilisé par Aleph (v2v) uniquement
```

---

## Étape P1-2 — `video_sequencer.py` : propager depuis `ShotStoryboardFrame`

Dans `build_requests()` :

```python
ref_urls = [frame.reference_image_url] if frame.reference_image_url else []

requests.append(
    VideoRequest(
        shot_id=frame.shot_id,
        scene_id=shot.scene_id,
        image_url=_prompt_image_source(frame.image_url, frame.image_b64),
        prompt=shot.prompt,
        action=shot.action,
        duration_sec=shot.duration_sec,
        seed=self._base_seed + i if self._base_seed is not None else None,
        character_reference_urls=ref_urls,   # ← ajout
    )
)
```

---

## Étape P1-3 — `runway_adapter.py` : corriger les deux bugs silencieux

### 3a — Corriger le routing Aleph

`gen4_aleph` doit appeler `video_to_video.create`, pas `image_to_video.create`.
Scinder `RunwayAdapter.generate()` :

```python
_I2V_MODELS = {"gen4.5", "gen4_turbo", "gen3a_turbo", "veo3", "veo3.1", "veo3.1_fast"}
_V2V_ALEPH_MODELS = {"gen4_aleph"}

def generate(self, request: VideoRequest) -> VideoClipResult:
    if self._model in _V2V_ALEPH_MODELS:
        return self._generate_aleph(request)
    return self._generate_i2v(request)
```

`_generate_aleph()` utilise `client.video_to_video.create` avec :
```python
create_kwargs = {
    "model": "gen4_aleph",
    "video_uri": request.image_url,   # clip précédent comme source
    "prompt_text": request.prompt,
}
if request.character_reference_urls:
    create_kwargs["references"] = [
        {"type": "image", "uri": url}
        for url in request.character_reference_urls if url
    ]
```

### 3b — Transmettre `last_frame_hint_url` pour Gen3aTurbo

Sur Gen3aTurbo, `prompt_image` accepte `[{position: "first", uri: ...}, {position: "last", uri: ...}]`.
Utiliser `last_frame_hint_url` comme contrainte de frame de fin :

```python
# Dans _generate_i2v(), si modèle gen3a_turbo et last_frame_hint_url présent
if self._model == "gen3a_turbo" and request.last_frame_hint_url:
    prompt_image = [
        {"position": "first", "uri": request.image_url},
        {"position": "last", "uri": request.last_frame_hint_url},
    ]
else:
    prompt_image = request.image_url
create_kwargs["prompt_image"] = prompt_image
```

---

## Étape P1-4 — Tests `test_video_sequencer.py`

Trois tests unitaires sans réseau :

**Test 1** — `build_requests` propage `reference_image_url` non vide dans
`character_reference_urls`.

**Test 2** — `build_requests` produit `character_reference_urls == []` quand
`reference_image_url` est vide.

**Test 3** — `RunwayAdapter` avec `model="gen4_aleph"` appelle
`video_to_video.create` (et non `image_to_video.create`) — via monkeypatch
du client.

---

## Ordre d'exécution Phase 1

1. Modifier `video_request.py` (1 ligne).
2. Modifier `video_sequencer.py` (3 lignes dans `build_requests`).
3. Modifier `runway_adapter.py` : routing Aleph + `last_frame_hint_url`.
4. Écrire les 3 tests.
5. `pytest aiprod_adaptation/tests/test_video_sequencer.py -v`
6. `pytest aiprod_adaptation/tests/ -x -q`

---

# PHASE 2 — Qualité prompt vidéo

Cette phase ne crée qu'un seul nouveau fichier (`runway_prompt_formatter.py`)
et modifie `prompt_finalizer.py`. Zéro risque de régression sur les passes
déterministes existantes. Impact immédiat sur la qualité des clips Runway.

## Contexte

`VideoSequencer.build_requests()` passe `shot.prompt` tel quel à Runway.
Ce prompt est une description narrative générée par `pass3_shots.py`, pas une
instruction de mouvement de caméra. Runway i2v est optimisé pour les prompts
de mouvement selon la structure officielle :

```
The camera [motion] as [subject] [action]. [Additional descriptions]
```

`Shot.camera_movement` (`dolly_in`, `whip_pan`, `tracking`, `handheld`…) et
`Shot.shot_type` existent, sont validés — et ne sont **pas utilisés côté vidéo**.

## Étape P2-1 — `video_gen/runway_prompt_formatter.py` (nouveau fichier)

**Table de mapping `camera_movement` → instruction Runway :**

```python
_CAMERA_MOTION_MAP: dict[str, str] = {
    "static":    "The locked-off camera remains perfectly still. Minimal subject motion only.",
    "dolly_in":  "The camera slowly dollies in",
    "dolly_out": "The camera slowly dollies out",
    "tracking":  "A tracking shot follows the subject",
    "pan":       "The camera pans",
    "tilt_up":   "The camera tilts upward",
    "tilt_down": "The camera tilts downward",
    "crane_up":  "A crane shot moves smoothly upward",
    "crane_down":"A crane shot moves smoothly downward",
    "handheld":  "Handheld camera. Natural camera shake.",
    "steadicam": "Smooth steadicam follows the subject",
    "whip_pan":  "Whip pan",
    "rack_focus":"Rack focus",
    "follow":    "The camera follows the subject",
}
```

**Fonction principale :**

```python
def format_runway_prompt(shot: Shot) -> str:
    """
    Transforme shot.prompt (narratif) en prompt motion Runway i2v.
    Structure : [camera motion] as the subject [action]. [narrative]. [anti-cut]
    """
    motion = _CAMERA_MOTION_MAP.get(shot.camera_movement, "The camera moves")
    base = f"{motion} as the subject {shot.prompt}"

    # Timestamps automatiques pour shots longs avec plusieurs action_units
    if shot.action is not None and shot.duration_sec >= 6:
        # Voir Étape P2-2 pour le détail
        base = _inject_timestamps(base, shot)

    # Anti-cut pour shots >= 5s non-transition
    beat = shot.metadata.get("beat_type", "")
    if shot.duration_sec >= 5 and beat != "transition":
        base += " Continuous, seamless shot."

    return base
```

**Intégration dans `VideoSequencer.build_requests()`** :

```python
# Remplacer prompt=shot.prompt par :
from aiprod_adaptation.video_gen.runway_prompt_formatter import format_runway_prompt

# Dans build_requests() :
prompt=format_runway_prompt(shot),
```

## Étape P2-2 — Timestamps automatiques (dans `runway_prompt_formatter.py`)

Pour les shots `duration_sec >= 6` avec plusieurs `action_units` dans la
scène parente, Runway peut traiter des séquences avec timestamps :

```
[00:01] X occurs. [00:04] Y occurs.
```

```python
def _inject_timestamps(base: str, shot: Shot) -> str:
    """
    Si shot.action contient des modifiers (sous-actions), les distribue
    en timestamps sur la durée du shot.
    """
    if shot.action is None or len(shot.action.modifiers) < 2:
        return base
    # Distribuer sur la durée : premier modifier à 1s, dernier au 2/3 de la durée
    mid = max(3, shot.duration_sec * 2 // 3)
    ts_parts = [
        f"[00:01] {shot.action.modifiers[0]}.",
        f"[00:{mid:02d}] {shot.action.modifiers[1]}.",
    ]
    return " ".join(ts_parts)
```

## Étape P2-3 — Règle R09 dans `core/global_coherence/prompt_finalizer.py`

**Source** : Flux Kontext documentation — pattern anti-dérive personnage :
```
"The woman with short black hair while maintaining the same facial features,
 hairstyle, and expression"
```

`prompt_finalizer.py` enrichit déjà les prompts via `R07/R08` (VisualBible).
Quand `ReferencePack` est fourni et que le `subject_id` du shot y existe avec
une `reference_image_url` non vide, aucune clause de préservation n'est injectée.
Résultat : dérive des traits garantie entre shots.

**Règle R09 à ajouter dans `finalize_prompts()`** :

```python
# R09 — Kontext preservation clause
# Condition : subject_id connu dans ReferencePack + reference_image_url présente
if (
    reference_pack is not None
    and shot.action is not None
    and shot.action.subject_id
    and reference_pack.character_reference_url(shot.action.subject_id)
):
    canonical = reference_pack.character_prompt(shot.action.subject_id)
    if canonical and PROMPT_LABEL_CHARACTER not in prompt:
        fragment = (
            f"while maintaining the same facial features, hairstyle, "
            f"and costume of {canonical}"
        )
        additions.append(f"{PROMPT_ENRICHMENT_SEPARATOR}{PROMPT_LABEL_CHARACTER}{fragment}")
```

**Signature de `finalize_prompts()` à étendre** :

```python
# Avant
def finalize_prompts(shots, visual_bible=None)

# Après
def finalize_prompts(shots, visual_bible=None, reference_pack=None)
```

Import à ajouter : `from aiprod_adaptation.image_gen.reference_pack import ReferencePack`
de type `TYPE_CHECKING` uniquement (pas de dépendance circulaire).

## Étape P2-4 — Tests

Fichier : `aiprod_adaptation/tests/test_runway_prompt_formatter.py`

**Test 1** — `format_runway_prompt` sur `camera_movement="dolly_in"` produit
un prompt commençant par `"The camera slowly dollies in"`.

**Test 2** — `format_runway_prompt` sur `camera_movement="static"` inclut
`"perfectly still"` et `"Minimal subject motion only"`.

**Test 3** — `duration_sec=6` et `beat_type != "transition"` → prompt
contient `"Continuous, seamless shot."`.

**Test 4** — `beat_type="transition"` → pas de `"Continuous, seamless shot."`.

**Test 5** — R09 : `finalize_prompts` avec `reference_pack` ayant
`character_reference_url` non vide → fragment `"while maintaining"` injecté.

**Test 6** — R09 : sans `reference_pack` → comportement identique à avant
(aucune régression R07/R08).

## Ordre d'exécution Phase 2

1. Créer `video_gen/runway_prompt_formatter.py` (mapping + `format_runway_prompt` + `_inject_timestamps`).
2. Modifier `video_sequencer.py` : `prompt=format_runway_prompt(shot)` dans `build_requests()`.
3. Modifier `core/global_coherence/prompt_finalizer.py` : ajouter `reference_pack` param + R09.
4. Écrire les 6 tests dans `test_runway_prompt_formatter.py`.
5. `pytest aiprod_adaptation/tests/test_runway_prompt_formatter.py -v`
6. `pytest aiprod_adaptation/tests/ -x -q`

---

# PHASE 3 — Backend ComfyUI local

Cette phase est indépendante des deux précédentes. Elle peut être démarrée
après la Phase 2, ou en parallèle si ComfyUI est disponible.

## Contexte

`FluxAdapter` existant cible A1111 (`POST /sdapi/v1/txt2img`). ComfyUI
utilise une API totalement différente (`POST /prompt` avec un workflow JSON
complet). Les deux cas d'usage requis (Flux Kontext Dev + XLabs Flux
IP-Adapter) partagent le même pattern ComfyUI — un seul adapter de base suffit.

## Étape P3-1 — `image_gen/comfyui_adapter.py` (nouveau fichier)

`ComfyUIAdapter(ImageAdapter)` — adapter de base pour tout workflow ComfyUI.

```python
class ComfyUIAdapter(ImageAdapter):
    """
    Adapter ComfyUI générique. Prend un workflow_template JSON et le
    remplit par substitution de clés nommées avant chaque appel.

    Requires: COMFYUI_API_URL env var (default: http://localhost:8188)
    Excluded from mypy and CI — integration only.
    """

    def __init__(
        self,
        workflow_template: dict,
        api_url: str | None = None,
        poll_interval: float = 1.0,
        timeout: float = 120.0,
    ) -> None:
        self._template = workflow_template
        self._url = api_url or os.environ.get("COMFYUI_API_URL", "http://localhost:8188")
        self._poll_interval = poll_interval
        self._timeout = timeout

    def generate(self, request: ImageRequest) -> ImageResult:
        # 1. Copier le template, substituer prompt/reference/seed
        # 2. POST /prompt → obtenir prompt_id
        # 3. Polling GET /history/{prompt_id} jusqu'à completion
        # 4. Récupérer l'image output → ImageResult
        ...
```

**Points d'implémentation clés** :
- Substitution des nœuds ComfyUI par `node_id` prédéfinis dans le template
  (pas de parsing générique — le template est fourni par le caller).
- Polling `GET /history/{prompt_id}` avec timeout.
- Récupération image via `GET /view?filename=...`.

## Étape P3-2 — `image_gen/flux_kontext_adapter.py` (nouveau fichier)

`FluxKontextAdapter(ComfyUIAdapter)` — frames de référence per-shot.

**Workflow ComfyUI embarqué** (template JSON inline) :
- Nœud `Load Diffusion Model` : `flux1-dev-kontext_fp8_scaled.safetensors`
- Nœud `DualCLIP Load` : `clip_l.safetensors` + `t5xxl_fp8_e4m3fn_scaled.safetensors`
- Nœud `Load VAE` : `ae.safetensors`
- Nœud `Load Image` : `reference_image_url` du personnage (character sheet)
- Nœud `CLIP Text Encode` : prompt enrichi Kontext

**Prompts Kontext à utiliser** (pattern documenté BFL) :
```
"Change the background to [new_location] while keeping the person
 in the exact same position, scale, and pose, preserving facial features"
```

**Intégration dans `StoryboardGenerator`** :

```python
# StoryboardGenerator.__init__() — nouveau param optionnel
kontext_adapter: FluxKontextAdapter | None = None

# Dans generate() — quand reference_pack présent ET reference_url connue :
if self._kontext_adapter and reference_url and location_changed_from_prev_shot:
    kontext_request = ImageRequest(
        shot_id=shot.shot_id,
        scene_id=shot.scene_id,
        prompt=f"Change the background to {location_prompt} while keeping "
               f"the character in the exact same position, preserving facial features.",
        reference_image_url=reference_url,
        seed=seed,
    )
    result = self._kontext_adapter.generate(kontext_request)
```

`location_changed_from_prev_shot` est vrai quand `shot.scene_id` change par
rapport au shot précédent du même personnage.

## Étape P3-3 — Workflow XLabs IP-Adapter (dans `comfyui_adapter.py`)

Le `FluxAdapter` existant active IP-Adapter via le format A1111
(`alwayson_scripts`), qui ne correspond pas à XLabs ComfyUI.

**Template workflow XLabs** à embarquer comme constante dans le module :
```
Flux Load IPAdapter → Apply Flux IPAdapter → KSampler
params : clip_vision_model, ipadapter_model, reference_image
```

Fonction factory :
```python
def make_xlabs_ipadapter_adapter(
    api_url: str | None = None,
    clip_vision_model: str = "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
    ipadapter_model: str = "flux-ip-adapter.safetensors",
) -> ComfyUIAdapter:
    """Retourne un ComfyUIAdapter pré-configuré avec le workflow XLabs."""
    template = _XLABS_IPADAPTER_WORKFLOW_TEMPLATE.copy()
    # Injecter clip_vision_model et ipadapter_model dans les nœuds appropriés
    ...
    return ComfyUIAdapter(workflow_template=template, api_url=api_url)
```

Ce workflow remplace le hack `alwayson_scripts.IP-Adapter` dans `FluxAdapter`
quand `COMFYUI_API_URL` est défini (détection automatique).

## Étape P3-4 — Tests

Fichier : `aiprod_adaptation/tests/test_comfyui_adapter.py`

**Test 1** — `ComfyUIAdapter.generate()` avec un serveur mock (monkeypatch
`requests.post` / `requests.get`) retourne un `ImageResult` valide.

**Test 2** — Polling timeout : si `/history` ne retourne jamais `completed`
avant timeout → `ImageResult` avec `model_used="error"`.

**Test 3** — `FluxKontextAdapter` construit le prompt Kontext correct avec
`"Change the background to [...] while keeping the character"`.

## Ordre d'exécution Phase 3

1. Créer `image_gen/comfyui_adapter.py` (base + polling).
2. Créer `image_gen/flux_kontext_adapter.py` (workflow template embarqué).
3. Ajouter `make_xlabs_ipadapter_adapter()` dans `comfyui_adapter.py`.
4. Modifier `image_gen/storyboard.py` : ajouter `kontext_adapter` param dans `StoryboardGenerator.__init__()`.
5. Écrire les 3 tests.
6. `pytest aiprod_adaptation/tests/test_comfyui_adapter.py -v`
7. `pytest aiprod_adaptation/tests/ -x -q`

---

# Tableau de priorité global

| # | Action | Phase | Fichiers touchés | Effort | Impact |
|---|---|---|---|---|---|
| 1 | `RunwayPromptFormatter` + anti-cut | 2 | `runway_prompt_formatter.py` + `video_sequencer.py` | Faible | **Critique** |
| 2 | Propagation `reference_image_url` | 1 | `video_request.py` + `video_sequencer.py` | Très faible | **Critique** |
| 3 | Routing Aleph `video_to_video` | 1 | `runway_adapter.py` | Faible | **Critique** (fix crash) |
| 4 | `last_frame_hint_url` Gen3aTurbo | 1 | `runway_adapter.py` | Très faible | **Élevé** |
| 5 | Kontext preservation clauses R09 | 2 | `prompt_finalizer.py` | Faible | **Élevé** |
| 6 | Sequential timestamps | 2 | `runway_prompt_formatter.py` | Faible | Moyen |
| 7 | `ComfyUIWorkflowAdapter` | 3 | `comfyui_adapter.py` | Moyen | Élevé (unlocks 8+9) |
| 8 | `FluxKontextAdapter` | 3 | `flux_kontext_adapter.py` | Moyen | **Élevé** |
| 9 | XLabs IP-Adapter workflow | 3 | `comfyui_adapter.py` | Moyen | Moyen |

**Note** : #3 (Aleph) est un crash garanti à l'exécution si `RUNWAY_VIDEO_MODEL=gen4_aleph`
est utilisé. À traiter en priorité absolue avant tout test de production.

---

## Ce que ce plan ne couvre pas

- **Act-Two** : namespace `character_performance` visible dans le SDK —
  endpoint API distinct de `video_to_video`, nécessite un adapter dédié.
  Hors scope ici, à traiter dans un plan séparé.
- **Character lock sur Gen4_turbo/Gen4.5** : impossible nativement via
  l'API SDK 4.12.0. La cohérence passe par la Phase 2 (R09 prompt) +
  Phase 3 (Kontext/XLabs côté image) + Aleph (v2v) pour le lock vidéo.
