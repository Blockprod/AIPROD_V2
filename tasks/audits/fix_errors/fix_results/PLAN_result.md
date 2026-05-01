---
type: plan_result
projet: AIPROD_V2
plan_date: 2026-04-27
creation: 2026-04-27 à 15:44
source_scan: tasks/audits/fix_errors/fix_results/SCAN_result.md
---

# PLAN_result — PLAN DE CORRECTION PAR BATCHES

---

## RAISONNEMENT DE GROUPEMENT

Les violations P0 (introduites ce session) sont traitées en priorité absolue car :
1. Les `# type: ignore` et `# noqa` sont INTERDITS absolus — bloquants pour toute release.
2. Elles se concentrent dans le module Option A (character_mask → prepass → storyboard → adapter).
3. L'ordre dépendance-first : character_mask → image_adapter → openai_image_adapter → character_prepass/storyboard → tests.

Dépendances critiques identifiées :
- `character_mask.py` ← importé par `character_prepass.py` ← importé par `episode_scheduler.py` ← `cli.py`
- `openai_image_adapter.py` ← importé conditionnellement par `storyboard.py`
- `image_adapter.ImageAdapter` ← sous-classé par `NullImageAdapter` ← utilisé dans tests
- `generate_edit` n'existe pas sur `ImageAdapter/NullImageAdapter` → cause du `type:ignore[override]` dans test_image_gen.py

---

## PLAN

