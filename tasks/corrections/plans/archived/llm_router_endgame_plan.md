---
title: Plan d'action — LLM Router Endgame
source: état réel du routeur au 2026-04-23 + validations repo + objectif de clôture production
creation: 2026-04-23 à 12:42
last_updated: 2026-04-23 à 13:41
status: completed
phase: RL (Router Endgame — clôture technique, observabilité, opérabilité)
corrections_totales: 8 (P1:4 P2:3 P3:1)
prerequis: routeur actuel validé — 345 tests verts, ruff clean, mypy strict clean
tests_avant: 345
tests_apres_cible: 363 atteints
---

# PLAN D'ACTION — LLM ROUTER ENDGAME — 2026-04-23

**Objectif** : faire sortir le routeur du statut de bonne heuristique interne pour en faire un sous-système de production explicable, pilotable, auditable et stable sur cas réels.

---

## Résumé exécutif

Le routeur est déjà techniquement solide. Il sait choisir entre Claude et Gemini selon la taille du prompt, la continuité narrative et la santé récente des providers. La suite n'est donc plus un chantier de fonctionnalité brute, mais un chantier de fermeture de produit.

La bonne stratégie n'est pas de continuer à empiler des heuristiques. La bonne stratégie est de verrouiller successivement quatre dimensions :

1. le sens des échecs provider ;
2. la politique de réaction du routeur ;
3. l'observabilité des décisions ;
4. l'exploitation réelle via CLI, artefacts et runbook.

Autrement dit : tant que le routeur ne sait pas expliquer pourquoi il a choisi un provider, pourquoi il l'a évité, et quelle dette de santé il lui attribue, la partie routeur n'est pas vraiment terminée.

---

## Positionnement du plan

Ce plan n'est pas un backlog d'améliorations possibles. C'est un plan de clôture.

Il vise à répondre à la question suivante :

> Que faut-il encore faire pour pouvoir dire honnêtement que la partie `LLMRouter` est terminée, propre, observable et exploitable en production locale ?

Le document est donc volontairement centré sur :

- le chemin critique ;
- les dépendances entre étapes ;
- les livrables concrets ;
- les validations obligatoires ;
- les risques de mauvaise fermeture.

---

## État courant consolidé

### Ce qui est déjà acquis

- routing court vs long entre Claude et Gemini ;
- préférence explicite sur prompts courts ;
- détection des prompts contextuels via `CONTEXT FROM PREVIOUS SCENES:` ;
- failover provider propre sur `LLMProviderError` ;
- cooldown mémoire intra-process ;
- backoff adaptatif après pannes répétées ;
- récupération graduelle de santé ;
- isolation des pénalités douces par profil de prompt ;
- tests d'intégration multi-chunk réels via `StoryExtractor.extract_all()` ;
- validation repo complète verte.

### État de clôture constaté

| Dimension | État actuel | Écart réel à combler |
|---|---|---|
| Sémantique des erreurs | fermée | catégories provider stables propagées jusqu'au routeur |
| Politique de réaction | fermée | sanctions différenciées selon `transient`, `rate_limit`, `auth`, `quota`, `schema` |
| Observabilité | fermée | trace routeur exportable via CLI avec `trace_history` et `last_trace` |
| Configurabilité | fermée | policy explicite et knobs d'environnement documentés |
| Validation opérateur | fermée | run réel `chapter1` validé en mode standard et en mode multi-chunk forcé |
| Documentation | fermée | README, `.env.example` et mini runbook opérateur alignés |

---

## Cible finale

À la fin de ce plan, le routeur doit être capable de répondre correctement, de manière stable et observable, aux six questions suivantes :

1. Quel profil de prompt ai-je détecté ?
2. Quel ordre de providers aurais-je choisi sans pénalité ?
3. Quelle dette de santé ou indisponibilité a modifié cette décision ?
4. Quelle catégorie d'erreur ai-je rencontrée en cas d'échec ?
5. Quelle réaction ai-je appliquée à cette catégorie ?
6. Comment un opérateur peut-il voir tout cela sans ouvrir `llm_router.py` ?

Si l'une de ces questions reste sans réponse fiable, la partie routeur n'est pas fermée.

---

## Définition de terminé

