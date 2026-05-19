---
audit: system_architect
version: 1.0
date: 2026-05-19
modele: claude-sonnet-4.6
perimetre: aiprod_adaptation/ · pipeline/ · production/
---

# AUDIT SYSTEM ARCHITECT — AIPROD_V2
## Deep Architectural Analysis — Cinematic Compiler Pipeline

> Produit par : `tasks/audits/code/audit_system_architect_prompt.md`
> Codebase explorée : `C:\Users\averr\AIPROD_V2` (commit `aa68ab2`)

---

## CLASSIFICATION SYSTÈME (VERDICT PRÉALABLE)

**Ce système est** : un **compilateur cinématographique déterministe hybridé** avec une couche générative optionnelle et un runtime d'orchestration de production.

Il ne se comporte pas comme un pipeline naïf. Il ne se comporte pas comme un système agent pur. Il se comporte comme **un compilateur à passes multiples avec un backend génératif sandboxé et un système d'orchestration de production séparé**.

Analogie exacte :
```
AIPROD_V2 ≅ LLVM (IR compiler) + CMake (build orchestration) + CUDA runtime (stochastic execution)
                ↑ deterministic           ↑ production scripting      ↑ GPU/API calls
```

---

## 1. ANALYSE DE VÉRITÉ ARCHITECTURALE

### 1.1 Graphe de contrôle réel

```
TEXT INPUT
    │
    ▼
[InputClassifier.classify()]  ──────── DETERMINISTIC (regex)
    │
    ├─► input_type == "script"
    │       └─► ScriptParser.parse()  ──── DETERMINISTIC
    │               └─► list[VisualScene] (skip P1+P2)
    │
    └─► input_type == "novel"
            │
            ├─► pipeline_mode == "generative" OR "auto"
            │       └─► StoryExtractor.extract_all(llm)  ⚠️ STOCHASTIC
            │               └─► list[VisualScene] via LLM
            │
            └─► pipeline_mode == "deterministic" OR llm fallback
                    ├─► segment(text)          [PASS 1] DETERMINISTIC
                    └─► visual_rewrite(scenes) [PASS 2] DETERMINISTIC

                            │
                            ▼
                    StoryValidator.validate_all()   DETERMINISTIC
                            │
                            ▼
                    simplify_shots(scenes)          [PASS 3] DETERMINISTIC
                            │
                            ▼
                    compile_episode(scenes, shots)  [PASS 4] DETERMINISTIC
                    ├─► check_and_enrich()          (R01–R04)
                    ├─► RuleEvaluator.evaluate()    (9 rules, P1–P5)
                    ├─► ConflictResolutionEngine    (HARD/SOFT)
                    └─► finalize_prompts()          (R05–R09)
                            │
                            ▼
                    AIPRODOutput (Pydantic v2 IR)
                            │
            ┌───────────────┼──────────────────────┐
            ▼               ▼                      ▼
    image generation   video generation       post-prod exports
    (Flux, Seedream,   (Runway, Kling,        (EDL, Resolve,
     ComfyUI, …)        Seedance, …)           audio cues)
    ⚠️ STOCHASTIC      ⚠️ STOCHASTIC           DETERMINISTIC
```

### 1.2 Où le déterminisme tient réellement

| Composant | Déterministe | Fichier | Preuve |
|---|:---:|---|---|
| Pass 1 — segmentation | ✅ | `pass1_segment.py` | Règles R01–R12, tables de phrases, zero LLM |
| Pass 2 — visual rewrite | ✅ | `pass2_visual.py` | `EMOTION_BODY_LANGUAGE`, `EMOTION_RULES`, zero LLM |
| Pass 3 — shot atomization | ✅ | `pass3_shots.py` | `INTENSITY_SHOT_SEQUENCES`, `CAMERA_MOVEMENT_RULES_V3` |
| Pass 4 — rule engine | ✅ | `pass4_compile.py` + `rule_engine/` | Evaluation triée `(priority ASC, id ASC)` |
| Conflict resolution | ✅ | `conflict_resolver.py:45–61` | `_MOVEMENT_DOWNGRADE_CHAIN` pure lookup |
| JSON output | ✅ | `schema.py` | Pydantic v2 `.model_dump_json()` stable |
| Métriques qualité | ✅ | `metrics/engine.py` | Formules pures, zero randomness |

