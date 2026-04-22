---
type: plan
dimension: tests
projet: AIPROD_V2
creation: 2026-04-22 à 10:22
---

# PLAN D'ACTION — TESTS — 2026-04-22
**Source** : tasks/audits/resultats/audit_tests_aiprod.md  
**Généré le** : 2026-04-22 à 10:22  
**Corrections totales** : 8 (P1:0 · P2:1 · P3:7)

## Résumé

La suite de tests est globalement saine (278/278, 92 % couverture). Le seul problème notable est `cli.py` à 73 % : les branches `--output-format csv/json-flat` et les loaders d'adapters non-null ne sont jamais appelés dans les tests. Les 7 corrections mineures ajoutent des tests pour des cas limites identifiés dans les guards (PASS 3 scène vide, PASS 4 titre espaces, engine StoryValidator→[]) et pour des fonctions utilitaires non couvertes (`CostReport.to_summary_str`, `CharacterPrepass` sans personnages, `AudioSynchronizer` vide).

---

## Corrections P1 — CRITIQUE

*Aucune. 278 tests passent, mypy=0, ruff=0. Aucun test critique manquant.*

---

## Corrections P2 — IMPORTANT

### [TA01] — Couvrir branches manquantes de cli.py (73 → ≥90 %)
**Priorité** : P2  
**Sévérité** : 🟠  
**Fichier** : `aiprod_adaptation/tests/test_cli.py` (ajouts), `aiprod_adaptation/cli.py:33-60, 135-139`  
**Problème** : `cli.py` à 73 % de couverture. Branches non testées :  
- `_load_image_adapter("flux"/"replicate")` → chemin importlib  
- `_load_video_adapter("smart"/"runway"/"kling")` → chemin importlib  
- `_load_audio_adapter("elevenlabs"/"openai")` → chemin importlib  
- `cmd_pipeline` avec `--output-format csv` (lignes 135-136)  
- `cmd_pipeline` avec `--output-format json-flat` (lignes 138-139)  

**Action** : Dans `test_cli.py`, ajouter `TestCLIPipelineFormats` avec 2 tests (`csv`, `json-flat`). Pour les loaders d'adapters non-null : ajouter 3 tests qui vérifient que les loaders lèvent `ModuleNotFoundError` ou `ImportError` quand le module backend est absent (patch `importlib.import_module`), ou patcher directement avec `MagicMock`.  

**Tests impactés** : Aucun existant cassé. Nouveaux tests ajoutés à `test_cli.py` (+5 tests environ → total ~283).  
**Risque** : Faible — tests en read-only sur cli.py, aucune modification du code de production.

---

## Corrections P3 — MINEUR

### [TA02] — Test `simplify_shots()` avec scène `visual_actions=[]`
**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/tests/test_pipeline.py` (ajout dans `TestEmptyInput`)  
**Problème** : `pass3_shots.py` lève `ValueError("PASS 3: scene '...' has empty visual_actions.")` pour une scène sans actions visuelles. Ce chemin (ligne 147 de `pass3_shots.py`) n'est pas couvert par les tests.  
**Action** :
```python
def test_pass3_scene_with_empty_visual_actions_raises(self) -> None:
    scene = cast(VisualScene, {
        "scene_id": "SC001", "characters": [], "location": "a room",
        "time_of_day": None, "visual_actions": [], "dialogues": [], "emotion": "neutral",
    })
    with pytest.raises(ValueError, match="PASS 3"):
        simplify_shots([scene])
```
**Tests impactés** : Aucun. Ajout pur dans `TestEmptyInput`.  
**Risque** : Nul.

---

### [TA03] — Test `compile_episode()` avec titre vide (espaces seulement)
**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/tests/test_pipeline.py` (ajout dans `TestEmptyInput`)  
**Problème** : `pass4_compile.py` lève `ValueError("PASS 4: title must not be empty.")` si `title.strip()` est vide, mais seul `""` est testé. `"   "` (espaces) n'est pas testé.  
**Action** :
```python
def test_pass4_whitespace_only_title_raises(self) -> None:
    shot = cast(ShotDict, {
        "shot_id": "SC001_SHOT_001", "scene_id": "SC001",
        "prompt": "someone stands.", "duration_sec": 4,
        "emotion": "neutral", "shot_type": "medium", "camera_movement": "static",
        "metadata": {"time_of_day_visual": "day", "dominant_sound": "dialogue"},
    })
    with pytest.raises(ValueError, match="PASS 4"):
        compile_episode([self._BASE_SCENE], [shot], "   ")
```
**Tests impactés** : Aucun.  
**Risque** : Nul.

---

### [TA04] — Test `run_pipeline` → StoryValidator filtre toutes les scènes
**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/tests/test_adaptation.py` (ajout dans `TestStoryValidator` ou nouvelle classe)  
**Problème** : `engine.py` lève `ValueError("PASS 2: StoryValidator produced no filmable scenes after validation.")` quand `validate_all()` retourne `[]`. Ce chemin (ligne `engine.py:89`) n'est pas couvert.  
**Action** : Patcher `StoryValidator.validate_all` pour retourner `[]` et vérifier que `run_pipeline` lève `ValueError` :
```python
def test_engine_raises_when_story_validator_filters_all_scenes(self) -> None:
    from unittest.mock import patch
    with patch(
        "aiprod_adaptation.core.engine.StoryValidator.validate_all",
        return_value=[],
    ):
        with pytest.raises(ValueError, match="StoryValidator produced no filmable scenes"):
            run_pipeline("John walked into the room.", "T")
