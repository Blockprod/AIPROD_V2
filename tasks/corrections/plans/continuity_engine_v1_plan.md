---
title: Plan d'action — Continuity Engine v1
source: concept_adaptation_engine.md + analyse pipeline audiovisuel complet
creation: 2026-04-21 à 14:49
last_updated: 2026-04-21 à 14:49
status: active
corrections_totales: 5 (P1:2 P2:2 P3:1)
prerequis: adaptation_layer_v1_plan.md complété (2026-04-21) — 60/60 tests
tests_avant: 60
tests_apres_cible: 75+
---

# PLAN D'ACTION — CONTINUITY ENGINE v1 — 2026-04-21

**Généré le** : 2026-04-21 à 14:49
**Étapes totales** : 5 (P1:2 · P2:2 · P3:1)

---

## Contexte

Sans Continuity Engine, les prompts générés par AIPROD_V2 sont **stateless** : chaque shot
ignore ce qui précède. Résultat à l'étape Image Generation :

```
Shot 1 : "John runs toward the door."
Shot 7 : "John stands near the window."   ← modèle image : qui est John ?
Shot 12: "John smiles."                    ← John a changé de tête entre shots
```

Le Continuity Engine résout ce problème en **3 responsabilités** :

1. **Character Registry** — profil physique par personnage, extrait automatiquement
2. **Emotion Arc Tracker** — suivi de l'arc émotionnel entre shots (pas de rupture silencieuse)
3. **Prompt Enricher** — injection de la description dans chaque `shot.prompt` avant export

**Sans Continuity Engine → images incohérentes → pipeline vidéo inutilisable.**

---

## Architecture cible

```
AIPRODOutput (actuel)
        ↓
[CE-01] CharacterRegistry.build(output)
        ↓  dict[str, CharacterProfile]
[CE-02] EmotionArcTracker.track(output)
        ↓  dict[shot_id, EmotionState]
[CE-03] PromptEnricher.enrich(output, registry, arcs)
        ↓  AIPRODOutput (prompts enrichis)
[CE-04] Wiring dans engine.py (optionnel, activé par flag)
[CE-05] Tests complets
```

**Fichiers à créer :**

```
aiprod_adaptation/
  core/
    continuity/
      __init__.py
      character_registry.py   ← CE-01
      emotion_arc.py          ← CE-02
      prompt_enricher.py      ← CE-03
  tests/
    test_continuity.py        ← CE-05
```

**Fichier à modifier :**
- `aiprod_adaptation/core/engine.py` — CE-04

---

## Modèle de données

```python
# character_registry.py
class CharacterProfile(TypedDict):
    name:        str
    description: str           # "30s, dark hair, blue jacket"
    first_scene: str           # scene_id d'introduction
    scenes:      List[str]     # toutes les scènes où il apparaît

# emotion_arc.py
class EmotionState(TypedDict):
    shot_id:        str
    scene_id:       str
    emotion:        str        # "neutral" | "fear" | "joy" | ...
    previous:       str | None # émotion du shot précédent
    transition_ok:  bool       # False si rupture abrupte détectée
```

---

## Corrections P1 — CRITIQUE (Fondation)

---

### [CE-01] ⏳ — `CharacterRegistry`

**Priorité** : P1
**Sévérité** : 🔴
**Fichier à créer** : `aiprod_adaptation/core/continuity/character_registry.py`

**Problème** : Les personnages sont connus (`scene.characters: List[str]`) mais leurs
descriptions physiques ne sont nulle part. Chaque prompt est généré sans savoir à quoi ressemble
le personnage.

**Action** :