### 1.3 Points d'injection stochastique réels

| Point d'injection | Fichier | Ligne | Contrôle |
|---|---|:---:|---|
| StoryExtractor LLM call | `core/adaptation/story_extractor.py` | ~L62 | Gated par `pipeline_mode != "deterministic"` |
| ClaudeAdapter | `core/adaptation/claude_adapter.py` | L56 | Optionnel, `NullLLMAdapter` par défaut |
| GeminiAdapter | `core/adaptation/gemini_adapter.py` | L127 | Optionnel, retry backoff exponentiel |
| Image gen (Flux, Seedream…) | `image_gen/` adapters | — | Hors AIPRODOutput, couche production |
| Video gen (Kling, Runway…) | `video_gen/` adapters | — | Hors AIPRODOutput, couche production |
| ComfyUI (shot_pipeline_v4) | `pipeline/shot_pipeline_v4.py` | L174 | uuid client ID (non-IR) |

**Conclusion** : Le déterminisme est **réel et correctement borné**. Les LLMs sont des entrées optionnelles dans la couche d'extraction narrative, pas des décideurs à l'intérieur du compilateur IR. La frontière `pipeline_mode` est le vrai garde-fou.

---

## 2. ZONES DE FAIBLESSE STRUCTURELLE

### 🔴 S-01 — Coupling VisualBible × 4 passes simultanées
**Sévérité : S (critique)**

`VisualBible` est injectée dans les 4 passes sans contrat formel :
- `pass1_segment.py:L285–316` : slug matching
- `pass2_visual.py:L465–477` : wardrobe + lighting fragments
- `pass3_shots.py:L198–210` : lighting directives + composition
- `pass4_compile.py (prompt_finalizer.py:L61–98)` : prompt enrichment

**Problème** : Si une entrée VisualBible change (format, champ manquant, slug renommé), la propagation du bug est silencieuse. Il n'y a pas de contrat de version sur `VisualBible`. Un slug modifié en P1 produit `reference_anchor_strength = 0.5` au lieu de `0.9` en P3 — dégradation qualité non détectée.

**Preuve** : `pass3_shots.py` ligne ~L603 :
```python
anchor_strength: float = 0.9 if reference_location_id else 0.5
```
Un slug manquant tombe en silence à 0.5. Aucun warning. Aucune erreur.

---

### 🔴 S-02 — TypedDict NotRequired = surface d'erreur silencieuse
**Sévérité : S (critique)**

`CinematicScene`, `VisualScene`, `ShotDict` utilisent des `TypedDict` avec `NotRequired`. Les passes suivantes accèdent à ces champs via `.get()` avec fallback :

```python
# pass3_shots.py ~L580
beat_type:      str | None = scene.get("beat_type")
action_intensity: str | None = scene.get("action_intensity")
emotional_layer:  str | None = scene.get("emotional_layer")
```

**Problème** : Si Pass 2 ne produit pas `action_intensity` (bug, edge case), Pass 3 reçoit `None`, et les lookups dans `INTENSITY_SHOT_SEQUENCES[(beat_type, action_intensity)]` dégradent silencieusement vers les fallbacks. Pas d'exception, pas de log — comportement altéré non détectable.

**Note** : Le `_validate_pass2_output()` ajouté en session courante atténue ce risque pour `action_intensity`, `emotion`, `emotional_beat_index`, `body_language_states`. Mais les autres champs `NotRequired` restent sans contrat.

---

### 🟠 A-01 — VisualBible est un singleton implicite partagé
**Sévérité : A (majeure)**

`VisualBible` est passé comme argument optionnel à chaque passe. Si `visual_bible=None`, les enrichissements sont silencieusement skippés avec des résultats dégradés. Il n'existe pas de "VisualBible vide" explicite — la distinction `None` vs `VisualBible({})` n'est pas formalisée.

