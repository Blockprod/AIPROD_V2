# Production — District Zero EP01 — Méthode professionnelle v3.0

## Principe
Chaque prompt est un document de production cinématographique réel.
Pas de "describe what you want" — des notes de DP, de gaffer, de directeur artistique.
Ce principe a produit un score ArcFace de 0.9378 — record validé le 2026-04-30.

## Sources de vérité
| Fichier | Contient |
|---------|---------|
| `characters.json` | 5 canoniques DOP-grade + portrait_brief par personnage |
| `locations.json` | 10 descripteurs DOP-grade + lighting_brief + colour par lieu |
| `storyboard.json` | 35 shots — briefs de production complets (state_override + audio_brief) |
| `dashboard.json` | seeds, location_keys, chemins master plates générées |
| `grade.json` | Show look transversal — grade d'épisode + per_scene_grade |

## Phases de production

### Phase A — Portraits référence ($0.15)
```
python production/run.py char-refs --dry-run
python production/run.py char-refs
```

### Phase B — Master plates lieux ($0.30)
```
python production/run.py location-refs --dry-run
python production/run.py location-refs
```

### Phase B2 — Validation ArcFace ($0)
```
python production/run.py benchmark
```

### Phase C — Shots EP01 (~$2.80)
```
python production/run.py shots --dry-run
python production/run.py shots --scene SCN_002          # une scène
python production/run.py shots --shot SCN_002_SHOT_001  # un shot
python production/run.py shots                          # tout EP01
```

### Rapport
```
python production/run.py report
```

### Phase D — Retakes (variable)
```
python production/run.py retakes --dry-run
python production/run.py retakes
```

### Phase E — Rough cut assembly ($0)
```
python production/run.py assembly        # 24fps par défaut
python production/run.py assembly --fps 30
```

## Conventions
- seed = N×11 : SCN_001→11, SCN_002→22 ... SCN_011→121
- ArcFace target : ≥ 0.85 en 1x (record 0.9378 Nara)
- metrics.jsonl : chaque shot tracé immédiatement après génération
- Ne jamais modifier pipeline/shot_pipeline.py sans rebenchmark ArcFace
- Ne jamais générer des shots avant que les refs personnages soient validées (Phase B2 OK)
- grade.json doit exister avant Phase B et Phase C (chargé dans les prompts)
- Convention de nommage outputs : `DZ_EP01_{SCN_ID}_{SHOT_ID}_v001.png` (géré automatiquement)

## Coût total EP01
| Phase | Opération | Coût |
|-------|-----------|------|
| A | 5 portraits référence | $0.15 |
| B | 10 master plates lieux | $0.30 |
| C | 35 shots EP01 | ~$2.80 |
| D | Retakes estimés 20% | ~$0.56 |
| E | Rough cut assembly | $0 |
| **Total** | | **~$3.81** |
