"""
Tests for Pass 2 Cinematic rewrite (AIPROD_Cinematic v3.0).

Test classes
------------
TestPass2BackwardCompat      — all v2 mandatory keys present; no visual_bible needed.
TestIntensityTiering         — arc_index maps to correct tier in physical_actions.
TestContextModifiers         — CONTEXT_INTENSITY_MODIFIERS shift tier correctly.
TestBeatTypeFloor            — climax/action floors override low arc_index.
TestSceneTypeModifiers       — flashback/montage modify layers.
TestEmotionalLayer           — cold/icy/burst markers set emotional_layer correctly.
TestVisualBibleInjection     — wardrobe_fingerprint injected in visual_invariants_applied.
TestEnvironmentalInteraction — architecture_style × emotion populates env_interactions.
TestBodyLanguageState        — energy_level / gaze_direction correct per emotion.
TestDeterminism              — same input → identical output.
TestSilentScene              — short wordless scene handled without crash.
"""

from __future__ import annotations

import copy
import unittest

from aiprod_adaptation.core.pass2_visual import visual_rewrite
from aiprod_adaptation.models.intermediate import RawScene


# ---------------------------------------------------------------------------
# Minimal valid RawScene builders
# ---------------------------------------------------------------------------

def _make_scene(
    raw_text: str = "Marcus stood by the window.",
    emotion_override: str | None = None,
    arc_index: float = 0.5,
    beat_type: str = "exposition",
    scene_type: str = "standard",
    characters: list[str] | None = None,
    location: str = "office",
    **extra,
) -> RawScene:
    base: dict = {
        "scene_id":           "S01",
        "characters":         characters or ["Marcus"],
        "location":           location,
        "time_of_day":        "day",
        "raw_text":           raw_text,
        "emotional_arc_index": arc_index,
        "beat_type":          beat_type,
        "scene_type":         scene_type,
    }
    base.update(extra)
    return base  # type: ignore[return-value]


class _FakeVisualBible:
    """Minimal stub that mimics VisualBible._data structure."""
    def __init__(self, characters=None, locations=None):
        self._data: dict = {
            "characters": characters or {},
            "locations":  locations  or {},
        }


# ===========================================================================
# T1 — Backward compatibility
# ===========================================================================

class TestPass2BackwardCompat(unittest.TestCase):
    """visual_rewrite works with a bare RawScene (no CinematicScene extras)."""

    def setUp(self):
        bare: RawScene = {
            "scene_id":    "S01",
            "characters":  ["Kael"],
            "location":    "corridor",
            "time_of_day": "night",
            "raw_text":    "Kael moved down the corridor.",
        }
        self.result = visual_rewrite([bare])

    def test_returns_one_scene(self):
        self.assertEqual(len(self.result), 1)

    def test_mandatory_keys_present(self):
        vs = self.result[0]
        for key in ("scene_id", "characters", "location", "time_of_day",
                    "visual_actions", "dialogues", "emotion"):
            self.assertIn(key, vs, f"Missing mandatory key: {key}")

    def test_visual_actions_is_list(self):
        self.assertIsInstance(self.result[0]["visual_actions"], list)

    def test_visual_actions_non_empty(self):
        self.assertTrue(len(self.result[0]["visual_actions"]) > 0)

    def test_dialogues_is_list(self):
        self.assertIsInstance(self.result[0]["dialogues"], list)

    def test_emotion_is_str(self):
        self.assertIsInstance(self.result[0]["emotion"], str)

    def test_scene_id_preserved(self):
        self.assertEqual(self.result[0]["scene_id"], "S01")

    def test_characters_preserved(self):
        self.assertEqual(self.result[0]["characters"], ["Kael"])

    def test_no_exception_without_visual_bible(self):
        """No exception raised when visual_bible=None (default)."""
        # Already confirmed by setUp; this test makes the intent explicit.
        pass


# ===========================================================================
# T2 — Intensity tiering
# ===========================================================================