**Impact à l'échelle** : Avec 10 épisodes en parallèle, chaque run pourrait utiliser une version différente de VisualBible (si mutée entre runs). Pas de versioning.

---

### 🟠 A-02 — Règles métier dispersées dans 6 modules
**Sévérité : A (majeure)**

Les règles cinématographiques sont réparties dans :
- `pass1_segment.py` : R01–R12 (segmentation rules)
- `pass2_visual.py` : `EMOTION_RULES`, `EMOTION_BODY_LANGUAGE`, `SCENE_TYPE_ACTION_MODIFIERS`
- `pass3_shots.py` : `INTENSITY_SHOT_SEQUENCES`, `CAMERA_MOVEMENT_RULES_V3`, `FEASIBILITY_BASE_SCORES`
- `pass4_compile.py` → `rule_engine/builtin_rules.py` : 9 règles P1–P5
- `global_coherence/consistency_checker.py` : R01–R04
- `global_coherence/prompt_finalizer.py` : R05–R09

**Problème** : Modifier une règle cinématographique (ex: "une scène de climax devrait toujours avoir un plan large d'ouverture") nécessite de chercher dans 6 fichiers. Il n'y a pas de registre de règles unifié. Cela produit de la fausse modularité — les passes semblent indépendantes mais partagent les mêmes domaines de règles.

---

### 🟠 A-03 — Fausse modularité : pass3_shots.py intègre de la logique P4
**Sévérité : A (majeure)**

`pass3_shots.py` contient :
- `resolve_lens_mm()` — logique de direction photographique
- `resolve_color_grade()` — logique de post-production
- `_resolve_lighting_directive()` — logique de direction artistique

Ces fonctions appartiennent conceptuellement à la couche P4 (compilation épisode + VisualBible enrichment), mais sont exécutées en P3. La conséquence : un changement de règle de `color_grade` pour une tonalité de scène doit être fait dans `pass3_shots.py`, pas dans `pass4`.

---

### 🟡 B-01 — ScriptParser bypasse P1+P2 sans vérification de contrat
**Sévérité : B (mineure)**

Quand `input_type == "script"`, `engine.py:L229` appelle `ScriptParser.parse()` qui retourne directement `list[VisualScene]`, skippant Pass 1 et Pass 2 complètement. `_validate_pass2_output()` n'est jamais appelé sur ce chemin. Les champs P2 (`physical_actions`, `body_language_states`, `emotional_beat_index`) peuvent être absents ou incorrects sans détection.

---

### 🟡 B-02 — LLMRouter : cooldown global, pas par endpoint
**Sévérité : B (mineure)**

`llm_router.py:L153–178` implémente un cooldown global par provider. Si Claude rate sur une requête longue (timeout réseau), il est mis en cooldown pour 300 secondes — même pour des requêtes courtes qui auraient réussi. Pas de distinction par type de request/endpoint.

---

## 3. ANALYSE GOUVERNANCE & FLUX DE CONTRÔLE

### 3.1 Y a-t-il un vrai control plane ?

**Réponse courte : non — il y a une orchestration séquentielle linéaire, pas un control plane.**

`engine.py:run_pipeline()` est le "chef d'orchestre" actuel. Il fait :
```
classify → [LLM extract | segment → visual_rewrite] → validate → simplify_shots → compile_episode
```

C'est une **chaîne séquentielle linéaire**, pas un DAG. Il n'y a pas de :
- Dépendances explicites entre passes (graphe)
- Rollback sur échec de passe
- Cache intermédiaire (si P3 échoue, il faut re-exécuter P1+P2)
- Versioning de l'IR entre passes
- Replay d'une passe isolée

### 3.2 Qui est le vrai orchestrateur ?

| Contexte | Orchestrateur |
|---|---|
| Text → AIPRODOutput (IR) | `engine.py:run_pipeline()` |
| AIPRODOutput → shots stylisés | `production/gen_shots_v4.py:run_all()` |
| Shot → clip vidéo | `pipeline/shot_pipeline_v4.py` |
| Clip → épisode assemblé | `pipeline/assembly.py` |

