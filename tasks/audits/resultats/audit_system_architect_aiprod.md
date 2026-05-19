---
type: audit
audit: system_architect
projet: AIPROD_V2
modele: sonnet-4.6
creation: 2026-05-19 à 15:25
derniere_revision: 2026-05-19
---

# AUDIT SYSTEM ARCHITECT — AIPROD_V2
## Reverse-engineering de l'exécution réelle du pipeline cinématique

---

## CLASSIFICATION SYSTÈME (VÉRITÉ D'EXÉCUTION)

**Ce que le système prétend être :** un compilateur cinématique déterministe (texte → IR structuré).

**Ce que le système EST réellement :**

> Un compilateur déterministe à 4 passes (Pass1–Pass4) embarqué dans une enveloppe d'orchestration stochastique multi-backends non gouvernée.

Plus précisément :

| Couche | Nature réelle | Déterminisme |
|---|---|---|
| Pass1 `segment()` | Compilateur pur — règles R01–R12, zéro état externe | ✅ byte-level |
| Pass2 `visual_rewrite()` | Compilateur pur — tables de règles, zéro LLM | ✅ byte-level |
| Pass3 `simplify_shots()` | Compilateur pur — plans déclaratifs, résolution déterministe | ✅ byte-level |
| Pass4 `compile_episode()` | Compilateur + rule engine (9 règles P1–P5) | ✅ byte-level |
| `engine.py` mode `generative` | Agent LLM déguisé en pipeline | ❌ stochastique |
| `engine.py:_enrich_script_scenes()` | Pass implicite hors contrat (heuristiques inline) | ✅ mais invisible |
| `EpisodeScheduler` | Orchestrateur séquentiel API payantes | ❌ stochastique |
| `gen_shots_v4.py` | Orchestrateur subprocess sans DAG | ⚠️ linéaire |
| Adapters image/vidéo/audio | 10+ APIs externes | ❌ stochastique |

Le système possède **trois orchestrateurs distincts** pour la même production, sans plan de contrôle unifié :
1. `engine.py:run_pipeline()` — pour le core Pass1–Pass4
2. `cli.py schedule → EpisodeScheduler` — pour la génération image/vidéo/audio
3. `production/gen_shots_v4.py` — pour le rendu frame-par-frame EP01

Ces trois orchestrateurs ne partagent ni état, ni trace, ni contrat de versioning.

---

## 1. ANALYSE ARCHITECTURALE — VÉRITÉ D'EXÉCUTION

### Graphe de contrôle réel

```
INPUT TEXT
   │
   ├─[mode=deterministic]──────────────────────────────────────────┐
   │                                                                │
   ├─[type=script]──► _enrich_script_scenes()  ◄── PASS CACHÉE   │
   │                  (heuristiques inline,                        │
   │                   mimique P1+P2 sans passer par P1/P2)        │
   │                          │                                     │
   │  [type=novel]            ▼                                     │
   │     │           VisualScene[] (P2 output simulé)               │
   │     ▼                    │                                     │
   │  segment()  ──►  visual_rewrite()                              │
   │  [PASS 1]        [PASS 2]                                      │
   │                          │                                     │
   └────────────────────────► │                                     │
                              ▼                                     │
                     StoryValidator.validate_all()                  │
                     [LLM optionnel en mode auto]                   │
                              │                                     │
                              ▼                                     │
                     simplify_shots()                               │
                     [PASS 3]                                       │
                              │                                     │
                              ▼                                     │
                     compile_episode()                              │
                     [PASS 4]                                       │
                     ├─ RuleEngine × 9 règles/shot                 │
                     ├─ ConsistencyChecker R01–R04                 │
                     ├─ PacingAnalyzer                             │
                     └─ PromptFinalizer                            │
                              │                                     │
                              ▼                                     │
                     AIPRODOutput (Pydantic v2)                     │
                     ◄──────────────────────────────────────────────┘
                              │
          ┌───────────────────┼─────────────────────┐
          ▼                   ▼                      ▼
  CLI pipeline          CLI schedule           gen_shots_v4.py
  (pure IR)         (StoryboardGenerator       (subprocess chain)
                    + VideoSequencer           Blender → Stylize
                    + AudioSynchronizer)       → Video → QG
                    [STOCHASTIQUE]             [SÉQUENTIEL]
```

