---
title: Consistency Framework — Réorientation stratégique
creation: 2026-04-28 à 15:30
status: active
priority: critical
---

# CONSTAT & RÉORIENTATION STRATÉGIQUE

## Diagnostic

Le système actuel démontre une fragilité conceptuelle majeure : il compile du texte en JSON, mais **ne garantit aucune cohérence** entre les éléments générés (image, vidéo, audio, narration).

**Problème racine** : Un compilateur narratif ne suffit pas. Il faut un **système de cohérence transverse** qui s'applique à TOUS les médias et TOUTES les échelles de temps.

---

# RÈGLES D'OR ABSOLUES (NON NÉGOCIABLES)

## 1. Cohérence narrative

| Règle | Application |
|-------|-------------|
| **Continuity lock** | Une action commencée dans un shot doit être terminée ou justifiée dans le suivant |
| **Temporal anchoring** | Chaque shot a un timestamp absolu (offset en secondes depuis le début de l'épisode) |
| **Causal chain** | Cause → Effet : aucun effet sans cause visible dans un shot précédent |
| **Dialogue sync** | Parole = mouvement de bouche correspondant dans l'image |

## 2. Cohérence visuelle / photographique

| Règle | Application |
|-------|-------------|
| **Character lock** | Un personnage a la même apparence (visage, vêtements, accessoires) TOUS les plans |
| **Location lock** | Un lieu a la même lumière, mêmes couleurs, mêmes repères fixes TOUS les plans |
| **Camera continuity** | Passage d'un plan à l'autre : respect des angles (180° rule), des mouvements de caméra |
| **Color grading ID** | Chaque épisode/scène a une LUT unique et documentée |
| **Lighting consistency** | Source de lumière principale identifiée et cohérente dans un même lieu/temps |

## 3. Cohérence audio

| Règle | Application |
|-------|-------------|
| **Voice lock** | Un personnage a la même voix (timbre, accent, volume) TOUS les dialogues |
| **Ambiance continuity** | Le bruit de fond (vent, foule, machine) est continu d'un shot à l'autre |
| **SFX synchronization** | Un bruit (porte, pas, coup) est aligné exactement avec l'action visuelle |
| **Dynamic range** | Niveaux sonores normalisés entre épisodes (-23 LUFS pour le dialogue) |

## 4. Cohérence structurelle (compilateur)

| Règle | Application |
|-------|-------------|
| **ID permanence** | Tout élément (personnage, lieu, accessoire) a un ID unique et persistant |
| **Metadata inheritance** | Un shot hérite des métadonnées de sa scène, un épisode de sa saison |
| **Version locking** | Toute modification d'une règle (ex: durée) est tracée et versionnée |
| **Determinism absolute** | Même input + même version = même output (pas de hasard, pas de timestamp) |

## 5. Cohérence inter-épisodes / saisons

| Règle | Application |
|-------|-------------|
| **Global asset registry** | Base de données centralisée de tous les personnages/lieux/accessoires |
| **Canon lock** | Une fois qu'un détail visuel ou narratif est établi, il ne change jamais |
| **Timeline master** | Calendrier absolu (ex: jour 1, jour 2…) pour toute la série |
| **Character arc tracking** | État émotionnel/moral d'un personnage évolue, mais est tracé |

---

# PLAN D'ACTION

## Phase 1 — Audit et documentation (1-2 jours)

Créer dans `tasks/corrections/plans/` :

```
tasks/corrections/plans/
├── 01_consistency_framework.md
├── 02_asset_registry_schema.json
├── 03_timeline_specification.md
├── 04_color_grading_guide.md
├── 05_audio_specification.md
└── 06_continuity_checklist.md
```

## Phase 2 — Extension du compilateur (3-5 jours)

Ajouter à `AIPRODOutput` :

```python
class GlobalAsset(BaseModel):
    asset_id: str
    asset_type: Literal["character", "location", "prop", "costume", "voice"]
    attributes: Dict[str, Any]
    first_occurrence: str

class Timeline(BaseModel):
    episode_offsets: Dict[str, int]
    absolute_timestamps: List[Dict[str, Any]]

class AIPRODOutput(BaseModel):
    title: str
    episodes: List[Episode]
    global_assets: List[GlobalAsset]
    master_timeline: Timeline
    color_luts: Dict[str, str]
```

## Phase 3 — Services de cohérence externes (1-2 semaines)

```
aiprod_adaptation/consistency/
├── asset_registry.py
├── continuity_checker.py
├── color_manager.py
├── audio_normalizer.py
└── timeline_engine.py
```

## Phase 4 — Tests de cohérence (2-3 jours)

Ajouter `tests/test_consistency.py` avec :
- test_character_appearance_consistent()
- test_location_lighting_consistent()
- test_audio_normalized()
- test_timestamps_monotonic()
- test_causal_chain_valid()
- test_color_lut_assigned()

## Phase 5 — Production pilot (en continu)

1. Chaque épisode → continuity_checker.py
2. Avant génération image/vidéo → exporter GlobalAsset
3. Avant montage audio → audio_normalizer.py
4. Avant export final → checklist

---

# PROCHAINE ACTION IMMÉDIATE

Créer les fichiers Phase 1 restants :
- `02_asset_registry_schema.json`
- `03_timeline_specification.md`
- `04_color_grading_guide.md`
- `05_audio_specification.md`
- `06_continuity_checklist.md`