**Problème** : Ces 4 orchestrateurs sont **découplés**. Il n'existe pas de coordinateur qui les lie. Si `run_all()` est interrompu à mi-chemin, le checkpoint reprend depuis le dernier shot — mais aucun mécanisme ne vérifie que l'IR `AIPRODOutput` n'a pas changé entre les runs.

### 3.3 DAG ou illusion linéaire ?

**Illusion linéaire.** L'exécution est P1→P2→P3→P4 sans dépendances déclarées. En réalité :

- P3 dépend de P2 (via `visual_actions`, `emotion`, `action_intensity`)
- P4 dépend de P3 (via `feasibility_score`, `reference_anchor_strength`)
- P4/prompt_finalizer dépend de VisualBible (external state)
- gen_shots_v4 dépend de AIPRODOutput **et** de Blender renders **et** des frames PNG

Ces dépendances existent mais ne sont pas modélisées. Un DAG formel exposerait :
```
text → P1 → P2 → P3 → P4 → AIPRODOutput
                              ↓
              VisualBible ──→ P4/prompt_finalizer
              Blender ──────→ gen_shots_v4/stylize
              ComfyUI ───────→ gen_shots_v4/stylize
```

### 3.4 Gouvernance runtime manquante (classée par priorité)

| Manque | Impact | Coût d'implémentation |
|---|---|:---:|
| **IR versioning** : aucune version sur AIPRODOutput entre runs | Si `storyboard.json` change, les runs précédents sont invalides sans le savoir | Moyen |
| **Execution trace** : aucun log structuré des décisions de passes | Debugging d'une anomalie shot requiert relancer le pipeline complet | Faible |
| **Inter-pass cache** : P1/P2 recalculés même si text n'a pas changé | Coût CPU inutile en développement itératif | Faible |
| **Rollback de shot** : un shot KO quality gate → re-run sans reprendre depuis P3 | Shot échoué = re-run complet du pipeline de stylisation | Élevé |
| **Dry-run IR only** : pas de mode "compile sans générer" différent du null backend | `--backend null` simule le chemin mais ne produit pas de vrai coût | Faible |

---

## 4. ANALYSE SCALABILITÉ & DÉFAILLANCES INDUSTRIELLES

### 4.1 1 épisode → 10 épisodes

**Ce qui casse :**

🔴 **Cohérence inter-épisodes** : `consistency/asset_registry.py` et `season/` existent mais la cohérence saisonnière n'est pas vérifiée automatiquement dans le pipeline de production (`gen_shots_v4.py` ne consulte pas le `SeasonEngine`). La cohérence saison est une couche optionnelle déconnectée du runtime.

🟠 **VisualBible partagée** : Avec 10 épisodes, la VisualBible évolue (nouveaux personnages, nouvelles locations). Si le slug d'une location change entre EP01 et EP05, les `reference_location_id` des épisodes précédents sont silencieusement invalides.

🟠 **Checkpoint unique** : `checkpoint_v4.json` est un fichier plat. Avec 10 épisodes × 35 shots = 350 shots, les collisions de checkpoint entre workers parallèles sont possibles.

### 4.2 35 shots → 10 000 shots

**Ce qui casse :**

🔴 **Séquentialité forcée de gen_shots_v4** : `run_all()` est une boucle `for shot_id in shot_ids`. Zéro parallélisme. 10 000 shots × ~30s/shot (Blender + ComfyUI) = ~83 heures de rendu séquentiel.

🔴 **Budget cap pré-exécution non scalable** : Le guard pre-loop fait `_count_frames()` pour **tous** les shots restants avant de commencer. Pour 10 000 shots × `os.listdir()` = 10 000 appels filesystem. Coût O(n) avant premier shot.

🔴 **AIPRODOutput non streamable** : L'IR entier est chargé en mémoire d'un coup. Pour 10 000 shots × ~5KB/shot de métadonnées Pydantic = ~50MB — acceptable maintenant, problématique à 100K shots.

🟠 **metrics_v4.jsonl** : Écriture en append, pas d'index. Relire `metrics_v4.jsonl` pour trouver les shots KO quality gate = scan linéaire O(n).

