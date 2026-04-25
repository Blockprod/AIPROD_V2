"""
Segmentation rules v3 — AIPROD_Cinematic Pass 1.

Single source of truth for all segmentation triggers used by
`pass1_segment.py`. All tables are plain Python data — JSON-serialisable,
fully deterministic, easily extensible.

Tables
------
LOCATION_PHRASES       (v2 compat — extended)
SUBLOCATION_PHRASES    (sub-location within the same parent location)
TIME_PHRASES           (v2 compat — extended)
FLASHBACK_TRIGGERS     (memory + past-tense cluster markers)
DREAM_TRIGGERS         (surreal / oneiric markers)
MONTAGE_MARKERS        (rapid-sequence prose markers)
ACT_BREAK_MARKERS      (structural act headers, screenplay format)
CLIFFHANGER_MARKERS    (end-of-episode tension markers)
SCENE_TYPE_WEIGHTS     (emotional weight per scene_type for arc scoring)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Location / sub-location phrases
# ---------------------------------------------------------------------------

#: Extended v2 list.  Each entry must end with a space so extraction picks
#: the noun phrase that follows without stripping too early.
LOCATION_PHRASES: list[str] = [
    # v2 originals
    "in the ",
    "inside the ",
    "at the ",
    "entered the ",
    "arrived at ",
    # v3 additions
    "moved to the ",
    "returned to the ",
    "stepped into the ",
    "stepped out of the ",
    "outside the ",
    "on the roof of the ",
    "beneath the ",
    "above the ",
    "across the ",
    "through the ",
    "beyond the ",
]

#: Sub-location triggers — a spatial shift within the same parent location.
#: When detected, a new CinematicScene opens with `sublocation` set and
#: `location` inherited from the current scene.
SUBLOCATION_PHRASES: list[str] = [
    "corner of the ",
    "far end of the ",
    "window in the ",
    "back of the ",
    "front of the ",
    "top of the ",
    "bottom of the ",
    "edge of the ",
    "centre of the ",
    "center of the ",
    "entrance to the ",
    "exit of the ",
    "hallway of the ",
    "corridor of the ",
    "rooftop of the ",
    "basement of the ",
    "upper floor of the ",
    "lower level of the ",
]

# ---------------------------------------------------------------------------
# Time phrases
# ---------------------------------------------------------------------------

#: Extended v2 list.
TIME_PHRASES: list[str] = [
    # v2 originals
    "the following morning",
    "the next day",
    "hours later",
    "meanwhile",
    "later",
    # v3 additions
    "weeks later",
    "months later",
    "years later",
    "years earlier",
    "days earlier",
    "moments later",
    "seconds later",
    "that night",
    "that evening",
    "that morning",
    "at dawn",
    "at dusk",
    "at midnight",
    "at noon",
    "the following week",
    "the following evening",
    "the day before",
    "earlier that day",
    "before dawn",
    "after dark",
    "three hours later",
    "two days later",
    "a week later",
    "a month later",
]

# ---------------------------------------------------------------------------
# Flashback detection
# ---------------------------------------------------------------------------

#: Prose memory markers.  When ≥ 1 of these appears within a window of
#: FLASHBACK_WINDOW sentences, the scene is classified as a flashback.
FLASHBACK_TRIGGERS: list[str] = [
    "remembered",
    "recalled",
    "could still",
    "used to",
    "back then",
    "back when",
    "as a child",
    "years ago",
    "long ago",
    "that day when",
    "the last time",
    "she had been",
    "he had been",
    "they had been",
    "it had been",
    "in those days",
    "in another life",
    "before the war",
    "before the accident",
    "before everything changed",
    "the memory of",
    "a memory surfaced",
]

#: Minimum number of flashback trigger hits required to open a flashback scene.
FLASHBACK_MIN_HITS: int = 1

#: Sentence window scanned for flashback hits (centred on trigger paragraph).
FLASHBACK_WINDOW: int = 3

# ---------------------------------------------------------------------------
# Dream / surreal detection
# ---------------------------------------------------------------------------

DREAM_TRIGGERS: list[str] = [
    "dreamed",
    "dreamt",
    "in the dream",
    "in her dream",
    "in his dream",
    "vision of",
    "a vision",
    "as if in a dream",
    "the walls seemed to",
    "everything blurred",
    "reality dissolved",
    "she was floating",
    "he was floating",
    "they were floating",
    "woke up in",
    "couldn't tell if it was real",
    "the ceiling rippled",
    "the floor tilted",
    "colours bled",
    "colors bled",
    "voices without faces",
    "face without a voice",
]

# ---------------------------------------------------------------------------
# Montage detection
# ---------------------------------------------------------------------------

#: Explicit prose markers for a rapid-cut montage passage.
MONTAGE_MARKERS: list[str] = [
    "montage",
    "quick cuts",
    "rapid succession",
    "one after another",
    "flash of",
    "flashes of",
    "glimpse of",
    "glimpses of",
    "a series of",
    "images of",
]

#: Minimum consecutive ultra-short paragraphs (< MONTAGE_MAX_SENTENCES each)
#: to auto-detect a montage sequence without explicit marker.
MONTAGE_MIN_SHORT_PARAS: int = 3
MONTAGE_MAX_SENTENCES:   int = 2   # paragraphs with ≤ this many sentences

# ---------------------------------------------------------------------------
# Structural act-break markers (screenplay / teleplay format)
# ---------------------------------------------------------------------------

#: These strings are matched case-insensitively, stripped, at paragraph start.
ACT_BREAK_MARKERS: dict[str, str] = {
    "teaser":      "teaser",
    "cold open":   "teaser",
    "act one":     "act1",
    "act 1":       "act1",
    "act two":     "act2",
    "act 2":       "act2",
    "act three":   "act3",
    "act 3":       "act3",
    "act four":    "act4",
    "act 4":       "act4",
    "tag":         "tag",
    "end of act":  "act_end",
    "smash cut to": "transition",
    "match cut to": "transition",
}

# ---------------------------------------------------------------------------
# Cliffhanger / episode-end markers
# ---------------------------------------------------------------------------

CLIFFHANGER_MARKERS: list[str] = [
    "cut to black",
    "smash to black",
    "fade to black",
    "to be continued",
    "[end]",
    "end of episode",
    "the signal died",
    "the line went dead",
    "the screen went dark",
    "darkness fell",
    "everything went dark",
    "silence.",
    "the last thing she heard",
    "the last thing he heard",
    "the last thing they heard",
]

# ---------------------------------------------------------------------------
# Scene type → dramatic weight (used to compute emotional_arc_index)
# ---------------------------------------------------------------------------

#: Higher value = more dramatic intensity at this scene_type.
SCENE_TYPE_WEIGHTS: dict[str, float] = {
    "teaser":      0.35,
    "standard":    0.50,
    "montage":     0.60,
    "flashback":   0.40,
    "dream":       0.45,
    "cliffhanger": 0.95,
    "tag":         0.20,
    "transition":  0.30,
}

# ---------------------------------------------------------------------------
# Beat type → arc weight (compounds emotional_arc_index)
# ---------------------------------------------------------------------------

BEAT_TYPE_WEIGHTS: dict[str, float] = {
    "exposition":      0.30,
    "dialogue_scene":  0.50,
    "action":          0.70,
    "transition":      0.25,
    "climax":          1.00,
    "denouement":      0.35,
}

# ---------------------------------------------------------------------------
# Location normalisation
# ---------------------------------------------------------------------------

#: Words stripped from raw location strings before matching against VisualBible.
LOCATION_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "this", "that", "some", "old", "new",
    "large", "small", "dark", "bright", "empty", "crowded",
})
