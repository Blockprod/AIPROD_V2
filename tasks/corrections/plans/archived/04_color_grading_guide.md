---
title: Color Grading Guide — LUT et cohérence chromatique
creation: 2026-04-28 à 15:33
status: active
---

# COLOR GRADING GUIDE

## Principe

Chaque lieu/moment a une LUT documentée et verrouillée. Une fois établie en EP_01, elle ne change pas (sauf arc narratif intentionnel, documenté dans l'IR).

## LUTs District Zero — Saison 1

| lut_id | Lieu / Contexte | Description | Palette dominante |
|--------|----------------|-------------|-------------------|
| `dz_outer_wall_night` | Muraille extérieure - nuit | Bleu-noir glacé, halos de searchlights blancs | `#0a0e1a`, `#1c2b4a`, `#e8f0ff` |
| `dz_transit_corridor_night` | Corridors de transit - nuit | Vert délavé industriel, tubes fluorescents | `#0d1a0d`, `#2a4a2a`, `#c8e0c0` |
| `dz_pressure_chamber_night` | Chambre à soupape - nuit | Gris acier, halos d'urgence orange | `#1a1a1a`, `#3a3a3a`, `#ff6b1a` |
| `dz_apartment_night` | Appartement Voss - nuit | Ambre chaud, contre-jour fenêtre bleue | `#2a1a08`, `#4a3010`, `#ffa030` |
| `dz_civic_atrium_day` | Atrium civique - jour | Blanc brutal, surfaces réfléchissantes | `#e0e8f0`, `#b0c0d0`, `#ffffff` |
| `dz_black_market_day` | Marché noir - jour | Brun-vert crasseux, lumière filtrée | `#1a1508`, `#3a2e18`, `#8a7040` |
| `dz_security_ops_day` | Centre opérations - jour | Bleu électronique froid, écrans | `#080e1a`, `#1030a0`, `#40a0ff` |
| `dz_service_spine_night` | Service spine scellé - nuit | Rouge stroboscopique, noir profond | `#1a0000`, `#3a0000`, `#ff2020` |
| `dz_observation_chamber` | Chambre d'observation | Ambre rouillé, lumière extérieure blanche | `#1a0e00`, `#3a2000`, `#ffe080` |
| `dz_apartment_pre_dawn` | Appartement Voss - pré-aube | Ambre résiduel, lumière rouge externe | `#1a0e04`, `#ff0000`, `#ffaa40` |

## Règles d'application

| Règle | Description |
|-------|-------------|
| **Un lieu = une LUT** | Toujours la même LUT pour le même `location_id`, quel que soit l'épisode |
| **Transition justifiée** | Si la LUT change pour un lieu, un `narrative_lut_override` doit être déclaré dans l'IR du shot |
| **Color grade hint** | Le champ `metadata.color_grade_hint` doit être cohérent avec la LUT du lieu |
| **Pas de désaturation arbitraire** | La désaturation/monochrome est réservée aux scènes de mort ou flashback |

## Mapping color_grade → LUT base

```python
COLOR_GRADE_TO_LUT_HINT = {
    "cool":          "bleu acier ou bleu-vert",
    "warm":          "ambre, orange, sépia chaud",
    "desaturated":   "réservé mort/flashback uniquement",
    "high_contrast": "noir profond + blanc dur (outer wall, climax)",
    "orange_teal":   "interdit — trop générique, perd l'identité District Zero",
    "neutral":       "transitions et scènes d'exposition pure",
    "bleach_bypass": "réservé vision subjective (POV Nara sous stress)",
    "monochrome":    "réservé séquences mémoire/rêve uniquement",
}
```

## Validation automatique (color_manager.py)

Le `ColorManager` vérifie :
1. Chaque `Shot` avec `location_id` connu a un `lut_id` assigné (via `LocationRegistry`)
2. `metadata.color_grade_hint` est compatible avec la LUT du lieu
3. Aucun shot n'utilise `orange_teal` (interdit District Zero S1)
4. `desaturated` et `monochrome` uniquement sur shots avec `beat_type == "denouement"` ou `scene_type == "flashback"`