🟠 **ComfyUI polling synchrone** : `shot_pipeline_v4.py` poll ComfyUI avec `time.sleep(2)` entre requêtes. 10 000 shots × polling overhead = gaspillage significatif de temps.

### 4.3 Développeur solo → équipe studio

**Ce qui casse :**

🔴 **Pas de locking sur storyboard.json** : Si deux développeurs modifient `storyboard.json` simultanément, les merges Git sont manuels. Pas de système de verrouillage de production.

🔴 **Pas de séparation dev/prod des configurations** : `_BUDGET_ALERT_USD = 250.0` est hardcodé. Pas de profils d'environnement. Un développeur qui teste peut déclencher 250$ de coûts Replicate par inadvertance.

🟠 **Rule engine non extensible sans code** : Ajouter une nouvelle règle cinématographique nécessite de modifier `builtin_rules.py` (code Python). Dans un studio, les DoP/superviseurs VFX ne peuvent pas contribuer des règles sans développeur.

🟠 **Pas de visualisation du graphe de décision** : Quand un shot a `feasibility_score < 40` et que le camera_movement est dégradé vers `static`, il n'y a pas de rapport lisible pour le réalisateur. `RuleEngineReport` existe mais n'est pas rendu en format humain.

### 4.4 Zones de coût exponentiel

| Zone | Cause | Coût actuel | À 100 épisodes |
|---|---|---|---|
| Image gen (Replicate) | 0.04$/frame × frames | $139.20/EP01 | ~$13,920 |
| Re-génération IR | Pas de cache P1-P4 | CPU only | ~50× si itératif |
| Quality gate re-runs | Shot KO = re-stylize complet | 1 shot coût | ×3–5 si KO rate = 20% |
| VisualBible enrichment | O(shots × characters × locations) | Négligeable | Quadratique si non indexé |

### 4.5 Ce qui ne peut pas être parallélisé

- **Passes P1→P4** : séquentielles par design (P2 dépend P1, etc.)
- **180-degree guard** (P3) : dépend de l'ordre des shots dans la scène
- **ConflictResolutionEngine** : dépend de l'ordre d'évaluation des règles
- **Checkpoint I/O** : écriture fichier unique non thread-safe

### 4.6 Dégradation silencieuse de la qualité à l'échelle

**Cas le plus dangereux :** `reference_anchor_strength` tombe à `0.5` si un slug VisualBible n'est pas trouvé. À l'échelle, si 40% des shots ont des slugs invalides, l'ensemble du rendu a `reference_anchor_strength = 0.5` sans aucune alerte. Le résultat visuel perd la cohérence de référence DoP sans que personne ne le sache.

---

## 5. REDESIGN NEXT-GENERATION

### 5.1 Architecture cible (AIPROD_V3 conceptuel)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     AIPROD CONTROL PLANE v1                             │
│  (DAG scheduler · IR versioning · Execution trace · Mode governance)    │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ orchestrates
         ┌─────────────────┼──────────────────────┐
         ▼                 ▼                      ▼
┌────────────────┐  ┌─────────────────┐  ┌────────────────────────┐
│  COMPILER      │  │  CREATIVE       │  │  PRODUCTION            │
│  LAYER (pure)  │  │  SANDBOX        │  │  RUNTIME               │
│                │  │  (gated)        │  │  (orchestration)       │
│  Pass 1–4      │  │                 │  │                        │
│  Rule Engine   │  │  LLM adapters   │  │  Blender render        │
│  VisualBible   │  │  Image gen      │  │  ComfyUI/Replicate     │
│  Metrics       │  │  Video gen      │  │  FFmpeg assembly       │
│  Quality Gate  │  │  Audio gen      │  │  Quality gate          │
│                │  │                 │  │                        │
│  ZERO APIs     │  │  ALL stochastic │  │  DAG-scheduled         │
│  ZERO I/O      │  │  SANDBOXED      │  │  checkpoint-aware      │
│  ZERO time     │  │  versioned      │  │  budget-gated          │
└────────┬───────┘  └────────┬────────┘  └───────────┬────────────┘
         │                   │                        │
         └───────────────────┴────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  VERSIONED IR   │
                    │  AIPRODOutput   │
                    │  v{hash}        │
                    │  + trace log    │
                    └─────────────────┘
