---
creation: 2026-04-21 à 21:58
source_audit: tasks/audits/resultats/audit_pipeline_aiprod.md
baseline_commit: 42f99d7
baseline_tests: 278
---

# PLAN D'ACTION — AUDIT PIPELINE — 2026-04-21

**Source** : tasks/audits/resultats/audit_pipeline_aiprod.md  
**Généré le** : 2026-04-21 à 21:58  
**Corrections totales** : 8 (P1:0 · P2:3 · P3:5)

## Résumé

Le pipeline est fonctionnel (278 tests verts, 0 mypy, 0 ruff). Aucun problème critique. Deux problèmes P2 touchent à la robustesse sur textes longs (déduplication cross-chunks agressive dans `extract_all`) et à la maintenabilité du code (alias `compile_output` avec ordre d'arguments inversé + manque de `DeprecationWarning`). Cinq mineurs concernent la cohérence des filtres de pensées internes, les guillemets typographiques, une guard différée d'une passe, un préfixe d'erreur non conforme, et la documentation d'une asymétrie de contrat.

---

## Corrections P2 — IMPORTANT

### [PA-01] — Déduplication cross-chunks trop agressive dans extract_all

**Priorité** : P2  
**Sévérité** : 🟠  
**Fichier** : `aiprod_adaptation/core/adaptation/story_extractor.py:173-181`  
**Problème** : La déduplication par clé `(location, first_character)` dans `extract_all()` élimine silencieusement la seconde occurrence de toute scène ayant même location et même premier personnage, même si elles proviennent de chunks différents et représentent des moments narratifs distincts. Sur un épisode de 45 minutes (135 scènes max, multi-chunks), ce comportement peut supprimer des scènes valides sans aucun log ni exception.  
**Action** : Supprimer la déduplication cross-chunks (les vrais doublons sont rares sur des chunks distincts) ou remplacer la clé par un hash des 200 premiers caractères de `raw_text`.

Option A — suppression de la déduplication (recommandée, la plus sûre) :
```python
# story_extractor.py — extract_all()
all_scenes: list[VisualScene] = []
prior_summary = ""
for chunk in chunks:
    scenes = self.extract_chunk(llm, chunk, budget, prior_summary)
    all_scenes.extend(scenes)
    if scenes:
        locations = ", ".join(s["location"] for s in scenes[-3:])
        prior_summary = f"Last scenes: {locations}."
return all_scenes
```

Option B — clé par contenu :
```python
key = (scene["location"], scene.get("raw_text", "")[:100])
```

**Tests impactés** : `test_adaptation.py::TestLLMRouterCompleteness` (4 tests), `test_pipeline.py` (indirectement via engine)  
**Risque** : Faible. Supprimer la déduplication peut introduire des doublons LLM réels, mais ceux-ci seront filtrés par `StoryValidator`. Option A préférable.

---

### [PA-02] — compile_output sans DeprecationWarning (pass4_compile.py)

**Priorité** : P2  
**Sévérité** : 🟠  
**Fichier** : `aiprod_adaptation/core/pass4_compile.py:76-77`  
**Problème** : L'alias `compile_output(title, scenes, shots)` a un ordre d'arguments inverse par rapport à `compile_episode(scenes, shots, title)`. L'inversion est correctement gérée en interne, mais aucun `DeprecationWarning` n'est émis — un mainteneur qui compare les signatures peut faire un appel positionnel erroné sans aucun signal. 9 appels actifs dans `test_pipeline.py` utilisent cet alias avec `(title, scenes, shots)`.  
**Action** : Ajouter un `DeprecationWarning` avec note sur l'inversion d'ordre.

```python
import warnings

def compile_output(
    title: str,
    scenes: List[VisualScene],
    shots: List[ShotDict],
    episode_id: str = "EP01",
) -> AIPRODOutput:
    """Deprecated. Use compile_episode(scenes, shots, title).
    NOTE: argument order differs from compile_episode (title comes first here).
    """
    warnings.warn(
        "compile_output() is deprecated. Use compile_episode(scenes, shots, title). "
        "NOTE: argument order differs — compile_output takes (title, scenes, shots).",
        DeprecationWarning,
        stacklevel=2,
    )
    return compile_episode(scenes, shots, title, episode_id)
```

**Tests impactés** : `test_pipeline.py` — 9 appels à `compile_output`. Ils continueront de passer (comportement inchangé) mais émettront des warnings dans pytest. Ajouter `@pytest.mark.filterwarnings("ignore::DeprecationWarning")` sur la classe concernée si les warnings deviennent gênants.  
**Risque** : Faible. Aucune régression fonctionnelle, uniquement ajout de warnings.

---

### [PA-03] — Synchroniser _INTERNAL_THOUGHT_WORDS entre Pass2 et StoryValidator

**Priorité** : P2  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/core/rules/emotion_rules.py:45`  
**Problème** : `emotion_rules.py` liste 6 mots (`_INTERNAL_THOUGHT_WORDS`), `story_validator.py` en liste 9 (+ `"felt"`, `"knew"`, `"hoped"`). Les actions contenant `"felt"`, `"knew"`, `"hoped"` ne sont pas filtrées par Pass2 (`_is_internal_thought`), peuvent aboutir dans `visual_actions`, et seront ensuite pénalisées par `StoryValidator`. Ce double passage réduit le score de scènes légitimes si d'autres actions valides co-existent.  
**Action** : Ajouter les 3 mots manquants dans `emotion_rules.py`.

```python
# emotion_rules.py
_INTERNAL_THOUGHT_WORDS: List[str] = [
    "thought", "wondered", "realized", "remembered", "imagined", "believed",
    "felt", "knew", "hoped",
]
```

**Tests impactés** : `test_adaptation.py` (tests Pass2), `test_pipeline.py` (tests end-to-end)  
**Risque** : Faible. Filtre plus agressif en Pass2 → légère réduction du nombre de `visual_actions` sur certains textes. Aucun test existant ne teste ces 3 mots spécifiquement.

---

## Corrections P3 — MINEUR

### [PA-04] — Étendre _DIALOGUE_RE aux guillemets typographiques

**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/core/pass2_visual.py:46`  
**Problème** : `_DIALOGUE_RE = re.compile(r'"([^"]*)"')` capture uniquement les guillemets droits ASCII (`"`). Les guillemets typographiques `"..."` (U+201C / U+201D), fréquents dans les romans anglophones et les textes générés par LLM, ne sont pas capturés. Les dialogues en guillemets courbes sont omis de `VisualScene.dialogues`.  
**Action** :

```python
_DIALOGUE_RE: re.Pattern[str] = re.compile(r'["\u201C]([^"\u201C\u201D]*)["\u201D]')
```

**Tests impactés** : `test_adaptation.py` (tests Pass2 avec dialogues)  
**Risque** : Très faible. Élargit la capture sans casser les patterns existants.

---

### [PA-05] — Guard raw_text vide au niveau scène individuelle (Pass2)

**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/core/pass2_visual.py` — début de `visual_rewrite()`  
**Problème** : Aucune garde sur `raw_text=""` au niveau d'une scène individuelle injectée manuellement (bypass de Pass1). L'erreur est propagée en Pass3 (`visual_actions=[]`) plutôt qu'en Pass2 où le problème est détecté. Comportement fonctionnel mais message d'erreur trompeur.  
**Action** : Ajouter au début de `visual_rewrite()` (ou équivalent) :

```python
for scene in scenes:
    if not scene.get("raw_text", "").strip():
        raise ValueError(
            f"PASS 2: scene '{scene.get('scene_id', '?')}' has empty raw_text."
        )
```

**Tests impactés** : `test_adaptation.py` (tests Pass2 edge cases)  
**Risque** : Très faible. Erreur déclenchée plus tôt — uniquement sur des appels malformés qui échouaient déjà.

---

### [PA-06] — Préfixe de guard StoryValidator non conforme (engine.py)

**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/core/engine.py:74`  
**Problème** : `raise ValueError("StoryValidator: no filmable scenes produced after validation.")` — préfixe `"StoryValidator:"` hétérogène avec la convention `"PASS N:"` des autres gardes du pipeline.  
**Action** :

```python
raise ValueError("PASS 2: StoryValidator produced no filmable scenes after validation.")
```

**Tests impactés** : `test_adaptation.py::TestLLMRouterCompleteness` — si un test vérifie le message d'erreur exact, mettre à jour le test.  
**Risque** : Très faible. Changement purement cosmétique. Vérifier que aucun test ne compare le message d'erreur exact avec `"StoryValidator:"`.

---

### [PA-07] — Documenter l'asymétrie voie rules-based / voie LLM pour pacing/tod_visual/sound

**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/core/pass3_shots.py` — accès aux champs `pacing`, `time_of_day_visual`, `dominant_sound`  
**Problème** : `pacing`, `time_of_day_visual`, `dominant_sound` ont toujours leurs valeurs par défaut sur la voie rules-based. Ce comportement est correct mais n'est pas documenté dans le code de Pass3, ce qui peut induire des mainteneurs en erreur sur la richesse réelle de ces champs en production vs. en test.  
**Action** : Ajouter un commentaire au point d'accès de ces champs :

```python
# NOTE: pacing/time_of_day_visual/dominant_sound are only populated on the LLM path
# (StoryExtractor via Normalizer). On the rule-based path (Pass1→Pass2), these fields
# are always their defaults ("medium" / "day" / "dialogue").
pacing = scene.get("pacing", "medium")
time_of_day_visual = scene.get("time_of_day_visual", "day")
dominant_sound = scene.get("dominant_sound", "dialogue")
```

**Tests impactés** : Aucun (commentaire uniquement).  
**Risque** : Nul.

---

### [PA-08] — Documenter extract_chunk single-chunk sans prior_summary explicite

**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/core/adaptation/story_extractor.py:171`  
**Problème** : `self.extract_chunk(llm, chunks[0], budget)` sans `prior_summary=""` explicite. Fonctionnel (valeur par défaut `""` dans la signature), mais asymétrique avec le path multi-chunks.  
**Action** :

```python
return self.extract_chunk(llm, chunks[0], budget, prior_summary="")
```

**Tests impactés** : Aucun.  
**Risque** : Nul.

---

## Ordre d'exécution recommandé

1. **[PA-03]** — Synchroniser `_INTERNAL_THOUGHT_WORDS` — 1 ligne, risque nul
2. **[PA-06]** — Corriger préfixe guard engine.py — 1 ligne, risque nul
3. **[PA-08]** — Rendre `prior_summary=""` explicite — 1 mot, risque nul
4. **[PA-04]** — Étendre `_DIALOGUE_RE` aux guillemets typographiques — 1 ligne
5. **[PA-07]** — Commenter asymétrie pacing/tod/sound dans pass3_shots.py — commentaire
6. **[PA-05]** — Ajouter guard `raw_text=""` en Pass2 — ~5 lignes
7. **[PA-02]** — Ajouter `DeprecationWarning` à `compile_output` — ~10 lignes
8. **[PA-01]** — Simplifier déduplication `extract_all` — retirer ~5 lignes

> Exécuter les corrections 1–5 en une seule passe (risque nul, toutes indépendantes).  
> Exécuter 6–8 séparément avec validation pytest après chaque étape.

---

## Validation finale

```powershell
# Depuis C:\Users\averr\AIPROD_V2 avec venv activé

# Tests
pytest aiprod_adaptation/tests/ -v --tb=short
# Cible : 278/278 (ou plus si de nouveaux tests sont ajoutés)

# Types
mypy aiprod_adaptation/ --ignore-missing-imports
# Cible : 0 erreurs

# Lint
ruff check .
# Cible : 0 erreurs

# Pipeline end-to-end (sanity check)
python -c "from aiprod_adaptation.core.engine import run_pipeline; print('OK')"
```

---

*Plan généré depuis `audit_pipeline_aiprod.md` — baseline commit `42f99d7` — 278 tests.*