La partie routeur sera considérée comme terminée uniquement si toutes les conditions ci-dessous sont vraies en même temps :

1. Le routeur produit une décision traçable contenant au minimum : `prompt_profile`, `token_estimate`, `base_order`, `final_order`, `availability`, `health_penalties`, `selected_provider`, `fallback_provider`, `decision_reason`, `result`.
2. Les erreurs provider remontent avec une catégorie machine-stable, pas seulement un message libre.
3. Le routeur ne traite plus identiquement un `transient`, un `rate_limit`, un `auth`, un `quota` et un `schema`.
4. La policy de routing et de quarantaine est explicite, centralisée et documentée.
5. Une matrice de tests couvre les profils `short`, `contextual_short`, `long` croisés avec succès, fallback, cooldown, quarantaine, récupération et contamination croisée.
6. Une commande réelle sur `chapter1.txt` peut produire en local un artefact de trace routeur lisible.
7. `README.md` et `.env.example` sont suffisants pour exploiter le routeur sans relire l'implémentation.

---

## Doctrine d'architecture

Le routeur final doit respecter les invariants suivants :

1. Le cooldown dur reste global au provider.
2. La santé douce reste locale au profil de prompt.
3. La sanction dépend de la catégorie d'échec, pas seulement du fait d'échouer.
4. La trace de décision ne doit jamais modifier la décision.
5. La politique doit être explicite, bornée et déterministe.
6. Le routeur ne doit pas devenir un moteur d'apprentissage implicite ou un système à mémoire persistante inter-process.

---

## Architecture cible

```text
Prompt
  ↓
[RL-01] Prompt profiling
  ↓  short | contextual_short | long
[RL-02] Base provider order
  ↓
[RL-03] Hard availability gate
  ↓
[RL-04] Soft reranking by profile health
  ↓
[RL-05] Provider call
  ↓
[RL-06] Failure classification
  ↓
[RL-07] Health / quarantine update
  ↓
[RL-08] RouterDecisionTrace export
```

Principe opérationnel :

- la décision du routeur est un petit pipeline déterministe ;
- chaque étape doit être testable indépendamment ;
- chaque étape doit aussi être reconstruisible dans la trace finale.

---

## Table des étapes

| ID | Priorité | Action | But concret | Livrable principal |
|---|---|---|---|---|
| RL-01 | 🔴 Critique | Taxonomie d'échecs provider | donner un sens machine aux échecs | `LLMFailureCategory` + adapters enrichis |
| RL-02 | 🔴 Critique | Réactions différenciées routeur | adapter cooldown / quarantaine / récupération | logique de sanction par catégorie |
| RL-03 | 🔴 Critique | Trace de décision routeur | rendre le choix auditable | `RouterDecisionTrace` sérialisable |
| RL-04 | 🔴 Critique | Matrice de validation exhaustive | fermer les angles morts de tests | suite routeur structurée |
| RL-05 | 🟠 Important | Policy explicite et configurable | sortir les constantes du code brut | `RouterPolicy` ou équivalent |
| RL-06 | 🟠 Important | Export CLI / compare des traces | rendre l'observabilité réellement utilisable | flags CLI + artefacts |
| RL-07 | 🟠 Important | Validation réelle sur `chapter1.txt` | prouver le comportement en conditions réelles | artefacts locaux de référence |
| RL-08 | 🟡 Finalisation | Documentation + runbook | clôturer l'exploitation routeur | README + `.env.example` + guide court |

---

## Lots d'exécution recommandés

### Lot 1 — Sémantique des échecs

- RL-01
- RL-02

But : faire en sorte que le routeur réagisse à des causes, pas seulement à des symptômes.

### Lot 2 — Observabilité et preuve

- RL-03
- RL-04

But : rendre la décision visible et garantir qu'elle est vraiment couverte.

### Lot 3 — Pilotage et exploitation

- RL-05
- RL-06

But : sortir la policy du code brut et la rendre actionnable via CLI/env.

### Lot 4 — Fermeture production

- RL-07
- RL-08

But : valider sur cas réel et documenter la version finale du routeur.

---

## Fichiers cibles

### À modifier probablement