```

### 5.2 Composants requis (par priorité)

#### PRIORITÉ 1 — Contrat IR formel avec versioning (faible coût, impact élevé)

```python
@dataclass(frozen=True)
class IRVersion:
    compiler_version: str    # "3.1.0"
    visual_bible_hash: str   # sha256 du JSON VisualBible
    rules_hash: str          # sha256 de builtin_rules.py + rule tables
    text_hash: str           # sha256 du texte source

class AIPRODOutput(BaseModel):
    ir_version: IRVersion    # Nouveau champ
    # ... champs existants
```

**Bénéfice** : Détecter automatiquement quand un re-run de production utilise un IR obsolète (VisualBible modifiée, règles changées).

#### PRIORITÉ 2 — Execution trace par shot (faible coût, debugging x10)

```python
@dataclass
class ShotTrace:
    shot_id: str
    pass3_rules_fired: list[str]      # ex: ["INTENSITY_SHOT_SEQUENCES:climax+explosive"]
    pass4_rules_resolved: list[str]   # ex: ["CHR-01: crane_up→tilt_up"]
    visual_bible_injections: list[str]
    anchor_strength_resolved: float
    feasibility_raw: int
    final_camera_movement: str        # après résolution
    drift_detected: bool              # emotional_beat_index vs final emotion
```

**Bénéfice** : Quand un shot produit un résultat inattendu, la trace permet de remonter à la règle exacte sans re-run.

#### PRIORITÉ 3 — DAG explicite pour gen_shots_v4 (coût moyen, scalabilité ×N)

Remplacer la boucle linéaire `for shot_id in shot_ids` par un graphe de dépendances :

```python
dag = ProductionDAG()
for shot in shots:
    blender_node = dag.add(BlenderRenderTask(shot))
    stylize_node = dag.add(StyleTask(shot), depends_on=[blender_node])
    video_node   = dag.add(VideoTask(shot),  depends_on=[stylize_node])
    qg_node      = dag.add(QGTask(shot),     depends_on=[video_node])

dag.execute(max_parallel=4, budget_cap=args.budget_cap)
```

**Bénéfice** : Blender renders de shots indépendants en parallèle. À 4 workers RTX 5080, le throughput × 4.

#### PRIORITÉ 4 — VisualBible versionnée et validée

```python
class VisualBible(BaseModel):
    version: str                     # "1.0.0"
    series_id: str                   # "district_zero"
    checksum: str                    # sha256 du JSON complet
    
    def validate_slugs(self, ir: AIPRODOutput) -> list[str]:
        """Retourne les slugs référencés dans l'IR mais absents de la Bible."""
```

**Bénéfice** : Détection en amont des `reference_anchor_strength` silencieux à 0.5.

#### PRIORITÉ 5 — Rule DSL externalisé (coût élevé, bénéfice long-terme)

```yaml
# rules/spc_crane_overhead.yaml
id: SPC-01-overhead-crane-up
priority: P3
description: "Interdire crane_up depuis vue overhead"
condition:
  operator: AND
  conditions:
    - field: ref_invariants.camera_height_class
      operator: EQ
      value: overhead
    - field: shot.camera_movement
      operator: EQ
      value: crane_up
action:
  type: DOWNGRADE_MOVEMENT
  target_field: shot.camera_movement
  value: tilt_up
```

**Bénéfice** : Les superviseurs VFX/DoP peuvent contribuer des règles sans toucher au code Python.

### 5.3 Modèle de cycle de vie d'exécution (v3 cible)

```
ÉTAPE 1 — COMPILE (pur, déterministe)
  Input: text + VisualBible v{hash}
  → InputClassifier.classify()
  → Pass 1–4 (rules-only)
  → AIPRODOutput + IRVersion{hash}
  → ShotTrace[] (trace complète)
  OUTPUT: ir_{hash}.json (immuable, versionnée)