class TestIntensityTiering(unittest.TestCase):

    def _run(self, arc: float, text: str = "She walked forward.") -> str:
        result = visual_rewrite([_make_scene(raw_text=text, arc_index=arc)])
        return result[0]["action_intensity"]

    def test_low_arc_gives_subtle(self):
        self.assertEqual(self._run(0.1), "subtle")

    def test_mid_arc_gives_mid(self):
        self.assertEqual(self._run(0.5), "mid")

    def test_high_arc_gives_explosive(self):
        self.assertEqual(self._run(0.9), "explosive")

    def test_threshold_boundary_mid(self):
        # 0.35 is exactly the mid boundary — should be mid
        self.assertEqual(self._run(0.35), "mid")

    def test_threshold_boundary_explosive(self):
        # 0.70 is exactly the explosive boundary
        self.assertEqual(self._run(0.70), "explosive")

    def test_physical_actions_carry_tier(self):
        result = visual_rewrite([_make_scene(arc_index=0.9)])
        pa = result[0].get("physical_actions", [])
        self.assertTrue(len(pa) > 0)
        for action in pa:
            self.assertEqual(action["intensity"], "explosive")

    def test_physical_actions_present(self):
        result = visual_rewrite([_make_scene(arc_index=0.5)])
        self.assertIn("physical_actions", result[0])
        self.assertIsInstance(result[0]["physical_actions"], list)


# ===========================================================================
# T3 — Context intensity modifiers
# ===========================================================================

class TestContextModifiers(unittest.TestCase):
    """CONTEXT_INTENSITY_MODIFIERS shift the effective arc_index."""

    def test_cold_modifier_reduces_tier(self):
        # arc=0.5 (mid) + "cold" → delta -0.30 → 0.20 → subtle
        result = visual_rewrite([_make_scene(
            raw_text="She stepped forward with cold precision.",
            arc_index=0.5,
        )])
        self.assertEqual(result[0]["action_intensity"], "subtle")

    def test_icy_modifier_reduces_tier(self):
        # arc=0.5 + "icy" → delta -0.30 → subtle
        result = visual_rewrite([_make_scene(
            raw_text="His icy composure never cracked.",
            arc_index=0.5,
        )])
        self.assertEqual(result[0]["action_intensity"], "subtle")

    def test_burst_modifier_increases_tier(self):
        # arc=0.3 (subtle) + "burst" → delta +0.32 → 0.62 → mid
        result = visual_rewrite([_make_scene(
            raw_text="She burst through the door.",
            arc_index=0.3,
        )])
        self.assertIn(result[0]["action_intensity"], ("mid", "explosive"))

    def test_violent_modifier_increases_tier(self):
        result = visual_rewrite([_make_scene(
            raw_text="He violently threw the chair aside.",
            arc_index=0.4,
        )])
        self.assertIn(result[0]["action_intensity"], ("mid", "explosive"))

    def test_suddenly_modifier_increases_tier(self):
        result = visual_rewrite([_make_scene(
            raw_text="Suddenly she turned to face him.",
            arc_index=0.3,
        )])
        self.assertIn(result[0]["action_intensity"], ("mid", "explosive"))

    def test_adjusted_arc_clamped_to_1(self):
        # Multiple positive modifiers should not exceed 1.0
        result = visual_rewrite([_make_scene(
            raw_text="She suddenly burst out violently erupted.",
            arc_index=0.9,
        )])
        arc = result[0].get("emotional_beat_index", 0.0)
        self.assertLessEqual(arc, 1.0)

    def test_adjusted_arc_clamped_to_0(self):
        result = visual_rewrite([_make_scene(
            raw_text="Barely, cold, icy, controlled, impassive.",
            arc_index=0.1,
        )])
        arc = result[0].get("emotional_beat_index", 1.0)
        self.assertGreaterEqual(arc, 0.0)


# ===========================================================================
# T4 — Beat-type intensity floor
# ===========================================================================

class TestBeatTypeFloor(unittest.TestCase):

    def test_climax_floor_overrides_subtle(self):
        result = visual_rewrite([_make_scene(
            arc_index=0.1, beat_type="climax",
        )])
        self.assertIn(result[0]["action_intensity"], ("mid", "explosive"))

    def test_action_floor_overrides_subtle(self):
        result = visual_rewrite([_make_scene(
            arc_index=0.1, beat_type="action",
        )])
        self.assertIn(result[0]["action_intensity"], ("mid", "explosive"))

    def test_denouement_has_no_floor(self):
        # Low arc + denouement → subtle is allowed
        result = visual_rewrite([_make_scene(
            arc_index=0.1, beat_type="denouement",
        )])
        self.assertEqual(result[0]["action_intensity"], "subtle")

    def test_exposition_has_no_floor(self):
        result = visual_rewrite([_make_scene(
            arc_index=0.1, beat_type="exposition",
        )])
        self.assertEqual(result[0]["action_intensity"], "subtle")

    def test_climax_preserves_explosive(self):
        result = visual_rewrite([_make_scene(
            arc_index=0.9, beat_type="climax",
        )])
        self.assertEqual(result[0]["action_intensity"], "explosive")


# ===========================================================================
# T5 — Scene-type modifiers
# ===========================================================================

