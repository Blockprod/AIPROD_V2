---
title: Audio Specification — Cohérence sonore
creation: 2026-04-28 à 15:33
status: active
---

# AUDIO SPECIFICATION

## Normes de niveau sonore

| Type | Norme | Valeur cible |
|------|-------|-------------|
| Dialogue | EBU R128 / LUFS intégré | **-23 LUFS** |
| Ambiance | Relatif au dialogue | -12 dB sous dialogue |
| SFX ponctuels | Peak normalisé | -6 dBTP max |
| Musique | Relatif au dialogue | -18 dB sous dialogue |
| Export final | True Peak max | **-1 dBTP** |

## Voice Lock — Règles par personnage

| Personnage | Timbre | Accent | Modèle TTS verrouillé |
|------------|--------|--------|----------------------|
| Nara Voss | Mezzo, légèrement tendu | Neutre urbain | `voice_nara_v1` |
| Elian Voss | Baryton chaud, fatigué | Neutre urbain + relâché | `voice_elian_v1` |
| Mira Sol | Soprano technique, précis | Légèrement académique | `voice_mira_v1` |
| Commander Vale | Basse autoritaire, contrôlée | Accent institutionnel | `voice_vale_v1` |
| Rook | Baryton rugueux | Accent bas-stack | `voice_rook_v1` |

## Ambiance par lieu

| location_id | Ambiance de fond | Notes |
|-------------|-----------------|-------|
| `district_zero_outer_wall_night` | Vent marin, vagues lointaines, métal | Continu, sans coupure |
| `lower_transit_stack_service_corridor_night` | Humming infrastructure, gouttes d'eau | Boucle 30s |
| `pressure_valve_chamber_night` | Sifflements vapeur, alarme basse | Alarme démarre SCN_003_SHOT_001 |
| `voss_apartment_lower_stack_late_night` | Silence résidentiel, grondement lointain | Très bas, -35 LUFS |
| `civic_atrium_central_core_morning` | Foule distante, échos architecture | -28 LUFS |
| `black_market_exchange_ventilation_sublevel_day` | Ventilation industrielle, voix lointaines | -25 LUFS |
| `security_operations_center_day` | Bip électronique, clavier, murmures | -28 LUFS |
| `sealed_service_spine_night` | Métal sous pression, silence tendu | -32 LUFS (strobe audio: silence/bip) |
| `external_observation_chamber_continuous` | Vent haute altitude, vibration mécanique | -30 LUFS |
| `voss_apartment_pre_dawn` | Silence profond → boots à l'extérieur → explosion | Séquence dynamique |

## Règles SFX

| Règle | Description |
|-------|-------------|
| **Sync frame-exact** | SFX démarrent exactement sur le frame de l'action correspondante |
| **No orphan SFX** | Aucun SFX sans action visuelle correspondante dans le même shot ou le précédent |
| **Continuity de porte** | SCN_011 : boots → vibration porte → silence → explosion (chain causale) |
| **Pas de réutilisation brute** | SFX identiques ne peuvent pas apparaître dans 2 scènes consécutives sans variation de pitch/reverb |

## Processus audio_normalizer.py

```
1. Lire tous les DialogueSpec de l'IR
2. Pour chaque réplique : calculer offset absolu (via Timeline)
3. Aligner le fichier TTS généré sur le timestamp du shot
4. Normaliser à -23 LUFS (dialogue)
5. Mixer avec ambiance lieu (offset = début du shot)
6. Appliquer SFX (frame-exact)
7. Vérifier True Peak < -1 dBTP
8. Exporter WAV 48kHz 24-bit
```
