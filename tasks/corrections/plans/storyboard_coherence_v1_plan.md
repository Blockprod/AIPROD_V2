---
title: Plan d'action — Storyboard Coherence v1
source: analyse_technique_p3_storyboard_2026-04-21
creation: 2026-04-21 à 17:20
last_updated: 2026-04-21 à 17:36
status: completed
phase: SB (Storyboard — refonte P3)
prerequis: story_engine_v1_plan.md complété (2026-04-21) — 179/179 tests
tests_avant: 179
tests_apres_cible: 210+
tests_apres_reel: 200
---

# PLAN D'ACTION — STORYBOARD COHERENCE v1 — 2026-04-21

**Étapes totales** : 6

| ID | Priorité | Action | Phase | Fichier(s) impactés |
|---|---|---|---|---|
| SB-01 | 🔴 Critique | Injecter `canonical_prompt` du personnage dans le prompt texte | P3 | `image_gen/storyboard.py`, `image_gen/character_image_registry.py` | ✅ FAIT |
| SB-02 | 🔴 Critique | Ajouter `STYLE_TOKEN` global dans `StoryboardGenerator` | P3 | `image_gen/storyboard.py` | ✅ FAIT |
| SB-03 | 🟠 Important | Créer `CharacterSheet` + `CharacterSheetRegistry` + prépass dédiée | P3 | `image_gen/character_sheet.py` (NEW), `image_gen/storyboard.py` | ✅ FAIT |
| SB-04 | 🟠 Important | Faire circuler `reference_image_url` vers les adapters prod (IP-Adapter) | P3 | `image_gen/flux_adapter.py`, `image_gen/replicate_adapter.py` | ✅ FAIT |
| SB-05 | 🟡 Nice-to-have | Enrichir `StoryboardOutput` : `prompt_used`, `seed_used`, champs cinématiques | P3/P4 | `image_gen/image_request.py`, `image_gen/storyboard.py` | ✅ FAIT |
| SB-06 | 🟡 Nice-to-have | Brancher `ImageResult.image_url` → `VideoRequest` comme keyframe img2vid | P4 | `video_gen/video_sequencer.py`, `video_gen/video_request.py` | ✅ FAIT |

---

## État des lieux — ce qui existe déjà (179 tests, commit 0078cf1)

### ✅ Ce qui est en place
- `CharacterImageRegistry` — stocke la **première** image générée par personnage et la passe comme `reference_image_url` aux shots suivants
- `ImageRequest.reference_image_url` — champ présent dans le modèle
- `Shot.metadata["time_of_day_visual"]` — injecté dans le prompt via `f"{shot.prompt} {tod_visual} lighting."` dans `storyboard.py`
- Seed déterministe : `base_seed + shot_index` dans `StoryboardGenerator`
- `last_frame_url` dans `VideoClipResult` — chaînage de continuité inter-shots dans la même scène

### ❌ Ce qui manque / est cassé
- `reference_image_url` est un **champ mort** : ni `FluxAdapter` ni `ReplicateAdapter` ne l'envoient à l'API
- Pas de `canonical_prompt` par personnage — la registry ne stocke qu'une URL d'image
- Pas de `STYLE_TOKEN` global — chaque prompt est indépendant → effet "image IA sans lien"
- `StoryboardOutput` ne conserve ni `prompt_used` ni `seed_used` → non-reproductibilité de fait
- `ImageResult.image_url` n'alimente pas `VideoRequest` comme keyframe de départ (img2vid)
- Aucune prépass "character sheet" — le 1er shot d'un personnage sert de référence non contrôlée

---

## SB-01 ✅ — Injecter `canonical_prompt` du personnage dans le prompt texte

**Problème** : actuellement `CharacterImageRegistry` ne stocke qu'une URL d'image. Le prompt du shot ne contient aucune description du personnage → incohérence visuelle garantie entre plans.

**Solution** : étendre `CharacterImageRegistry` pour stocker un `canonical_prompt` par personnage, et l'injecter dans le prompt du shot.

### Fichiers à modifier
- `image_gen/character_image_registry.py` — ajouter `register_prompt(name, prompt)` + `get_canonical_prompt(name)`
- `image_gen/storyboard.py` — enrichir le prompt avec `canonical_prompt` du personnage principal de la scène

### Contrat attendu
```python
# character_image_registry.py
def register_prompt(self, character: str, canonical_prompt: str) -> None:
    """Store canonical_prompt for character only if not already registered."""

def get_canonical_prompt(self, character: str) -> str:
    """Return canonical_prompt for character, or empty string if unknown."""
```

```python
# storyboard.py — dans generate()
canonical = char_registry.get_canonical_prompt(primary_char)
enriched_prompt = f"{shot.prompt} {tod_visual} lighting. {canonical}".strip()
```

### Tests à écrire (dans `test_image_gen.py`)
- `test_registry_stores_canonical_prompt` — register_prompt + get_canonical_prompt
- `test_registry_canonical_prompt_not_overwritten` — 2e register_prompt ignoré
- `test_storyboard_injects_canonical_prompt_in_prompt` — prompt final contient la description
- `test_storyboard_no_canonical_prompt_does_not_crash` — personnage sans canonical_prompt → pas de crash