```
PLAN = [
  # ════════════════════════════════════════════════════════════════════
  # BATCH 1 — P0 · character_mask.py + pyproject.toml
  # Bloquer mypy-strict + supprimer type:ignore
  # Dépendance : aucune — feuille du graphe d'import
  # ════════════════════════════════════════════════════════════════════
  {
    batch: 1,
    module: "image_gen/character_mask + config",
    files: [
      "aiprod_adaptation/image_gen/character_mask.py",
      "pyproject.toml"
    ],
    error_types: ["interdit-type_ignore×2", "mypy-import-not-found", "mypy-unused-ignore×2"],
    estimated_fixes: 5,
    difficulty: "Facile",
    actions: [
      "character_mask.py:36 — supprimer '# type: ignore[import-untyped]' sur l'import rembg",
      "character_mask.py:77 — supprimer '# type: ignore[import-untyped]' sur l'import PIL",
      "pyproject.toml — ajouter section [[tool.mypy.overrides]] :",
      "  [[tool.mypy.overrides]]",
      "  module = 'aiprod_adaptation.image_gen.character_mask'",
      "  ignore_missing_imports = true",
      "  (résout import-not-found + unused-ignore × 2 simultanément)",
    ],
    verify: "python -m mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ aiprod_adaptation/cli.py main.py --strict → 0 error"
  },

  # ════════════════════════════════════════════════════════════════════
  # BATCH 2 — P0 · image_adapter.py + openai_image_adapter.py
  # Supprimer noqa PLC0415 + préparer le terrain pour supprimer type:ignore[override] dans tests
  # Dépendance : character_mask.py doit être propre (Batch 1)
  # ════════════════════════════════════════════════════════════════════
  {
    batch: 2,
    module: "image_gen/adapters (base + openai)",
    files: [
      "aiprod_adaptation/image_gen/image_adapter.py",
      "aiprod_adaptation/image_gen/openai_image_adapter.py"
    ],
    error_types: ["interdit-noqa×1", "fondation-generate_edit"],
    estimated_fixes: 3,
    difficulty: "Facile",
    actions: [
      "image_adapter.py — ajouter méthode concrete generate_edit() sur ImageAdapter et NullImageAdapter :",
      "  Dans ImageAdapter (ABC) : méthode concrete (non-abstractmethod) generate_edit(request, reference_rgba) -> ImageResult",
      "  Implémentation par défaut : délègue à self.generate(request)",
      "  (Permet à TrackingAdapter(NullImageAdapter) de l'overrider sans type:ignore[override])",
      "openai_image_adapter.py:138 — déplacer 'import io' en tête de fichier (section imports stdlib)",
      "  Supprimer 'import io  # noqa: PLC0415' dans le corps de generate_edit()",
      "  io est stdlib pur — aucun risque d'import circulaire",
    ],
    verify: "python -m ruff check aiprod_adaptation/image_gen/image_adapter.py aiprod_adaptation/image_gen/openai_image_adapter.py → 0 error ; python -m mypy aiprod_adaptation/image_gen/image_adapter.py --ignore-missing-imports → 0 error"
  },

  # ════════════════════════════════════════════════════════════════════
  # BATCH 3 — P0 · character_prepass.py + storyboard.py
  # Supprimer noqa PLC0415 × 4 + E501 × 2
  # Dépendance : image_adapter.py doit avoir generate_edit (Batch 2)
  # ════════════════════════════════════════════════════════════════════
  {
    batch: 3,
    module: "image_gen/prepass + storyboard",
    files: [
      "aiprod_adaptation/image_gen/character_prepass.py",
      "aiprod_adaptation/image_gen/storyboard.py"
    ],
    error_types: ["interdit-noqa×4", "ruff-E501×2"],
    estimated_fixes: 6,
    difficulty: "Facile",
    actions: [
      "character_prepass.py:114 — déplacer 'import base64' en tête de fichier (stdlib)",
      "character_prepass.py:115 — déplacer 'from aiprod_adaptation.image_gen.character_mask import ...' en tête de fichier",
      "  Même package — aucun import circulaire possible",
      "  Supprimer les deux '# noqa: PLC0415'",
      "character_prepass.py:141 — couper la ligne E501 (wrap avant 120 chars)",
      "storyboard.py:320 — déplacer 'from aiprod_adaptation.image_gen.flux_kontext_adapter import FluxKontextAdapter' en tête",
      "  Vérifier qu'aucun import circulaire n'existe (storyboard → flux_kontext_adapter → storyboard ?)",
      "storyboard.py:406 — déplacer 'from aiprod_adaptation.image_gen.openai_image_adapter import OpenAIImageAdapter' en tête",
      "  openai_image_adapter n'importe pas storyboard → pas de circulaire",
      "  Supprimer les deux '# noqa: PLC0415'",
      "storyboard.py:415 — couper la ligne E501 (wrap condition ou string avant 120 chars)",
    ],
    pre_check: "python -c 'from aiprod_adaptation.image_gen import flux_kontext_adapter' → pas d'erreur (vérifie pas de circulaire)",
    verify: "python -m ruff check aiprod_adaptation/image_gen/character_prepass.py aiprod_adaptation/image_gen/storyboard.py → 0 error"
  },

  # ════════════════════════════════════════════════════════════════════
  # BATCH 4 — P0 · test_image_gen.py
  # Supprimer type:ignore[override] + tous ruff
  # Dépendance : image_adapter.py doit avoir generate_edit (Batch 2)
  # ════════════════════════════════════════════════════════════════════
  {
    batch: 4,
    module: "tests/test_image_gen",
    files: [
      "aiprod_adaptation/tests/test_image_gen.py"
    ],
    error_types: [
      "interdit-type_ignore×1",
      "ruff-F401×2",
      "ruff-I001×8",
      "ruff-ARG002×2",
      "ruff-E501×4"
    ],
    estimated_fixes: 17,
    difficulty: "Facile",
    actions: [
      "L.1361 — supprimer '# type: ignore[override]' sur generate_edit de TrackingAdapter",
      "  Valide car ImageAdapter.generate_edit() est désormais une méthode concrete (Batch 2)",
      "L.1012 — supprimer import 'io' inutilisé",
      "L.1017 — supprimer import '_build_hf_client' inutilisé",
      "L.1361/1408 — renommer 'reference_rgba' → '_reference_rgba' (ARG002)",
      "L.900,926,1012,1041,1215,1237,1331,1375 — trier les blocs d'imports (I001)",
      "  Méthode : ruff --fix sur ce fichier uniquement pour les I001",
      "L.1257,1406,1410 — couper les 3 lignes E501 (wrap avant 120 chars)",
      "  L.1257 — wrap le commentaire de la signature de méthode ou l'argument",
    ],
    verify: "python -m ruff check aiprod_adaptation/tests/test_image_gen.py → 0 error ; python -m pytest aiprod_adaptation/tests/test_image_gen.py -q --tb=short → 1048/X passed"
  },

  # ════════════════════════════════════════════════════════════════════
  # BATCH 5 — P1 · core/pass2_visual.py + core/pass4_compile.py
  # Noqa pré-existants dans core/ — INTERDITS
  # Dépendance : aucune (fichiers indépendants)
  # ════════════════════════════════════════════════════════════════════
  {
    batch: 5,
    module: "core/passes (visual + compile)",
    files: [
      "aiprod_adaptation/core/pass2_visual.py",
      "aiprod_adaptation/core/pass4_compile.py"
    ],
    error_types: ["interdit-noqa×2"],
    estimated_fixes: 2,
    difficulty: "Moyen",
    actions: [
      "pass2_visual.py:314 — _detect_emotional_layer(raw_text, emotion) noqa: ARG001",
      "  Constater si 'emotion' est réellement inutilisé dans le corps de la fonction",
      "  Fix : renommer le paramètre en '_emotion' dans la signature",
      "  OU : utiliser 'emotion' dans la logique si c'est un bug (vérifier la spec)",
      "  Supprimer le '# noqa: ARG001'",
      "pass4_compile.py:245 — 'except Exception:  # noqa: BLE001'",
      "  Identifier les exceptions réelles pouvant être levées dans le bloc try",
      "  Fix : remplacer 'except Exception:' par 'except (OSError, KeyError, ValueError):' ou similaire",
      "  Supprimer le '# noqa: BLE001'",
    ],
    verify: "python -m ruff check aiprod_adaptation/core/pass2_visual.py aiprod_adaptation/core/pass4_compile.py → 0 error ; python -m pytest aiprod_adaptation/tests/ -q --tb=no → 0 failed"
  },

  # ════════════════════════════════════════════════════════════════════
  # BATCH 6 — P1 · test_pass4_cinematic.py + test_rule_engine.py
  # type:ignore[union-attr] pré-existants — remplacement par assert guards
  # Dépendance : aucune (tests indépendants)
  # ════════════════════════════════════════════════════════════════════
  {
    batch: 6,
    module: "tests/cinematic + rule_engine",
    files: [
      "aiprod_adaptation/tests/test_pass4_cinematic.py",
      "aiprod_adaptation/tests/test_rule_engine.py"
    ],
    error_types: ["interdit-type_ignore×10"],
    estimated_fixes: 10,
    difficulty: "Facile",
    actions: [
      "test_pass4_cinematic.py:519 → .pacing_profile.shot_count  # type: ignore[union-attr]",
      "  Fix : ajouter 'assert out.episodes[0].pacing_profile is not None' avant l'accès",
      "  Supprimer le '# type: ignore[union-attr]' (L.519,523,527,550,555,559,563,567 — 8 lignes)",
      "  Pattern à répéter pour pacing_profile (4 tests) et consistency_report (4 tests)",
      "test_rule_engine.py:537,567 — type: ignore[union-attr]",
      "  Fix : assert results[0].conflict is not None avant accès à .conflict.shot_id / .current_value",
      "  Supprimer les 2 type:ignore",
    ],
    verify: "python -m pytest aiprod_adaptation/tests/test_pass4_cinematic.py aiprod_adaptation/tests/test_rule_engine.py -q --tb=short → 0 failed"
  },

  # ════════════════════════════════════════════════════════════════════
  # BATCH 7 — P1 · test_pass2_cinematic.py
  # type:ignore[return-value] — 1 violation, nécessite inspection du type
  # ════════════════════════════════════════════════════════════════════
  {
    batch: 7,
    module: "tests/pass2_cinematic",
    files: [
      "aiprod_adaptation/tests/test_pass2_cinematic.py"
    ],
    error_types: ["interdit-type_ignore×1"],
    estimated_fixes: 1,
    difficulty: "Moyen",
    actions: [
      "test_pass2_cinematic.py:56 — 'return base  # type: ignore[return-value]'",
      "  Inspecter la signature de la fonction helper _make_scene() et le type de 'base'",
      "  Fix probable : annoter le retour comme dict[str, Any] ou ajuster le type déclaré",
      "  Supprimer le type:ignore",
    ],
    verify: "python -m pytest aiprod_adaptation/tests/test_pass2_cinematic.py -q --tb=short → 0 failed"
  },

  # ════════════════════════════════════════════════════════════════════
  # BATCH 8 — P1 · ideogram_image_adapter.py + test_cli.py + test_scheduling.py
  # Violations mécaniques — F401, I001, no-any-return
  # ════════════════════════════════════════════════════════════════════
  {
    batch: 8,
    module: "image_gen/ideogram + tests divers",
    files: [
      "aiprod_adaptation/image_gen/ideogram_image_adapter.py",
      "aiprod_adaptation/tests/test_cli.py",
      "aiprod_adaptation/tests/test_scheduling.py"
    ],
    error_types: ["ruff-F401×3", "mypy-no-any-return×2", "ruff-I001×2", "interdit-noqa×2"],
    estimated_fixes: 7,
    difficulty: "Facile",
    actions: [
      "ideogram_image_adapter.py:4 — supprimer import 'io' inutilisé",
      "ideogram_image_adapter.py:47,140 — supprimer # noqa",
      "  Vérifier pourquoi noqa : probablement S310 (urlopen) — évaluer si warning légitime",
      "  Fix : soit utiliser requests/httpx (déjà en dépendance ?), soit urlopen avec timeout",
      "  En dernier recours — si urllib.request.urlopen est seule option : corriger sans noqa",
      "ideogram_image_adapter.py:48 — annotate return type bytes (cast(bytes, ...) si Any)",
      "ideogram_image_adapter.py:147 — annotate return type str",
      "test_cli.py:1036 — supprimer import 'sys' inutilisé",
      "test_scheduling.py:333 — supprimer import 'json' inutilisé",
      "test_scheduling.py:268,333 — trier blocs d'imports (I001, ruff --fix)",
    ],
    verify: "python -m ruff check aiprod_adaptation/image_gen/ideogram_image_adapter.py aiprod_adaptation/tests/test_cli.py aiprod_adaptation/tests/test_scheduling.py → 0 error"
  },

  # ════════════════════════════════════════════════════════════════════
  # BATCH 9 — P1 · huggingface_image_adapter.py
  # F811 classe redéfinie + F841 var non utilisée + UP024 × 2
  # ════════════════════════════════════════════════════════════════════
  {
    batch: 9,
    module: "image_gen/huggingface",
    files: [
      "aiprod_adaptation/image_gen/huggingface_image_adapter.py"
    ],
    error_types: ["ruff-F811", "ruff-F841", "ruff-UP024×2", "mypy-no-redef"],
    estimated_fixes: 4,
    difficulty: "Complexe",
    actions: [
      "L.70 et L.155 — HuggingFaceImageAdapter défini deux fois (branche conditionnelle)",
      "  Inspecter la structure : probablement 'if HF_AVAILABLE: class ... else: class ... (stub)'",
      "  Fix : une seule classe avec méthode generate() qui lève NotImplementedError si lib absente",
      "  OU : renommer la stub en HuggingFaceImageAdapterStub et exposer un alias",
      "L.99 — supprimer variable 'is_dev' assignée mais non lue",
      "L.89,180 — remplacer EnvironmentError par OSError (UP024)",
    ],
    verify: "python -m ruff check aiprod_adaptation/image_gen/huggingface_image_adapter.py → 0 error ; python -m mypy aiprod_adaptation/image_gen/huggingface_image_adapter.py --ignore-missing-imports → 0 error"
  },

  # ════════════════════════════════════════════════════════════════════
  # BATCH 10 — P1 · replicate_adapter.py
  # N806 × 3 + mypy assignment + attr-defined × 2
  # ════════════════════════════════════════════════════════════════════
  {
    batch: 10,
    module: "image_gen/replicate",
    files: [
      "aiprod_adaptation/image_gen/replicate_adapter.py"
    ],
    error_types: ["ruff-N806×3", "mypy-assignment", "mypy-attr-defined×2"],
    estimated_fixes: 5,
    difficulty: "Moyen",
    actions: [
      "L.152 — déplacer '_MAX_UPSCALE_PIXELS' hors de la fonction, en constante module-level",
      "L.247,248 — déplacer '_MAX_RETRIES' et '_BASE_WAIT' en module-level",
      "L.155 — Image.LANCZOS : utiliser Image.Resampling.LANCZOS (Pillow >= 10.0)",
      "  Ou cast : img.resize(size, getattr(Image, 'Resampling', Image).LANCZOS)",
      "L.155 — incompatible types Image vs ImageFile : annoter la variable comme Image.Image",
      "L.243 — replicate.Client : cast ou typing.cast(Any, replicate).Client si non exporté",
    ],
    verify: "python -m ruff check aiprod_adaptation/image_gen/replicate_adapter.py → 0 error ; python -m mypy aiprod_adaptation/image_gen/replicate_adapter.py --ignore-missing-imports → 0 error"
  },
]
```