### Points d'injection stochastique

| Localisation | Vecteur | Visible dans l'IR ? |
|---|---|---|
| `engine.py:234` — `StoryExtractor.extract_all()` | Claude/Gemini | Non — remplace Pass1+Pass2 entièrement |
| `engine.py:264` — `StoryValidator.validate_all()` | LLM optionnel | Non — filtre des scènes sans trace |
| `cli.py:_load_llm_adapter()` — router | Cooldown/quarantine runtime | Non |
| `storyboard.py:StoryboardGenerator` | 9+ image APIs | Non — résultat non tracé dans l'IR |
| `video_sequencer.py:VideoSequencer` | Runway/Kling | Non |
| `audio_synchronizer.py:AudioSynchronizer` | ElevenLabs/OpenAI/Runway | Non |
| `shot_pipeline_v4.py` | Replicate ControlNet ($0.04/frame) | Non |

**Conclusion critique :** le Core IR (Pass1–Pass4) est genuinement déterministe. Mais il est **entouré d'une couche opaque stochastique** sans traçabilité, sans versioning, et sans isolation formelle.

---

## 2. ZONES DE FAIBLESSE STRUCTURELLE

### Flaw S1 — La Pass Cachée (Sévérité : CRITIQUE)

`engine.py:_enrich_script_scenes()` est une **cinquième passe non documentée** qui s'applique uniquement aux inputs de type `script`. Elle reconstruit manuellement `beat_type`, `action_intensity`, `emotional_beat_index`, `continuity_flags`, `reference_location_id` via des heuristiques inline (`_EMOTION_TO_BEAT`, `_ACTION_KEYWORDS_HIGH/MID`, `_beat_from_position()`).

**Problème structurel :**
- Cette passe ne passe PAS par `segment()` ni `visual_rewrite()` — elle bypasse le contrat de validation de Pass1 et Pass2
- Elle produit un `VisualScene[]` **sans que `_validate_pass2_output()` soit appelé**
- Les heuristiques inline (lignes 61–147 de `engine.py`) dupliquent la logique des règles R01–R12 sans partager de code
- Résultat : deux code paths vers Pass3 avec des garanties différentes, invisible à l'extérieur

### Flaw S2 — IR TypedDict avec 17 champs NotRequired (Sévérité : ÉLEVÉE)

`VisualScene` possède 17 champs `NotRequired`. Pass3 y accède via `.get()` avec des valeurs par défaut silencieuses :

```python
action_intensity: str | None = scene.get("action_intensity")   # → None si absent
emotional_layer: str | None  = scene.get("emotional_layer")    # → None si absent
beat_type: str | None        = scene.get("beat_type")          # → None si absent
```

**Problème :** Pass3 opère en **mode dégradé silencieux** quand les champs cinématiques sont absents. Il n'y a aucune distinction au niveau du type entre un `VisualScene` produit par Pass2 (complet) et un `RawScene` minimal compatible. La dégradation est invisible dans les logs et les tests.

Le contrat de données inter-passes est un **contrat de type**, non un **contrat sémantique**. Nos additions A1/A2 commencent à corriger ce point mais ne couvrent pas tous les chemins (notamment la pass cachée).

### Flaw S3 — Fausse Modularité des Adapters (Sévérité : MOYENNE)

Chaque adapter (image, vidéo, audio) implémente une interface ABC. En apparence propre. Mais :

- `_load_image_adapter()` dans `cli.py` contient 9 branches `if/elif` avec instanciation directe — couplage fort entre CLI et implémentations concrètes
- `SmartVideoRouter` (video_gen) prend des décisions runtime de composition Runway/Kling — logique d'orchestration embarquée dans un adapter
- Les coûts sont hardcodés dans `cli.py` (`_DRY_RUN_COST_PER_SHOT`, etc.) — pas dans les adapters eux-mêmes — rupture du principe d'encapsulation

### Flaw S4 — Explosion de Complexité dans les Tables de Règles (Sévérité : MOYENNE)

