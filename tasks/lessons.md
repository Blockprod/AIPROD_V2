# AIPROD — Leçons apprises
**Création :** 2026-04-20 à 17:56   (Self-Improvement Loop)

> Lire ce fichier au début de chaque session.
> Mettre à jour après toute correction de l'utilisateur.
> Chaque entrée = un pattern d'erreur à ne plus reproduire.

---

## L-01 · Fonction renommée entre passes → ImportError silencieux

**Contexte** : Prompt de refactoring renomme `compile_output` en `compile_episode` dans pass4_compile.py.
**Erreur** : `test_pipeline.py` importe `compile_output` → `ImportError` à la collecte pytest → 0 tests lancés.
**Règle** : Quand une fonction publique est renommée, toujours ajouter un alias backward-compat (`compile_output = lambda …`) ou mettre à jour toutes les imports simultanément. Vérifier avec `grep -r "old_name"` avant de renommer.
**Ref** : `pass4_compile.py` — session 2026-04-20

---

## L-02 · Fixture de test en format ancien → IndexError ou KeyError silencieux

**Contexte** : `TestInternalThoughts` passait des dicts avec clé `visual_actions` directement à `transform_visuals`, mais après Prompt 3/6 la fonction lit `raw_text`.
**Erreur** : `visual_rewrite` recevait `raw_text=""` → `visual_actions=[]` → `actions[0]` → `IndexError`.
**Règle** : Quand le format inter-passes change, mettre à jour les fixtures de test immédiatement. Toujours vérifier les clés attendues par chaque fonction avant de créer/modifier des fixtures.
**Ref** : `test_pipeline.py::TestInternalThoughts` — session 2026-04-20

---

## L-03 · Segmentation sur paragraphe unique → toujours 1 scène

**Contexte** : `TestMultiLocation._TEXT` était une seule ligne sans `\n\n` — le segmenteur ne créait jamais 2 scènes.
**Erreur** : `test_two_scenes_produced` échouait : `len(scenes) == 1` même avec 2 locations.
**Règle** : Pour tester la segmentation multi-scènes, les deux blocs doivent être séparés par `\n\n` (double newline). Un texte sur une seule ligne n'est qu'un seul paragraphe pour Pass 1.
**Ref** : `test_pipeline.py::TestMultiLocation` — session 2026-04-20

---

## L-04 · Shot.duration_sec sans contrainte Pydantic → test direct inutile

**Contexte** : Prompt 1/6 retire le `Field(ge=3, le=8)` de `Shot.duration_sec`. Le test `test_shot_model_rejects_invalid_duration_directly` appelait `Shot(duration_sec=0)` en espérant une exception Pydantic.
**Erreur** : Aucune exception levée — `Shot(duration_sec=0)` réussissait silencieusement.
**Règle** : La validation de durée [3,8] est dans Pass 4 (`compile_episode`), pas dans le modèle Pydantic. Tester la contrainte via `compile_output("title", [scene], [shot_invalid])` → `ValueError`.
**Ref** : `test_pipeline.py::TestInvalidDuration` — session 2026-04-20

---

## L-05 · `replace_string_in_file` sur un fichier avec beaucoup de code → patchage partiel

**Contexte** : Utilisation de `replace_string_in_file` pour remplacer uniquement un docstring en haut d'un fichier de 250 lignes → le nouveau code s'est ajouté au début mais l'ancien code est resté à la suite.
**Erreur** : `SyntaxError: from __future__ imports must occur at the beginning of the file` — deux blocs `from __future__ import annotations` dans le même fichier.
**Règle** : Pour réécrire entièrement un fichier, utiliser `create_file` + `Copy-Item -Force` plutôt que `replace_string_in_file`. Ne jamais utiliser `replace_string_in_file` pour remplacer uniquement l'en-tête d'un gros fichier quand le corps doit aussi changer.
**Ref** : `pass3_shots.py` — session 2026-04-20

---

## L-06 · Noms de fonctions réels vs noms dans le prompt de spec

**Contexte** : Prompt 5/6 de la spec cite `segment_scenes` (pass1) et `simplify_shots` (pass3), mais les fonctions réelles dans le repo s'appellent `segment` et `atomize_shots` (avec alias `simplify_shots`).
**Erreur** : Implémenter `engine.py` avec `segment_scenes` → `ImportError` à l'exécution.
**Règle** : Toujours vérifier les noms réels des fonctions avec `grep_search` avant d'implémenter un orchestrateur ou un test. La spec peut utiliser un nom différent de l'implémentation réelle.
**Ref** : `engine.py` — session 2026-04-20

---

## L-07 · `"felt"` absent des mots de suppression de Pass 2

**Contexte** : `_INTERNAL_THOUGHT_WORDS` ne contient pas `"felt"`. La phrase "He felt very excited…" passe à travers Pass 2 et apparaît dans `visual_actions`.
**Erreur** : `test_no_internal_thought_in_visual_actions` vérifiant `{"felt"}` → AssertionError.
**Règle** : `_INTERNAL_THOUGHT_WORDS` = `["thought", "wondered", "realized", "remembered", "imagined", "believed"]` (spec exacte Prompt 3/6). `"felt"` est intentionnellement exclu. Les tests doivent vérifier uniquement les mots listés dans la spec, pas une liste élargie.
**Ref** : `pass2_visual.py`, `test_pipeline.py::TestFullPipeline` — session 2026-04-20

---

## L-08 · Logs structlog → stdout corrompt le JSON de main.py

**Contexte** : `structlog` configuré sans préciser le fichier de sortie → logs écrits sur `sys.stdout` par défaut.
**Erreur** : `python main.py | python -m json.tool` → erreur de parsing car le stdout contient du JSON de logs mélangé avec le JSON de sortie.
**Règle** : Toujours configurer structlog avec `logger_factory=structlog.PrintLoggerFactory(file=sys.stderr)`. Les logs vont sur stderr, la sortie pipeline sur stdout. Vérifier avec `python main.py 2>$null | python -m json.tool`.
**Ref** : `engine.py` — session 2026-04-20

---

## L-09 · Ordre des paramètres : compile_output vs compile_episode

**Contexte** : `compile_output(title, scenes, shots)` (ancien) vs `compile_episode(scenes, shots, title)` (nouveau Prompt 5/6).
**Erreur** : L'alias `compile_output = compile_episode` sans inversion d'arguments cassait silencieusement les appels des tests qui utilisaient l'ordre `(title, scenes, shots)`.
**Règle** : Quand l'ordre des paramètres change entre deux versions, l'alias de compat doit réordonner explicitement : `def compile_output(title, scenes, shots): return compile_episode(scenes, shots, title)`. Ne jamais faire une simple assignation `alias = new_func` si la signature diffère.
**Ref** : `pass4_compile.py` — session 2026-04-20
