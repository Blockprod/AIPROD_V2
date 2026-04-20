# AIPROD ADAPTATION ENGINE v2

A **deterministic narrative compiler** that transforms raw narrative text into structured cinematic data.

It is NOT a creative system. It is a strict compiler: same input always produces byte-identical output.

---

## Architecture

```
aiprod_adaptation/
├── core/
│   ├── pass1_segment.py   — PASS 1: Segmentation (text → scene dicts)
│   ├── pass2_visual.py    — PASS 2: Visual transformation (thoughts → physical actions)
│   ├── pass3_shots.py     — PASS 3: Shot atomization (scenes → shot dicts)
│   ├── pass4_compile.py   — PASS 4: Compilation + validation (dicts → Pydantic models)
│   └── engine.py          — run_pipeline() entry point
├── models/
│   └── schema.py          — Scene / Shot / Episode / AIPRODOutput (Pydantic v2)
├── tests/
│   └── test_pipeline.py   — pytest suite (7 categories, 23 test cases)
└── examples/
    └── sample.txt         — Sample narrative input
main.py                    — CLI entry point
pyproject.toml             — Project metadata and dependencies
.env                       — Environment configuration
```

---

## Requirements

- Python 3.11+
- pydantic >= 2.0

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
# Run the pipeline on the sample text
python main.py
```

Output is pretty-printed JSON conforming to `AIPRODOutput`.

---

## Running Tests

```bash
pytest aiprod_adaptation/tests/ -v
```

---

## Pipeline Passes

| Pass | File | Input | Output |
|------|------|-------|--------|
| 1 | `pass1_segment.py` | `str` raw text | `List[dict]` scene dicts |
| 2 | `pass2_visual.py` | `List[dict]` scenes | `List[dict]` scenes (visuals rewritten) |
| 3 | `pass3_shots.py` | `List[dict]` scenes | `List[dict]` shot dicts |
| 4 | `pass4_compile.py` | title + scenes + shots | `AIPRODOutput` (Pydantic) |

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
