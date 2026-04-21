# AIPROD ADAPTATION ENGINE v2

A **deterministic narrative compiler** that transforms raw narrative text into structured cinematic data.

It is NOT a creative system. It is a strict compiler: same input always produces byte-identical output.

---

## Architecture

```
aiprod_adaptation/
├── core/
│   ├── pass1_segment.py   — PASS 1: Segmentation (text → List[RawScene])
│   ├── pass2_visual.py    — PASS 2: Visual transformation (thoughts → physical actions)
│   ├── pass3_shots.py     — PASS 3: Shot atomization (scenes → List[ShotDict])
│   ├── pass4_compile.py   — PASS 4: Compilation + validation (→ Pydantic models)
│   ├── engine.py          — run_pipeline() entry point
│   └── rules/
│       ├── segmentation_rules.py  — LOCATION_PHRASES, TIME_PHRASES
│       ├── emotion_rules.py       — EMOTION_RULES, _INTERNAL_THOUGHT_WORDS
│       └── duration_rules.py      — _MOTION_VERBS, _INTERACTION_VERBS, _PERCEPTION_VERBS
├── models/
│   ├── schema.py          — Scene / Shot / Episode / AIPRODOutput (Pydantic v2)
│   └── intermediate.py    — RawScene / VisualScene / ShotDict (TypedDict inter-pass contracts)
├── tests/
│   └── test_pipeline.py   — pytest suite (8 categories, 33 test cases)
└── examples/
    ├── sample.txt         — Minimal narrative input (smoke test baseline)
    └── chapter1.txt       — Rich narrative input (4 characters, 3+ locations, dialogues)
main.py                    — CLI entry point
pyproject.toml             — Project metadata and dependencies
.env                       — Environment configuration
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

# Full help
python main.py --help
```

Output is pretty-printed JSON conforming to `AIPRODOutput`.

---

## Running Tests

```bash
pytest aiprod_adaptation/tests/ -v
```

33 test cases across 8 categories: empty input, multi-location segmentation, time-jump segmentation, internal-thought conversion, determinism, invalid duration, full pipeline smoke test, real narrative text.

---

## Development — Lint Sequence

```bash
# 1. Style and imports
ruff check aiprod_adaptation/

# 2. Static type checking (strict)
mypy aiprod_adaptation/core/ aiprod_adaptation/models/ --strict

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

## Absolute Invariants

- Fully deterministic: same input → identical output (byte-level)
- No randomness, no LLMs, no external APIs, no datetime, no hashing for ordering
- Raises `ValueError` on any validation failure — never corrects or ignores
- All lists preserve strict input order
- No sets, no implicit sorting

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
- +1 s if prompt length > 80 characters
- Clamped to [3, 8]
