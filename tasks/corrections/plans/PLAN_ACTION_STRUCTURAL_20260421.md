---
modele: sonnet-4.6
mode: agent
contexte: codebase
source_audit: tasks/audits/resultats/audit_structural_aiprod.md
creation: 2026-04-21 à 22:13
---

# PLAN D'ACTION — AUDIT STRUCTUREL — 2026-04-21

**Source** : tasks/audits/resultats/audit_structural_aiprod.md  
**Généré le** : 2026-04-21 à 22:13  
**Corrections totales** : 8 (P1: 0 · P2: 3 · P3: 5)

---

## Résumé

Aucun problème critique (P1) : les 278 tests passent, le pipeline déterministe est intact.  
3 corrections P2 portent sur la règle projet "aucun `# type: ignore`" (cli.py), le couplage `character_prepass → storyboard` (DEFAULT_STYLE_TOKEN), et l'incohérence des aliases backward-compat.  
5 corrections P3 sont du nettoyage pur : dead code `novel_pipe.py`, module doc-only `duration_rules.py`, méthode orpheline `prepass_character_sheets()`, backends sans CLI, et refactoring optionnel de `run_pipeline()`.

---

## Corrections P2 — IMPORTANT

### [SS-01] — Supprimer le couplage DEFAULT_STYLE_TOKEN

**Priorité** : P2  
**Sévérité** : 🟠  
**Fichier** : `aiprod_adaptation/image_gen/character_prepass.py:14`  
**Problème** : `character_prepass.py` importe `DEFAULT_STYLE_TOKEN` depuis `storyboard.py`. Couplage inter-module pour une simple constante string : toute modification de `storyboard.DEFAULT_STYLE_TOKEN` répercute un changement de comportement silencieux dans `CharacterPrepass`.  
**Action** : Supprimer l'import de `storyboard`. Déclarer la constante directement dans `character_prepass.py` :

```python
# character_prepass.py — remplacer la ligne 14 par :
_DEFAULT_STYLE_TOKEN = (
    "cinematic storyboard, 16:9 aspect ratio, film grain, anamorphic lens, color graded"
)
```

Remplacer l'unique usage `DEFAULT_STYLE_TOKEN` (ligne 43) par `_DEFAULT_STYLE_TOKEN`.  
**Tests impactés** : `test_image_gen.py` (CharacterPrepass tests)  
**Risque** : faible — constante identique, comportement inchangé.

---

### [SS-02] — Éliminer les # type: ignore dans cli.py