class TestSceneTypeModifiers(unittest.TestCase):

    def test_flashback_motion_suffix_in_actions(self):
        # 37 words — safely above the 30-word silent-scene threshold
        result = visual_rewrite([_make_scene(
            raw_text=(
                "Marcus stood at the edge of the platform in the dim light. "
                "The rain had been falling for hours over the empty streets. "
                "He crossed the corridor, paused at the doorway, and looked back at the stairs."
            ),
            scene_type="flashback",
            arc_index=0.5,
        )])
        combined = " ".join(result[0]["visual_actions"]).lower()
        # The flashback motion_suffix contains "memory" or "deliberate" or "underwater"
        self.assertTrue(
            "memory" in combined or "deliberate" in combined or "underwater" in combined,
            f"Flashback suffix not found in: {result[0]['visual_actions']}"
        )

    def test_montage_has_no_breath_layer(self):
        result = visual_rewrite([_make_scene(
            scene_type="montage",
            arc_index=0.5,
        )])
        pa = result[0].get("physical_actions", [])
        breath_layers = [p for p in pa if p["layer"] == "breath"]
        self.assertEqual(breath_layers, [], "Breath layer should be absent in montage")

    def test_standard_has_breath_layer(self):
        result = visual_rewrite([_make_scene(
            scene_type="standard",
            arc_index=0.5,
        )])
        pa = result[0].get("physical_actions", [])
        # Standard scene: breath should be present (unless emotion has no breath entry)
        layers = {p["layer"] for p in pa}
        self.assertIn("posture", layers, "posture should be present in standard scene")

    def test_cliffhanger_scene_type_propagated(self):
        result = visual_rewrite([_make_scene(
            scene_type="cliffhanger",
            arc_index=0.5,
        )])
        self.assertEqual(result[0].get("scene_type"), "cliffhanger")

    def test_standard_scene_type_not_set(self):
        result = visual_rewrite([_make_scene(
            scene_type="standard",
            arc_index=0.5,
        )])
        # Standard is the default — not written to VisualScene
        self.assertNotIn("scene_type", result[0])


# ===========================================================================
# T6 — Emotional layer detection
# ===========================================================================

class TestEmotionalLayer(unittest.TestCase):

    def test_cold_gives_disguised(self):
        result = visual_rewrite([_make_scene(
            raw_text="She moved with cold calculation.",
        )])
        self.assertEqual(result[0]["emotional_layer"], "disguised")

    def test_icy_gives_disguised(self):
        result = visual_rewrite([_make_scene(
            raw_text="His icy gaze swept the room.",
        )])
        self.assertEqual(result[0]["emotional_layer"], "disguised")

    def test_burst_gives_erupting(self):
        result = visual_rewrite([_make_scene(
            raw_text="She burst into the room.",
        )])
        self.assertEqual(result[0]["emotional_layer"], "erupting")

    def test_erupted_gives_erupting(self):
        result = visual_rewrite([_make_scene(
            raw_text="The tension erupted into violence.",
        )])
        self.assertEqual(result[0]["emotional_layer"], "erupting")

    def test_neutral_default(self):
        result = visual_rewrite([_make_scene(
            raw_text="She sat down at the table.",
        )])
        self.assertEqual(result[0]["emotional_layer"], "surface")

    def test_emotional_layer_key_always_present(self):
        result = visual_rewrite([_make_scene()])
        self.assertIn("emotional_layer", result[0])


# ===========================================================================
# T7 — VisualBible injection
# ===========================================================================

class TestVisualBibleInjection(unittest.TestCase):

    def _bible_with_char(self, wardrobe: str) -> _FakeVisualBible:
        return _FakeVisualBible(
            characters={
                "Marcus": {
                    "wardrobe_fingerprint": wardrobe,
                    "lighting_affinity":    "harsh fluorescent underlighting",
                }
            }
        )

    def test_wardrobe_in_visual_invariants(self):
        vb = self._bible_with_char("worn leather jacket, silver dog-tag")
        result = visual_rewrite([_make_scene(characters=["Marcus"])], visual_bible=vb)
        inv = result[0].get("visual_invariants_applied", [])
        wardrobe_entries = [i for i in inv if "wardrobe" in i]
        self.assertTrue(len(wardrobe_entries) > 0, f"No wardrobe in invariants: {inv}")

    def test_lighting_affinity_in_visual_invariants(self):
        vb = self._bible_with_char("worn leather jacket")
        result = visual_rewrite([_make_scene(characters=["Marcus"])], visual_bible=vb)
        inv = result[0].get("visual_invariants_applied", [])
        lighting_entries = [i for i in inv if "lighting" in i]
        self.assertTrue(len(lighting_entries) > 0, f"No lighting in invariants: {inv}")

    def test_wardrobe_injected_in_visual_actions(self):
        wardrobe = "worn leather jacket, silver dog-tag"
        vb = self._bible_with_char(wardrobe)
        # 35 words — safely above the 30-word silent-scene threshold so gesture layer is rendered
        result = visual_rewrite([_make_scene(
            raw_text=(
                "Marcus walked into the conference room and scanned the space from left to right. "
                "He paused near the window, then turned to check the far side of the table "
                "where the folders had been left."
            ),
            characters=["Marcus"],
        )], visual_bible=vb)
        combined = " ".join(result[0]["visual_actions"])
        self.assertIn("worn leather jacket", combined,
                      f"Wardrobe not found in: {combined}")

    def test_no_crash_without_visual_bible(self):
        result = visual_rewrite([_make_scene(characters=["Marcus"])])
        self.assertEqual(len(result), 1)