---

## RÉSUMÉ

```
RÉSUMÉ:
  total_batches    : 10
  total_files      : 15  (certains fichiers partagés entre batches)
  estimated_fixes  : 60  (violations individuelles supprimées)

  ordre_execution  : [Batch1 → Batch2 → Batch3 → Batch4 → Batch5 → Batch6 → Batch7 → Batch8 → Batch9 → Batch10]

  priorité_P0_session (BLOQUANT) :
    Batch 1 → Batch 2 → Batch 3 → Batch 4
    Ces 4 batches doivent être traités avant tout nouveau run de génération.

  priorité_P1_préexistant :
    Batch 5 → Batch 6 → Batch 7 → Batch 8 → Batch 9 → Batch 10

  dépendances_critiques :
    Batch2 (image_adapter.generate_edit) DOIT précéder Batch4 (test_image_gen type:ignore)
    Batch1 (mypy override) DOIT précéder toute vérification mypy --strict

  violations_après_batches_P0 :
    type_ignore : 0   (14 → 0)
    noqa        : 5   (11 → 5 : idéogramme/replicate pré-existants, Batch 8)
    → Release P0 readiness après Batch 1-4 : 0 interdit ajouté ce session

  violations_après_tous_batches :
    type_ignore : 0   ✅
    noqa        : 0   ✅
    ruff        : 0   ✅
    mypy_strict : 0   ✅
```

---

## COMMANDE P3

Pour lancer chaque batch de correction :
```
#file:tasks/audits/fix_errors/P3_FIX_prompt.md
Applique les corrections du batch demandé.
```
Préciser le numéro de batch : "Applique les corrections du Batch 1."
