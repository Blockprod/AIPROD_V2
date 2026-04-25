# AIPROD ADAPTATION ENGINE v2

AIPROD Adaptation Engine v2 est un compilateur narratif déterministe écrit en Python qui transforme un texte brut (roman, script, synopsis) en une représentation structurée de séquences visuelles exploitables dans des pipelines de génération de contenu. Le système repose sur une architecture en quatre passes strictes : segmentation du texte en scènes via des règles explicites (changements de lieu, de temps ou d'action), transformation des éléments narratifs abstraits (pensées, émotions) en actions physiques observables, décomposition de ces actions en shots atomiques accompagnés de descriptions visuelles textuelles et de durées calculées de manière déterministe, puis validation et compilation finale en un modèle de données hiérarchique typé (`AIPRODOutput` via Pydantic). Le moteur garantit un déterminisme strict — même entrée, même sortie au niveau byte — sans recours à des modèles IA, sans aléatoire ni dépendance externe. Le résultat constitue une forme intermédiaire orientée "prompt visuel structuré", servant de base à des couches aval (export, transformation ou intégration), tout en restant volontairement découplé des moteurs de rendu finaux.

---

## Architecture

```
aiprod_adaptation/
├── core/
│   ├── pass1_segment.py      — PASS 1: Segmentation (text → List[RawScene])
│   ├── pass2_visual.py       — PASS 2: Visual transformation (thoughts → physical actions)
│   ├── pass3_shots.py        — PASS 3: Shot atomization (scenes → List[ShotDict])
│   ├── pass4_compile.py      — PASS 4: Compilation + validation (→ Pydantic models)
│   ├── engine.py             — run_pipeline() entry point
│   └── rules/
│       ├── segmentation_rules.py    — LOCATION_PHRASES, TIME_PHRASES
│       ├── emotion_rules.py         — EMOTION_RULES, _INTERNAL_THOUGHT_WORDS
│       ├── duration_rules.py        — _MOTION_VERBS, _INTERACTION_VERBS, _PERCEPTION_VERBS
│       └── cinematography_rules.py  — SHOT_TYPE_RULES, CAMERA_MOVEMENT_*_KEYWORDS
├── models/
│   ├── schema.py             — Scene / Shot / Episode / AIPRODOutput (Pydantic v2)
│   └── intermediate.py       — RawScene / VisualScene / ShotDict (TypedDict inter-pass contracts)
├── backends/
│   ├── base.py               — BackendBase (abstract export interface)
│   ├── csv_export.py         — CsvExport (one row per shot, 8 columns)
│   └── json_flat_export.py   — JsonFlatExport (flat list of shot objects)
├── tests/
│   ├── test_pipeline.py      — pytest suite (9 categories, 39 test cases)
│   └── test_backends.py      — pytest suite (2 categories, 6 test cases)
└── examples/
    ├── sample.txt            — Minimal narrative input (smoke test baseline)
    └── chapter1.txt          — Rich narrative input (4 characters, 3+ locations, dialogues)
main.py                       — CLI entry point
pyproject.toml                — Project metadata and dependencies
```

---

## Requirements

- Python 3.11+
- pydantic >= 2.0
- structlog >= 21.0

---

## Installation

```bash
# Create and activate the virtual environment
py -3.11 -m venv venv
venv\Scripts\activate      # Windows PowerShell

# Install dependencies
pip install -e ".[dev]"
```

---

## Usage

```bash
# Run the pipeline on a narrative text file
python main.py --input aiprod_adaptation/examples/sample.txt

# With a custom title and episode ID
python main.py --input chapter.txt --title "Episode 1" --episode-id EP01

# Write output to a file instead of stdout
python main.py --input chapter.txt --output output.json

# Export as CSV or flat JSON
python main.py --input chapter.txt --output output.csv --format csv
python main.py --input chapter.txt --output output.json --format json-flat

# Full help
python main.py --help

# Compare rules vs LLM on the same input via the packaged CLI
aiprod compare --input aiprod_adaptation/examples/chapter1.txt --title "Chapter 1"

# Also persist the rules and LLM JSON outputs used by the comparison
aiprod compare --input aiprod_adaptation/examples/chapter1.txt --title "Chapter 1" --output compare.txt --rules-output rules.json --llm-output llm.json

# Emit the comparison summary itself as structured JSON
aiprod compare --input aiprod_adaptation/examples/chapter1.txt --title "Chapter 1" --output compare.json --output-format json

# Force router to prefer Gemini on short prompts for one invocation
aiprod pipeline --input aiprod_adaptation/examples/chapter1.txt --title "Chapter 1" --output output.json --llm-adapter router --router-short-provider gemini --require-llm

# Persist the router decision trace alongside the pipeline output
aiprod pipeline --input aiprod_adaptation/examples/chapter1.txt --title "Chapter 1" --output output.json --llm-adapter router --router-trace-output router-trace.json --require-llm

# Force a real multi-chunk router run on chapter1 and persist the full trace history
aiprod compare --input aiprod_adaptation/examples/chapter1.txt --title "Chapter 1" --llm-adapter router --output compare.json --output-format json --rules-output rules.json --llm-output llm.json --router-trace-output router-trace.json --max-chars-per-chunk 500

# Same override on the direct entry point
python main.py --input aiprod_adaptation/examples/chapter1.txt --output output.json --llm-adapter router --router-short-provider gemini --require-llm

# Same trace export on the direct entry point
python main.py --input aiprod_adaptation/examples/chapter1.txt --output output.json --llm-adapter router --router-trace-output router-trace.json --require-llm

# Same forced multi-chunk validation on the direct entry point
python main.py --input aiprod_adaptation/examples/chapter1.txt --output output.json --llm-adapter router --router-trace-output router-trace.json --max-chars-per-chunk 500 --require-llm
```

## Story Workflow

To choose a different story, change the text file passed to `--input`.

Recommended workflow:

```bash
# 1. Start from the reusable template
copy stories/story_template.txt stories/my_new_story.txt

# 2. Edit stories/my_new_story.txt with your own synopsis, script, or chapter

# 3. Compile the story into AIPROD IR
aiprod pipeline --input stories/my_new_story.txt --title "My New Story" --output out/my_new_story_ir.json --llm-adapter router --pipeline-mode generative --require-llm

# 4. Generate media from that compiled story
aiprod schedule --input out/my_new_story_ir.json --output out/my_new_story_run --image-adapter runway --video-adapter runway --audio-adapter runway
```

Template file:
- `stories/story_template.txt`

Practical rule:
- one file per story
- change `--input`, `--title`, and `--output` for each new video project

Optional LLM environment knobs:
- `GEMINI_MODEL` overrides the primary Gemini model, default `gemini-2.5-flash`
- `GEMINI_FALLBACK_MODELS` defines comma-separated Gemini fallback models tried on transient provider failures
- `LLM_ROUTER_SHORT_PROVIDER` selects the preferred short-text provider for `router` (`claude` by default, `gemini` also supported)
- `LLM_ROUTER_PROVIDER_COOLDOWN_SEC` controls how long the router avoids retrying a provider that just failed within the same process (default: `300` seconds)
- `LLM_ROUTER_PROVIDER_MAX_COOLDOWN_SEC` caps the adaptive router backoff after repeated provider failures in the same process (default: `2400` seconds)
- `LLM_ROUTER_AUTH_QUARANTINE_SEC` overrides the longer router quarantine used for authentication failures
- `LLM_ROUTER_QUOTA_QUARANTINE_SEC` overrides the longer router quarantine used for quota and billing failures

Optional router CLI knob:
- `--router-short-provider claude|gemini` overrides the short-text router preference for the current `pipeline`, `compare`, or `main.py` invocation only
- `--router-trace-output PATH` writes the router decision trace JSON for `pipeline`, `compare`, or `main.py` when the router adapter is used
- `--max-chars-per-chunk N` overrides the StoryExtractor chunk size for the current invocation and is useful to force a real multi-chunk router validation on shorter inputs like `chapter1.txt`
- `aiprod compare --output-format json` writes the comparison summary as structured JSON instead of plain text

Router behaviour notes:
- prompts containing `CONTEXT FROM PREVIOUS SCENES:` are treated as continuity-heavy and are routed to Gemini first, even when they are short
- router failures are now classified (`transient`, `rate_limit`, `auth`, `quota`, `schema`, `unknown`) so cooldown and quarantine behavior can differ by failure type
- when router trace export is enabled, the JSON contains `trace_history` for the run and `last_trace` for quick inspection

Output format:
- `json` (default) — pretty-printed `AIPRODOutput` with nested episodes/scenes/shots
- `csv` — one row per shot: `episode_id, scene_id, shot_id, shot_type, camera_movement, prompt, duration_sec, emotion`
- `json-flat` — flat JSON array, one object per shot

---

## Running Tests

```bash
pytest aiprod_adaptation/tests/ -v
```

42 test cases across 9 categories: empty input, multi-location segmentation, time-jump segmentation, internal-thought conversion, determinism, invalid duration, full pipeline smoke test, real narrative text, shot structure validation.

---

## Development — Lint Sequence

```bash
# 1. Style and imports
ruff check aiprod_adaptation/

# 2. Static type checking (strict)
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ aiprod_adaptation/backends/ --strict

# 3. Tests
pytest aiprod_adaptation/tests/ -v
```

All three commands must pass before any commit.

---

## Pipeline Passes

| Pass | File | Input | Output |
|------|------|-------|--------|
| 1 | `pass1_segment.py` | `str` raw text | `List[RawScene]` |
| 2 | `pass2_visual.py` | `List[RawScene]` | `List[VisualScene]` |
| 3 | `pass3_shots.py` | `List[VisualScene]` | `List[ShotDict]` |
| 4 | `pass4_compile.py` | title + scenes + shots | `AIPRODOutput` (Pydantic v2) |

---

## Shot IR Fields

Each `Shot` in the output carries structured cinematic fields:

| Field | Type | Values | Description |
|---|---|---|---|
| `shot_type` | `str` | `wide` · `medium` · `close_up` · `pov` | Framing type, derived deterministically from action verbs |
| `camera_movement` | `str` | `static` · `follow` · `pan` | Camera behaviour: follows motion, pans on interaction, static otherwise |
| `prompt` | `str` | free text | Visual description without any prefix |
| `duration_sec` | `int` | 3–8 | Duration clamped to [3, 8] |
| `emotion` | `str` | — | Dominant emotion of the parent scene |

---

## Cinematography Rules (deterministic)

**`shot_type` — first match wins:**

| Rule | Trigger keywords |
|---|---|
| `pov` | `pov`, `point of view` |
| `close_up` | facial words: smile, frown, jaw, eyes, stare, glare… |
| `wide` | motion words: walk, run, move, approach, rush… |
| `medium` | fallback (default) |

**`camera_movement`:**

| Value | Condition |
|---|---|
| `follow` | motion verb present (walk, run, enter, arrive…) |
| `pan` | interaction verb present, no motion (touch, grab, give…) |
| `static` | default |

---

## Absolute Invariants

- Fully deterministic: same input → identical output (byte-level)
- No randomness, no LLMs, no external APIs, no datetime, no hashing for ordering
- Raises `ValueError` on any validation failure — never corrects or ignores
- All lists preserve strict input order
- No sets, no implicit sorting
- Core never imports from backends

---

## Emotion → Physical Action Mapping

| Emotion | Observable Action |
|---------|-------------------|
| angry | clenches fists, jaw tightens, steps forward aggressively |
| scared | trembles, takes backward steps, eyes widen |
| sad | lowers head, moves slowly, shoulders slumped |
| happy | smiles broadly, moves with energy, gestures openly |
| nervous | fidgets, paces, bites lip |

---

## Shot Duration Rules (deterministic)

- Base = 3 seconds
- +1 s if motion verb present
- +1 s if interaction verb present
- +1 s if perception verb present
- +1 s if action description > 10 words
- Clamped to [3, 8]
