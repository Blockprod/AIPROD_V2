---
title: Plan d'action — Image Generation Connector v1
source: plan_global_revise.md
creation: 2026-04-21 à 15:01
last_updated: 2026-04-21 à 15:01
status: active
phase: P3
corrections_totales: 6 (P1:2 P2:2 P3:2)
prerequis: continuity_engine_v1_plan.md complété (2026-04-21) — 76/76 tests
tests_avant: 76
tests_apres_cible: 96+
---

# PLAN D'ACTION — IMAGE GENERATION CONNECTOR v1 — 2026-04-21

**Généré le** : 2026-04-21 à 15:01
**Étapes totales** : 6 (P1:2 · P2:2 · P3:2)

---

## Contexte

Le pipeline AIPROD_V2 produit actuellement des `Shot` objects avec :
- `shot.prompt` — texte visuel enrichi (après Continuity Engine)
- `shot.shot_type` — `wide | medium | close_up | pov`
- `shot.camera_movement` — `static | follow | pan`
- `shot.emotion` — état émotionnel de la scène

Ces données sont la **matière première exacte** pour un modèle de génération d'image.
Objectif P3 : brancher un connector image sur cette sortie pour produire un **storyboard**.

### Modèles cibles

| Modèle | API | Avantage | Mode CI |
|---|---|---|---|
| **Flux.1** (Black Forest Labs) | REST JSON | Open source, gratuit en local | NullImageAdapter |
| **Midjourney** | Discord bot / API tierce | Qualité cinématique | NullImageAdapter |
| **Replicate** | REST JSON | Héberge Flux + SDXL + autres | NullImageAdapter |

**Choix d'architecture** : même pattern que `LLMAdapter` —
`ImageAdapter` (ABC) → `NullImageAdapter` (CI) + `FluxAdapter` / `ReplicateAdapter` (prod).

---

## Architecture cible

```
AIPRODOutput (shots enrichis par Continuity Engine)
        ↓
[IG-01] ImageRequest — modèle de données de requête image
        ↓
[IG-02] ImageAdapter (ABC) + NullImageAdapter (CI)
        ↓
[IG-03] FluxAdapter + ReplicateAdapter (prod, exclus CI)
        ↓
[IG-04] StoryboardGenerator — orchestre les N appels shot→image
        ↓
[IG-05] StoryboardOutput — modèle de données de résultat
        ↓
[IG-06] Tests + wiring engine.py (flag enable_image_gen)
```

**Fichiers à créer :**

```
aiprod_adaptation/
  image_gen/
    __init__.py
    image_request.py      ← IG-01 : ImageRequest (Pydantic)
    image_adapter.py      ← IG-02 : ImageAdapter ABC + NullImageAdapter
    flux_adapter.py       ← IG-03 : FluxAdapter (exclu CI)
    replicate_adapter.py  ← IG-03 : ReplicateAdapter (exclu CI)
    storyboard.py         ← IG-04+05 : StoryboardGenerator + StoryboardOutput
  tests/
    test_image_gen.py     ← IG-06
```

**Fichier à modifier :**
- `aiprod_adaptation/core/engine.py` — IG-06 (flag `enable_image_gen`)

---

## Modèle de données

```python
# image_request.py
class ImageRequest(BaseModel):
    shot_id:         str
    scene_id:        str
    prompt:          str          # shot.prompt enrichi (Continuity Engine output)
    negative_prompt: str = ""
    width:           int = 1024
    height:          int = 576    # 16:9 cinématique
    num_steps:       int = 28
    guidance_scale:  float = 7.5
    seed:            int | None = None

class ImageResult(BaseModel):
    shot_id:    str
    image_url:  str   # URL signée (Replicate/Flux cloud) ou path local
    image_b64:  str = ""   # base64 si retourné directement
    model_used: str
    latency_ms: int

class StoryboardOutput(BaseModel):
    title:    str
    images:   List[ImageResult]
    total_shots: int
    generated: int   # nombre d'images réellement générées (≠ total si erreurs)
```

---

## Corrections P1 — CRITIQUE (Fondation)

---