ÉTAPE 2 — PLAN (déterministe)
  Input: ir_{hash}.json
  → Calculer DAG de production (dépendances shot)
  → Estimer coût total (frames × cost_per_frame)
  → Présenter plan à l'utilisateur avec budget
  OUTPUT: production_plan_{hash}.json

ÉTAPE 3 — CREATIVE ENRICHMENT (sandboxé, optionnel)
  Input: ir_{hash}.json + creative_config.json
  → LLM story enrichment (si mode generative)
  → Seed image references (depuis character_refs/)
  → Location master plates (gen_location_refs --local)
  OUTPUT: creative_assets_{hash}/

ÉTAPE 4 — RENDER PIPELINE (orchestré, parallèle)
  Input: ir_{hash}.json + creative_assets_{hash}/
  → DAGScheduler.execute(max_parallel=N, budget_cap=X)
  → Pour chaque shot (parallèle par groupes indépendants):
      Blender render → ComfyUI/Replicate stylize → FFmpeg clip
  → QualityGate par shot (SSIM, ArcFace, luminance)
  → Checkpoint auto par shot
  OUTPUT: clips/{shot_id}.mp4

ÉTAPE 5 — ASSEMBLY & POST-PROD (déterministe)
  Input: clips/ + ir_{hash}.json
  → assembly.py (FFmpeg concat)
  → EDL export / Resolve XML / audio cues
  OUTPUT: {episode_id}_master.mp4 + deliverables/
