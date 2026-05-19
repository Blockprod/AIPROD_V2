---
type: plan_action
audit_source: audit_system_architect_aiprod.md
date: 2026-05-19
creation: 2026-05-19 à 15:50
corrections_total: 11
p1: 3
p2: 5
p3: 3
---

# PLAN D'ACTION — SYSTEM ARCHITECT — 2026-05-19

**Source** : tasks/audits/resultats/audit_system_architect_aiprod.md
**Généré le** : 2026-05-19 à 15:50
**Corrections totales** : 11 (P1:3 P2:5 P3:3)

## Résumé

L'audit identifie un compilateur cinématographique mature (core IR = production-grade) mais dont le
runtime d'orchestration et la gouvernance sont research-grade. Les 3 risques immédiats sont : la
dégradation silencieuse de `reference_anchor_strength` via des slugs VisualBible invalides, l'absence
de versioning IR permettant des runs de production sur IR obsolète, et le bypass du contrat P2 par le
chemin `ScriptParser`. Les autres corrections stabilisent la qualité et la maintenabilité à long terme.

---

## Corrections P1 — CRITIQUE

### [ID-01] — validate_slugs() VisualBible avant tout run
**Priorité** : P1
**Sévérité** : 🔴 S-01
**Fichiers** :
- `aiprod_adaptation/core/pass3_shots.py:~L603`
- `aiprod_adaptation/core/pass1_segment.py:L285–316`
- `aiprod_adaptation/core/pass2_visual.py:L465–477`
- `aiprod_adaptation/core/pass3_shots.py:L198–210`
- `aiprod_adaptation/core/global_coherence/prompt_finalizer.py:L61–98`
**Problème** : Si un slug VisualBible est manquant ou renommé, `anchor_strength` tombe
silencieusement de 0.9 à 0.5 (`anchor_strength: float = 0.9 if reference_location_id else 0.5`).
Aucun warning, aucune exception. À 40% de slugs invalides, tout l'épisode perd la cohérence de
référence DoP sans alerte.
**Action** :
1. Ajouter une méthode `validate_slugs(ir: AIPRODOutput) -> list[str]` sur `VisualBible` qui
   retourne les slugs référencés dans l'IR mais absents de la Bible.
2. Appeler cette méthode dans `engine.py:run_pipeline()` juste avant le début de P3, lever
   `ValueError` si des slugs manquent.
3. Optionnel (safer) : émettre un `warnings.warn()` en mode "lax" configuré par flag.
```python
# À ajouter dans engine.py, après compilation P2, avant P3
if visual_bible:
    missing = visual_bible.validate_slugs(cinematic_scenes)
    if missing:
        raise ValueError(f"VisualBible: slugs manquants : {missing}")
```
**Tests impactés** :
- Ajouter `tests/test_visual_bible_slugs.py` avec fixture slug manquant → expect ValueError
- Vérifier `tests/test_pass3_shots.py` : les cas avec VisualBible doivent avoir des slugs valides
**Risque** : Faible — détection d'erreurs existantes silencieuses, n'altère pas le comportement
normal

---

### [ID-02] — IRVersion hash dans AIPRODOutput
**Priorité** : P1
**Sévérité** : 🔴 S-04
**Fichiers** :
- `aiprod_adaptation/models/schema.py` (AIPRODOutput)
- `aiprod_adaptation/core/pass4_compile.py`
- `production/gen_shots_v4.py`
**Problème** : Il n'y a pas de versioning de l'IR entre runs. Si la VisualBible ou les règles changent
entre deux runs de production, `gen_shots_v4.py` peut continuer sur un `storyboard.json` qui référence
un IR obsolète. Non détectable — le checkpoint reprend mais les décisions P3/P4 sont périmées.
**Action** :
1. Ajouter un dataclass `IRVersion` (frozen) dans `schema.py` :
```python
from dataclasses import dataclass
import hashlib, json

@dataclass(frozen=True)
class IRVersion:
    compiler_version: str
    visual_bible_hash: str   # sha256(json.dumps(visual_bible, sort_keys=True))
    rules_hash: str          # sha256 de builtin_rules module source
    text_hash: str           # sha256 du texte source input

class AIPRODOutput(BaseModel):
    ir_version: IRVersion | None = None   # None = backward-compat
    # ... champs existants inchangés
```
2. Calculer et injecter `IRVersion` en fin de `pass4_compile.py`.
3. Dans `gen_shots_v4.py:run_all()`, vérifier que le hash VisualBible du checkpoint correspond
   à l'IR courant ; logguer un warning si mismatch.
**Tests impactés** :
- `tests/test_schema.py` : vérifier `IRVersion` présent dans le JSON de sortie
- Aucune régression prévue (champ optionnel `None` = backward-compat)
**Risque** : Faible — champ optionnel, backward-compatible, pas de logique métier modifiée