- `aiprod_adaptation/core/adaptation/llm_router.py`
- `aiprod_adaptation/core/adaptation/llm_adapter.py`
- `aiprod_adaptation/core/adaptation/claude_adapter.py`
- `aiprod_adaptation/core/adaptation/gemini_adapter.py`
- `aiprod_adaptation/cli.py`
- `main.py`
- `aiprod_adaptation/tests/test_adaptation.py`
- `aiprod_adaptation/tests/test_cli.py`
- `README.md`
- `.env.example`

### Nouveaux fichiers autorisés si et seulement si cela simplifie réellement le design

- `aiprod_adaptation/core/adaptation/router_policy.py`
- `aiprod_adaptation/core/adaptation/router_trace.py`
- `aiprod_adaptation/tests/test_router_trace.py`

Règle : ne pas créer de fichiers par confort abstrait. Si `llm_router.py` reste lisible et testable sans éclatement, rester simple.

---

## Plan détaillé

## RL-01 — Taxonomie d'échecs provider

**Priorité** : P1  
**Sévérité** : 🔴  
**Dépendances** : aucune  
**Fichiers principaux** : `llm_adapter.py`, `claude_adapter.py`, `gemini_adapter.py`, `test_adaptation.py`

### Problème

Le routeur voit actuellement une erreur provider, mais pas encore sa nature. Or un `auth`, un `quota`, un `rate_limit` ou un JSON mal formé ne doivent pas produire la même réaction.

### Action

1. Enrichir `LLMProviderError` avec une catégorie typée.
2. Faire remonter cette catégorie depuis Claude et Gemini.
3. Préserver un message humain lisible et un signal machine stable.
4. Définir le vocabulaire cible des catégories dès cette étape.

### Sortie attendue

- `LLMFailureCategory` ou équivalent ;
- `LLMProviderError` enrichie ;
- adapters producteurs de catégories stables.

### Tests à ajouter

- `test_router_preserves_provider_error_category_from_adapter`
- `test_router_raises_both_provider_categories_in_final_error`
- `test_claude_adapter_maps_auth_failure_category`
- `test_gemini_adapter_maps_rate_limit_failure_category`

### Risque principal

Cartographier trop tôt des catégories trop fines et se retrouver avec une API d'erreurs instable.

### Règle de conception

Commencer petit : `transient`, `rate_limit`, `auth`, `quota`, `schema`, `unknown` suffisent.

---

## RL-02 — Réactions différenciées par catégorie d'échec

**Priorité** : P1  
**Sévérité** : 🔴  
**Dépendance** : RL-01  
**Fichier principal** : `llm_router.py`

### Problème

Le routeur sait déjà ralentir un provider défaillant, mais pas encore appliquer la bonne sanction selon la gravité et la nature de l'échec.

### Action

1. Conserver le backoff adaptatif pour `transient` et `rate_limit`.
2. Introduire une quarantaine plus dure pour `auth` et `quota`.
3. Décider explicitement du traitement `schema` : pénalité provider, pénalité de profil, ou combinaison bornée.
4. Encadrer la récupération pour éviter qu'un succès isolé n'efface une panne grave trop vite.

### Politique cible minimale

| Catégorie | Effet minimal attendu |
|---|---|
| `transient` | cooldown adaptatif global + pénalité douce du profil courant |
| `rate_limit` | cooldown plus fort mais retryable |
| `auth` | quarantaine longue, quasi non retryable tant que la config n'est pas corrigée |
| `quota` | quarantaine longue bornée, distincte du transient |
| `schema` | pénalité locale au profil de prompt, pas de bannissement aveugle |
| `unknown` | fallback conservateur proche de `transient` |

### Tests à ajouter

- `test_router_auth_failure_quarantines_provider_longer`
- `test_router_rate_limit_uses_retry_backoff_not_hard_quarantine`
- `test_router_schema_failure_penalizes_current_profile_only`
- `test_router_success_clears_quarantine_progressively`

### Risque principal

Rendre la politique trop compliquée et perdre la lisibilité de `llm_router.py`.

### Garde-fou

Si la logique dépasse un seuil de lisibilité, extraire uniquement la policy, pas le coeur du routeur.

---

## RL-03 — Trace de décision routeur

