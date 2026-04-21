---
title: Plan d'action — Story Engine v1
source: analyse_technique_p1_p2_2026-04-21
creation: 2026-04-21 à 16:30
last_updated: 2026-04-21 à 16:30
status: active
phase: SE (Story Engine — refonte P1/P2)
prerequis: pipeline_quality_v1_plan.md complété (2026-04-21) — 150/150 tests
tests_avant: 150
tests_apres_cible: 180+
---

# PLAN D'ACTION — STORY ENGINE v1 — 2026-04-21

**Étapes totales** : 5

| ID | Priorité | Action | Phase | Fichier(s) impactés |
|---|---|---|---|---|
| SE-01 | 🔴 Critique | Remplacer les 3 appels LLM par 1 appel avec JSON schema strict | P1 | `core/adaptation/` |
| SE-02 | 🔴 Critique | Ajouter `StoryValidator` avec score de filmabilité avant Pass 3 | P1/P2 | `core/adaptation/` |
| SE-03 | 🔴 Critique | Définir `ProductionBudget` + interface `extract_chunk` (point d'extension P6) | P1 | `core/`, `models/` |
| SE-04 | 🟡 Important | Enrichir `VisualScene` avec `pacing`, `time_of_day_visual`, `dominant_sound` | P2 | `models/intermediate.py`, `core/` |
| SE-05 | 🟢 Nice-to-have | Support Gemini 2.5 Pro pour romans longs (> 80K tokens) | P1 | `core/adaptation/` |

---

## SE-01 ⏳ — Remplacer les 3 appels LLM par 1 appel avec JSON schema strict

### Problème

`novel_pipe.py` effectue **3 appels LLM séquentiels** (`extract_scenes` → `make_cinematic` → `to_screenplay`).
Chaque appel introduit latence, coût, et risque de dérive du format.
Les prompts ne contraignent pas structurellement la sortie (pas de JSON schema enforcement).

```python
# Actuel — 3 appels, chaque étape peut produire un JSON malformé
extract_scenes(llm, text)    # Appel 1
make_cinematic(llm, scenes)  # Appel 2 — redondant si prompt bien écrit
to_screenplay(llm, scenes)   # Appel 3 — redondant si schema fourni
```

### Solution : `StoryExtractor` — 1 appel avec tool_use / structured output

**Nouveau composant : `StoryExtractor`**

```python
class StoryExtractor:
    """
    Remplace novel_pipe.py.
    1 seul appel LLM avec JSON schema enforcement.
    Fallback vers rule-based si LLM retourne moins de 2 scènes.
    """

    PRODUCTION_SCHEMA: dict[str, Any] = {
        "type": "object",
        "required": ["scenes"],
        "properties": {
            "scenes": {
                "type": "array",
                "maxItems": 150,
                "items": {
                    "type": "object",
                    "required": ["location", "characters", "actions", "emotion"],
                    "properties": {
                        "location":   {"type": "string", "minLength": 3},
                        "characters": {"type": "array", "maxItems": 2,
                                       "items": {"type": "string"}},
                        "actions":    {"type": "array", "minItems": 1, "maxItems": 6,
                                       "items": {"type": "string", "maxLength": 120}},
                        "dialogues":  {"type": "array", "items": {"type": "string"}},
                        "emotion":    {"enum": ["angry","scared","sad",
                                                "happy","nervous","neutral"]},
                    }
                }
            }
        }
    }

    def extract(
        self,
        llm: LLMAdapter,
        text: str,
        budget: "ProductionBudget",
        prior_summary: str = "",
    ) -> list[VisualScene]:
        """
        1 appel LLM structuré → list[VisualScene].
        prior_summary : résumé des scènes précédentes (vide pour chunk unique, utilisé par P6).
        """
        ...
```

**Prompt système injecté (contraintes de production explicites) :**

```
RÔLE : Tu es un scénariste professionnel qui adapte du texte en screenplay filmable.

CONTRAINTES ABSOLUES :
- Maximum {budget.max_scenes} scènes pour cette séquence
- Chaque action = 1 shot = 3 à 8 secondes de vidéo
- Maximum 2 personnages visibles par scène
- Zéro pensée intérieure, zéro narration — uniquement actions observables
- Chaque action doit être filmable avec une caméra (aucune action imaginaire ou abstraite)
- Maximum 6 actions par scène
- Location = 1 décor concret identifiable (ex: "wooden cabin interior" — pas "somewhere")
- Émotion = 1 valeur parmi : angry, scared, sad, happy, nervous, neutral

CONTEXTE PRÉCÉDENT (si applicable) :
{prior_summary}

RETOURNE uniquement le JSON conforme au schema fourni. Aucun texte autour.
```

**Suppression de `novel_pipe.py`** : les fonctions `extract_scenes`, `make_cinematic`, `to_screenplay` sont obsolètes. Le fichier est conservé avec un `DeprecationWarning` pointant vers `StoryExtractor`.

**Fichiers à créer :**
- `aiprod_adaptation/core/adaptation/story_extractor.py`

**Fichiers à modifier :**
- `aiprod_adaptation/core/adaptation/novel_pipe.py` — ajout `DeprecationWarning`
- `aiprod_adaptation/core/engine.py` — utiliser `StoryExtractor` au lieu de `run_novel_pipe`
- `aiprod_adaptation/core/adaptation/__init__.py` — exporter `StoryExtractor`

**Tests à ajouter** (`test_adaptation.py` → `TestStoryExtractor`) :
```
test_extractor_returns_visual_scenes
test_extractor_single_call_not_three
test_extractor_fallback_on_empty_llm_output
test_extractor_respects_max_scenes_budget
test_extractor_prior_summary_injected_in_prompt
```

---

## SE-02 ⏳ — `StoryValidator` avec score de filmabilité

### Problème

Aucune validation intermédiaire entre la sortie LLM (ou rule-based) et Pass 3.
Des scènes non filmables (pensées intérieures non filtrées, location manquante, actions abstraites)
arrivent jusqu'à `simplify_shots()` et produisent des shots invalides ou des prompts inutilisables
pour les générations image/vidéo.

### Solution : `StoryValidator` entre P1 et P3

**Nouveau composant : `StoryValidator`**

```python
@dataclass
class SceneValidationResult:
    scene_id: str
    is_valid: bool
    score: float           # 0.0 à 1.0
    issues: list[str]      # codes d'erreur détectés

class StoryValidator:
    """
    Valide chaque VisualScene avant Pass 3.
    Score < threshold → scène marquée invalide, exclue ou renvoyée au LLM.
    Entièrement déterministe (zéro LLM).
    """

    INTERNAL_THOUGHT_WORDS = [
        "thought", "wondered", "realized", "remembered",
        "imagined", "believed", "felt", "knew", "hoped",
    ]

    IMPOSSIBLE_ACTION_PATTERNS = [
        "dreamed", "dreamt", "imagined", "fantasized",
        "hallucinated", "envisioned",
    ]

    def validate(self, scene: VisualScene) -> SceneValidationResult:
        issues: list[str] = []

        # Localisation filmable
        if not scene["location"] or scene["location"].lower() == "unknown":
            issues.append("location_missing")

        # Actions filmables
        if not scene["visual_actions"]:
            issues.append("no_filmable_actions")

        for action in scene["visual_actions"]:
            lower = action.lower()
            if any(w in lower for w in self.INTERNAL_THOUGHT_WORDS):
                issues.append(f"internal_thought: {action[:60]}")
            if any(p in lower for p in self.IMPOSSIBLE_ACTION_PATTERNS):
                issues.append(f"impossible_action: {action[:60]}")

        # Personnages (max 2)
        if len(scene["characters"]) > 2:
            issues.append(f"too_many_characters: {len(scene['characters'])}")

        # Émotion valide
        valid_emotions = {"angry", "scared", "sad", "happy", "nervous", "neutral"}
        if scene["emotion"] not in valid_emotions:
            issues.append(f"invalid_emotion: {scene['emotion']}")

        score = max(0.0, 1.0 - len(issues) * 0.25)
        return SceneValidationResult(
            scene_id=scene["scene_id"],
            is_valid=len(issues) == 0,
            score=score,
            issues=issues,
        )

    def validate_all(
        self, scenes: list[VisualScene], threshold: float = 0.5
    ) -> list[VisualScene]:
        """Retourne uniquement les scènes dont le score >= threshold."""
        ...
```

**Intégration dans `engine.py` :**
```python
# Après extraction LLM ou rule-based, avant Pass 3 :
validator = StoryValidator()
scenes = validator.validate_all(scenes, threshold=0.5)
if not scenes:
    raise ValueError("StoryValidator: aucune scène filmable produite.")
```

**Fichiers à créer :**
- `aiprod_adaptation/core/adaptation/story_validator.py`

**Fichiers à modifier :**
- `aiprod_adaptation/core/engine.py` — insérer `StoryValidator` dans le flux principal
- `aiprod_adaptation/core/adaptation/__init__.py` — exporter `StoryValidator`, `SceneValidationResult`

**Tests à ajouter** (`test_adaptation.py` → `TestStoryValidator`) :
```
test_valid_scene_scores_1_0
test_missing_location_detected
test_internal_thought_detected
test_impossible_action_detected
test_too_many_characters_detected
test_invalid_emotion_detected
test_validate_all_filters_below_threshold
test_validate_all_raises_if_no_valid_scenes
```

---

## SE-03 ⏳ — `ProductionBudget` + interface `extract_chunk`

### Problème

Le pipeline n'a aucune notion de durée cible ou de budget de production.
Un roman de 300 pages et une nouvelle de 5 pages produisent des outputs de tailles
arbitraires. Pour un épisode de 45 minutes (540 shots, 135 scènes), le LLM doit
savoir combien de scènes produire. Sans ce contrat, P6 (Scale & Orchestration)
ne peut pas appeler `StoryExtractor` en boucle de manière cohérente.

### Solution : `ProductionBudget` dataclass + `extract_chunk` sur `StoryExtractor`

**Nouveau composant : `ProductionBudget`**

```python
@dataclass(frozen=True)
class ProductionBudget:
    """
    Contraintes de production injectées dans les prompts LLM
    et utilisées par P6 pour le chunking multi-épisodes.

    Valeurs par défaut : court-métrage (~3 minutes).
    """
    target_duration_sec: int = 180    # 180s = 3 min, 2700s = 45 min
    max_scenes: int = 12              # 135 pour 45 min
    max_shots_per_scene: int = 6
    max_characters: int = 4
    chunk_size: int = 20              # Scènes par appel LLM (pour chunking P6)

    @property
    def shots_estimate(self) -> int:
        return self.max_scenes * self.max_shots_per_scene  # estimation haute

    @classmethod
    def for_short(cls) -> "ProductionBudget":
        """3 minutes — court-métrage."""
        return cls(target_duration_sec=180, max_scenes=12, max_characters=4)

    @classmethod
    def for_episode_45(cls) -> "ProductionBudget":
        """45 minutes — épisode série."""
        return cls(target_duration_sec=2700, max_scenes=135,
                   max_characters=6, chunk_size=20)
```

**Interface `extract_chunk` sur `StoryExtractor` :**

```python
# Méthode déjà définie dans SE-01, signature complète documentée ici :
def extract_chunk(
    self,
    llm: LLMAdapter,
    text: str,
    budget: ProductionBudget,
    prior_summary: str = "",   # "" pour chunk 1, résumé des N scènes précédentes pour P6
) -> list[VisualScene]:
    """
    Point d'extension P6 — appelé N fois pour chunker un long texte.
    prior_summary assure la cohérence narrative inter-chunks.
    Avec prior_summary="" → comportement identique à extract() (P1/P2 normal).
    """
```

**Intégration dans `run_pipeline` :**

```python
def run_pipeline(
    text: str,
    title: str,
    episode_id: str = "EP01",
    llm: "LLMAdapter | None" = None,
    character_descriptions: "dict[str, str] | None" = None,
    budget: "ProductionBudget | None" = None,   # ← nouveau paramètre optionnel
) -> AIPRODOutput:
    _budget = budget or ProductionBudget.for_short()
    ...
```

Le paramètre `budget` est **optionnel et rétrocompatible** — les appels existants sans `budget` utilisent les defaults `for_short()`.

**Fichiers à créer :**
- `aiprod_adaptation/core/production_budget.py`

**Fichiers à modifier :**
- `aiprod_adaptation/core/engine.py` — ajouter `budget` param + passer à `StoryExtractor`
- `aiprod_adaptation/core/__init__.py` — exporter `ProductionBudget`
- `aiprod_adaptation/core/adaptation/story_extractor.py` — consommer `ProductionBudget`

**Tests à ajouter** (`test_pipeline.py` → `TestProductionBudget`) :
```
test_budget_default_values
test_budget_for_short_factory
test_budget_for_episode_45_factory
test_budget_shots_estimate_property
test_pipeline_accepts_budget_param
test_pipeline_budget_none_uses_default
```

---

## SE-04 ⏳ — Enrichir `VisualScene` avec `pacing`, `time_of_day_visual`, `dominant_sound`

### Problème

`VisualScene` ne transmet pas à P3/P4/P5 les informations que le LLM détecte naturellement
lors de l'extraction. `pass3_shots.py` ne connaît ni le rythme voulu ni la lumière ambiante.
`AudioSynchronizer` ne sait pas si une scène est dominée par du dialogue ou du silence.

### Solution : 3 champs optionnels dans `VisualScene`

```python
class VisualScene(TypedDict, total=False):
    # Champs obligatoires (existants — inchangés)
    scene_id:       str
    characters:     list[str]
    location:       str
    time_of_day:    Optional[str]
    visual_actions: list[str]
    dialogues:      list[str]
    emotion:        str

    # Nouveaux champs optionnels (total=False — rétrocompatibles)
    pacing:              str   # "fast" | "slow" | "medium"
    time_of_day_visual:  str   # "dawn" | "day" | "dusk" | "night" | "interior"
    dominant_sound:      str   # "dialogue" | "ambient" | "silence"
```

**Utilisation en aval :**

- `pass3_shots.py` : `pacing == "fast"` → durées shots clampées à [3, 5] ; `"slow"` → [5, 8]
- `image_gen/storyboard.py` : `time_of_day_visual` injecté dans le prompt image (ex: `"golden hour"`, `"overcast night"`)
- `post_prod/audio_synchronizer.py` : `dominant_sound == "silence"` → `AudioRequest.text = ""` (pas de TTS généré)

**Intégration dans `StoryExtractor` :**
Ces 3 champs sont ajoutés au `PRODUCTION_SCHEMA` et au prompt système. Le LLM les renseigne
avec zéro coût marginal — ils sont déduits naturellement du contexte narratif.

**Defaults déterministes si absents :**
```python
pacing             = "medium"
time_of_day_visual = "day"
dominant_sound     = "dialogue"
```

**Fichiers à modifier :**
- `aiprod_adaptation/models/intermediate.py` — ajouter les 3 champs optionnels
- `aiprod_adaptation/core/pass3_shots.py` — consommer `pacing` pour le clamping duration
- `aiprod_adaptation/image_gen/storyboard.py` — injecter `time_of_day_visual` dans le prompt
- `aiprod_adaptation/post_prod/audio_synchronizer.py` — court-circuiter TTS si `dominant_sound == "silence"`
- `aiprod_adaptation/core/adaptation/story_extractor.py` — ajouter au schema + prompt

**Tests à ajouter** (`test_pipeline.py` → `TestVisualSceneEnrichment`) :
```
test_pacing_fast_clamps_shot_duration_to_5
test_pacing_slow_clamps_shot_duration_minimum_5
test_time_of_day_visual_injected_in_image_prompt
test_dominant_sound_silence_skips_tts
test_missing_pacing_uses_medium_default
```

---

## SE-05 ⏳ — Support Gemini 2.5 Pro pour romans longs (> 80K tokens)

### Problème

`ClaudeAdapter` utilise `claude-sonnet-4-5` avec 200K tokens de contexte.
Pour un roman complet (200+ pages ≈ 150K-300K tokens), Claude peut saturer sa fenêtre.
Gemini 2.5 Pro offre 1M tokens de contexte — seul modèle viable pour un roman entier en 1 appel.

### Solution : `GeminiAdapter` + sélection automatique par `LLMRouter`

**Nouveau composant : `GeminiAdapter`**

```python
class GeminiAdapter(LLMAdapter):
    """
    Google Gemini 2.5 Pro via google-generativeai SDK.
    Exclu de mypy (prod adapter).
    Activé automatiquement si input > TOKEN_THRESHOLD.
    """
    MODEL = "gemini-2.5-pro"
    TOKEN_THRESHOLD = 80_000   # ~80K tokens ≈ 60K mots ≈ roman court

    def generate_json(self, prompt: str) -> dict[str, Any]:
        ...
```

**Nouveau composant : `LLMRouter`**

```python
class LLMRouter(LLMAdapter):
    """
    Sélectionne automatiquement le bon adapter selon la taille de l'input.
    - input <= 80K tokens → ClaudeAdapter
    - input >  80K tokens → GeminiAdapter
    Permet de forcer un adapter via constructor.
    """
    def __init__(
        self,
        claude: LLMAdapter,
        gemini: LLMAdapter,
        token_threshold: int = 80_000,
    ) -> None: ...

    def generate_json(self, prompt: str) -> dict[str, Any]:
        token_estimate = len(prompt) // 4   # approximation chars/4
        if token_estimate <= self._threshold:
            return self._claude.generate_json(prompt)
        return self._gemini.generate_json(prompt)
```

**Fichiers à créer :**
- `aiprod_adaptation/core/adaptation/gemini_adapter.py` (exclu mypy)
- `aiprod_adaptation/core/adaptation/llm_router.py`

**Fichiers à modifier :**
- `aiprod_adaptation/core/adaptation/__init__.py` — exporter `LLMRouter`
- `pyproject.toml` — ajouter `gemini_adapter\\.py` à la liste d'exclusions mypy

**Tests à ajouter** (`test_adaptation.py` → `TestLLMRouter`) :
```
test_router_uses_claude_for_short_input
test_router_uses_gemini_for_long_input
test_router_threshold_boundary
test_router_custom_threshold
test_router_null_adapters_both_paths
```

---

## Récapitulatif fichiers

### Fichiers à créer (6)
| Fichier | Étape |
|---|---|
| `aiprod_adaptation/core/production_budget.py` | SE-03 |
| `aiprod_adaptation/core/adaptation/story_extractor.py` | SE-01 |
| `aiprod_adaptation/core/adaptation/story_validator.py` | SE-02 |
| `aiprod_adaptation/core/adaptation/llm_router.py` | SE-05 |
| `aiprod_adaptation/core/adaptation/gemini_adapter.py` | SE-05 |

### Fichiers à modifier (10)
| Fichier | Étapes |
|---|---|
| `aiprod_adaptation/models/intermediate.py` | SE-04 |
| `aiprod_adaptation/core/engine.py` | SE-01, SE-02, SE-03 |
| `aiprod_adaptation/core/pass3_shots.py` | SE-04 |
| `aiprod_adaptation/core/adaptation/novel_pipe.py` | SE-01 (DeprecationWarning) |
| `aiprod_adaptation/core/adaptation/__init__.py` | SE-01, SE-02, SE-05 |
| `aiprod_adaptation/core/__init__.py` | SE-03 |
| `aiprod_adaptation/image_gen/storyboard.py` | SE-04 |
| `aiprod_adaptation/post_prod/audio_synchronizer.py` | SE-04 |
| `aiprod_adaptation/core/adaptation/story_extractor.py` | SE-03, SE-04 |
| `pyproject.toml` | SE-05 |

---

## Tests attendus

| Fichier test | Tests ajoutés | Étape |
|---|---|---|
| `test_adaptation.py` | +5 `TestStoryExtractor` | SE-01 |
| `test_adaptation.py` | +8 `TestStoryValidator` | SE-02 |
| `test_pipeline.py` | +6 `TestProductionBudget` | SE-03 |
| `test_pipeline.py` | +5 `TestVisualSceneEnrichment` | SE-04 |
| `test_adaptation.py` | +5 `TestLLMRouter` | SE-05 |

**Total nouveaux tests : +29 → cible : 179 tests**

---

## Notes d'implémentation

- **Rétrocompatibilité totale** : `run_pipeline()` sans `budget` fonctionne exactement comme avant.
- **Zéro breaking change** : les 3 nouveaux champs `VisualScene` sont `total=False` (optionnels).
- **`novel_pipe.py` conservé** avec `DeprecationWarning` — pas supprimé, pas cassé.
- **`GeminiAdapter` exclu mypy** comme tous les prod adapters (pattern établi).
- **`LLMRouter` inclus mypy** (zéro dépendance externe, 100% typable).
- **`StoryExtractor.extract_chunk`** est identique à `extract` quand `prior_summary=""` — un seul code path.
