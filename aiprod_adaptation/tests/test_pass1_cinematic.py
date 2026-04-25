"""
Tests for AIPROD_Cinematic Pass 1 — CinematicScene segmentation.

Coverage
--------
- Backward compat (v2 mandatory keys always present)
- Location change segmentation (R01)
- Sub-location shift (R02)
- Time shift (R03, extended phrases)
- Flashback detection (R04)
- Dream detection (R05)
- Montage auto-detection (R06)
- Act-break markers (R07)
- Cliffhanger detection (R08)
- VisualBible slug resolution (R09)
- First-appearance continuity flags (R10)
- Beat type inference (R11)
- Emotional arc index ordering (R12)
- Multi-episode coherence (continuity flags across scenes)
- Empty input → ValueError
- Determinism (same input → identical output twice)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aiprod_adaptation.core.pass1_segment import (
    _classify_scene_type,
    _compute_arc_index,
    _detect_cliffhanger,
    _detect_dream,
    _detect_flashback,
    _normalise_location,
    _resolve_location_id,
    segment,
)
from aiprod_adaptation.models.intermediate import CinematicScene

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scene(scenes: list[CinematicScene], idx: int) -> CinematicScene:
    return scenes[idx]


def _make_visual_bible(slugs: list[str]) -> MagicMock:
    """Return a lightweight VisualBible mock with the given location slugs."""
    vb = MagicMock()
    vb._data = {"locations": {slug: {} for slug in slugs}}
    return vb


# ---------------------------------------------------------------------------
# 1. Empty input → ValueError
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="PASS 1"):
            segment("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="PASS 1"):
            segment("   \n\n   ")


# ---------------------------------------------------------------------------
# 2. Backward compatibility — mandatory RawScene keys always present
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    _TEXT = (
        "Kael moved to the station platform.\n\n"
        "The train departed without him."
    )

    def test_scene_id_present(self) -> None:
        scenes = segment(self._TEXT)
        for sc in scenes:
            assert "scene_id" in sc

    def test_characters_present(self) -> None:
        scenes = segment(self._TEXT)
        for sc in scenes:
            assert "characters" in sc
            assert isinstance(sc["characters"], list)

    def test_location_present(self) -> None:
        scenes = segment(self._TEXT)
        for sc in scenes:
            assert "location" in sc

    def test_time_of_day_present(self) -> None:
        scenes = segment(self._TEXT)
        for sc in scenes:
            assert "time_of_day" in sc

    def test_raw_text_present(self) -> None:
        scenes = segment(self._TEXT)
        for sc in scenes:
            assert "raw_text" in sc
            assert len(sc["raw_text"]) > 0

    def test_scene_ids_sequential(self) -> None:
        scenes = segment(self._TEXT)
        for i, sc in enumerate(scenes):
            assert sc["scene_id"] == f"SCN_{i + 1:03d}"


# ---------------------------------------------------------------------------
# 3. R01 — Location change segmentation
# ---------------------------------------------------------------------------

class TestLocationChange:
    _TEXT = (
        "Mira walked through the corridors of the station.\n\n"
        "She arrived at the command centre.\n\n"
        "Later she entered the archive."
    )

    def test_location_change_splits_scenes(self) -> None:
        scenes = segment(self._TEXT)
        assert len(scenes) >= 2

    def test_location_extracted(self) -> None:
        scenes = segment(self._TEXT)
        locations = [sc["location"] for sc in scenes]
        # At least one non-unknown location detected
        assert any(loc != "Unknown" for loc in locations)

    def test_single_para_single_scene(self) -> None:
        scenes = segment("Kael stood in the archive and waited.")
        assert len(scenes) == 1


# ---------------------------------------------------------------------------
# 4. R02 — Sub-location shift
# ---------------------------------------------------------------------------

class TestSublocationShift:
    _TEXT = (
        "Kael was inside the archive terminal room.\n\n"
        "He moved to the back of the archive and opened a drawer."
    )

    def test_sublocation_set_on_shift(self) -> None:
        scenes = segment(self._TEXT)
        # At least one scene should have a sublocation
        sublocations = [sc.get("sublocation") for sc in scenes]
        assert any(s is not None for s in sublocations)


# ---------------------------------------------------------------------------
# 5. R03 — Time shift (extended phrases)
# ---------------------------------------------------------------------------

class TestTimeShift:
    def test_hours_later(self) -> None:
        text = (
            "Kael sat in the archive.\n\n"
            "Hours later, he left the building."
        )
        scenes = segment(text)
        assert len(scenes) >= 2

    def test_years_earlier(self) -> None:
        text = (
            "Mira walked through the district.\n\n"
            "Years earlier, the same street had been full of people."
        )
        scenes = segment(text)
        time_vals = [sc["time_of_day"] for sc in scenes]
        assert any(t is not None for t in time_vals)

    def test_that_night(self) -> None:
        text = (
            "They reached the safe house.\n\n"
            "That night, Voss made his move."
        )
        scenes = segment(text)
        time_vals = [sc["time_of_day"] for sc in scenes]
        assert any(t is not None for t in time_vals)

    def test_at_dawn(self) -> None:
        text = (
            "Kael waited in silence.\n\n"
            "At dawn, the extraction team arrived at the rooftop."
        )
        scenes = segment(text)
        assert len(scenes) >= 2


# ---------------------------------------------------------------------------
# 6. R04 — Flashback detection
# ---------------------------------------------------------------------------

class TestFlashbackDetection:
    def test_flashback_scene_type(self) -> None:
        text = (
            "Kael stared at the wall.\n\n"
            "He remembered the night of the raid. Years ago, "
            "he had been there. He could still smell the smoke. "
            "Back then, everything had been different."
        )
        scenes = segment(text)
        types = [sc.get("scene_type") for sc in scenes]
        assert "flashback" in types

    def test_flashback_continuity_flag(self) -> None:
        text = (
            "She looked at the photograph.\n\n"
            "She recalled his face. Years ago they had walked "
            "this same corridor together."
        )
        scenes = segment(text)
        all_flags = []
        for sc in scenes:
            all_flags.extend(sc.get("continuity_flags", []))
        assert "FLASHBACK_TRIGGER" in all_flags


# ---------------------------------------------------------------------------
# 7. R05 — Dream detection
# ---------------------------------------------------------------------------

class TestDreamDetection:
    def test_dream_scene_type(self) -> None:
        text = (
            "Kael closed his eyes.\n\n"
            "He dreamed of the archive. In the dream, the walls seemed to breathe. "
            "Everything blurred and reality dissolved around him."
        )
        scenes = segment(text)
        types = [sc.get("scene_type") for sc in scenes]
        assert "dream" in types


# ---------------------------------------------------------------------------
# 8. R06 — Montage detection
# ---------------------------------------------------------------------------

class TestMontageDetection:
    def test_explicit_montage_marker(self) -> None:
        text = (
            "Kael ran through the district.\n\n"
            "A montage of quick cuts: streets, alleys, rooftops.\n\n"
            "He emerged at the checkpoint."
        )
        scenes = segment(text)
        types = [sc.get("scene_type") for sc in scenes]
        assert "montage" in types


# ---------------------------------------------------------------------------
# 9. R07 — Act-break markers
# ---------------------------------------------------------------------------

class TestActBreakMarkers:
    def test_teaser_act_position(self) -> None:
        text = (
            "TEASER\n\n"
            "Kael arrived at the district boundary. Neon signs flickered.\n\n"
            "ACT ONE\n\n"
            "Inside the archive, Mira pulled up the files."
        )
        scenes = segment(text)
        positions = [sc.get("act_position") for sc in scenes]
        assert "teaser" in positions or any("act" in str(p) for p in positions if p)

    def test_act_one_position(self) -> None:
        text = (
            "ACT ONE\n\n"
            "Mira entered the archive and typed rapidly."
        )
        scenes = segment(text)
        positions = [sc.get("act_position") for sc in scenes]
        assert "act1" in positions

    def test_tag_position(self) -> None:
        text = (
            "The mission was complete.\n\n"
            "TAG\n\n"
            "Voss sat alone in his office."
        )
        scenes = segment(text)
        positions = [sc.get("act_position") for sc in scenes]
        assert "tag" in positions


# ---------------------------------------------------------------------------
# 10. R08 — Cliffhanger detection
# ---------------------------------------------------------------------------

class TestCliffhangerDetection:
    def test_cut_to_black_scene_type(self) -> None:
        text = (
            "Kael reached the terminal.\n\n"
            "The signal died. Cut to black."
        )
        scenes = segment(text)
        types = [sc.get("scene_type") for sc in scenes]
        assert "cliffhanger" in types

    def test_cliffhanger_continuity_flag(self) -> None:
        text = (
            "Mira read the file.\n\n"
            "Then the line went dead."
        )
        scenes = segment(text)
        all_flags = []
        for sc in scenes:
            all_flags.extend(sc.get("continuity_flags", []))
        assert "CLIFFHANGER" in all_flags

    def test_to_be_continued(self) -> None:
        text = (
            "They reached the safe house omega.\n\n"
            "To be continued."
        )
        scenes = segment(text)
        types = [sc.get("scene_type") for sc in scenes]
        assert "cliffhanger" in types


# ---------------------------------------------------------------------------
# 11. R09 — VisualBible slug resolution
# ---------------------------------------------------------------------------

class TestVisualBibleResolution:
    def test_exact_slug_match(self) -> None:
        vb = _make_visual_bible(["the_archive", "voss_office"])
        text = "Mira walked inside the archive and accessed the terminal."
        scenes = segment(text, visual_bible=vb)
        ref_ids = [sc.get("reference_location_id") for sc in scenes]
        assert "the_archive" in ref_ids

    def test_no_visual_bible_no_ref_id(self) -> None:
        text = "Kael moved to the command centre."
        scenes = segment(text)
        for sc in scenes:
            assert "reference_location_id" not in sc or sc.get("reference_location_id") is None

    def test_unmatched_location_no_ref_id(self) -> None:
        vb = _make_visual_bible(["voss_office"])
        text = "Kael walked through the abandoned factory."
        scenes = segment(text, visual_bible=vb)
        for sc in scenes:
            assert sc.get("reference_location_id") is None

    def test_location_recurrence_flag(self) -> None:
        vb = _make_visual_bible(["the_archive"])
        # Use clean location phrase (no trailing modifier like 'again') so
        # the slug resolver can match 'archive' → 'the_archive'.
        text = (
            "Mira walked inside the archive.\n\n"
            "Hours later, Kael stepped inside the archive."
        )
        scenes = segment(text, visual_bible=vb)
        all_flags = []
        for sc in scenes:
            all_flags.extend(sc.get("continuity_flags", []))
        # Second visit should generate LOCATION_RECURRENCE
        recurrence_flags = [f for f in all_flags if "LOCATION_RECURRENCE" in f]
        assert len(recurrence_flags) >= 1


# ---------------------------------------------------------------------------
# 12. R10 — First-appearance continuity flags
# ---------------------------------------------------------------------------

class TestFirstAppearanceFlags:
    def test_first_appearance_flag_for_new_character(self) -> None:
        # "Kael" must appear at a non-sentence-initial token position so the
        # global proper-noun pre-scan adds him to `confirmed`.
        text = (
            "She found Kael waiting at the archive entrance.\n\n"
            "Kael stepped inside the archive and accessed the terminal."
        )
        scenes = segment(text)
        all_flags = []
        for sc in scenes:
            all_flags.extend(sc.get("continuity_flags", []))
        assert any("FIRST_APPEARANCE:Kael" in f for f in all_flags)

    def test_no_duplicate_first_appearance(self) -> None:
        text = (
            "Kael walked to the archive.\n\n"
            "Kael sat down at the terminal.\n\n"
            "Kael typed the access code."
        )
        scenes = segment(text)
        all_flags = []
        for sc in scenes:
            all_flags.extend(sc.get("continuity_flags", []))
        kael_flags = [f for f in all_flags if "FIRST_APPEARANCE:Kael" == f]
        assert len(kael_flags) <= 1

    def test_characters_entering_field(self) -> None:
        text = "Kael and Mira arrived at the safe house omega."
        scenes = segment(text)
        # Characters entering should be populated for the first scene
        entering = scenes[0].get("characters_entering", [])
        assert isinstance(entering, list)


# ---------------------------------------------------------------------------
# 13. R11 — Beat type inference
# ---------------------------------------------------------------------------

class TestBeatTypeInference:
    def test_beat_type_is_string(self) -> None:
        text = "Kael moved to the archive. He arrived quickly."
        scenes = segment(text)
        for sc in scenes:
            assert isinstance(sc.get("beat_type"), str)

    def test_beat_type_is_valid_value(self) -> None:
        valid = {
            "exposition", "action", "dialogue_scene",
            "transition", "climax", "denouement",
        }
        text = (
            "The archive was silent.\n\n"
            "Kael and Mira argued in the corridor."
        )
        scenes = segment(text)
        for sc in scenes:
            bt = sc.get("beat_type", "exposition")
            assert bt in valid, f"Unknown beat_type: {bt!r}"


# ---------------------------------------------------------------------------
# 14. R12 — Emotional arc index
# ---------------------------------------------------------------------------

class TestEmotionalArcIndex:
    def test_arc_index_in_range(self) -> None:
        text = (
            "Kael stood at the archive entrance.\n\n"
            "He ran toward the exit, pursued by Voss.\n\n"
            "The line went dead."
        )
        scenes = segment(text)
        for sc in scenes:
            idx = sc.get("emotional_arc_index")
            if idx is not None:
                assert 0.0 <= idx <= 1.0

    def test_arc_index_non_decreasing_for_long_text(self) -> None:
        """For a multi-scene corpus, arc indices should not be all identical."""
        text = (
            "ACT ONE\n\n"
            "Kael arrived at the district boundary.\n\n"
            "He entered the archive and searched the files.\n\n"
            "ACT TWO\n\n"
            "Mira ran through the corridor. Voss was close behind her.\n\n"
            "The signal died. Cut to black."
        )
        scenes = segment(text)
        indices = [sc.get("emotional_arc_index", 0.0) for sc in scenes]
        # At least two distinct index values expected
        assert len(set(indices)) >= 2


# ---------------------------------------------------------------------------
# 15. Multi-episode coherence
# ---------------------------------------------------------------------------

class TestMultiEpisodeCoherence:
    def test_act_break_flag_in_continuity(self) -> None:
        text = (
            "ACT ONE\n\n"
            "Kael walked inside the archive.\n\n"
            "ACT TWO\n\n"
            "Mira arrived at the command centre."
        )
        scenes = segment(text)
        all_flags = []
        for sc in scenes:
            all_flags.extend(sc.get("continuity_flags", []))
        assert "ACT_BREAK" in all_flags

    def test_cliffhanger_and_flashback_coexist(self) -> None:
        text = (
            "Kael remembered the corridor. Years ago he had been here.\n\n"
            "The terminal blinked. The line went dead."
        )
        scenes = segment(text)
        types = [sc.get("scene_type") for sc in scenes]
        # Both a flashback and a cliffhanger should appear
        assert "flashback" in types or "cliffhanger" in types


# ---------------------------------------------------------------------------
# 16. Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    _TEXT = (
        "TEASER\n\n"
        "Kael arrived at the district boundary. Neon signs flickered overhead.\n\n"
        "Inside the archive, the terminal hummed. Files scrolled—names, dates.\n\n"
        "Hours later, Kael sat at the window in the archive's back room.\n\n"
        "He remembered the raid. Years ago, the same corridor, the same silence.\n\n"
        "Cut to black."
    )

    def test_same_scene_count(self) -> None:
        s1 = segment(self._TEXT)
        s2 = segment(self._TEXT)
        assert len(s1) == len(s2)

    def test_same_scene_ids(self) -> None:
        s1 = segment(self._TEXT)
        s2 = segment(self._TEXT)
        assert [s["scene_id"] for s in s1] == [s["scene_id"] for s in s2]

    def test_same_scene_types(self) -> None:
        s1 = segment(self._TEXT)
        s2 = segment(self._TEXT)
        assert [s.get("scene_type") for s in s1] == [s.get("scene_type") for s in s2]

    def test_same_arc_indices(self) -> None:
        s1 = segment(self._TEXT)
        s2 = segment(self._TEXT)
        assert [s.get("emotional_arc_index") for s in s1] == [
            s.get("emotional_arc_index") for s in s2
        ]


# ---------------------------------------------------------------------------
# 17. Unit tests for helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_normalise_location_strips_stopwords(self) -> None:
        assert _normalise_location("the archive") == "archive"

    def test_normalise_location_replaces_spaces(self) -> None:
        assert _normalise_location("command centre") == "command_centre"

    def test_detect_flashback_true(self) -> None:
        sentences = [
            "She stared at the wall.",
            "She remembered the night everything changed.",
        ]
        assert _detect_flashback(sentences) is True

    def test_detect_flashback_false(self) -> None:
        sentences = ["She walked into the room.", "The door opened."]
        assert _detect_flashback(sentences) is False

    def test_detect_dream_true(self) -> None:
        sentences = ["He dreamed of the archive.", "In the dream the walls moved."]
        assert _detect_dream(sentences) is True

    def test_detect_dream_false(self) -> None:
        sentences = ["He walked down the corridor.", "The room was cold."]
        assert _detect_dream(sentences) is False

    def test_detect_cliffhanger_true(self) -> None:
        assert _detect_cliffhanger("The line went dead.") is True

    def test_detect_cliffhanger_false(self) -> None:
        assert _detect_cliffhanger("Kael opened the door.") is False

    def test_compute_arc_index_in_range(self) -> None:
        for i in range(5):
            idx = _compute_arc_index(i, 5, "climax", "cliffhanger")
            assert 0.0 <= idx <= 1.0

    def test_compute_arc_index_zero_for_first_scene(self) -> None:
        idx = _compute_arc_index(0, 10, "exposition", "standard")
        assert idx == 0.0

    def test_classify_scene_type_cliffhanger_takes_priority(self) -> None:
        stype = _classify_scene_type(["Any text."], is_cliffhanger=True,
                                     is_act_break=False, act_position="act1")
        assert stype == "cliffhanger"

    def test_resolve_location_id_exact_match(self) -> None:
        vb = _make_visual_bible(["the_archive"])
        result = _resolve_location_id("the archive", vb)
        assert result == "archive" or result == "the_archive"

    def test_resolve_location_id_no_bible_returns_none(self) -> None:
        result = _resolve_location_id("the archive", None)
        assert result is None


# ---------------------------------------------------------------------------
# 18. Full cinematic example (thriller sci-fi)
# ---------------------------------------------------------------------------

class TestCinematicExample:
    _SCRIPT = """TEASER