**Priorité** : P2  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/cli.py:35,50,59`  
**Problème** : 3 occurrences de `# type: ignore[no-any-return]` sur le retour `cls()` dans `_load_image_adapter()`, `_load_video_adapter()`, `_load_audio_adapter()`. Viole la règle projet "Aucun `# type: ignore` dans le codebase". `getattr(module, class_name)` retourne `Any`, donc `cls()` est `Any`, incompatible avec le type de retour déclaré.  
**Action** : Remplacer `cls()` par `typing.cast(ReturnType, cls())` dans chacune des 3 fonctions. Ajouter `import typing` si absent (vérifier — il n'est pas encore importé).

```python
# _load_image_adapter (ligne 35)
import typing
return typing.cast(ImageAdapter, cls())

# _load_video_adapter (ligne 50)
return typing.cast(VideoAdapter, cls())

# _load_audio_adapter (ligne 59)
return typing.cast(AudioAdapter, cls())
```

**Tests impactés** : `mypy aiprod_adaptation/cli.py`  
**Risque** : faible — `typing.cast` est un no-op au runtime.

---

### [SS-03] — Ajouter DeprecationWarning aux aliases restants

**Priorité** : P2  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/core/pass3_shots.py:185`, `aiprod_adaptation/core/pass2_visual.py:166`  
**Problème** : `atomize_shots = simplify_shots` (pass3) et `transform_visuals = visual_rewrite` (pass2) sont de simples réassignations, sans `DeprecationWarning`. Incohérence avec `compile_output` (pass4_compile.py:76) qui émet un warning explicite. Un appelant externe utilisant ces noms ne sera jamais notifié de la migration.  
**Action** : Convertir les deux aliases en fonctions wrapper émettant un `DeprecationWarning` :

```python
# pass3_shots.py — remplacer la ligne 185 par :
def atomize_shots(scenes: List[VisualScene]) -> List[ShotDict]:
    """Deprecated. Use simplify_shots()."""
    import warnings
    warnings.warn(
        "atomize_shots() is deprecated. Use simplify_shots().",
        DeprecationWarning,
        stacklevel=2,
    )
    return simplify_shots(scenes)
```

```python
# pass2_visual.py — remplacer la ligne 166 par :
def transform_visuals(scenes: List[RawScene]) -> List[VisualScene]:
    """Deprecated. Use visual_rewrite()."""
    import warnings
    warnings.warn(
        "transform_visuals() is deprecated. Use visual_rewrite().",
        DeprecationWarning,
        stacklevel=2,
    )
    return visual_rewrite(scenes)
```

**Attention** : `test_pipeline.py:43,47` appelle `transform_visuals([])` et `atomize_shots([])`. Ces appels déclenchent désormais un `DeprecationWarning` avant de lever `ValueError`. Ajouter `@pytest.mark.filterwarnings("ignore::DeprecationWarning")` sur les tests concernés, ou capturer le warning dans le test.  
**Tests impactés** : `test_pipeline.py` — vérifier les tests qui utilisent `atomize_shots` et `transform_visuals`  
**Risque** : moyen — les tests qui appellent les aliases doivent être adaptés pour ne pas échouer si `warnings.filterwarnings("error")` est actif.

---

## Corrections P3 — MINEUR

### [SS-04] — Annoter novel_pipe.py comme dead code

**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/core/adaptation/novel_pipe.py:1`  
**Problème** : `novel_pipe.py` contient 4 fonctions (`extract_scenes`, `make_cinematic`, `to_screenplay`, `run_novel_pipe`) dont aucune n'est appelée depuis le code de production. `run_novel_pipe()` lève déjà un `DeprecationWarning` mais le message référence `StoryExtractor.extract()` (qui n'existe pas tel quel — c'est `extract_all()` ou `extract_chunk()`). 2 tests legacy (`test_adaptation.py:128,132`) maintiennent ce module en vie.  
**Action** : Ajouter un commentaire de module en tête de fichier (avant les imports) :

```python
# DEAD CODE — deprecated since StoryExtractor was introduced.
# Retained only for test_adaptation.py legacy tests (test_novel_pipe_*).
# Do not import from this module in production code.
# Scheduled for removal once legacy tests are migrated.
```

Corriger aussi le message de deprecation de `run_novel_pipe()` (ligne 57) :

```python
# Avant :
"run_novel_pipe() is deprecated. Use StoryExtractor.extract() instead."
# Après :
"run_novel_pipe() is deprecated. Use StoryExtractor.extract_all() instead."
```

**Tests impactés** : `test_adaptation.py` (2 tests `test_novel_pipe_*`)  
**Risque** : faible — commentaires uniquement + correction de message, zéro impact fonctionnel.

---

### [SS-05] — Supprimer duration_rules.py ou le convertir en doc

**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/core/rules/duration_rules.py`  
**Problème** : Module Python contenant uniquement une docstring/des commentaires. Zéro code exécutable. Les règles de durée réelles sont dans `verb_categories.py` et `pass3_shots.py`. Ce fichier crée une fausse impression de documentation officielle synchronisée avec le code.  
**Action (option recommandée)** : Transformer en docstring inline dans `pass3_shots.py`. Supprimer `duration_rules.py` ou le vider en gardant une référence :

```python
# duration_rules.py — remplacer tout le contenu par :
"""
Duration rules — documentation only.
Actual implementation: aiprod_adaptation/core/pass3_shots.py (_compute_duration)
Verb lists: aiprod_adaptation/core/rules/verb_categories.py
"""
```

**Tests impactés** : aucun (le module n'est importé par aucun test ni code de production)  
**Risque** : faible.

---

### [SS-06] — Documenter prepass_character_sheets() comme méthode de test uniquement

**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/image_gen/storyboard.py:59`  
**Problème** : `StoryboardGenerator.prepass_character_sheets()` opère sur un `CharacterSheetRegistry` mais n'est invoquée par aucun chemin de production (`engine.py`, `cli.py`, `episode_scheduler.py`). Son existence dans `StoryboardGenerator` alourdit la responsabilité de la classe.  
**Action** : Ajouter un commentaire explicite sur la méthode sans la supprimer (elle est testée) :

```python
def prepass_character_sheets(
    self,
    registry: "CharacterSheetRegistry",
    ...
) -> None:
    """
    Pre-generate character reference images from explicit descriptions.

    NOTE: This method is NOT called by the production pipeline (engine.py,
    EpisodeScheduler, cli.py). It is provided for advanced use cases where
    callers want to inject explicit character sheets before generate().
    """
```

**Tests impactés** : `test_image_gen.py` (3 tests `prepass_character_sheets`)  
**Risque** : faible — modification de docstring uniquement.

---

### [SS-07] — Exposer les backends CSV/JSON-flat via la CLI

**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/cli.py`, `aiprod_adaptation/backends/`  
**Problème** : `CsvExport` et `JsonFlatExport` sont fonctionnels et testés (9 tests) mais inaccessibles à l'utilisateur final sans code Python. `cmd_pipeline` ne propose pas d'option `--format csv|json-flat|json`.  
**Action** : Ajouter `--format` à `cmd_pipeline` :

```python
# build_parser() — ajouter à p_pipeline :
p_pipeline.add_argument(
    "--format",
    choices=["json", "csv", "json-flat"],
    default="json",
    help="Output format (default: json/Pydantic)",
)

# cmd_pipeline() — ajouter après run_pipeline() :
if args.format == "csv":
    from aiprod_adaptation.backends.csv_export import CsvExport
    Path(args.output).write_text(CsvExport().export(output), encoding="utf-8")
elif args.format == "json-flat":
    from aiprod_adaptation.backends.json_flat_export import JsonFlatExport
    Path(args.output).write_text(JsonFlatExport().export(output), encoding="utf-8")
else:
    save_output(output, args.output)
```

**Tests impactés** : `test_backends.py` (inchangé), nouveaux tests CLI si souhaités  
**Risque** : faible — ajout d'une option CLI, aucune modification des backends existants.

---

### [SS-08] — Extraire la continuité optionnelle de run_pipeline()

**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/core/engine.py:88-96`  
**Problème** : L'injection de continuité (`CharacterRegistry`, `EmotionArcTracker`, `PromptEnricher`) est inlinée dans `run_pipeline()` derrière un `if character_descriptions`. Cette logique est fonctionnellement distincte du pipeline de compilation IR et alourdit `run_pipeline()` (3 responsabilités : classify + compile + enrich).  
**Action** : Extraire en fonction privée `_apply_continuity_enrichment(output, character_descriptions, text)` appelée conditionnellement depuis `run_pipeline()`. La signature publique de `run_pipeline()` reste identique.

```python
def _apply_continuity_enrichment(
    output: AIPRODOutput,
    character_descriptions: dict[str, str],
    text: str,
) -> AIPRODOutput:
    from aiprod_adaptation.core.continuity.character_registry import CharacterRegistry
    from aiprod_adaptation.core.continuity.emotion_arc import EmotionArcTracker
    from aiprod_adaptation.core.continuity.prompt_enricher import PromptEnricher
    registry = CharacterRegistry(character_descriptions).build(text)
    EmotionArcTracker().track(output)
    return PromptEnricher(registry).enrich(output)
```

**Tests impactés** : `test_pipeline.py` — tests de continuité  
**Risque** : faible — refactoring interne, comportement identique.

---

## Ordre d'exécution recommandé

| # | ID | Titre | Priorité | Risque | Durée estimée |
|---|---|---|---|---|---|
| 1 | SS-02 | Éliminer les # type: ignore dans cli.py | P2 | faible | ~5 min |
| 2 | SS-01 | Supprimer le couplage DEFAULT_STYLE_TOKEN | P2 | faible | ~5 min |
| 3 | SS-03 | Ajouter DeprecationWarning aux aliases | P2 | moyen | ~15 min |
| 4 | SS-04 | Annoter novel_pipe.py comme dead code | P3 | faible | ~5 min |
| 5 | SS-05 | Convertir duration_rules.py en doc | P3 | faible | ~5 min |
| 6 | SS-06 | Documenter prepass_character_sheets() | P3 | faible | ~5 min |
| 7 | SS-07 | Exposer backends via CLI | P3 | faible | ~15 min |
| 8 | SS-08 | Extraire continuité de run_pipeline() | P3 | faible | ~20 min |

---

## Validation finale

```bash
# Activer l'environnement
venv\Scripts\Activate.ps1

# Tests
pytest aiprod_adaptation/tests/ -v
# → 278/278 (ou + si nouveaux tests ajoutés pour SS-07)

# Type checking
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/cli.py
# → 0 errors

# Linting
ruff check .
# → 0 errors

# Vérification règle projet : aucun # type: ignore hors tests
Select-String -Path "aiprod_adaptation\*.py","aiprod_adaptation\core\*.py","aiprod_adaptation\image_gen\*.py","aiprod_adaptation\video_gen\*.py","aiprod_adaptation\post_prod\*.py" -Pattern "type: ignore" -Recurse
# → 0 résultats hors adapters (runway, kling, replicate, openai_tts, elevenlabs importent des libs untyped)
```