```python
class CharacterProfile(TypedDict):
    name:        str
    description: str
    first_scene: str
    scenes:      List[str]

class CharacterRegistry:
    def build(self, output: AIPRODOutput) -> dict[str, CharacterProfile]:
        """Extrait tous les personnages uniques de l'output et initialise leurs profils."""
        registry: dict[str, CharacterProfile] = {}
        for episode in output.episodes:
            for scene in episode.scenes:
                for character in scene.characters:
                    name = character.strip()
                    if not name:
                        continue
                    if name not in registry:
                        registry[name] = CharacterProfile(
                            name=name,
                            description="",   # à enrichir par LLM ou input utilisateur
                            first_scene=scene.scene_id,
                            scenes=[scene.scene_id],
                        )
                    else:
                        if scene.scene_id not in registry[name]["scenes"]:
                            registry[name]["scenes"].append(scene.scene_id)
        return registry

    def enrich_from_text(
        self, registry: dict[str, CharacterProfile], descriptions: dict[str, str]
    ) -> dict[str, CharacterProfile]:
        """Injecte des descriptions manuelles ou issues d'un LLM.
        descriptions = {"John": "30s, dark hair, blue jacket, athletic build"}
        """
        for name, description in descriptions.items():
            if name in registry:
                registry[name]["description"] = description
        return registry
```

**Règle** : `description` vide par défaut — l'utilisateur ou un LLM l'enrichit.
Si vide, le `PromptEnricher` n'injecte rien (pas de dégradation silencieuse).

**Tests** (dans `test_continuity.py`) — classe `TestCharacterRegistry` :
```python
test_registry_extracts_all_characters       # 2 personnages → 2 entrées
test_registry_deduplicates_characters       # même perso dans 2 scènes → 1 entrée
test_registry_tracks_all_scenes             # perso dans 3 scènes → scenes=[3 ids]
test_registry_empty_output_returns_empty    # 0 personnage → {}
test_enrich_from_text_updates_description   # description injectée → visible dans registry
```

**Risque** : Nul — nouveau fichier, pas branché.
**Validation** : 60 + 5 = 65 tests verts.

---

### [CE-02] ⏳ — `EmotionArcTracker`

**Priorité** : P1
**Sévérité** : 🔴
**Fichier à créer** : `aiprod_adaptation/core/continuity/emotion_arc.py`

**Problème** : L'émotion est actuellement au niveau de la scène (`scene.emotion`) mais pas
trackée entre shots consécutifs. Une rupture abrupte (`fear` → `neutral` en 1 shot) est
invisible et produit une incohérence narrative.

**Action** :

```python
# Transitions émotionnelles considérées abruptes
_ABRUPT_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("fear",    "joy"),
    ("joy",     "fear"),
    ("terror",  "neutral"),
    ("neutral", "terror"),
    ("grief",   "joy"),
    ("joy",     "grief"),
})

class EmotionState(TypedDict):
    shot_id:       str
    scene_id:      str
    emotion:       str
    previous:      NotRequired[str]
    transition_ok: bool

class EmotionArcTracker:
    def track(self, output: AIPRODOutput) -> list[EmotionState]:
        """Produit la liste ordonnée des états émotionnels shot par shot."""
        states: list[EmotionState] = []
        previous_emotion: str | None = None
        for episode in output.episodes:
            for shot in episode.shots:
                transition_ok = True
                if previous_emotion is not None:
                    transition_ok = (
                        previous_emotion, shot.emotion
                    ) not in _ABRUPT_TRANSITIONS
                state = EmotionState(
                    shot_id=shot.shot_id,
                    scene_id=shot.scene_id,
                    emotion=shot.emotion,
                    transition_ok=transition_ok,
                )
                if previous_emotion is not None:
                    state["previous"] = previous_emotion
                states.append(state)
                previous_emotion = shot.emotion
        return states

    def get_warnings(self, states: list[EmotionState]) -> list[str]:
        """Retourne les messages d'avertissement pour les transitions abruptes."""
        return [
            f"Abrupt emotion transition at shot {s['shot_id']}: "
            f"{s.get('previous', '?')} → {s['emotion']}"
            for s in states
            if not s["transition_ok"]
        ]
```