---

## SB-02 ⏳ — Ajouter `STYLE_TOKEN` global dans `StoryboardGenerator`

**Problème** : chaque prompt est indépendant → styles visuels hétérogènes entre plans d'une même séquence.

**Solution** : définir un `STYLE_TOKEN` global (configurable à l'instanciation) injecté en fin de chaque prompt.

### Fichiers à modifier
- `image_gen/storyboard.py` — `__init__` accepte `style_token: str = DEFAULT_STYLE_TOKEN`

### Contrat attendu
```python
DEFAULT_STYLE_TOKEN = "cinematic storyboard, 16:9 aspect ratio, film grain, anamorphic lens, color graded"

class StoryboardGenerator:
    def __init__(
        self,
        adapter: ImageAdapter,
        base_seed: int | None = None,
        style_token: str = DEFAULT_STYLE_TOKEN,
    ) -> None: ...

# Dans generate() :
enriched_prompt = f"{shot.prompt} {tod_visual} lighting. {canonical} {self._style_token}".strip()
```

### Tests à écrire
- `test_style_token_default_injected_in_all_prompts` — tous les prompts contiennent le token par défaut
- `test_style_token_custom_overrides_default` — token custom transmis à l'instanciation
- `test_style_token_empty_string_accepted` — style_token="" ne casse pas le pipeline

---

## SB-03 ⏳ — `CharacterSheet` + `CharacterSheetRegistry` + prépass dédiée

**Problème** : le 1er shot d'un personnage sert de référence — mais c'est une image non contrôlée (action aléatoire, mauvais cadrage). La référence devrait être une image canonique générée de façon déterministe.

**Solution** : introduire un `CharacterSheet` (dataclass) + `CharacterSheetRegistry` + une méthode `prepass_character_sheets()` dans `StoryboardGenerator`.

### Fichiers à créer
- `image_gen/character_sheet.py` (NEW)

### Fichiers à modifier
- `image_gen/storyboard.py` — `prepass_character_sheets(characters_map)` + intégration dans `generate()`
- `image_gen/__init__.py` — exposer `CharacterSheet`, `CharacterSheetRegistry`

### Contrat attendu
```python
# image_gen/character_sheet.py
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class CharacterSheet:
    name: str
    canonical_prompt: str           # "tall man, brown coat, short gray hair, 40s, neutral expression, full body"
    seed: int = 42                  # seed fixe pour reproductibilité
    image_url: str = ""             # rempli après génération

class CharacterSheetRegistry:
    def __init__(self) -> None:
        self._sheets: dict[str, CharacterSheet] = {}

    def register(self, sheet: CharacterSheet) -> None:
        if sheet.name not in self._sheets:
            self._sheets[sheet.name] = sheet

    def get(self, name: str) -> CharacterSheet | None:
        return self._sheets.get(name)

    def all_sheets(self) -> list[CharacterSheet]:
        return list(self._sheets.values())
```

```python
# storyboard.py — prépass
def prepass_character_sheets(
    self,
    registry: CharacterSheetRegistry,
) -> CharacterSheetRegistry:
    """Generate one canonical image per character sheet. Idempotent."""
    for sheet in registry.all_sheets():
        if not sheet.image_url:
            req = ImageRequest(
                shot_id=f"CHAR_{sheet.name}",
                scene_id="CHARACTER_SHEET",
                prompt=f"{sheet.canonical_prompt} {self._style_token}",
                seed=sheet.seed,
            )
            try:
                result = self._adapter.generate(req)
                sheet.image_url = result.image_url
            except Exception:
                pass
    return registry
```

### Tests à écrire
- `test_character_sheet_registry_register_and_get` — register + get
- `test_character_sheet_registry_no_overwrite` — 2e register ignoré
- `test_character_sheet_registry_all_sheets_returns_list`
- `test_prepass_generates_one_image_per_sheet` — N sheets → N appels adapter
- `test_prepass_idempotent` — sheet déjà avec image_url → 0 appel adapter
- `test_prepass_error_does_not_crash` — adapter raise → image_url reste ""

---

## SB-04 ⏳ — Faire circuler `reference_image_url` vers les adapters prod

**Problème** : `ImageRequest.reference_image_url` est un champ mort. Ni `FluxAdapter` ni `ReplicateAdapter` ne l'envoient à l'API. La cohérence visuelle via IP-Adapter est inexistante en prod.

**Solution** : transmettre `reference_image_url` dans le payload des adapters prod quand il est non-vide.

### Fichiers à modifier
- `image_gen/flux_adapter.py` — ajouter `"alwayson_scripts": {"IP-Adapter": {"args": [{"image": ref_url, "weight": 0.6}]}}` si `reference_image_url` non vide
- `image_gen/replicate_adapter.py` — ajouter `"image": ref_url` dans le payload si Replicate model le supporte

### Contrat attendu
```python
# flux_adapter.py
if request.reference_image_url:
    payload["alwayson_scripts"] = {
        "IP-Adapter": {
            "args": [{"image": request.reference_image_url, "weight": 0.6, "enabled": True}]
        }
    }
```

> **Note** : les adapters prod sont exclus de mypy et des tests CI. Pas de tests unitaires requis — tests d'intégration uniquement (marqués `@pytest.mark.integration`).

---

## SB-05 ⏳ — Enrichir `StoryboardOutput` avec `prompt_used`, `seed_used`, champs cinématiques

**Problème** : `StoryboardOutput` ne conserve pas le prompt réellement envoyé ni le seed utilisé → impossible de reproduire ou d'auditer une génération.

**Solution** : créer `ShotStoryboardFrame` (remplace `ImageResult` dans `StoryboardOutput`) avec tous les champs cinématiques exploitables par P4/P5.

### Fichiers à modifier
- `image_gen/image_request.py` — ajouter `ShotStoryboardFrame` (nouveau modèle Pydantic)
- `image_gen/storyboard.py` — `generate()` retourne `List[ShotStoryboardFrame]` au lieu de `List[ImageResult]`
- `image_gen/__init__.py` — exposer `ShotStoryboardFrame`

### Contrat attendu
```python
# image_gen/image_request.py
class ShotStoryboardFrame(BaseModel):
    shot_id: str
    scene_id: str
    image_url: str
    image_b64: str = ""
    model_used: str
    latency_ms: int
    prompt_used: str                    # prompt RÉEL après enrichissement
    seed_used: Optional[int]
    shot_type: str
    camera_movement: str
    time_of_day_visual: str
    dominant_sound: str
    characters_in_frame: List[str]
    reference_image_url: str = ""

class StoryboardOutput(BaseModel):
    title: str
    frames: List[ShotStoryboardFrame]   # ancien champ: images
    style_token: str
    total_shots: int
    generated: int
```

### Tests à écrire
- `test_storyboard_frame_has_prompt_used` — prompt_used correspond au prompt enrichi
- `test_storyboard_frame_has_seed_used` — seed_used = base_seed + index
- `test_storyboard_output_has_style_token` — style_token conservé dans output
- `test_storyboard_output_frames_count` — len(frames) == total_shots

---

## SB-06 ⏳ — Brancher `ImageResult.image_url` → `VideoRequest` comme keyframe img2vid

**Problème** : `VideoSequencer` construit les `VideoRequest` à partir de `Shot.prompt` uniquement. L'image storyboard générée n'est pas transmise comme keyframe de départ → le modèle vidéo part de zéro, sans continuité visuelle avec le storyboard.

**Solution** : passer le `StoryboardOutput` en paramètre optionnel de `VideoSequencer.build_requests()` et injecter `image_url` dans `VideoRequest.image_url`.

### Fichiers à modifier
- `video_gen/video_request.py` — ajouter `image_url: str = ""` dans `VideoRequest`
- `video_gen/video_sequencer.py` — `build_requests()` accepte `storyboard: StoryboardOutput | None = None`
- `video_gen/__init__.py` — vérifier les exports

### Contrat attendu
```python
# VideoSequencer.build_requests()
def build_requests(
    self,
    output: AIPRODOutput,
    storyboard: StoryboardOutput | None = None,
) -> List[VideoRequest]:
    frame_map: dict[str, str] = {}
    if storyboard is not None:
        frame_map = {f.shot_id: f.image_url for f in storyboard.frames}
    return [
        VideoRequest(
            shot_id=shot.shot_id,
            scene_id=shot.scene_id,
            prompt=shot.prompt,
            duration_sec=shot.duration_sec,
            image_url=frame_map.get(shot.shot_id, ""),
        )
        for shot in _all_shots(output)
    ]
```

### Tests à écrire
- `test_video_request_has_image_url_field` — champ présent, valeur par défaut ""
- `test_sequencer_without_storyboard_image_url_empty` — sans storyboard, image_url = ""
- `test_sequencer_with_storyboard_injects_image_url` — image_url transmis depuis storyboard
- `test_sequencer_storyboard_partial_match` — shot sans frame correspondant → image_url = ""

---

## Compte de tests attendu

| Fichier | Tests actuels | Nouveaux (SB) | Total |
|---|---|---|---|
| `test_image_gen.py` | 20 | +16 (SB-01: 4, SB-02: 3, SB-03: 6, SB-05: 4) | 36 |
| `test_video_gen.py` | 25 | +4 (SB-06: 4) | 29 |
| **Total** | **179** | **+20** | **199** |

> SB-04 : adapters prod exclus CI — tests d'intégration uniquement, hors comptage.

---

## Ordre d'exécution recommandé

```
SB-01 → SB-02 (atomiques, pas de dépendance)
SB-03 (dépend de SB-01 pour canonical_prompt dans registry)
SB-05 (dépend de SB-01 + SB-02 pour prompt_used enrichi)
SB-04 (adapters prod, indépendant, peut se faire en parallèle)
SB-06 (dépend de SB-05 pour ShotStoryboardFrame.image_url)
```
