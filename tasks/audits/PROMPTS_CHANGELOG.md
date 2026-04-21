# PROMPTS CHANGELOG — AIPROD_V2

> Historique de tous les prompts de refactoring et d'amélioration appliqués au projet.
> Une ligne = une session de travail ayant modifié le codebase.

| Date | Session | Fichiers modifiés | Description |
|---|---|---|---|
| 2026-04-20 | Refactoring 1/6 | `models/schema.py` | Suppression `Field(ge=3, le=8)` sur `Shot.duration_sec` — contrainte déplacée en Pass 4 |
| 2026-04-20 | Refactoring 2/6 | `pass1_segment.py` | Réécriture segmenteur — clé `raw_text`, format `SCN_XXX`, triggers location/time/paragraphe |
| 2026-04-20 | Refactoring 3/6 | `pass2_visual.py` | Réécriture visual rewrite — `_INTERNAL_THOUGHT_WORDS`, `EMOTION_RULES`, `_DIALOGUE_RE` |
| 2026-04-20 | Refactoring 4/6 | `pass3_shots.py` | Réécriture shot decomposition — `simplify_shots`, shot_id `SCN_XXX_SHOT_XXX`, durée [3,8] |
| 2026-04-20 | Refactoring 5/6 | `pass4_compile.py`, `engine.py` | Réécriture compilation + orchestration — `compile_episode`, structlog |
| 2026-04-20 | Refactoring 6/6 | `test_pipeline.py`, `main.py`, `engine.py` | Fix 7 tests échoués, title `"Sample Episode"`, logs stderr |