**Priorité** : P1  
**Sévérité** : 🔴  
**Dépendances** : RL-01, RL-02  
**Fichiers** : `llm_router.py`, `cli.py`, `test_adaptation.py`, `test_cli.py`

### Problème

Le routeur devient plus intelligent, donc plus difficile à lire mentalement depuis l'extérieur. Sans trace, un bon comportement reste trop souvent opaque.

### Action

1. Introduire une structure de trace sérialisable.
2. Capturer les éléments qui expliquent réellement la décision.
3. Exposer cette trace sans divulguer de données sensibles.
4. Garantir que le mode trace est strictement passif.

### Champs minimaux

- `token_estimate`
- `prompt_profile`
- `base_order`
- `final_order`
- `provider_availability`
- `health_penalties`
- `selected_provider`
- `fallback_provider`
- `failure_category`
- `decision_reason`
- `outcome`

### Tests à ajouter

- `test_router_trace_reports_contextual_short_profile`
- `test_router_trace_reports_penalty_and_availability`
- `test_router_trace_reports_failure_category`
- `test_router_trace_does_not_change_selected_provider`

### Risque principal

Produire une trace trop bavarde et peu exploitable.

### Règle de qualité

La trace doit expliquer la décision, pas rejouer l'intégralité de l'appel provider.

---

## RL-04 — Matrice de validation routeur exhaustive

**Priorité** : P1  
**Sévérité** : 🔴  
**Dépendance** : RL-03  
**Fichiers** : `test_adaptation.py`, éventuellement fichier routeur dédié

### Problème

Les tests actuels sont bons, mais encore empilés par scénario. Le routeur mérite une couverture structurée comme composant propre.

### Action

1. Regrouper la couverture par profils et familles de comportement.
2. Coder explicitement la matrice minimale de décision.
3. Conserver un ou deux tests `StoryExtractor.extract_all()` comme garde-fou sur le flux réel.
4. Séparer, si nécessaire, les tests purement routeur des tests plus larges d'adaptation.

### Matrice minimale

| Profil | Succès | Fallback | Cooldown | Quarantaine | Récupération | Contamination croisée |
|---|---|---|---|---|---|---|
| `short` | oui | oui | oui | oui | oui | oui |
| `contextual_short` | oui | oui | oui | oui | oui | oui |
| `long` | oui | oui | oui | oui | oui | oui |

### Sortie attendue

- suite de tests plus lisible ;
- angles morts explicitement fermés ;
- preuve nette que la trace n'a pas cassé le comportement.

---

## RL-05 — Policy explicite et configurable

**Priorité** : P2  
**Sévérité** : 🟠  
**Dépendances** : RL-01, RL-02  
**Fichiers** : `llm_router.py`, `cli.py`, `main.py`, `.env.example`, `README.md`

### Problème

La policy existe déjà, mais sous forme de logique et de constantes distribuées. Tant qu'elle n'est pas formulée comme policy, elle reste difficile à piloter et à expliquer.

### Action

1. Centraliser les constantes dans `RouterPolicy` ou équivalent.
2. Limiter les knobs à ceux qui ont une vraie valeur opérateur.
3. Définir des défauts conservateurs et stables.
4. Préserver la compatibilité des comportements actuels par défaut.

### Knobs réalistes

- `LLM_ROUTER_SHORT_PROVIDER`
- `LLM_ROUTER_PROVIDER_COOLDOWN_SEC`
- `LLM_ROUTER_PROVIDER_MAX_COOLDOWN_SEC`
- `LLM_ROUTER_AUTH_QUARANTINE_SEC`
- `LLM_ROUTER_QUOTA_QUARANTINE_SEC`
- `LLM_ROUTER_TRACE`

### Critère d'acceptation

La policy du routeur devient lisible dans un seul endroit et pilotable sans patcher le code.

---

## RL-06 — Export CLI / compare des traces

**Priorité** : P2  
**Sévérité** : 🟠  
**Dépendances** : RL-03, RL-05  
**Fichiers** : `cli.py`, `main.py`, `README.md`, `test_cli.py`

### Problème

Une trace interne ne suffit pas. Il faut la rendre exploitable depuis les points d'entrée réels du projet.

### Action