La logique cinématique est dispersée dans 11 fichiers de règles :

| Fichier | Rôle |
|---|---|
| `body_language_rules.py` | Templates corps × émotion × tier |
| `cinematography_rules_v3.py` | Séquences shots |
| `dop_style_rules.py` | Mapping beat/émotion/ton |
| `duration_rules.py` | Durées par beat+intensité |
| `emotion_rules.py` | Détection émotion |
| `visual_transformation_rules_v3.py` | Actions visuelles |
| + 5 autres | ... |

Ajouter une nouvelle émotion implique de modifier **4 à 6 fichiers simultanément** sans outil de cohérence. Il n'y a pas de source de vérité unique pour le vocabulaire émotionnel du système.

### Flaw S5 — SeasonCoherenceTracker hors contrat Pydantic (Sévérité : FAIBLE)

`season/models.py` utilise des `dataclass` Python natifs, pas Pydantic, contrairement au reste du système. Il n'y a pas de validation des contraintes sur `mean_feasibility_score`, `consistency_score`, etc. Divergence de contrat non détectée.

### Zone de Debugging Théoriquement Impossible

Scénario : un shot en sortie de `gen_shots_v4.py` a un prompt incohérent avec le `storyboard.json`. Retracer l'origine :

1. Le shot vient de `storyboard.json` → lequel vient de `CLI schedule` → qui appelle `StoryboardGenerator`
2. `StoryboardGenerator` appelle l'image adapter → résultat non tracé dans l'IR
3. Le prompt a été modifié par `PromptFinalizer` en Pass4 → enrichissement non versionné
4. La scène d'origine peut avoir été produite par `_enrich_script_scenes()` → pass cachée

**Aucun mécanisme ne permet de rejouer un run identique** ni de pinpointer la transformation fautive.

---

## 3. ANALYSE GOUVERNANCE ET FLUX DE CONTRÔLE

### Qui est le vrai orchestrateur ?

| Scénario | Orchestrateur effectif | Nature |
|---|---|---|
| `python main.py` | `engine.py:run_pipeline()` | Compilateur pur |
| `aiprod schedule --input ...` | `cli.py → EpisodeScheduler` | Séquenceur API |
| `python production/gen_shots_v4.py --all` | `gen_shots_v4.py` | Subprocess runner |

**Trois orchestrateurs distincts, zéro état partagé, zéro protocole commun.**

### DAG ou illusion linéaire ?

Le système prétend être un pipeline en passes. En réalité :

- **Pass1→Pass2→Pass3→Pass4 :** vrai DAG (données uniquement, pas de boucles) ✅
- **EpisodeScheduler :** séquenceur linéaire avec NullBackend fallback implicite ⚠️
- **gen_shots_v4.py :** boucle `for shot_id in shot_ids:` — linéaire, bloquante, zero parallelisme ❌

Il n'existe pas de **graphe d'exécution déclaratif**. Le DAG est implicite dans le code, non matérialisé comme structure de données.

### Gouvernance runtime manquante

| Fonctionnalité | Statut |
|---|---|
| Versioning des sorties IR par pass | ❌ Absent |
| Trace ID par run (corrélation cross-pass) | ❌ Absent |
| Rollback d'une passe | ❌ Absent (checkpoint only tracks "processed") |
| Replay déterministe d'un run complet | ❌ Impossible (inputs LLM/API non archivés) |
| Hash de validation du contrat IR entre passes | ❌ Absent |
| Mode lock (prevent accidental stochastic execution) | ⚠️ Partiel (mode="deterministic" flag mais non enforced at runtime) |
| Audit log des mutations par rule engine | ✅ Présent (RuleEngineReport) — mais non persisté |

---

## 4. ANALYSE SCALABILITÉ ET DÉFAILLANCES INDUSTRIELLES

### 1 épisode → 10 épisodes

| Point de rupture | Impact |
|---|---|
| `SeasonCoherenceTracker` — state en mémoire uniquement | Perte état entre runs |
| Visual Bible — fichier JSON unique partagé | Contention R/W en équipe |
| `storyboard.json` — output monolithique | Merge conflicts en équipe |
| Rule engine — O(shots × rules) par épisode | Acceptable à 35 shots, linéaire à 350 |
| Checkpoint — liste JSON de shot_ids | Aucune validation d'intégrité |
| metrics_v4.jsonl — append sans rotation | Croissance illimitée |