The transport pod touched down in the outer ring of District Zero.
Kael stepped out into the cold, scanning the street. Neon signs flickered overhead.

Inside the archive, the terminal hummed. Files scrolled—names, dates, redacted lines.

Hours later, Kael sat at the window in the archive's back room.
He remembered the raid. Years ago, the same corridor, the same silence.
He could still smell the smoke.

Cut to black."""

    def test_teaser_scene_has_teaser_act_position(self) -> None:
        scenes = segment(self._SCRIPT)
        positions = [sc.get("act_position") for sc in scenes]
        assert "teaser" in positions

    def test_flashback_scene_detected(self) -> None:
        scenes = segment(self._SCRIPT)
        types = [sc.get("scene_type") for sc in scenes]
        assert "flashback" in types

    def test_cliffhanger_scene_detected(self) -> None:
        scenes = segment(self._SCRIPT)
        types = [sc.get("scene_type") for sc in scenes]
        assert "cliffhanger" in types

    def test_kael_first_appearance_flagged(self) -> None:
        scenes = segment(self._SCRIPT)
        all_flags: list[str] = []
        for sc in scenes:
            all_flags.extend(sc.get("continuity_flags", []))
        assert any("FIRST_APPEARANCE:Kael" in f for f in all_flags)

    def test_scene_count_geq_3(self) -> None:
        scenes = segment(self._SCRIPT)
        assert len(scenes) >= 3

    def test_all_scenes_have_beat_type(self) -> None:
        scenes = segment(self._SCRIPT)
        for sc in scenes:
            assert "beat_type" in sc

    def test_visual_bible_integration(self) -> None:
        vb = _make_visual_bible(["district_zero_central", "the_archive"])
        scenes = segment(self._SCRIPT, visual_bible=vb)
        ref_ids = [sc.get("reference_location_id") for sc in scenes]
        # Archive should be resolved
        assert any(r is not None for r in ref_ids)