**Tests** (dans `test_continuity.py`) — classe `TestEmotionArcTracker` :
```python
test_arc_tracks_all_shots_in_order      # N shots → N états dans l'ordre
test_arc_first_shot_has_no_previous     # 1er shot → pas de clé "previous"
test_arc_detects_abrupt_transition      # fear→joy → transition_ok=False
test_arc_accepts_smooth_transition      # neutral→joy → transition_ok=True
test_arc_get_warnings_returns_messages  # 1 rupture → 1 warning
```

**Risque** : Nul — nouveau fichier, pas branché.
**Validation** : 65 + 5 = 70 tests verts.

---

## Corrections P2 — IMPORTANT

---

### [CE-03] ⏳ — `PromptEnricher`

**Priorité** : P2
**Sévérité** : 🟠
**Fichier à créer** : `aiprod_adaptation/core/continuity/prompt_enricher.py`

**Problème** : Les prompts actuels sont stateless. `"John runs toward the door."` ne contient
aucune information sur l'apparence de John. Un modèle image génère une personne aléatoire.

**Action** :

```python
class PromptEnricher:
    def enrich(
        self,
        output: AIPRODOutput,
        registry: dict[str, CharacterProfile],
        arc_states: list[EmotionState],
    ) -> AIPRODOutput:
        """Retourne un nouvel AIPRODOutput avec les prompts enrichis.
        Ne modifie pas l'objet d'entrée (immutabilité — déterminisme préservé).
        """
        arc_by_shot = {s["shot_id"]: s for s in arc_states}
        enriched_episodes = []

        for episode in output.episodes:
            # Trouver les personnages présents dans cet épisode
            episode_chars = {
                c for scene in episode.scenes for c in scene.characters
            }
            enriched_shots = []
            for shot in episode.shots:
                enriched_prompt = self._enrich_prompt(
                    shot.prompt, episode_chars, registry, arc_by_shot.get(shot.shot_id)
                )
                enriched_shots.append(shot.model_copy(update={"prompt": enriched_prompt}))
            enriched_episodes.append(
                episode.model_copy(update={"shots": enriched_shots})
            )

        return output.model_copy(update={"episodes": enriched_episodes})

    def _enrich_prompt(
        self,
        prompt: str,
        characters: set[str],
        registry: dict[str, CharacterProfile],
        arc_state: EmotionState | None,
    ) -> str:
        parts = [prompt]
        for char in sorted(characters):  # sorted → déterminisme garanti
            profile = registry.get(char)
            if profile and profile["description"]:
                parts.append(f"{char}: {profile['description']}.")
        if arc_state and not arc_state["transition_ok"]:
            parts.append(f"[CONTINUITY WARNING: abrupt emotion transition]")
        return " ".join(parts)
```

**Règle d'or** : `sorted(characters)` — déterminisme byte-level préservé.
Si `description` est vide → rien injecté, prompt original inchangé.
`model_copy` Pydantic v2 → pas de mutation en place.

**Tests** (dans `test_continuity.py`) — classe `TestPromptEnricher` :
```python
test_enrich_injects_character_description   # description présente → dans le prompt
test_enrich_skips_empty_description         # description vide → prompt inchangé
test_enrich_is_deterministic                # 2 appels identiques → même output byte-level
test_enrich_does_not_mutate_input           # output original inchangé après enrich
```

**Risque** : Faible — nouveau fichier, pas branché. Aucun test existant impacté.
**Validation** : 70 + 4 = 74 tests verts.

---

### [CE-04] ⏳ — Wiring dans `engine.py` (flag `enable_continuity`)

**Priorité** : P2
**Sévérité** : 🟠
**Fichier à modifier** : `aiprod_adaptation/core/engine.py`

**Problème** : Le Continuity Engine doit être **optionnel** (flag) pour ne pas imposer une
`descriptions` dict à tous les callers existants. Les 60 tests doivent rester verts sans
modification.

**Action** :