### 35 shots → 10 000 shots

| Point de rupture | Impact | Complexité |
|---|---|---|
| `gen_shots_v4.py` — subprocess séquentiel | 10 000 shots × ~3min = 500h CPU | O(n) mais non parallélisable |
| Replicate API — zero concurrence | ~$400 + queue rate-limit | Bloquant |
| ComfyUI — single request | ~250h de rendu GPU | Bloquant |
| Checkpoint JSON — lecture complète à chaque shot | O(n²) total I/O | Critique à >1000 shots |
| `_count_frames()` — `glob("frame_*.png")` par shot | O(shots × frames) à chaque run | Coûteux |

**Coût réel à 10 000 shots (Replicate) :**
- ~85 frames/shot moyen × $0.04 = **$34 000** — aucun mécanisme de batch discount ni de cache d'images similaires

### Développeur seul → Studio (équipe)

| Point de rupture | Impact |
|---|---|
| CLI-only, pas d'API REST | Impossible à intégrer dans des workflows studio |
| Checkpoint — aucun lock fichier | Corruption si deux processus tournent en parallèle |
| storyboard.json — pas de namespace multi-utilisateur | Collision de shot_id entre projets |
| Secrets — `.env` fichier plat | Non compatible avec secrets management (Vault, etc.) |
| Aucune interface de monitoring | Impossible de suivre N runs simultanés |

### Dégradation silencieuse de qualité à l'échelle

1. **Drift émotionnel** : `emotion` détectée en Pass1 par first-match keyword, sans contextualisation narrative. À grande échelle, des scènes complexes auront des émotions mal classifiées, propageant silencieusement de mauvais paramètres corps/pose en Pass2 et Pass3.

2. **Feasibility score falsement élevé** : `_compute_feasibility_score()` en Pass3 est un calcul de table (shot_type × camera_movement × intensity). Il ne tient pas compte des contraintes de continuité inter-shots — un score de 80 par shot ne garantit pas la cohérence de séquence.

3. **PromptFinalizer sans validation sémantique** : `finalize_prompts()` enrichit les prompts avec des invariants visuels sans vérifier la compatibilité sémantique. À 10 000 shots, des combinaisons conflictuelles passeront inaperçues.

---

## 5. ARCHITECTURE NEXT-GENERATION — REDESIGN

### Séparation requise en 3 couches formelles