---

### [ID-03] — Contrat P2 sur chemin ScriptParser
**Priorité** : P1
**Sévérité** : 🔴 B-01
**Fichier** : `aiprod_adaptation/core/engine.py:L229`
**Problème** : Quand `input_type == "script"`, `ScriptParser.parse()` retourne directement
`list[VisualScene]` en bypassant Pass 1 et Pass 2. `_validate_pass2_output()` n'est jamais appelé
sur ce chemin. Les champs P2 (`physical_actions`, `body_language_states`, `emotional_beat_index`)
peuvent être absents ou incorrects — Pass 3 reçoit des données non validées.
**Action** :
Dans `engine.py`, après l'appel à `ScriptParser.parse()`, appeler explicitement
`_validate_pass2_output()` sur les scènes retournées (import depuis `pass2_visual`).
```python
# engine.py ~L229 — après ScriptParser.parse()
from aiprod_adaptation.core.pass2_visual import _validate_pass2_output

scenes: list[VisualScene] = ScriptParser(text).parse()
_validate_pass2_output(scenes)   # contrat P2 même sur chemin script
```
**Tests impactés** :
- `tests/test_engine.py` : ajouter cas `input_type=script` avec champ P2 manquant → expect ValueError
- Vérifier que les fixtures script existantes ont des champs P2 valides
**Risque** : Moyen — peut casser des fixtures existantes si elles ont des champs P2 absents.
Inspecter `tests/` avant application.

---

## Corrections P2 — IMPORTANT

### [ID-04] — Contrat complet pour champs TypedDict NotRequired restants
**Priorité** : P2
**Sévérité** : 🟠 S-02
**Fichier** : `aiprod_adaptation/core/pass3_shots.py:~L580`
**Problème** : Plusieurs champs `NotRequired` de `VisualScene` sont consommés via `.get()` avec
fallback silencieux en P3 : `beat_type`, `emotional_layer`, `scene_type`, `character_movements`. Si
ces champs sont absents (edge case, bug P2, chemin script), les lookups `INTENSITY_SHOT_SEQUENCES`
dégradent vers des fallbacks sans aucun log.
**Note** : `_validate_pass2_output()` couvre déjà `action_intensity`, `emotion`,
`emotional_beat_index`, `body_language_states`. Il reste : `beat_type`, `emotional_layer`,
`scene_type`, `character_movements`.
**Action** :
Étendre `_validate_pass2_output()` dans `pass2_visual.py` pour vérifier les champs restants
critiques (au minimum `beat_type` — utilisé comme clé de lookup dans P3) :
```python
# Dans _validate_pass2_output(), après les checks existants
beat_type = scene.get("beat_type")
if not beat_type:
    raise ValueError(f"PASS 2: scene '{scene_id}' manque beat_type (requis par P3 INTENSITY_SHOT_SEQUENCES).")
```
**Tests impactés** : `tests/test_pass2_visual.py`, `tests/test_pass3_shots.py`
**Risque** : Faible — extension du validateur existant

---

### [ID-05] — Formaliser VisualBible None vs VisualBible vide
**Priorité** : P2
**Sévérité** : 🟠 A-01
**Fichiers** :
- `aiprod_adaptation/core/visual_bible.py`
- `aiprod_adaptation/core/pass1_segment.py`, `pass2_visual.py`, `pass3_shots.py`, `pass4_compile.py`
**Problème** : `visual_bible=None` skippe silencieusement tous les enrichissements VisualBible.
La distinction `None` (non fournie) vs `VisualBible({})` (vide intentionnel) n'est pas formalisée.
Les 4 passes testent `if visual_bible:` sans message clair sur le comportement attendu.
**Action** :
1. Ajouter une méthode de classe `VisualBible.empty() -> VisualBible` qui retourne une instance
   explicitement vide (vs `None`).
2. Documenter la politique dans le type hint : `visual_bible: VisualBible | None = None`
   signifie "désactivé" (pas "vide"). Ajouter une assertion au début de chaque passe :
```python
# Au début de visual_rewrite(), simplify_shots(), etc.
if visual_bible is None:
    import warnings
    warnings.warn("VisualBible non fournie — enrichissements désactivés.", stacklevel=2)
```
**Tests impactés** : Aucun test existant ne devrait régresser
**Risque** : Faible — ajout de warning non bloquant

---