1. Ajouter un flag de type `--router-trace-output PATH`.
2. Le supporter au minimum dans `aiprod pipeline`, `aiprod compare` et `main.py`.
3. Pour `compare`, sauvegarder la trace à côté des artefacts déjà générés.
4. S'assurer que l'absence de flag ne change strictement rien au comportement courant.

### Tests à ajouter

- `test_cli_pipeline_can_emit_router_trace_json`
- `test_cli_compare_can_emit_router_trace_json`
- `test_cli_no_trace_flag_preserves_current_behavior`

### Critère d'acceptation

Le routeur devient observable depuis la CLI, pas seulement depuis le code Python.

---

## RL-07 — Validation réelle sur `chapter1.txt`

**Priorité** : P2  
**Sévérité** : 🟠  
**Dépendances** : RL-06  
**Fichiers** : artefacts locaux, README si nécessaire

### Problème

Le routeur est très bien testé, mais la fermeture d'un sous-système passe aussi par un run réel de référence reproductible.

### Action

1. Définir une commande standard de validation réelle avec `--llm-adapter router`.
2. Produire au minimum `compare.json`, `rules.json`, `llm.json` et `router_trace.json`.
3. Vérifier que la trace montre bien au moins un cas contextuel réel.
4. Conserver les artefacts uniquement en local dans `artifacts/`.

### Commande cible

```bash
aiprod compare \
  --input aiprod_adaptation/examples/chapter1.txt \
  --title "Chapter 1" \
  --llm-adapter router \
  --output artifacts/chapter1-router-compare/compare.json \
  --output-format json \
  --rules-output artifacts/chapter1-router-compare/rules.json \
  --llm-output artifacts/chapter1-router-compare/llm.json \
  --router-trace-output artifacts/chapter1-router-compare/router_trace.json
```

### Critère d'acceptation

Le routeur est auditable sur un cas réel standard du repo, pas seulement dans des mocks.

### Exécution réalisée

Deux validations réelles ont été exécutées sur `chapter1.txt` :

1. un run standard pour vérifier la production d'artefacts de comparaison et de trace ;
2. un run multi-chunk forcé via `--max-chars-per-chunk 500` pour démontrer une vraie continuité contextuelle observable.

### Artefacts validés

- `artifacts/chapter1-router-compare/compare.json`
- `artifacts/chapter1-router-compare/rules.json`
- `artifacts/chapter1-router-compare/llm.json`
- `artifacts/chapter1-router-compare/router_trace.json`
- `artifacts/chapter1-router-compare/compare_forced_chunks.json`
- `artifacts/chapter1-router-compare/rules_forced_chunks.json`
- `artifacts/chapter1-router-compare/llm_forced_chunks.json`
- `artifacts/chapter1-router-compare/router_trace_forced_chunks.json`

### Résultat observé

Le run standard prouve que le chemin réel CLI produit bien les artefacts attendus.

Le run forcé prouve le comportement multi-chunk réellement utile pour la clôture : la trace contient `5` décisions routeur, dont `4` avec `prompt_profile: contextual_short`, toutes routées vers Gemini avec `decision_reason: contextual short prompt prefers gemini`.

### Statut

RL-07 est clôturé.

---

## RL-08 — Documentation finale et runbook opérateur

**Priorité** : P3  
**Sévérité** : 🟡  
**Dépendances** : RL-05, RL-06, RL-07  
**Fichiers** : `README.md`, `.env.example`, éventuellement `tasks/lessons.md`

### Problème

Une logique routeur mature mais non documentée retombe vite au statut de boîte noire privée du développeur qui l'a écrite.

### Action

1. Documenter les profils de prompt et leurs priorités de base.
2. Documenter la taxonomie d'erreurs provider.
3. Documenter le sens des champs de trace routeur.
4. Ajouter un mini runbook opérateur.
5. Délimiter explicitement le hors périmètre pour éviter les attentes floues.

### Runbook minimal attendu

- si `auth` : vérifier la configuration et ne pas attendre une auto-récupération ;
- si `quota` : traiter comme un problème de capacité, pas comme une instabilité transitoire ;
- si `rate_limit` : attendre la fenêtre de récupération ;
- si `schema` : inspecter le type de prompt et la sortie provider ;
- si `transient` : laisser le routeur gérer le backoff.

