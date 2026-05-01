---
title: Timeline Specification — Ancrage temporel absolu
creation: 2026-04-28 à 15:33
status: active
---

# TIMELINE MASTER — Spécification

## Principe

Chaque shot de chaque épisode a un **timestamp absolu** calculé depuis le début de l'épisode. Ce timestamp est déterministe : il ne dépend que de la somme des `duration_sec` des shots précédents.

## Contrat de données

```python
class Timeline(BaseModel):
    episode_offsets: Dict[str, int]
    # Clé = episode_id, valeur = offset en secondes depuis le début de la saison
    # Ex: {"EP_01": 0, "EP_02": 2340, "EP_03": 4800}

    absolute_timestamps: List[Dict[str, Any]]
    # Liste ordonnée de tous les shots avec leur timestamp absolu
    # Ex: [{"shot_id": "SCN_001_SHOT_001", "episode_id": "EP_01",
    #        "offset_in_episode": 0, "offset_in_season": 0,
    #        "duration_sec": 5, "end_offset": 5}]
```

## Règles de calcul

| Règle | Description |
|-------|-------------|
| **Monotonie absolue** | `offset_in_episode` est strictement croissant dans un épisode |
| **Pas de chevauchement** | `end_offset(shot_n) == offset(shot_n+1)` — aucun gap, aucun overlap |
| **Héritage saison** | `offset_in_season = episode_offsets[episode_id] + offset_in_episode` |
| **Déterminisme** | Même liste de shots → même timestamps, toujours |

## Exemple : Épisode 01 District Zero

```
EP_01 offset = 0s
SCN_001_SHOT_001 → t=0s   durée=5s → t_end=5s
SCN_001_SHOT_002 → t=5s   durée=4s → t_end=9s
SCN_001_SHOT_003 → t=9s   durée=6s → t_end=15s
SCN_001_SHOT_004 → t=15s  durée=3s → t_end=18s
...
```

## Règles narrative de timing

| Scène | Type | Durée cible |
|-------|------|-------------|
| Establishing shot | wide | 4-6s |
| Dialogue exchange | medium | 3-5s par réplique |
| Action peak | close_up/insert | 3-4s |
| Climax | extreme_wide | 6-8s |
| Transition | any | 3s |

## Validation automatique (timeline_engine.py)

Le `TimelineEngine` doit vérifier :
1. `offset_in_episode[0] == 0`
2. `offset[n] + duration[n] == offset[n+1]` pour tout n
3. `offset_in_season[shot] == episode_offsets[episode_id] + offset_in_episode[shot]`
4. Durées dans `[3, 8]` secondes (déjà validé par `Shot.validate_duration_sec`)