```

---

## 6. FLAWS CLASSÉS PAR SÉVÉRITÉ

### Tier S — Critique (bloquant production à l'échelle)

| ID | Flaw | Fichier | Ligne | Impact |
|---|---|---|---|---|
| **S-01** | VisualBible sans versioning ni validation de slugs | `pass3_shots.py` | ~L603 | Dégradation silencieuse `anchor_strength` à 0.5 |
| **S-02** | TypedDict NotRequired sans contrat complet | `models/intermediate.py` | — | Fallbacks silencieux en P3 pour tous champs non validés |
| **S-03** | gen_shots_v4 séquentiel, non parallélisable | `gen_shots_v4.py` | L84 | Throughput × 1 peu importe le hardware |
| **S-04** | Pas d'IR versioning entre runs | `engine.py`, `gen_shots_v4.py` | — | Run de production sur IR obsolète non détectable |

### Tier A — Majeure (dette technique significative)

| ID | Flaw | Fichier | Impact |
|---|---|---|---|
| **A-01** | VisualBible singleton sans immutabilité garantie | `visual_bible.py` | Mutation possible entre passes |
| **A-02** | Règles métier dispersées dans 6 modules | Multiple | Maintenance O(n modules) pour 1 règle |
| **A-03** | P3 intègre logique P4 (lens_mm, color_grade) | `pass3_shots.py` | Couplage conceptuel P3/P4 |
| **A-04** | ScriptParser bypasse P1+P2 sans validation | `engine.py:L229` | Pas de `_validate_pass2_output` sur chemin script |
| **A-05** | Orchestrateurs découplés (engine/gen_shots/assembly) | Multiple | Pas de coordinateur global |
| **A-06** | Pas d'execution trace par shot | — | Debugging anomalies impossible sans re-run |

### Tier B — Mineure (amélioration qualité)

| ID | Flaw | Fichier | Impact |
|---|---|---|---|
| **B-01** | LLMRouter cooldown global (pas par endpoint) | `llm_router.py:L153` | Faux positifs de cooldown |
| **B-02** | Budget cap pre-loop O(n) filesystem scan | `gen_shots_v4.py:L85–100` | Ralentissement à 10K shots |
| **B-03** | `metrics_v4.jsonl` sans index | `gen_shots_v4.py:L263` | Scan linéaire pour KO shots |
| **B-04** | ComfyUI polling synchrone (`time.sleep(2)`) | `shot_pipeline_v4.py` | Overhead polling × 10K shots |
| **B-05** | RuleEngineReport pas rendu en format humain | `pass4_compile.py` | Superviseur ne peut pas lire les décisions |

---

## 7. CONTRADICTIONS ARCHITECTURALES CACHÉES

### Contradiction #1 — "Déterministe" mais dépend du filesystem

Le déterminisme du core est réel. Mais `gen_shots_v4.py` fait :
```python
frame_count = _count_frames(RENDERS_DIR / shot_id / "frames")
```
Si les frames Blender ne sont pas présentes (premier run), `estimated_cost = 0.0`. Le budget guard est trompé : il estime $0 alors que le coût réel sera >$0 après le render.

### Contradiction #2 — "Pipeline" mais pas de gestion des effets de bord

Pass 4 mute les shots (`validated_shots`) in-place via ConflictResolutionEngine. Ce n'est pas une transformation pure — les `Shot` Pydantic sont modifiés. Si une erreur survient après la 5ème mutation, l'état intermédiaire est perdu.

### Contradiction #3 — "Module séparé" mais LLMRouter connaît les détails des adapters

`llm_router.py` importe et instancie directement `ClaudeAdapter` et `GeminiAdapter`. Ce n'est pas une vraie inversion de dépendance — c'est une factory couplée. Si un 3ème provider est ajouté, `LLMRouter` doit être modifié.

### Contradiction #4 — "IR central" mais 2 représentations IR simultanées

Le système maintient **deux** représentations IR en parallèle :
1. `TypedDict` (CinematicScene, VisualScene, ShotDict) — intermediate passes
2. `Pydantic BaseModel` (Scene, Shot, Episode, AIPRODOutput) — final validated output

La conversion TypedDict → Pydantic se fait en P4. Entre P1 et P4, le "IR" n'est pas validé par Pydantic — c'est un TypedDict non contraint.

---

## 8. VERDICT FINAL

### Classification système

> **AIPROD_V2 est un compilateur cinématographique déterministe de grade Research/Production, avec une couche de génération stochastique optionnelle et un runtime d'orchestration de production fonctionnel mais non scalable.**

### Score par dimension

| Dimension | Score | Justification |
|---|:---:|---|
| Déterminisme core (P1–P4) | 9/10 | Réel, prouvé, gated correctement |
| Architecture IR | 7/10 | TypedDict + Pydantic dual-IR, NotRequired non contractualisé |
| Rule engine | 8/10 | DSL propre, résolution déterministe, mais non externalisé |
| Scalabilité runtime | 4/10 | Séquentiel, pas de DAG, pas de parallélisme |
| Gouvernance runtime | 3/10 | Pas de versioning IR, pas de trace, pas de rollback |
| Qualité code | 8/10 | ruff/mypy clean, 1072 tests, no type:ignore |
| Maintenabilité | 6/10 | Règles dispersées, fausse modularité P3/P4 |

### Verdict de maturité

```
╔══════════════════════════════════════════════════════════════════════╗
║  PROTOTYPE-GRADE    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   ║
║  RESEARCH-GRADE     ████████████████████████████░░░░░░░░░░░░░░░░░░  ║  ← ACTUEL
║  PRODUCTION-GRADE   ████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ║  ← core IR
║  STUDIO-GRADE       ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ║
╚══════════════════════════════════════════════════════════════════════╝
```

**Le core IR (P1–P4 + rule engine) est production-grade.**
**Le runtime d'orchestration (gen_shots_v4 + assembly) est research-grade.**
**La gouvernance (versioning IR, DAG, trace) est à construire.**

### Prochaines étapes recommandées (par ROI)

1. **[Immédiat]** Valider tous les slugs VisualBible avant run de production (`validate_slugs()`) — 30 lignes
2. **[Court terme]** Ajouter `ShotTrace` minimal dans P4 — 50 lignes, debugging ×10
3. **[Moyen terme]** IRVersion + hash dans AIPRODOutput — 20 lignes, sécurité re-run
4. **[Long terme]** DAG parallèle dans gen_shots_v4 — scalabilité ×N workers
5. **[Futur]** Rule DSL YAML externalisé — contribution sans code

---

*Audit généré le 2026-05-19 par GitHub Copilot (Claude Sonnet 4.6)*
*Codebase commit : `aa68ab2` — 1072 tests verts · ruff clean · mypy strict clean*