```
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — DETERMINISTIC COMPILER                                   │
│  ──────────────────────────────                                     │
│  Input: raw text | fountain script | fountain XML                   │
│                                                                     │
│  IR₀: RawText                                                       │
│    │  [Pass1: segment()] + hash(IR₀→IR₁)                          │
│  IR₁: CinematicScene[]                                             │
│    │  [Pass2: visual_rewrite()] + hash(IR₁→IR₂)                   │
│  IR₂: VisualScene[]                                                │
│    │  [Pass3: simplify_shots()] + hash(IR₂→IR₃)                   │
│  IR₃: ShotDict[]                                                   │
│    │  [Pass4: compile_episode()] + hash(IR₃→IR₄)                  │
│  IR₄: AIPRODOutput (Pydantic v2, sealed)                           │
│                                                                     │
│  Invariants :                                                       │
│  • Chaque IRₙ est sérialisé + hashé (SHA-256) avant de passer     │
│  • Aucun appel LLM/API dans cette couche                           │
│  • Chaque passe expose un PassContract (champs requis en sortie)   │
│  • _enrich_script_scenes() devient Pass0 (explicite, tracée)       │
└─────────────────────────────────────────────────────────────────────┘
                               │ IR₄ sealed + run_id
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 2 — STOCHASTIC CREATIVE LAYER (sandboxed)                   │
│  ───────────────────────────────────────────────                    │
│  Input: IR₄ sealed + run_id                                        │
│                                                                     │
│  ┌─────────────────────────────────────────────────────┐           │
│  │ Image Worker Pool (N workers, async)                 │           │
│  │  • character_prepass (1 job/character)              │           │
│  │  • per-shot stylization (N jobs, parallel)          │           │
│  └─────────────────────────────────────────────────────┘           │
│                                                                     │
│  ┌─────────────────────────────────────────────────────┐           │
│  │ Video Worker Pool                                    │           │
│  │  • per-shot clip generation                         │           │
│  └─────────────────────────────────────────────────────┘           │
│                                                                     │
│  ┌─────────────────────────────────────────────────────┐           │
│  │ Audio Worker Pool                                    │           │
│  │  • TTS per dialogue line                            │           │
│  │  • Score/SFX per scene                             │           │
│  └─────────────────────────────────────────────────────┘           │
│                                                                     │
│  Invariants :                                                       │
│  • Chaque résultat est associé au run_id + shot_id                 │
│  • Les seeds sont déterministes (extraits de l'IR₄)                │
│  • Les réponses API sont archivées (résultat binaire + metadata)    │
│  • Aucune mutation de IR₄ dans cette couche                        │
└─────────────────────────────────────────────────────────────────────┘
                               │ results + run_id
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 3 — EXECUTION CONTROL PLANE (MANQUANT ACTUELLEMENT)         │
│  ────────────────────────────────────────────────────────           │
│                                                                     │
│  AIPRODExecutor                                                     │
│  ├── DAGScheduler                                                   │
│  │   • Graphe d'exécution déclaratif (nodes = pass outputs)        │
│  │   • Dépendances explicites (shot B dépend de character_prepass) │
│  │   • Parallélisme Layer 2 (async workers, N concurrent shots)    │
│  │                                                                  │
│  ├── ExecutionStore (SQLite ou fichier JSONL indexé)               │
│  │   • run_id UUID + timestamp + mode + input_hash                 │
│  │   • IR snapshot par passe (IR₁, IR₂, IR₃, IR₄)                │
│  │   • hash chain validation (IR₀ → ... → IR₄)                    │
│  │   • résultats Layer 2 associés au run_id                        │
│  │                                                                  │
│  ├── ReplayEngine                                                   │
│  │   • Rejouer depuis IRₙ d'un run précédent                      │
│  │   • Partial replay (re-stylize shot X uniquement)               │
│  │   • Diff entre deux runs (IR₄ A vs IR₄ B)                      │
│  │                                                                  │
│  ├── BudgetController                                               │
│  │   • Cap configurable par couche (image, vidéo, audio)           │
│  │   • Estimation upfront depuis IR₄ (frame count × coût)         │
│  │   • Circuit breaker (arrêt si dépassement mid-run)              │
│  │                                                                  │
│  └── ModeEnforcer                                                   │
│      • DETERMINISTIC_ONLY — Layer 2 désactivée                    │
│      • CREATIVE_ONLY — Layer 1 skip si IR₄ déjà en store          │
│      • HYBRID — orchestration explicite des deux couches           │
└─────────────────────────────────────────────────────────────────────┘
```

### Composants requis (détail)

#### PassContract formel

Remplacer les TypedDict NotRequired par un contrat de sortie validé :

```python
@dataclass(frozen=True)
class Pass2Contract:
    """Contrat de sortie garanti de visual_rewrite()."""
    scene_id: str
    emotion: str                    # non-vide, valeur canonique
    action_intensity: Literal["subtle", "mid", "explosive"]
    emotional_beat_index: float     # ∈ [0.0, 1.0]
    visual_actions: list[str]       # len ≥ 1
    body_language_states: list[BodyLanguageState]  # len ≥ 1 si characters non-vide
    pass_hash: str                  # SHA-256 de la sérialisation

# Pass3 reçoit list[Pass2Contract], plus list[VisualScene] avec get() silencieux
```

#### DAG déclaratif minimal