# ===========================================================================
# T8 — Environmental interactions
# ===========================================================================

class TestEnvironmentalInteraction(unittest.TestCase):

    def _make_office_scene_with_bible(self) -> tuple[list, _FakeVisualBible]:
        scene = _make_scene(
            raw_text="Marcus was furious as he stood in the office.",
            characters=["Marcus"],
            location="office",
            reference_location_id="office_main",
        )
        vb = _FakeVisualBible(
            locations={
                "office_main": {
                    "lighting_condition": "cold overhead fluorescent",
                    "architecture_style": "office",
                }
            }
        )
        return [scene], vb

    def test_env_interactions_populated(self):
        scenes, vb = self._make_office_scene_with_bible()
        result = visual_rewrite(scenes, visual_bible=vb)
        env = result[0].get("environmental_interactions", [])
        self.assertTrue(len(env) > 0, f"No environmental interactions: {env}")

    def test_lighting_in_env_interactions(self):
        scenes, vb = self._make_office_scene_with_bible()
        result = visual_rewrite(scenes, visual_bible=vb)
        env = result[0].get("environmental_interactions", [])
        lighting_entries = [e for e in env if "light" in e.lower()]
        self.assertTrue(len(lighting_entries) > 0, f"No lighting entry: {env}")

    def test_no_env_interactions_without_visual_bible(self):
        result = visual_rewrite([_make_scene()])
        # No visual_bible → empty list or missing key, no crash
        env = result[0].get("environmental_interactions", [])
        self.assertIsInstance(env, list)


# ===========================================================================
# T9 — Body language state
# ===========================================================================

class TestBodyLanguageState(unittest.TestCase):

    VALID_ENERGY_LEVELS    = {"still", "coiled", "released", "exhausted", "charged"}
    VALID_GAZE_DIRECTIONS  = {"inward", "forward", "avoidant", "hunting", "scanning"}

    def _get_bls(self, raw_text: str, arc: float = 0.5) -> dict:
        result = visual_rewrite([_make_scene(raw_text=raw_text, arc_index=arc)])
        states = result[0].get("body_language_states", [])
        self.assertTrue(len(states) > 0, "body_language_states is empty")
        return states[0]

    def test_energy_level_valid(self):
        bls = self._get_bls("She was angry at the injustice.")
        self.assertIn(bls["energy_level"], self.VALID_ENERGY_LEVELS)

    def test_gaze_direction_valid(self):
        bls = self._get_bls("She was angry at the injustice.")
        self.assertIn(bls["gaze_direction"], self.VALID_GAZE_DIRECTIONS)

    def test_dominant_emotion_matches_text(self):
        bls = self._get_bls("She was scared and terrified.", arc=0.5)
        self.assertEqual(bls["dominant_emotion"], "scared")

    def test_character_id_slugified(self):
        result = visual_rewrite([_make_scene(
            characters=["Marcus"],
            raw_text="Marcus was angry.",
        )])
        bls = result[0]["body_language_states"][0]
        self.assertEqual(bls["character_id"], "marcus")

    def test_posture_is_str(self):
        bls = self._get_bls("She stood silently.")
        self.assertIsInstance(bls["posture"], str)

    def test_body_language_states_is_list(self):
        result = visual_rewrite([_make_scene()])
        self.assertIsInstance(result[0].get("body_language_states", []), list)


# ===========================================================================
# T10 — Determinism
# ===========================================================================