### [IG-01] ⏳ — `ImageRequest` + `ImageResult` + `StoryboardOutput`

**Priorité** : P1
**Sévérité** : 🔴
**Fichier à créer** : `aiprod_adaptation/image_gen/image_request.py`

**Problème** : Pas de contrat de données entre pipeline et modèle image.
Chaque adapter doit recevoir un objet normalisé — pas un `Shot` brut.

**Action** :

```python
from __future__ import annotations

from pydantic import BaseModel, field_validator
from typing import List, Optional

_ASPECT_RATIOS: frozenset[tuple[int, int]] = frozenset({
    (1024, 576),   # 16:9 cinématique (défaut)
    (1024, 1024),  # carré
    (576, 1024),   # portrait
})

class ImageRequest(BaseModel):
    shot_id:         str
    scene_id:        str
    prompt:          str
    negative_prompt: str   = "blurry, low quality, watermark, text, oversaturated"
    width:           int   = 1024
    height:          int   = 576
    num_steps:       int   = 28
    guidance_scale:  float = 7.5
    seed:            Optional[int] = None

    @field_validator("num_steps")
    @classmethod
    def validate_steps(cls, v: int) -> int:
        if not (1 <= v <= 150):
            raise ValueError(f"num_steps must be between 1 and 150, got {v}")
        return v

    @field_validator("guidance_scale")
    @classmethod
    def validate_guidance(cls, v: float) -> float:
        if not (1.0 <= v <= 30.0):
            raise ValueError(f"guidance_scale must be between 1.0 and 30.0, got {v}")
        return v


class ImageResult(BaseModel):
    shot_id:    str
    image_url:  str
    image_b64:  str = ""
    model_used: str
    latency_ms: int


class StoryboardOutput(BaseModel):
    title:       str
    images:      List[ImageResult]
    total_shots: int
    generated:   int   # ≤ total_shots (erreurs possibles)
```

**Règle** : `negative_prompt` a une valeur par défaut sécurisée (qualité + no watermark).
`seed=None` → aléatoire (prod) ; `seed=42` → déterministe (tests).

**Tests** (dans `test_image_gen.py`) — classe `TestImageRequest` :
```python
test_image_request_default_values            # width=1024, height=576, steps=28
test_image_request_invalid_steps_raises      # num_steps=0 → ValueError
test_image_request_invalid_guidance_raises   # guidance_scale=0.5 → ValueError
test_storyboard_output_generated_count       # generated <= total_shots
```

**Risque** : Nul — nouveau fichier, pas branché.
**Validation** : 76 + 4 = 80 tests verts.

---

### [IG-02] ⏳ — `ImageAdapter` ABC + `NullImageAdapter`

**Priorité** : P1
**Sévérité** : 🔴
**Fichier à créer** : `aiprod_adaptation/image_gen/image_adapter.py`

**Problème** : Sans interface abstraite, les tests CI dépendraient d'une API externe.
Pattern identique à `LLMAdapter` / `NullLLMAdapter`.

**Action** :

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult


class ImageAdapter(ABC):
    @abstractmethod
    def generate(self, request: ImageRequest) -> ImageResult:
        """Generate a single image from a request. Raises on hard failure."""
        ...


class NullImageAdapter(ImageAdapter):
    """Deterministic stub for CI — returns a placeholder result instantly."""

    MODEL_NAME: str = "null"

    def generate(self, request: ImageRequest) -> ImageResult:
        return ImageResult(
            shot_id=request.shot_id,
            image_url=f"null://storyboard/{request.shot_id}.png",
            image_b64="",
            model_used=self.MODEL_NAME,
            latency_ms=0,
        )
