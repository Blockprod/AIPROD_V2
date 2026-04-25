"""
PASS 1 — CINEMATIC SEGMENTATION  (AIPROD_Cinematic v3.0)
=========================================================
Input : raw_text: str,  visual_bible: VisualBible | None = None
Output: list[CinematicScene]

Segmentation rules (deterministic, rule-based — no LLM):
---------------------------------------------------------
R01  Location change (LOCATION_PHRASES)           → new scene, location=value
R02  Sub-location shift (SUBLOCATION_PHRASES)     → new scene, sublocation=value, location inherited
R03  Time shift (TIME_PHRASES extended)           → new scene, time_of_day=value
R04  Flashback cluster (FLASHBACK_TRIGGERS ×N)    → scene_type="flashback"
R05  Dream markers (DREAM_TRIGGERS)               → scene_type="dream"
R06  Explicit MONTAGE_MARKERS or ≥3 ultra-short
     consecutive paragraphs                       → scene_type="montage"
R07  ACT_BREAK_MARKERS at paragraph start         → act_position=value
R08  CLIFFHANGER_MARKERS at paragraph end         → scene_type="cliffhanger", flag
R09  VisualBible slug match on location string    → reference_location_id=slug
R10  Character first appearance                   → continuity_flags += FIRST_APPEARANCE
R11  Beat-type category shift (dense keyword hit) → new scene, beat_type=value
R12  Emotional arc index computed continuously    → emotional_arc_index=[0.0,1.0]

Backward compatibility
----------------------
The public `segment()` function returns `list[CinematicScene]`.  CinematicScene
is a superset of RawScene — all mandatory keys are identical.  Downstream
consumers that only access scene_id / characters / location / time_of_day /
raw_text continue to work without modification.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from aiprod_adaptation.models.intermediate import CinematicScene

if TYPE_CHECKING:
    from aiprod_adaptation.core.visual_bible import VisualBible

# ---------------------------------------------------------------------------
# Rule tables (single source of truth)
# ---------------------------------------------------------------------------
from .rules.dop_style_rules import resolve_beat_type
from .rules.segmentation_rules_v3 import (
    ACT_BREAK_MARKERS,
    BEAT_TYPE_WEIGHTS,
    CLIFFHANGER_MARKERS,
    DREAM_TRIGGERS,
    FLASHBACK_MIN_HITS,
    FLASHBACK_TRIGGERS,
    FLASHBACK_WINDOW,
    LOCATION_STOP_WORDS,
    MONTAGE_MARKERS,
    MONTAGE_MAX_SENTENCES,
    MONTAGE_MIN_SHORT_PARAS,
    SCENE_TYPE_WEIGHTS,
    SUBLOCATION_PHRASES,
)
from .rules.segmentation_rules_v3 import (
    LOCATION_PHRASES as LOCATION_PHRASES_V3,
)
from .rules.segmentation_rules_v3 import (
    TIME_PHRASES as TIME_PHRASES_V3,
)

# ---------------------------------------------------------------------------
# Action-category verb tables (unchanged from v2 for R11)
# ---------------------------------------------------------------------------

_MOTION_VERBS: list[str] = [
    "walk", "walked", "run", "ran", "move", "moved", "enter", "entered",
    "arrive", "arrived", "leave", "left", "step", "stepped", "rush", "rushed",
    "hurry", "hurried",
]
_SPEECH_VERBS: list[str] = [
    "said", "say", "told", "tell", "asked", "ask", "replied", "reply",
    "whispered", "whisper", "shouted", "shout", "spoke", "speak",
    "answered", "answer", "called", "call",
]
_PERCEPTION_VERBS: list[str] = [
    "saw", "see", "looked", "look", "heard", "hear", "felt", "feel",
    "noticed", "notice", "watched", "watch", "observed", "observe",
    "sensed", "sense",
]
_INTERACTION_VERBS: list[str] = [
    "gave", "give", "took", "take", "touched", "touch", "held", "hold",
    "grabbed", "grab", "handed", "hand", "pushed", "push", "pulled", "pull",
    "opened", "open", "closed", "close",
]
_STATE_VERBS: list[str] = [
    "was", "were", "is", "are", "became", "become", "seemed", "seem",
    "appeared", "appear", "remained", "remain", "stayed", "stay",
    "waited", "wait",
]

_CATEGORY_VERBS: list[tuple[str, list[str]]] = [
    ("motion",      _MOTION_VERBS),
    ("speech",      _SPEECH_VERBS),
    ("perception",  _PERCEPTION_VERBS),
    ("interaction", _INTERACTION_VERBS),
    ("state",       _STATE_VERBS),
]

_EXCLUDE_WORDS: frozenset[str] = frozenset({
    "The", "A", "An", "He", "She", "They", "We", "It", "His", "Her",
    "Their", "Its", "This", "That", "These", "Those", "Later", "Meanwhile",
    "Suddenly", "Then", "Now", "Here", "There",
})

_GENERIC_LOCATIONS: frozenset[str] = frozenset({
    "room", "door", "table", "window", "wall", "floor",
    "stairs", "hall", "hallway", "corridor",
})


# ---------------------------------------------------------------------------
# Helpers — low-level
# ---------------------------------------------------------------------------

def _make_scene_id(index: int) -> str:
    return f"SCN_{index + 1:03d}"


def _split_sentences(text: str) -> list[str]:
    parts: list[str] = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _action_category(sentence_lower: str) -> str:
    for category, verbs in _CATEGORY_VERBS:
        for verb in verbs:
            if re.search(r"\b" + re.escape(verb) + r"\b", sentence_lower):
                return category
    return "state"


def _detect_location_from_phrases(
    sentence_lower: str, phrase_list: list[str]
) -> str | None:
    """Return the noun phrase following the first matching trigger, or None."""
    for phrase in phrase_list:
        if phrase in sentence_lower:
            idx = sentence_lower.index(phrase) + len(phrase)
            remainder = sentence_lower[idx:]
            match = re.match(r"[a-z0-9 '\-]+", remainder)
            if match:
                raw = match.group(0).strip()
                for conj in (" and ", " but ", " or ", " then ", ","):
                    if conj in raw:
                        raw = raw[: raw.index(conj)]
                raw = raw.strip()
                if not raw or raw in _GENERIC_LOCATIONS:
                    return "Unknown"
                return raw
            return "Unknown"
    return None


def _detect_location(sentence_lower: str) -> str | None:
    return _detect_location_from_phrases(sentence_lower, LOCATION_PHRASES_V3)


def _detect_sublocation(sentence_lower: str) -> str | None:
    return _detect_location_from_phrases(sentence_lower, SUBLOCATION_PHRASES)


def _detect_time(sentence_lower: str) -> str | None:
    for phrase in TIME_PHRASES_V3:
        if phrase in sentence_lower:
            return phrase
    return None


def _collect_confirmed_nouns(all_paragraphs: list[str]) -> frozenset[str]:
    """Pre-scan: words that appear at non-initial token position → proper nouns."""
    confirmed: set[str] = set()
    for para in all_paragraphs:
        for sentence in _split_sentences(para):
            tokens = sentence.split()
            for i, token in enumerate(tokens):
                if i == 0:
                    continue
                clean = re.sub(r"'s?$", "", token).rstrip(".,!?;:\"'")
                if clean.isalpha() and clean[0].isupper() and clean not in _EXCLUDE_WORDS:
                    confirmed.add(clean)
    return frozenset(confirmed)


def _extract_proper_nouns(
    sentences: list[str], confirmed: frozenset[str]
) -> list[str]:
    seen: list[str] = []
    for sentence in sentences:
        tokens = sentence.split()
        for i, token in enumerate(tokens):
            clean = re.sub(r"'s?$", "", token).rstrip(".,!?;:\"'")
            if not clean.isalpha():
                continue
            if not clean[0].isupper():
                continue
            if i == 0 and clean not in confirmed:
                continue
            if clean in _EXCLUDE_WORDS:
                continue
            if clean not in seen:
                seen.append(clean)
    return seen


# ---------------------------------------------------------------------------
# Helpers — cinematic detection
# ---------------------------------------------------------------------------

def _detect_act_break(paragraph: str) -> str | None:
    """
    Match ACT_BREAK_MARKERS against the start of a paragraph (case-insensitive).
    Returns the act_position value (e.g. "teaser", "act1") or None.
    """
    stripped = paragraph.strip().lower()
    for marker, act_pos in ACT_BREAK_MARKERS.items():
        if stripped.startswith(marker):
            return act_pos
    return None


def _detect_cliffhanger(paragraph: str) -> bool:
    """Return True if the paragraph ends with a cliffhanger marker."""
    lowered = paragraph.strip().lower()
    for marker in CLIFFHANGER_MARKERS:
        if lowered.endswith(marker) or marker in lowered:
            return True
    return False


def _detect_flashback(sentences: list[str]) -> bool:
    """
    Return True when FLASHBACK_MIN_HITS trigger words appear within any
    FLASHBACK_WINDOW consecutive sentences.
    """
    window = FLASHBACK_WINDOW
    n = len(sentences)
    for start in range(n):
        end = min(start + window, n)
        chunk = " ".join(sentences[start:end]).lower()
        hits = sum(1 for t in FLASHBACK_TRIGGERS if t in chunk)
        if hits >= FLASHBACK_MIN_HITS:
            return True
    return False


def _detect_dream(sentences: list[str]) -> bool:
    text_lower = " ".join(sentences).lower()
    return any(marker in text_lower for marker in DREAM_TRIGGERS)


def _detect_explicit_montage(sentences: list[str]) -> bool:
    text_lower = " ".join(sentences).lower()
    return any(marker in text_lower for marker in MONTAGE_MARKERS)


def _classify_scene_type(
    sentences: list[str],
    is_cliffhanger: bool,
    is_act_break: bool,
    act_position: str | None,
) -> str:
    """Determine narrative scene type. `act_position` is structural metadata
    stored separately — it does NOT override the narrative classification."""
    if is_cliffhanger:
        return "cliffhanger"
    if _detect_dream(sentences):
        return "dream"
    if _detect_flashback(sentences):
        return "flashback"
    if _detect_explicit_montage(sentences):
        return "montage"
    return "standard"


# ---------------------------------------------------------------------------
# Helpers — VisualBible integration
# ---------------------------------------------------------------------------

def _normalise_location(raw: str) -> str:
    """Lowercase, replace spaces with underscores, strip stop words."""
    tokens = raw.lower().split()
    tokens = [t for t in tokens if t not in LOCATION_STOP_WORDS]
    return "_".join(tokens) if tokens else raw.lower().replace(" ", "_")


def _resolve_location_id(
    location: str, visual_bible: VisualBible | None
) -> str | None:
    """
    Match a raw location string against the VisualBible location slugs.

    Strategy (priority order):
    1. Exact normalised match (e.g. "the archive" → "the_archive")
    2. Substring: slug contains all tokens of the normalised location
    3. Substring: normalised location contains all tokens of the slug
    Returns the slug string or None.
    """
    if visual_bible is None:
        return None
    norm = _normalise_location(location)
    slugs: list[str] = list(visual_bible._data.get("locations", {}).keys())
    # Pass 1: exact match
    if norm in slugs:
        return norm
    # Pass 2: slug tokens ⊆ location tokens
    loc_tokens = set(norm.split("_"))
    for slug in slugs:
        slug_tokens = set(slug.split("_"))
        if slug_tokens and slug_tokens <= loc_tokens:
            return slug
    # Pass 3: location tokens ⊆ slug tokens
    for slug in slugs:
        slug_tokens = set(slug.split("_"))
        if loc_tokens and loc_tokens <= slug_tokens:
            return slug
    return None


# ---------------------------------------------------------------------------
# Helpers — emotional arc index
# ---------------------------------------------------------------------------

def _compute_arc_index(
    scene_position: int,
    total_scenes_estimated: int,
    beat_type: str,
    scene_type: str,
) -> float:
    """
    Continuous dramatic intensity in [0.0, 1.0].

    arc = clamp(position_ratio × beat_weight × scene_weight, 0.0, 1.0)

    We multiply by position_ratio so early scenes have lower index than
    late scenes with the same beat type (natural escalation).
    """
    if total_scenes_estimated <= 0:
        return 0.0
    position_ratio = scene_position / max(total_scenes_estimated, 1)
    beat_w  = BEAT_TYPE_WEIGHTS.get(beat_type, 0.5)
    scene_w = SCENE_TYPE_WEIGHTS.get(scene_type, 0.5)
    raw = position_ratio * beat_w * scene_w
    return round(min(1.0, max(0.0, raw)), 4)


# ---------------------------------------------------------------------------
# Scene builder
# ---------------------------------------------------------------------------

def _build_cinematic_scene(
    index:            int,
    paragraphs:       list[str],
    location:         str,
    sublocation:      str | None,
    time_of_day:      str | None,
    act_position:     str | None,
    scene_type:       str,
    confirmed:        frozenset[str],
    known_characters: set[str],
    known_locations:  set[str],
    visual_bible:     VisualBible | None,
    total_estimated:  int,
) -> CinematicScene:
    raw = " ".join(paragraphs)
    sentences = _split_sentences(raw)
    characters = _extract_proper_nouns(sentences, confirmed)

    # Beat type inference via DoP rules
    beat_type = resolve_beat_type(raw)

    # Reference location resolution
    ref_location_id = _resolve_location_id(location, visual_bible)

    # Continuity flags
    continuity_flags: list[str] = []
    characters_entering: list[str] = []
    for char in characters:
        if char not in known_characters:
            continuity_flags.append(f"FIRST_APPEARANCE:{char}")
            characters_entering.append(char)
    if scene_type == "cliffhanger":
        continuity_flags.append("CLIFFHANGER")
    if scene_type == "flashback":
        continuity_flags.append("FLASHBACK_TRIGGER")
    if act_position in ("act1", "act2", "act3", "act4", "act_end"):
        continuity_flags.append("ACT_BREAK")
    if ref_location_id and ref_location_id in known_locations:
        continuity_flags.append(f"LOCATION_RECURRENCE:{ref_location_id}")

    # Emotional arc
    arc_index = _compute_arc_index(index, total_estimated, beat_type, scene_type)

    scene: CinematicScene = {
        "scene_id":    _make_scene_id(index),
        "characters":  characters,
        "location":    location,
        "time_of_day": time_of_day,
        "raw_text":    raw,
        "scene_type":  scene_type,
        "beat_type":   beat_type,
        "emotional_arc_index": arc_index,
    }

    if sublocation is not None:
        scene["sublocation"] = sublocation
    if act_position is not None:
        scene["act_position"] = act_position
    if ref_location_id is not None:
        scene["reference_location_id"] = ref_location_id
    if characters_entering:
        scene["characters_entering"] = characters_entering
    if continuity_flags:
        scene["continuity_flags"] = continuity_flags

    return scene


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def segment(
    raw_text: str,
    visual_bible: VisualBible | None = None,
) -> list[CinematicScene]:
    """
    PASS 1 — Segment raw_text into a list of CinematicScene dicts.

    Parameters
    ----------
    raw_text      : str
        Raw narrative text (paragraphs separated by double newlines).
    visual_bible  : VisualBible | None
        Optional series visual bible.  When provided, detected locations are
        resolved to VisualBible slugs and stored in reference_location_id.

    Returns
    -------
    list[CinematicScene]
        Each dict is a superset of RawScene — backward compatible.

    Raises
    ------
    ValueError    if raw_text is empty or segmentation yields zero scenes.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("PASS 1: raw_text must not be empty.")

    paragraphs: list[str] = [
        p.strip() for p in re.split(r"\n{2,}", raw_text) if p.strip()
    ]

    # Global pre-scan for confirmed proper nouns
    confirmed = _collect_confirmed_nouns(paragraphs)

    # First pass: estimate total scene count for arc index computation.
    # We use a heuristic: one scene per location/time break + extras.
    # This avoids two full passes; we update below after the real count.
    estimated_scene_count = max(1, len(paragraphs) // 2)

    scenes:           list[CinematicScene] = []
    scene_index:      int = 0
    known_characters: set[str] = set()
    known_locations:  set[str] = set()

    current_paragraphs: list[str] = []
    current_location:   str = "Unknown"
    current_sublocation: str | None = None
    current_time:       str | None = None
    current_act:        str | None = None
    prev_category:      str | None = None

    # State for R06 montage auto-detection
    short_para_streak: int = 0

    def _flush(
        c_type:   str,
        act_pos:  str | None,
        subloc:   str | None,
    ) -> None:
        nonlocal scene_index
        if not current_paragraphs:
            return
        sc = _build_cinematic_scene(
            index=scene_index,
            paragraphs=current_paragraphs,
            location=current_location,
            sublocation=subloc,
            time_of_day=current_time,
            act_position=act_pos,
            scene_type=c_type,
            confirmed=confirmed,
            known_characters=known_characters,
            known_locations=known_locations,
            visual_bible=visual_bible,
            total_estimated=estimated_scene_count,
        )
        scenes.append(sc)
        # Update world state
        known_characters.update(sc["characters"])
        if sc.get("reference_location_id"):
            known_locations.add(sc["reference_location_id"])
        scene_index += 1

    pending_act_break: str | None = None  # carry act_position to next scene

    for para_idx, paragraph in enumerate(paragraphs):

        # ---- R07: Act break detection at paragraph start ----
        act_break_value = _detect_act_break(paragraph)
        if act_break_value is not None:
            # Close current scene first
            if current_paragraphs:
                sentences_tmp = _split_sentences(" ".join(current_paragraphs))
                ctype = _classify_scene_type(sentences_tmp, False, False, current_act)
                _flush(ctype, current_act, current_sublocation)
                current_paragraphs = []
                current_sublocation = None
                current_time = None
            current_act = act_break_value
            pending_act_break = act_break_value
            # Act-break paragraphs are structural headers, not scene content — skip
            continue

        sentences = _split_sentences(paragraph)
        if not sentences:
            continue

        # ---- R08: Cliffhanger detection ----
        is_cliffhanger = _detect_cliffhanger(paragraph)

        # ---- R06: Ultra-short paragraph tracking ----
        is_short = len(sentences) <= MONTAGE_MAX_SENTENCES
        if is_short:
            short_para_streak += 1
        else:
            short_para_streak = 0

        # ---- R01/R02: Location detection ----
        loc:    str | None = None
        subloc: str | None = None
        for sentence in sentences:
            sl = sentence.lower()
            if loc is None:
                loc = _detect_location(sl)
            if subloc is None:
                subloc = _detect_sublocation(sl)

        # ---- R03: Time detection ----
        time_val: str | None = None
        for sentence in sentences:
            if time_val is None:
                time_val = _detect_time(sentence.lower())

        # ---- R11: Action category shift ----
        first_category = _action_category(sentences[0].lower())
        category_shift = (
            para_idx > 0
            and prev_category is not None
            and first_category != prev_category
        )

        # ---- Decide whether to open a new scene ----
        open_new_scene = False

        if loc is not None and loc != current_location:
            open_new_scene = True
        elif subloc is not None and subloc != current_sublocation:
            open_new_scene = True
        elif time_val is not None:
            open_new_scene = True
        elif pending_act_break is not None and current_paragraphs:
            open_new_scene = True
        elif is_cliffhanger and current_paragraphs:
            # R08: cliffhanger paragraph always starts its own scene so
            # the preceding scene can be classified independently (flashback,
            # dream, etc.) without being overridden by the cliffhanger.
            open_new_scene = True
        elif (
            category_shift
            and current_paragraphs
        ):
            open_new_scene = True

        if open_new_scene and current_paragraphs:
            sentences_so_far = _split_sentences(" ".join(current_paragraphs))
            ctype = _classify_scene_type(
                sentences_so_far,
                is_cliffhanger=False,
                is_act_break=pending_act_break is not None,
                act_position=current_act,
            )
            # R06 montage auto-detection on the accumulated block
            if short_para_streak >= MONTAGE_MIN_SHORT_PARAS:
                ctype = "montage"
            _flush(ctype, current_act, current_sublocation)
            current_paragraphs = []
            current_sublocation = None
            current_time = None
            current_act = pending_act_break
            pending_act_break = None
            short_para_streak = 0

        # ---- Update current scene state ----
        if loc is not None and loc != "Unknown":
            current_location = loc
        if subloc is not None:
            current_sublocation = subloc
        if time_val is not None:
            current_time = time_val
        if pending_act_break is not None and not current_paragraphs:
            current_act = pending_act_break
            pending_act_break = None

        current_paragraphs.append(paragraph)
        prev_category = _action_category(sentences[-1].lower())

    # ---- Flush final accumulated scene ----
    if current_paragraphs:
        sentences_final = _split_sentences(" ".join(current_paragraphs))
        is_cliff = _detect_cliffhanger(current_paragraphs[-1])
        ctype = _classify_scene_type(
            sentences_final,
            is_cliffhanger=is_cliff,
            is_act_break=False,
            act_position=current_act,
        )
        if short_para_streak >= MONTAGE_MIN_SHORT_PARAS:
            ctype = "montage"
        _flush(ctype, current_act, current_sublocation)

    if not scenes:
        raise ValueError("PASS 1: segmentation produced zero scenes.")

    # ---- Recompute arc indices with real scene count ----
    real_count = len(scenes)
    for i, sc in enumerate(scenes):
        sc["emotional_arc_index"] = _compute_arc_index(
            i, real_count, sc.get("beat_type", "exposition"), sc.get("scene_type", "standard")
        )

    return scenes