### [ID-06] — Déplacer resolve_lens_mm / resolve_color_grade / _resolve_lighting_directive de P3 à P4
**Priorité** : P2
**Sévérité** : 🟠 A-03
**Fichier** : `aiprod_adaptation/core/pass3_shots.py`
**Problème** : Trois fonctions de direction artistique sont exécutées en P3 alors qu'elles
appartiennent conceptuellement à la couche P4 (enrichissement VisualBible + règles de compilation) :
- `resolve_lens_mm()` — direction photographique
- `resolve_color_grade()` — post-production
- `_resolve_lighting_directive()` — direction artistique
Un changement de règle `color_grade` doit être fait dans `pass3_shots.py` — contre-intuitif.
**Action** :
1. Déplacer les 3 fonctions dans `pass4_compile.py` (ou un module `pass4_art_direction.py`).
2. Dans P3, laisser les champs non résolus avec une valeur sentinelle (ex: `"__unresolved__"`).
3. En P4, appeler les 3 fonctions sur chaque shot avant `finalize_prompts()`.
**Tests impactés** : Tests unitaires P3 et P4 — les champs résolus seront now produits par P4.
**Risque** : Élevé — refactoring inter-passes. À faire en branche dédiée avec snapshot test
(before/after JSON de sortie doivent être identiques). Ne pas mélanger avec d'autres corrections.

---

### [ID-07] — Séparation config dev/prod pour _BUDGET_ALERT_USD
**Priorité** : P2
**Sévérité** : 🟠 — section 4.3
**Fichier** : `production/gen_shots_v4.py`
**Problème** : `_BUDGET_ALERT_USD = 250.0` est hardcodé. Il n'y a pas de profil d'environnement.
Un dev qui lance `gen_shots_v4.py` en test peut déclencher $250 de coûts Replicate par inadvertance.
Le flag `--budget-cap` ajouté en session courante atténue mais ne protège pas par défaut.
**Action** :
1. Lire `AIPROD_BUDGET_CAP_USD` depuis l'environnement avec fallback sécurisé :
```python
import os
_BUDGET_ALERT_USD: float = float(os.environ.get("AIPROD_BUDGET_CAP_USD", "0.0"))
# Default 0.0 = tout run sans --budget-cap ou var env est bloqué
```
2. Ajouter un `.env.example` avec `AIPROD_BUDGET_CAP_USD=250.0` pour la prod.
3. Documenter dans README production que le cap doit être explicitement configuré.
**Tests impactés** : `tests/test_gen_shots_v4.py` — mock env var dans les tests
**Risque** : Faible — seule la valeur par défaut change (plus restrictive)

---

### [ID-08] — DAG parallèle pour gen_shots_v4 (scalabilité)
**Priorité** : P2
**Sévérité** : 🔴 S-03
**Fichier** : `production/gen_shots_v4.py:run_all()`
**Problème** : `run_all()` est une boucle `for shot_id in shot_ids` 100% séquentielle. Pour EP01
(35 shots × ~30s Blender), la séquentialité est acceptable. Pour 10 épisodes × 35 shots = 350 shots,
le throughput est ×1 peu importe le hardware disponible. Le budget guard `_count_frames()` fait aussi
O(n) appels filesystem avant le premier shot.
**Action** (implémentation incrémentale — ne pas tout faire en une fois) :
1. **Court terme** : Extraire une fonction `_process_single_shot(shot_id, …)` pure pour faciliter
   la parallélisation future.
2. **Moyen terme** : Remplacer la boucle par `concurrent.futures.ThreadPoolExecutor(max_workers=N)`
   avec `N` configurable via `--max-workers` (défaut: 1 = séquentiel backward-compat).