```python
dag = ExecutionDAG()
dag.add_node("pass1", fn=segment, inputs=["raw_text"])
dag.add_node("pass2", fn=visual_rewrite, inputs=["pass1.output"])
dag.add_node("pass3", fn=simplify_shots, inputs=["pass2.output"])
dag.add_node("pass4", fn=compile_episode, inputs=["pass2.output", "pass3.output"])
dag.add_node("char_prepass", fn=character_prepass, inputs=["pass4.output"],
             parallel=True, workers=4)
dag.add_node("stylize", fn=stylize_frames, inputs=["char_prepass.output"],
             parallel=True, workers=N, depends_on=["char_prepass"])
dag.execute(run_id=uuid4(), mode=ModeEnforcer.HYBRID)
```

### Modèle de cycle de vie d'exécution (step-by-step)

```
1. AIPRODExecutor.run(input_text, config)
   ├─ générer run_id (UUID)
   ├─ hash input → input_hash
   ├─ vérifier ExecutionStore (run déjà existant pour cet input_hash ?)
   │
2. LAYER 1 — Compiler
   ├─ Pass0: _enrich_or_segment() → IR₀ + hash
   ├─ Pass1: segment() → IR₁ + hash
   ├─ Pass2: visual_rewrite() + _validate_pass2_output() → IR₂ + hash
   ├─ Pass3: simplify_shots() → IR₃ + hash
   ├─ Pass4: compile_episode() → IR₄ + hash
   ├─ Valider hash chain : hash(IR₃) ∈ IR₄.metadata
   ├─ Persister IR₁..IR₄ dans ExecutionStore (run_id)
   │
3. LAYER 3 — Control Plane : BudgetController.estimate(IR₄, config)
   ├─ Calculer coût total (frame_count × cost_per_frame)
   ├─ Si coût > budget_cap → SystemExit avec détail
   │
4. LAYER 2 — Creative (parallel)
   ├─ DAGScheduler.submit_graph(IR₄, run_id)
   ├─ character_prepass × N_characters (parallel, bloquant avant stylize)
   ├─ stylize_frames × N_shots (parallel, N workers)
   ├─ video_gen × N_shots (parallel, après stylize)
   ├─ audio_gen × N_scenes (parallel, indépendant)
   │
5. LAYER 3 — Control Plane : AssemblyEngine
   ├─ assembly.assemble_episode(clips, audio, storyboard)
   ├─ QualityGate.check(output) → QualityReport
   ├─ Archiver tous les résultats (run_id → assets)
   │
6. ExecutionStore.finalize(run_id, status, metrics)
```

---

## VERDICT FINAL

### Scores par couche

| Couche | Score | Grade |
|---|---|---|
| Core compiler Pass1–Pass4 | 8.5/10 | **Production-grade** |
| Rule engine DSL (9 règles P1–P5) | 7.5/10 | **Production-grade** |
| IR contracts (Pydantic v2) | 6.5/10 | Pre-production (NotRequired drift) |
| Adapter surface (image/vidéo/audio) | 6/10 | Research-grade (pas de sandboxing) |
| Orchestration globale | 3.5/10 | Prototype (3 orchestrateurs, zéro DAG) |
| Scalabilité industrielle | 2/10 | Prototype (séquentiel, sans parallélisme) |
| Gouvernance runtime | 2/10 | Prototype (pas de versioning ni replay) |

### Classification finale

> **PRE-PRODUCTION GRADE — Avancé**

Le cœur compilateur (Pass1–Pass4) est **production-grade**. Il peut générer un épisode de haute qualité de manière fiable avec supervision humaine.

L'enveloppe d'exécution (orchestration, adapters, production pipeline) est **research/pre-production-grade**. Elle peut produire EP01/35 shots avec supervision manuelle, mais ne peut pas fonctionner autonomement à l'échelle d'une saison (S1 = 10 épisodes, 350+ shots) sans les trois composants manquants :

1. **Control Plane** (DAG + versioning + replay)
2. **Parallélisme Layer 2** (async workers)
3. **PassContracts formels** (hash chain, typage fort)

Le système n'est pas encore **Studio-grade** — ce qui nécessiterait en plus : API REST, multi-tenancy, monitoring temps-réel, et intégration avec les outils DCC (DaVinci, Nuke, Maya).

---

*Audit réalisé le 2026-05-19 à 15:25 — sonnet-4.6 — sur base codebase réel `C:\Users\averr\AIPROD_V2` (commit `bc66f01`)*