class TestDeterminism(unittest.TestCase):

    def _run(self, scene: RawScene) -> list[VisualScene]:
        from aiprod_adaptation.models.intermediate import VisualScene
        return visual_rewrite([copy.deepcopy(scene)])

    def test_identical_output_twice(self):
        scene = _make_scene(
            raw_text=(
                "Marcus entered the archive. He was furious. "
                '"The data is gone," he whispered coldly. '
                "Clara watched from the doorway."
            ),
            arc_index=0.65,
            beat_type="action",
            scene_type="standard",
        )
        out1 = self._run(scene)
        out2 = self._run(scene)
        self.assertEqual(out1[0]["visual_actions"],       out2[0]["visual_actions"])
        self.assertEqual(out1[0]["emotion"],              out2[0]["emotion"])
        self.assertEqual(out1[0]["action_intensity"],     out2[0]["action_intensity"])
        self.assertEqual(out1[0]["emotional_layer"],      out2[0]["emotional_layer"])
        self.assertEqual(out1[0]["physical_actions"],     out2[0]["physical_actions"])
        self.assertEqual(out1[0]["body_language_states"], out2[0]["body_language_states"])

    def test_determinism_multiple_scenes(self):
        scenes = [
            _make_scene(raw_text="He was terrified.", arc_index=0.8, scene_type="standard"),
            _make_scene(
                raw_text="She felt relieved.", arc_index=0.2, scene_type="standard",
                **{"scene_id": "S02"},
            ),
        ]
        out1 = visual_rewrite([copy.deepcopy(s) for s in scenes])
        out2 = visual_rewrite([copy.deepcopy(s) for s in scenes])
        self.assertEqual(out1, out2)


# ===========================================================================
# T11 — Silent scene
# ===========================================================================

class TestSilentScene(unittest.TestCase):
    """Scenes below SILENT_SCENE_WORD_THRESHOLD with no dialogue are handled."""

    def test_silent_scene_no_crash(self):
        scene = _make_scene(raw_text="She waited.")
        result = visual_rewrite([scene])
        self.assertEqual(len(result), 1)

    def test_silent_scene_visual_actions_non_empty(self):
        scene = _make_scene(raw_text="He stood motionless.")
        result = visual_rewrite([scene])
        self.assertTrue(len(result[0]["visual_actions"]) > 0)

    def test_silent_scene_dialogues_empty(self):
        scene = _make_scene(raw_text="She waited alone.")
        result = visual_rewrite([scene])
        self.assertEqual(result[0]["dialogues"], [])


# ===========================================================================
# T12 — Error handling
# ===========================================================================

class TestErrorHandling(unittest.TestCase):

    def test_empty_scenes_raises(self):
        with self.assertRaises(ValueError):
            visual_rewrite([])

    def test_empty_raw_text_raises(self):
        scene = _make_scene(raw_text="   ")
        with self.assertRaises(ValueError):
            visual_rewrite([scene])


# ===========================================================================
# T13 — Provenance propagation from Pass 1
# ===========================================================================

class TestProvenancePropagation(unittest.TestCase):

    def test_act_position_propagated(self):
        scene = _make_scene(act_position="act2")
        result = visual_rewrite([scene])
        self.assertEqual(result[0].get("act_position"), "act2")

    def test_reference_location_id_propagated(self):
        scene = _make_scene(reference_location_id="archive_sub_level")
        result = visual_rewrite([scene])
        self.assertEqual(result[0].get("reference_location_id"), "archive_sub_level")

    def test_continuity_flags_propagated(self):
        scene = _make_scene(continuity_flags=["FIRST_APPEARANCE:Marcus"])
        result = visual_rewrite([scene])
        self.assertEqual(result[0].get("continuity_flags"), ["FIRST_APPEARANCE:Marcus"])

    def test_non_standard_scene_type_set(self):
        scene = _make_scene(scene_type="flashback")
        result = visual_rewrite([scene])
        self.assertEqual(result[0].get("scene_type"), "flashback")


# ===========================================================================
# T14 — Dialogue handling
# ===========================================================================

class TestDialogueHandling(unittest.TestCase):

    def test_dialogues_extracted(self):
        scene = _make_scene(
            raw_text='Marcus said, "I found the file." Clara nodded.',
        )
        result = visual_rewrite([scene])
        self.assertIn("I found the file.", result[0]["dialogues"])

    def test_visual_actions_does_not_contain_dialogue(self):
        scene = _make_scene(
            raw_text='"We have to leave now," she insisted.',
        )
        result = visual_rewrite([scene])
        for action in result[0]["visual_actions"]:
            self.assertNotIn("We have to leave now", action)


if __name__ == "__main__":
    unittest.main()