3. **Long terme** : DAG complet avec dépendances explicites (voir section 5.2 de l'audit).
**Tests impactés** : `tests/test_gen_shots_v4.py` — mock filesystem + API calls
**Risque** : Élevé pour moyen/long terme. Court terme (extraction fonction pure) = risque faible.
Implémenter en 3 PRs séparées.

---

## Corrections P3 — MINEUR

### [ID-09] — Registre de règles unifié (règles dispersées dans 6 modules)
**Priorité** : P3
**Sévérité** : 🟠 A-02
**Fichiers** :
- `pass1_segment.py`, `pass2_visual.py`, `pass3_shots.py`
- `rule_engine/builtin_rules.py`
- `global_coherence/consistency_checker.py`, `global_coherence/prompt_finalizer.py`
**Problème** : Les règles cinématographiques sont dans 6 fichiers. Modifier une règle de style
(ex: "une scène climax doit avoir un plan large d'ouverture") nécessite de chercher dans tout le
codebase. Fausse modularité — les passes semblent indépendantes mais partagent les mêmes domaines.
**Action** :
1. Créer `aiprod_adaptation/core/rules/RULES_REGISTRY.md` qui documente chaque règle
   avec son emplacement précis (chemin + ligne).
2. À terme : externaliser les tables de données pures (ex: `INTENSITY_SHOT_SEQUENCES`,
   `CAMERA_MOVEMENT_RULES_V3`) dans des fichiers YAML chargés au démarrage.
**Tests impactés** : Aucun (documentation d'abord)
**Risque** : Nul (phase 1 = documentation uniquement)

---

### [ID-10] — LLMRouter cooldown par endpoint, pas global
**Priorité** : P3
**Sévérité** : 🟡 B-02
**Fichier** : `aiprod_adaptation/core/adaptation/llm_router.py:L153–178`
**Problème** : Le cooldown est global par provider. Un timeout réseau sur une requête longue
met Claude en cooldown 300s — même pour des requêtes courtes qui auraient réussi. Perte de
disponibilité inutile.
**Action** :
Remplacer `dict[str, float]` cooldown par `dict[tuple[str, str], float]` clé `(provider, request_type)`.
Distinguer au minimum `request_type in {"short", "long"}` basé sur `token_threshold`.
**Tests impactés** : `tests/test_llm_router.py`
**Risque** : Faible — changement interne du LLMRouter, non visible hors du module

---

### [ID-11] — metrics_v4.jsonl : index partiel pour éviter scan linéaire
**Priorité** : P3
**Sévérité** : 🟡 — section 4.2
**Fichier** : `production/metrics_v4.jsonl`
**Problème** : `metrics_v4.jsonl` est un fichier append-only sans index. Retrouver les shots KO
quality gate = scan linéaire O(n). À 350 shots (10 épisodes), acceptable. À 10 000 shots, lent.
**Action** :
1. Ajouter une fonction `load_failed_shots(jsonl_path) -> list[str]` dans `gen_shots_v4.py`
   qui filtre les lignes `"quality_gate": "FAIL"` à la lecture.
2. Optionnel : générer un `metrics_v4_index.json` (dict `shot_id → line_number`) mis à jour
   en append à chaque écriture.
**Tests impactés** : `tests/test_gen_shots_v4.py`
**Risque** : Nul (fonction utilitaire additive)

---

## Ordre d'exécution recommandé

| Ordre | ID | Titre | Durée estimée |
|:---:|---|---|---|
| 1 | [ID-01] | validate_slugs() VisualBible | ~30 lignes + test |
| 2 | [ID-03] | Contrat P2 sur chemin ScriptParser | ~5 lignes + test |
| 3 | [ID-04] | Contrat TypedDict NotRequired restants | ~15 lignes |
| 4 | [ID-02] | IRVersion hash dans AIPRODOutput | ~40 lignes + test |
| 5 | [ID-05] | Formaliser VisualBible None vs vide | ~20 lignes |
| 6 | [ID-07] | Séparation config dev/prod budget cap | ~10 lignes |
| 7 | [ID-08-court] | Extraire _process_single_shot() | ~refactor |
| 8 | [ID-10] | LLMRouter cooldown par endpoint | ~20 lignes |
| 9 | [ID-11] | metrics_v4.jsonl load_failed_shots() | ~10 lignes |
| 10 | [ID-09] | RULES_REGISTRY.md documentation | ~doc uniquement |
| 11 | [ID-06] | Déplacer resolve_lens_mm/color_grade/lighting | branche dédiée |

> **Note** : [ID-06] (A-03) doit être fait en branche dédiée avec snapshot test avant/après.
> Ne pas mixer avec d'autres corrections.
> **[ID-08] moyen/long terme** (DAG parallèle) = feature majeure, planifier en sprint dédié.

---

## Validation finale

```powershell
# Après chaque correction P1
venv\Scripts\Activate.ps1
$env:PYTHONIOENCODING="utf-8"

# Tests unitaires
pytest aiprod_adaptation/tests/ -v

# Qualité statique
ruff check .
mypy aiprod_adaptation/ --strict

# Vérifier aucun type:ignore introduit
Select-String -Recurse -Pattern "type: ignore" aiprod_adaptation/ | Select-Object Path, LineNumber, Line
```

### Critères de succès

- [ ] `pytest aiprod_adaptation/tests/ -v` → 100% green (1072+ tests)
- [ ] `ruff check .` → 0 erreurs
- [ ] `mypy aiprod_adaptation/ --strict` → exit 0
- [ ] Aucun `# type: ignore` dans le codebase
- [ ] `_validate_pass2_output()` appelé sur TOUS les chemins d'entrée (script + roman + LLM)
- [ ] `validate_slugs()` lève ValueError sur slug VisualBible manquant
- [ ] `IRVersion` présent dans `AIPRODOutput` JSON de sortie
- [ ] `_BUDGET_ALERT_USD` ne peut plus être 250$ par défaut sans configuration explicite