### Critère d'acceptation

Un opérateur peut comprendre et exploiter le routeur sans lire le code.

### Exécution réalisée

Le README expose maintenant :

1. les commandes `pipeline`, `compare` et `main.py` avec export de trace routeur ;
2. les knobs `LLM_ROUTER_AUTH_QUARANTINE_SEC`, `LLM_ROUTER_QUOTA_QUARANTINE_SEC` et `LLM_ROUTER_SHORT_PROVIDER` ;
3. le nouveau levier `--max-chars-per-chunk` pour forcer une validation réelle multi-chunk ;
4. le sens opérateur des catégories d'échec et de la trace routeur.

Le `.env.example` documente les quarantaines `auth` et `quota`.

### Statut

RL-08 est clôturé.

---

## Jalons de clôture

| Jalon | Condition de passage | Étapes requises | État |
|---|---|---|---|
| G1 | le routeur comprend la nature des échecs | RL-01 | atteint |
| G2 | le routeur réagit correctement aux échecs | RL-02 | atteint |
| G3 | le routeur peut expliquer sa décision | RL-03, RL-04 | atteint |
| G4 | le routeur est pilotable et observable en run réel | RL-05, RL-06, RL-07 | atteint |
| G5 | le routeur est documenté et clôturé | RL-08 | atteint |

Règle : ne pas considérer G3 atteint si la trace existe mais n'est pas testée sur les vrais profils de prompt.

---

## Protocole de validation obligatoire

À chaque étape substantielle :

```bash
pytest aiprod_adaptation/tests/test_adaptation.py -q --tb=short
pytest aiprod_adaptation/tests/test_cli.py -q --tb=short
pytest aiprod_adaptation/tests/ -q --tb=short
ruff check .
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py --strict
```

Pour RL-06 et RL-07, ajouter en plus une validation réelle sur `chapter1.txt`.

---

## Invariants non négociables

1. Aucun fallback silencieux si `require_llm=True`.
2. Aucun `# type: ignore`.
3. Aucun comportement non déterministe ajouté au routeur.
4. Le mode trace ne modifie jamais la décision.
5. Les erreurs utilisateur restent lisibles malgré l'enrichissement machine des catégories.
6. Les artefacts routeur restent locaux et non versionnés dans `artifacts/`.
7. La configuration par défaut doit rester simple, stable et sûre.

---

## Hors périmètre explicite

Les sujets suivants ne sont pas nécessaires pour clôturer la partie routeur :

1. apprentissage statistique ou scoring ML ;
2. persistance disque de la santé provider entre plusieurs processus ;
3. auto-tuning par benchmark massif ;
4. ajout de providers supplémentaires ;
5. télémétrie distante ou métriques distribuées.

Si ces sujets deviennent prioritaires, ils relèvent d'un futur plan `router_v2`, pas de cette clôture.

---

## Ordre d'exécution recommandé

```text
RL-01  Taxonomie d'échecs provider
  ↓
RL-02  Réactions différenciées du routeur
  ↓
RL-03  Trace de décision
  ↓
RL-04  Matrice de validation exhaustive
  ↓
RL-05  Policy explicite et configurable
  ↓
RL-06  Export CLI / compare des traces
  ↓
RL-07  Validation réelle sur chapter1
  ↓
RL-08  Documentation finale et runbook
```

Pourquoi cet ordre :

- on ne rend pas observable une logique qui n'a pas encore de sémantique stable ;
- on ne documente pas une policy qui n'est pas encore figée ;
- on ne déclare pas le routeur terminé sans run réel de référence.

---

## Résultat attendu après exécution complète

À l'issue de l'exécution réelle de ce plan, le routeur est :

- juste dans son choix provider ;
- robuste face aux providers flappy ;
- équitable vis-à-vis des différents profils de prompt ;
- explicable par artefact ;
- pilotable par policy claire ;
- validé sur scénario réel ;
- documenté comme un composant de production.

En pratique, cela signifie que la partie `routeur` ne sera plus une intelligence implicite cachée dans `llm_router.py`, mais une pièce du système dont on peut lire, tester, piloter et auditer la décision.