```

**Tests** (dans `test_image_gen.py`) — classe `TestNullImageAdapter` :
```python
test_null_adapter_returns_image_result       # isinstance(result, ImageResult)
test_null_adapter_is_deterministic           # 2 appels identiques → même URL
test_null_adapter_shot_id_preserved          # result.shot_id == request.shot_id
```

**Risque** : Nul.
**Validation** : 80 + 3 = 83 tests verts.

---

## Corrections P2 — IMPORTANT

---

### [IG-03] ⏳ — `FluxAdapter` + `ReplicateAdapter` (prod, exclus CI)

**Priorité** : P2
**Sévérité** : 🟠
**Fichiers à créer** :
- `aiprod_adaptation/image_gen/flux_adapter.py`
- `aiprod_adaptation/image_gen/replicate_adapter.py`

**Problème** : Connexion réelle aux APIs de génération image.

**FluxAdapter** (API locale ou Flux.1-dev via HTTP) :
```python
# Variable d'env : FLUX_API_URL (défaut: http://localhost:7860)
# Format API : compatible ComfyUI / A1111 REST
class FluxAdapter(ImageAdapter):
    def __init__(self, api_url: str | None = None) -> None:
        import os
        self._url = api_url or os.environ.get("FLUX_API_URL", "http://localhost:7860")

    def generate(self, request: ImageRequest) -> ImageResult:
        import time, requests  # type: ignore[import-untyped]
        t0 = time.monotonic()
        payload = {
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "width": request.width,
            "height": request.height,
            "num_inference_steps": request.num_steps,
            "guidance_scale": request.guidance_scale,
            "seed": request.seed if request.seed is not None else -1,
        }
        resp = requests.post(f"{self._url}/sdapi/v1/txt2img", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        latency = int((time.monotonic() - t0) * 1000)
        return ImageResult(
            shot_id=request.shot_id,
            image_url="",
            image_b64=data["images"][0],
            model_used="flux.1",
            latency_ms=latency,
        )
```

**ReplicateAdapter** (Replicate.com — Flux.1-schnell ou SDXL) :
```python
# Variable d'env : REPLICATE_API_TOKEN
# Modèle : black-forest-labs/flux-schnell (gratuit 50 req/jour)
class ReplicateAdapter(ImageAdapter):
    MODEL: str = "black-forest-labs/flux-schnell"

    def __init__(self, api_token: str | None = None) -> None:
        import os
        self._token = api_token or os.environ.get("REPLICATE_API_TOKEN", "")

    def generate(self, request: ImageRequest) -> ImageResult:
        import time, replicate as _replicate  # type: ignore[import-untyped]
        t0 = time.monotonic()
        output = _replicate.run(
            self.MODEL,
            input={
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "width": request.width,
                "height": request.height,
                "num_inference_steps": request.num_steps,
                "guidance": request.guidance_scale,
                "seed": request.seed,
                "output_format": "webp",
            },
        )
        latency = int((time.monotonic() - t0) * 1000)
        return ImageResult(
            shot_id=request.shot_id,
            image_url=str(output[0]),
            image_b64="",
            model_used=self.MODEL,
            latency_ms=latency,
        )
```

**Exclusion CI** : les deux adapters sont exclus de mypy.
```toml
# pyproject.toml — à ajouter
[tool.mypy]
exclude = [
    "aiprod_adaptation/core/adaptation/claude_adapter\\.py",
    "aiprod_adaptation/image_gen/flux_adapter\\.py",
    "aiprod_adaptation/image_gen/replicate_adapter\\.py",
]
```

**Tests** : pas de tests CI (adapters marqués `@pytest.mark.integration`).
**Risque** : Faible — isolés, pas de régression.

---

### [IG-04] ⏳ — `StoryboardGenerator`

**Priorité** : P2
**Sévérité** : 🟠
**Fichier à créer** : `aiprod_adaptation/image_gen/storyboard.py`

**Problème** : Besoin d'un orchestrateur qui :
1. Convertit `AIPRODOutput.shots` → `List[ImageRequest]`
2. Appelle `adapter.generate()` pour chaque shot
3. Collecte les résultats + gère les erreurs sans crasher
4. Retourne `StoryboardOutput`

**Action** :

```python
import time
from typing import List

from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import (
    ImageRequest, ImageResult, StoryboardOutput
)
from aiprod_adaptation.models.schema import AIPRODOutput, Shot


class StoryboardGenerator:
    def __init__(self, adapter: ImageAdapter, base_seed: int | None = None) -> None:
        self._adapter = adapter
        self._base_seed = base_seed  # None → aléatoire ; int → déterministe (tests)

    def generate(self, output: AIPRODOutput) -> StoryboardOutput:
        all_shots: List[Shot] = [
            shot for ep in output.episodes for shot in ep.shots
        ]
        results: List[ImageResult] = []

        for i, shot in enumerate(all_shots):
            seed = self._base_seed + i if self._base_seed is not None else None
            request = ImageRequest(
                shot_id=shot.shot_id,
                scene_id=shot.scene_id,
                prompt=shot.prompt,
                seed=seed,
            )
            try:
                result = self._adapter.generate(request)
                results.append(result)
            except Exception:
                # Ne pas crasher — continuer les autres shots
                results.append(ImageResult(
                    shot_id=shot.shot_id,
                    image_url="error://generation-failed",
                    image_b64="",
                    model_used="error",
                    latency_ms=0,
                ))

        return StoryboardOutput(
            title=output.title,
            images=results,
            total_shots=len(all_shots),
            generated=sum(1 for r in results if r.model_used != "error"),
        )

    def build_requests(self, output: AIPRODOutput) -> List[ImageRequest]:
        """Build requests without generating — useful for inspection/tests."""
        return [
            ImageRequest(
                shot_id=shot.shot_id,
                scene_id=shot.scene_id,
                prompt=shot.prompt,
                seed=self._base_seed + i if self._base_seed is not None else None,
            )
            for i, shot in enumerate(
                shot for ep in output.episodes for shot in ep.shots
            )
        ]
```

**Tests** (dans `test_image_gen.py`) — classe `TestStoryboardGenerator` :
```python
test_storyboard_generates_one_result_per_shot   # N shots → N ImageResult
test_storyboard_is_deterministic                # base_seed=42 → identique 2x
test_storyboard_title_preserved                 # output.title → storyboard.title
test_storyboard_generated_count_correct         # NullAdapter → generated == total_shots
test_storyboard_build_requests_count            # N shots → N ImageRequest
test_storyboard_error_in_adapter_does_not_crash # adapter raise → result.model_used == "error"
```

**Risque** : Faible.
**Validation** : 83 + 6 = 89 tests verts.

---

## Corrections P3 — MINEUR

---

### [IG-05] ⏳ — Wiring `engine.py` (flag `enable_image_gen`)

**Priorité** : P3
**Sévérité** : 🟡
**Fichier à modifier** : `aiprod_adaptation/core/engine.py`

**Problème** : Exposer la génération image directement depuis `run_pipeline()`
comme option avancée (opt-in, identique au pattern Continuity Engine).

**Action** :

```python
def run_pipeline(
    text: str,
    title: str,
    episode_id: str = "EP01",
    llm: "LLMAdapter | None" = None,
    character_descriptions: "dict[str, str] | None" = None,
    image_adapter: "ImageAdapter | None" = None,   # ← nouveau
    image_base_seed: "int | None" = None,           # ← nouveau
) -> "tuple[AIPRODOutput, StoryboardOutput | None]":
    ...
    storyboard: StoryboardOutput | None = None
    if image_adapter is not None:
        from aiprod_adaptation.image_gen.storyboard import StoryboardGenerator
        storyboard = StoryboardGenerator(
            adapter=image_adapter,
            base_seed=image_base_seed,
        ).generate(output)

    return output, storyboard
```

⚠️ **Breaking change minimal** : le type de retour passe de `AIPRODOutput` à
`tuple[AIPRODOutput, StoryboardOutput | None]`. Les callers existants devront unpacker :
`output, _ = run_pipeline(...)`.

→ Alternative plus safe : garder `run_pipeline` inchangé + créer `run_pipeline_with_images()`.

**Choix recommandé** : nouvelle fonction `run_pipeline_with_images()` — zéro régression.

```python
def run_pipeline_with_images(
    text: str,
    title: str,
    episode_id: str = "EP01",
    llm: "LLMAdapter | None" = None,
    character_descriptions: "dict[str, str] | None" = None,
    image_adapter: "ImageAdapter | None" = None,
    image_base_seed: "int | None" = None,
) -> "tuple[AIPRODOutput, StoryboardOutput | None]":
    output = run_pipeline(text, title, episode_id, llm, character_descriptions)
    storyboard: StoryboardOutput | None = None
    if image_adapter is not None:
        from aiprod_adaptation.image_gen.storyboard import StoryboardGenerator
        storyboard = StoryboardGenerator(
            adapter=image_adapter,
            base_seed=image_base_seed,
        ).generate(output)
    return output, storyboard
```

**Avantage** : `run_pipeline()` inchangé → 76 tests existants inchangés.

**Tests** (dans `test_image_gen.py`) — classe `TestRunPipelineWithImages` :
```python
test_run_pipeline_with_images_null_adapter       # NullImageAdapter → storyboard non None
test_run_pipeline_with_images_no_adapter         # adapter=None → storyboard is None
test_run_pipeline_output_unchanged               # output identique avec ou sans image_adapter
```

**Risque** : Nul — nouvelle fonction.
**Validation** : 89 + 3 = 92 tests verts.

---

### [IG-06] ⏳ — `__init__.py` + exports publics `image_gen`

**Priorité** : P3
**Sévérité** : 🟡
**Fichier à créer** : `aiprod_adaptation/image_gen/__init__.py`

**Action** :

```python
from aiprod_adaptation.image_gen.image_adapter import ImageAdapter, NullImageAdapter
from aiprod_adaptation.image_gen.image_request import (
    ImageRequest, ImageResult, StoryboardOutput
)
from aiprod_adaptation.image_gen.storyboard import StoryboardGenerator

__all__ = [
    "ImageAdapter",
    "NullImageAdapter",
    "ImageRequest",
    "ImageResult",
    "StoryboardOutput",
    "StoryboardGenerator",
]
```

**Risque** : Nul.

---

## Ordre d'exécution recommandé

```
IG-01  ImageRequest + ImageResult + StoryboardOutput   → modèles de données
  ↓
IG-02  ImageAdapter ABC + NullImageAdapter             → interface + stub CI
  ↓
IG-03  FluxAdapter + ReplicateAdapter                  → adapters prod (exclu mypy/CI)
  ↓
IG-04  StoryboardGenerator                             → orchestrateur
  ↓
IG-05  run_pipeline_with_images() dans engine.py       → wiring
  ↓
IG-06  __init__.py exports                             → clôture le module
```

---

## Variables d'environnement requises (prod uniquement)

| Variable | Adapter | Défaut | Usage |
|---|---|---|---|
| `FLUX_API_URL` | `FluxAdapter` | `http://localhost:7860` | URL du serveur local Flux/A1111 |
| `REPLICATE_API_TOKEN` | `ReplicateAdapter` | `""` | Token Replicate.com |

---

## Ce qui n'est PAS dans ce plan (hors scope — Image Gen v2)

| Exclu | Raison | Plan futur |
|---|---|---|
| Midjourney adapter | API non officielle / bot Discord — instable | Image Gen v2 |
| DALL-E 3 adapter | OpenAI — format différent | Image Gen v2 |
| Upload S3 / CDN | Stockage — hors scope pipeline | Image Gen v2 |
| Retry + rate limiting | Robustesse prod | Image Gen v2 |
| Prompt style injection (cinematic, 4K) | Template de prompt avancé | Image Gen v2 |
| Batch async generation | Performance | Image Gen v2 |

---

## Validation finale

```bash
venv\Scripts\Activate.ps1

ruff check aiprod_adaptation/

mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/image_gen/ --strict

pytest aiprod_adaptation/tests/ -v --tb=short -m "not integration"
```

Cibles après exécution complète :
- [ ] 92+ tests pytest verts (76 + 16 nouveaux IG-01 à IG-05)
- [ ] ruff 0 erreurs
- [ ] mypy strict 0 erreurs (FluxAdapter + ReplicateAdapter exclus)
- [ ] `test_rule_pipeline_byte_identical` vert (inchangé)
- [ ] `test_storyboard_is_deterministic` vert (nouveau)
- [ ] `run_pipeline()` signature inchangée — 76 tests existants non impactés
