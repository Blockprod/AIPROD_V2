---
title: Continuity Checklist — Validation avant export
creation: 2026-04-28 à 15:33
status: active
---

# CONTINUITY CHECKLIST

Checklist à passer **avant tout export final** d'un épisode.
Chaque item doit être ✅ avant de passer en production.

---

## A. Cohérence narrative

- [ ] **A1** — Chaque shot a un `prompt` non vide
- [ ] **A2** — Chaque `shot_id` est unique dans l'épisode
- [ ] **A3** — L'ordre des `shot_id` dans chaque scène est monotone (`SHOT_001 < SHOT_002 < ...`)
- [ ] **A4** — Aucun effet visible sans cause dans un shot précédent (causal chain)
- [ ] **A5** — Les `continuity_flags` de l'IR sont tous résolus (pas de flag `[UNRESOLVED]`)

## B. Cohérence visuelle

- [ ] **B1** — Chaque personnage présent dans un shot a un `reference_anchor_strength >= 0.8`
- [ ] **B2** — Chaque `location_id` a une `lut_id` assignée dans le `GlobalAssetRegistry`
- [ ] **B3** — Aucun shot `orange_teal` (interdit District Zero S1)
- [ ] **B4** — `desaturated`/`monochrome` uniquement sur `beat_type == denouement` ou `scene_type == flashback`
- [ ] **B5** — La `180° rule` est respectée : les personnages ne changent pas de côté frame sans coupe justifiée
- [ ] **B6** — `feasibility_score >= 70` pour tous les shots

## C. Cohérence temporelle

- [ ] **C1** — `offset_in_episode[0] == 0`
- [ ] **C2** — Timestamps monotones : `offset[n] + duration[n] == offset[n+1]`
- [ ] **C3** — Durées dans `[3, 8]` secondes pour tous les shots
- [ ] **C4** — Durée totale de l'épisode dans `[18, 28]` minutes (1080–1680 secondes)

## D. Cohérence audio

- [ ] **D1** — Chaque dialogue a un fichier TTS généré et normalisé à -23 LUFS
- [ ] **D2** — Chaque lieu a une piste d'ambiance assignée
- [ ] **D3** — SFX frame-exact sur toutes les actions physiques (porte, pas, explosion)
- [ ] **D4** — True Peak < -1 dBTP sur le mix final

## E. Cohérence structurelle (IR)

- [ ] **E1** — Tous les `character_ids` référencés dans les shots existent dans le `GlobalAssetRegistry`
- [ ] **E2** — Tous les `location_id` référencés existent dans le `GlobalAssetRegistry`
- [ ] **E3** — `visual_bible_summary` est non vide si `visual_bible_path` est défini
- [ ] **E4** — `rule_engine_report.hard_conflicts_resolved == 0` (aucun conflit non résolu)
- [ ] **E5** — `global_assets` non vide (au moins 1 personnage et 1 lieu enregistrés)
- [ ] **E6** — `master_timeline.absolute_timestamps` couvre tous les shots de l'épisode

## F. Cohérence inter-épisodes (si EP > 01)

- [ ] **F1** — Aucun personnage ne change de `physical_description` entre épisodes sans `canon_locked: false` dans son asset
- [ ] **F2** — Les `lut_id` des lieux récurrents sont identiques entre épisodes
- [ ] **F3** — Le `emotional_arc` de chaque personnage est continu (état EP_N correspond à la fin de EP_N-1)
- [ ] **F4** — `episode_offsets` de la `Timeline` sont cohérents avec les durées des épisodes précédents

---

## Exécution automatique

```bash
# Lancer la checklist complète sur un épisode
python -m aiprod_adaptation.consistency.continuity_checker \
    --ir out/district_zero_ep01_production_cut_ir.json \
    --registry tasks/corrections/plans/02_asset_registry_schema.json \
    --output out/district_zero_ep01_continuity_report.json
```

---

## Seuils de blocage

| Score | Action |
|-------|--------|
| 100% ✅ | Export autorisé |
| ≥ 90% ✅ | Export conditionnel — signaler les items manquants |
| < 90% ✅ | **Export BLOQUÉ** — corriger avant de continuer |