```
**Tests impactés** : Aucun.  
**Risque** : Faible — utilise `unittest.mock.patch`.

---

### [TA05] — Test `CharacterPrepass.run()` avec output sans personnages
**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/tests/test_image_gen.py` (ajout dans `TestCharacterPrepass`)  
**Problème** : `character_prepass.py` lignes 72-74 non couvertes : quand `_unique_characters()` retourne `[]` (toutes scènes ont `characters=[]`), `generated=0`, `failed=0`.  
**Action** :
```python
def test_character_prepass_handles_output_with_no_characters(self) -> None:
    from aiprod_adaptation.image_gen.character_prepass import CharacterPrepass
    from aiprod_adaptation.image_gen.image_adapter import NullImageAdapter
    output = _make_output([[]], ["neutral"])  # 1 scène, 0 personnages
    result = CharacterPrepass(adapter=NullImageAdapter(), base_seed=0).run(output)
    assert result.generated == 0
    assert result.failed == 0
```
**Tests impactés** : Aucun.  
**Risque** : Nul — cas valide déjà géré par le code, test manquant seulement.

---

### [TA06] — Test `CostReport.to_summary_str()` format
**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/tests/test_scheduling.py` (ajout dans `TestCostReport`)  
**Problème** : `cost_report.py` ligne 42 (`to_summary_str`) jamais appelée dans les tests.  
**Action** :
```python
def test_cost_report_to_summary_str_format(self) -> None:
    from aiprod_adaptation.core.cost_report import CostReport
    c = CostReport(image_api_calls=3, video_api_calls=2, audio_api_calls=5,
                   llm_tokens_input=100, llm_tokens_output=50)
    s = c.to_summary_str()
    assert "Image: 3 calls" in s
    assert "Video: 2 calls" in s
    assert "Audio: 5 calls" in s
    assert "Total: $0.0000" in s
```
**Tests impactés** : Aucun.  
**Risque** : Nul.

---

### [TA07] — Test `AudioSynchronizer.generate()` avec VideoOutput vide
**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/tests/test_post_prod.py` (ajout dans `TestAudioSynchronizer`)  
**Problème** : `AudioSynchronizer.generate()` avec `VideoOutput.clips=[]` n'est pas testé — résultat attendu : timeline vide, total_duration=0.  
**Action** :
```python
def test_audio_synchronizer_with_empty_clips(self) -> None:
    from aiprod_adaptation.video_gen.video_request import VideoOutput
    empty_video = VideoOutput(title="T", clips=[], total=0, generated=0, failed=0)
    _results, production = AudioSynchronizer(
        adapter=NullAudioAdapter()
    ).generate(empty_video, _video_and_output()[1])
    assert production.timeline == []
    assert production.total_duration_sec == 0
```
**Tests impactés** : Aucun.  
**Risque** : Faible — à vérifier que `AudioSynchronizer.generate()` ne lève pas si clips=[].

---

### [TA08] — Test `CostReport.merge()` avec CostReport vide (élément neutre)
**Priorité** : P3  
**Sévérité** : 🟡  
**Fichier** : `aiprod_adaptation/tests/test_scheduling.py` (ajout dans `TestCostReport`)  
**Problème** : `CostReport.merge(CostReport())` devrait retourner un CostReport identique à l'original (élément neutre). Non testé.  
**Action** :
```python
def test_cost_report_merge_with_empty_is_identity(self) -> None:
    from aiprod_adaptation.core.cost_report import CostReport
    c = CostReport(image_api_calls=3, video_api_calls=2, llm_cost_usd=1.5)
    merged = c.merge(CostReport())
    assert merged.image_api_calls == 3
    assert merged.video_api_calls == 2
    assert merged.llm_cost_usd == 1.5
```
**Tests impactés** : Aucun.  
**Risque** : Nul.

---

## Ordre d'exécution recommandé

```
TA02 → TA03 → TA04 → TA05 → TA06 → TA07 → TA08 → TA01
```

Logique :
- TA02, TA03 : tests purs dans `TestEmptyInput` — ajouts les plus simples, aucun mock
- TA04 : mock `StoryValidator.validate_all` dans `test_adaptation.py` — simple
- TA05 : test `CharacterPrepass` sans perso — dépend du helper `_make_output` existant dans `test_continuity.py`
- TA06, TA08 : tests `CostReport` purement unitaires
- TA07 : test `AudioSynchronizer` vide — vérifier d'abord le comportement du code avant d'écrire le test
- TA01 en dernier : le plus complexe (mock importlib, tests formats CLI)

**Validation finale** :
```powershell
venv\Scripts\Activate.ps1
pytest aiprod_adaptation/tests/ -q --tb=short 2>&1 | Select-Object -Last 3
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py --strict 2>&1 | Select-Object -Last 2
ruff check aiprod_adaptation/ 2>&1 | Select-Object -Last 2
```
Attendu : **≥285 tests passants**, mypy=0, ruff=0.