```python
def run_pipeline(
    text: str,
    title: str,
    episode_id: str = "EP01",
    llm: "LLMAdapter | None" = None,
    character_descriptions: "dict[str, str] | None" = None,  # ← nouveau
) -> AIPRODOutput:
    ...
    # Après compile_episode, si descriptions fournies :
    if character_descriptions:
        from aiprod_adaptation.core.continuity.character_registry import CharacterRegistry
        from aiprod_adaptation.core.continuity.emotion_arc import EmotionArcTracker
        from aiprod_adaptation.core.continuity.prompt_enricher import PromptEnricher

        registry = CharacterRegistry().build(output)
        registry = CharacterRegistry().enrich_from_text(registry, character_descriptions)
        arc_states = EmotionArcTracker().track(output)
        output = PromptEnricher().enrich(output, registry, arc_states)

    return output
```

**Signature finale de `run_pipeline`** :
```python
run_pipeline(
    text="...",
    title="...",
    episode_id="EP01",
    llm=None,                       # NullLLMAdapter si absent
    character_descriptions=None,    # pas de continuity si absent
)
```

**Tests** (dans `test_continuity.py`) — classe `TestEngineWithContinuity` :
```python
test_engine_without_continuity_unchanged     # character_descriptions=None → comportement identique
test_engine_with_descriptions_enriches_prompts  # descriptions dict → prompts contiennent descriptions
```

**Risque** : Faible — flag opt-in, valeur par défaut `None` → 60 tests existants non impactés.
**Validation** : 74 + 2 = 76 tests verts.

---

## Corrections P3 — MINEUR

---

### [CE-05] ⏳ — `__init__.py` + exports publics du module continuity

**Priorité** : P3
**Sévérité** : 🟡
**Fichier à créer** : `aiprod_adaptation/core/continuity/__init__.py`

**Action** :

```python
# aiprod_adaptation/core/continuity/__init__.py
from aiprod_adaptation.core.continuity.character_registry import CharacterRegistry
from aiprod_adaptation.core.continuity.emotion_arc import EmotionArcTracker
from aiprod_adaptation.core.continuity.prompt_enricher import PromptEnricher

__all__ = ["CharacterRegistry", "EmotionArcTracker", "PromptEnricher"]
```

**Risque** : Nul.

---

## Ordre d'exécution recommandé

```
CE-01  CharacterRegistry        → isolé, 0 dépendance externe
  ↓
CE-02  EmotionArcTracker        → isolé, 0 dépendance externe
  ↓
CE-03  PromptEnricher           → dépend CE-01 + CE-02
  ↓
CE-04  Wiring engine.py         → dépend CE-01/02/03 ; flag opt-in → 0 régression
  ↓
CE-05  __init__.py exports      → clôture le module
```

---

## Ce qui n'est PAS dans ce plan (hors scope — Continuity v2)

| Exclu | Raison | Plan futur |
|---|---|---|
| Extraction auto des descriptions via LLM | Feature — nécessite ClaudeAdapter + prompt dédié | Continuity v2 |
| Costume tracking par scène | Feature — descriptions varient selon le contexte | Continuity v2 |
| Cohérence visuelle décors/props | Hors scope personnages | Continuity v2 |
| Export storyboard (images) | Phase suivante — Image Generation connector | Image Gen v1 |

---

## Validation finale

```bash
venv\Scripts\Activate.ps1

ruff check aiprod_adaptation/

mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ --strict

pytest aiprod_adaptation/tests/ -v --tb=short -m "not integration"

# Déterminisme : vérifier que PromptEnricher est byte-identical
pytest aiprod_adaptation/tests/ -v -k "test_enrich_is_deterministic or test_rule_pipeline_byte_identical"
```

Cibles après exécution complète :
- [ ] 76+ tests pytest verts (60 + 16 nouveaux CE-01 à CE-04)
- [ ] ruff 0 erreurs
- [ ] mypy strict 0 erreurs
- [ ] `test_rule_pipeline_byte_identical` vert (inchangé)
- [ ] `test_enrich_is_deterministic` vert (nouveau)
- [ ] `run_pipeline(..., character_descriptions=None)` → comportement identique aux 60 tests existants
