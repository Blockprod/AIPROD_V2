---
title: Plan d'action — Production Ready
creation: 2026-04-21 à 10:14
last_updated: 2026-04-21 à 11:22
status: completed — 39/39 tests verts, mypy strict, ruff, backends/
objectif: Transformer AIPROD_V2 en système 100% production ready
---

# Plan d'action — AIPROD_V2 Production Ready

---

## État courant (21 avril 2026 — après exécution axes F+T)

| Composant | État |
|---|---|
| Pipeline 4 passes | ✅ opérationnel |
| 33/33 tests | ✅ verts |
| TypedDicts inter-passes | ✅ câblés |
| `core/rules/` centralisé | ✅ fait |
| CLI utilisable | ✅ argparse complet |
| Épisodes multi-segments | ✅ episode_id dynamique |
| Texte réel testé | ✅ chapter1.txt + smoke test |
| README synchronisé | ✅ à jour |
| mypy strict | ✅ 0 erreur sur 13 fichiers |
| ruff | ✅ 0 warning |
| Consommateur JSON défini | ✅ Option C — IR universel + couche `backends/` |

---

## AXE 1 — FONCTIONNEL

> Objectif : le pipeline tourne sur de vrais fichiers et produit une sortie exploitable.

### F1 — CLI avec argument de fichier ✅ FAIT

**Implémenté dans** : `main.py` (réécriture complète)

```bash
python main.py --input chapter.txt --title "Episode 1" --episode-id EP01 --output out.json
```

**Résultat** :
- `--input FILE` (requis) — chemin absolu ou relatif
- `--title TITLE` (optionnel — défaut : nom du fichier sans extension)
- `--episode-id ID` (optionnel — défaut : EP01)
- `--output FILE` (optionnel — défaut : stdout)
- erreur claire + sys.exit(1) si fichier introuvable

---

### F2 — Support multi-épisodes (épisode_id dynamique) ✅ FAIT

**Implémenté dans** : `pass4_compile.py`, `engine.py`

**Résultat** :
- `compile_episode(scenes, shots, title, episode_id="EP01")` — paramètre avec défaut
- `run_pipeline(text, title, episode_id="EP01")` — propagé depuis engine
- `compile_output` (alias backward-compat) mis à jour en conséquence
- 33/33 tests verts — tests EP01 passent via défaut

---

### F3 — Texte narratif réel ✅ FAIT

**Implémenté dans** : `examples/chapter1.txt`, `tests/test_pipeline.py` (`TestRealText`)

**Résultat** :
- `chapter1.txt` : 4 personnages (Marcus, Clara, Thomas, Sofia), 4 lieux, dialogues, pensées, time shifts
- `TestRealText::test_real_text_no_crash` : vérifie ≥3 scènes, ≥1 shot, durées valides
- E2E validé : JSON bien formé sur stdout, logs sur stderr

---

## AXE 2 — TECHNIQUE

> Objectif : zéro dette statique, documentation à jour.

### T1 — Validation mypy ✅ FAIT

**Corrections appliquées** (4 fichiers) :
- `pass1_segment.py` : `_build_scene() -> dict` → `-> RawScene`, `List[dict]` → `List[RawScene]`
- `pass2_visual.py` : `output: List[dict]` → `List[VisualScene]`
- `pass3_shots.py` : `shots: List[dict]` → `List[ShotDict]`

**Résultat** : `Success: no issues found in 13 source files` — aucun `# type: ignore`

---

### T2 — Mise à jour README ✅ FAIT

**Résultat** :
- Architecture : `core/rules/`, `models/intermediate.py`, `examples/chapter1.txt` ajoutés
- Usage : nouveaux arguments CLI documentés (`--input`, `--title`, `--episode-id`, `--output`)
- Tests : 33 test cases, 8 catégories
- Pipeline passes : signatures TypedDict exactes
- Section "Développement" : séquence lint ruff + mypy + pytest

---

### T3 — Commande de lint standardisée ✅ FAIT

**Résultat** :
- `ruff>=0.1` ajouté dans `pyproject.toml` `[project.optional-dependencies] dev`
- `[tool.mypy]` déjà présent (python_version=3.11, strict=true)
- Séquence lint documentée dans README section "Développement"
- Vérification : ruff ✅ mypy ✅ pytest ✅ (33/33)

---

## AXE 3 — STRATÉGIQUE

> Objectif : définir ce qui consomme le JSON et finaliser le format de sortie.

### S1 — Définir le consommateur du JSON ✅ FAIT

**Décision** : Option C — IR universel + couche `backends/` indépendante.

**Principe retenu** : `Shot` = IR minimal agnostique du renderer. Le core ne connaît jamais les backends.
Détail complet dans `tasks/corrections/plans/backends_ir_plan.md`.

---

### S2 — Enrichissement du prompt shot ✅ FAIT

**Solution appliquée** : `metadata: dict[str, Any] = {}` ajouté dans `Shot` (Pydantic) et `ShotDict` (TypedDict).
Champ réservé aux backends — jamais utilisé par le core.

**Résultat** :
- `pass3_shots.py` peuple `metadata={}` dans chaque shot
- Les backends image/vidéo futurs enrichiront ce champ sans toucher au core
- 39/39 tests verts, mypy strict 0 erreur

---

### S3 — Interface de production ✅ FAIT

**Solution appliquée** : Option A (`--output FILE`) + flag `--format`.

**Résultat** :
- `main.py --output output.json` écrit le résultat dans un fichier
- `main.py --format csv` — sortie CSV via `CsvExport`
- `main.py --format json-flat` — liste plate de shots via `JsonFlatExport`
- logs structlog toujours sur stderr (inchangé)
- backends extensibles via `BackendBase` ABC dans `backends/base.py`

---

## Ordre d'exécution

```
F1 (CLI argparse)              ✅ FAIT — 2026-04-21
    ↓
F2 (episode_id dynamique)      ✅ FAIT — 2026-04-21
    ↓
T1 (mypy)                      ✅ FAIT — 2026-04-21
    ↓
F3 (texte réel + smoke test)   ✅ FAIT — 2026-04-21
    ↓
T2 + T3 (README + lint)        ✅ FAIT — 2026-04-21
    ↓
S1 (décision consommateur)     ✅ FAIT — 2026-04-21 (Option C — IR universel + backends/)
    ↓
S2 (enrichissement prompt)     ✅ FAIT — 2026-04-21 (metadata: dict[str, Any])
    ↓
S3 (interface production)      ✅ FAIT — 2026-04-21 (--output + --format csv/json-flat)
```

---

## Invariants à respecter tout au long

- **32/32 tests verts** à chaque étape
- **`test_json_byte_identical` doit toujours passer**
- **Zéro `# type: ignore`** dans le code
- **structlog → stderr uniquement**, JSON sur stdout
- **Aucun `random/uuid/datetime/set`** dans `core/`
- **Aliases préservés** : `transform_visuals`, `atomize_shots`, `compile_output`

---

## Définition de "Production Ready" — ATTEINT ✅

1. ✅ `python main.py --input FILE --title "Titre"` tourne sur n'importe quel fichier narratif
2. ✅ mypy + ruff + pytest passent sans erreur ni warning (39/39)
3. ✅ Le consommateur du JSON est défini (IR universel + `backends/`) et le format validé bout en bout
4. ✅ README reflète l'état réel du code
5. ✅ Un texte narratif réel a été traité et validé (`chapter1.txt`)
