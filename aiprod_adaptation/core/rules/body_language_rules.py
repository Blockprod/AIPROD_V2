"""
Body Language Rules — AIPROD_Cinematic Pass 2 v3.0.

Single source of truth for multi-layer physical action descriptions.
Each emotion × 3 intensity tiers × 5 physical layers = deterministic,
cinematographically precise action directives.

Layers (in composition order):
    posture          — weight, spine, centre-of-gravity
    gesture          — hands, arms, spatial occupancy
    gaze             — eye contact, blink, gaze target
    micro_expression — face musculature, jaw, brow, lip corners
    breath           — respiration pattern, audibility

Intensity tiers (driven by emotional_arc_index from Pass 1):
    subtle           — arc_index < 0.35  : contained, controlled, leaking
    mid              — 0.35 ≤ arc_index < 0.70 : visible, muscular engagement
    explosive        — arc_index ≥ 0.70  : full-body, uncontrolled expression

All strings are English imperative-present directives suitable for shot prompts,
storyboard annotations, and video-generation conditioning text.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Layer names (ordered for composition)
# ---------------------------------------------------------------------------

PHYSICAL_ACTION_LAYERS: list[str] = [
    "posture",
    "gesture",
    "gaze",
    "micro_expression",
    "breath",
]

INTENSITY_TIERS: list[str] = ["subtle", "mid", "explosive"]


# ---------------------------------------------------------------------------
# EMOTION_BODY_LANGUAGE
# Structure: emotion → tier → layer → description string
# 15 emotions × 3 tiers × 5 layers
# ---------------------------------------------------------------------------

EMOTION_BODY_LANGUAGE: dict[str, dict[str, dict[str, str]]] = {

    # ------------------------------------------------------------------ angry
    "angry": {
        "subtle": {
            "posture":          "weight shifts imperceptibly forward; spine rigid, feet rooted",
            "gesture":          "hands pressed flat on nearest surface, knuckles just beginning to whiten",
            "gaze":             "eyes fix on single point, blink rate drops to near zero; jaw angle widens peripheral awareness",
            "micro_expression": "jaw muscle pulses twice; lips compress to a thin line; forehead deliberately held still",
            "breath":           "breathing slows to controlled nasal rhythm, audible only in silence",
        },
        "mid": {
            "posture":          "chest expands, shoulders square to subject; stance widens half a step",
            "gesture":          "fist forms at side, knuckles whiten; forearm tendons trace visible lines under skin",
            "gaze":             "direct eye contact held with no blinking; head lowers a fraction, targeting",
            "micro_expression": "jaw muscle pulses visibly; lips pressed to a line; nostrils flare on exhale",
            "breath":           "nasal breathing becomes audible, controlled but straining at the edges",
        },
        "explosive": {
            "posture":          "full-body lunge forward, centre of gravity drops; arms open, nothing held back",
            "gesture":          "arm sweeps objects from surface or slams down; hands open then grip whatever is in reach",
            "gaze":             "locked on target, pupils constrict; whites of eyes visible all around",
            "micro_expression": "face fully contorts; temple veins visible; teeth exposed, jaw thrust forward",
            "breath":           "sharp forceful exhale through bared teeth; next inhale chest-heaving",
        },
    },

    # ------------------------------------------------------------------ scared
    "scared": {
        "subtle": {
            "posture":          "body holds very still, weight balanced and poised — the freeze before flight",
            "gesture":          "hands draw slightly toward the body, fingers close fractionally",
            "gaze":             "peripheral vision hyperactivated; eyes sweep exits without moving the head",
            "micro_expression": "nostrils flare on inhale; upper lip tightens; nothing else moves",
            "breath":           "shallow rapid nose-breathing, barely audible; throat holds the next sound",
        },
        "mid": {
            "posture":          "backward half-step, body angles slightly sideways to the threat",
            "gesture":          "hands rise instinctively to chest height, palms forward or turned inward",
            "gaze":             "eyes widen, full iris visible; head turns sharply toward the threat source",
            "micro_expression": "brows lift and draw together; lower lip drops; skin drains",
            "breath":           "sharp audible inhale through nose; held one full beat",
        },
        "explosive": {
            "posture":          "full recoil backward, stumbles or crashes against whatever is behind",
            "gesture":          "arms fly outward or fold over the face and chest; no coordination",
            "gaze":             "wide fixed stare, pupils fully dilated, whites fully exposed",
            "micro_expression": "mouth opens, face loses muscular control entirely",
            "breath":           "audible gasp — or silence where a scream should be; chest spasms",
        },
    },

    # ------------------------------------------------------------------ sad
    "sad": {
        "subtle": {
            "posture":          "slight forward incline from hips; head bows a single degree",
            "gesture":          "hands clasp together at the lap, or press flat on thighs",
            "gaze":             "eyes drop to middle distance; blink rate slows; focus softens",
            "micro_expression": "inner corners of brows rise; lower lip softens; nothing dramatic",
            "breath":           "breath lengthens; one slow full exhale as if releasing something held",
        },
        "mid": {
            "posture":          "shoulders round forward; spine curves; body folds gently inward",
            "gesture":          "hands cover the lower face or press flat against the chest",
            "gaze":             "eyes redden; blink rate increases as if fighting what's rising",
            "micro_expression": "chin dimples; lip corners pull down; brow creases at centre",
            "breath":           "trembling inhale; voice would crack if anything were said",
        },
        "explosive": {
            "posture":          "body collapses onto nearest surface or sinks to the floor",
            "gesture":          "hands grip knees or whatever surface is near; body doubles forward",
            "gaze":             "eyes close or stare unfocused while tears fall, unchecked",
            "micro_expression": "full facial collapse — every held muscle released at once",
            "breath":           "shuddering uncontrolled breaths; audible; rhythm fractured",
        },
    },

    # ------------------------------------------------------------------ happy
    "happy": {
        "subtle": {
            "posture":          "natural upright; slight opening of the chest; weight evenly settled",
            "gesture":          "hands relaxed and open; weight distributed; no fidgeting",
            "gaze":             "relaxed eye contact; slight crinkling at outer corners",
            "micro_expression": "lip corners lift; Duchenne marker activates — eyes participate",
            "breath":           "easy, full breathing; one small unconscious exhale of contentment",
        },
        "mid": {
            "posture":          "tall and open; energy visible in upright stance and easy movement",
            "gesture":          "expressive hands; natural outward gestures that claim space",
            "gaze":             "direct warm eye contact; full-face engagement; no avoidance",
            "micro_expression": "full smile, cheekbones raised; crow's feet visible and honest",
            "breath":           "easy full breathing with occasional audible exhale on laugh-adjacent sounds",
        },
        "explosive": {
            "posture":          "full-body movement — pacing, turning; body can't contain the energy",
            "gesture":          "animated wide gesturing; may touch nearby person or object impulsively",
            "gaze":             "widely sweeping, inclusive; eye contact given freely to everyone present",
            "micro_expression": "face fully alight; teeth visible; laugh lines deep; skin flushed",
            "breath":           "laughter-adjacent breathing; speech quickens and pitches higher",
        },
    },

    # ------------------------------------------------------------------ nervous
    "nervous": {
        "subtle": {
            "posture":          "weight shifts subtly from foot to foot; an almost imperceptible sway",
            "gesture":          "thumb traces knuckle once; pen clicked; small displacement activity",
            "gaze":             "eye contact holds briefly then glances away; returns; glances again",
            "micro_expression": "rapid micro-swallow; lower lip taken between teeth for one beat",
            "breath":           "one controlled breath drawn before speaking; held fractionally long",
        },
        "mid": {
            "posture":          "pacing and stillness alternate; body unable to settle into one position",
            "gesture":          "hands constantly occupied — adjusting clothing, touching face, handling object",
            "gaze":             "unable to hold eye contact; eyes dart to exits and back",
            "micro_expression": "lips pursed; jaw works; blink rate elevated to a nervous rhythm",
            "breath":           "shallow chest breathing; occasional involuntary sigh escapes",
        },
        "explosive": {
            "posture":          "erratic, purposeless motion — sits, stands, paces without direction",
            "gesture":          "hands move constantly and without coordination between activities",
            "gaze":             "wild eye movement; unable to fix on any single point",
            "micro_expression": "face tight and pale; lips drawn back; expression brittle",
            "breath":           "rapid, shallow, audible; approaching hyperventilation",
        },
    },

    # ------------------------------------------------------------------ contempt
    "contempt": {
        "subtle": {
            "posture":          "weight drifts to one hip; a fractional lean away that requires no effort",
            "gesture":          "hand brushes the air once — clearing something of no importance",
            "gaze":             "eyes drop a fraction below the interlocutor's, evaluating downward",
            "micro_expression": "one corner of the mouth pulls back asymmetrically; nothing else moves",
            "breath":           "measured exhale through the nose; unhurried, disdainful",
        },
        "mid": {
            "posture":          "full body turns oblique; deliberate maintained distance claimed",
            "gesture":          "hand raises palm-forward — brief, unambiguous dismissal",
            "gaze":             "held slightly averted with periodic cold evaluative returns",
            "micro_expression": "full one-sided sneer; head tilt completes the expression",
            "breath":           "audible exhale of dismissal; the sound of someone not worth breath",
        },
        "explosive": {
            "posture":          "turns fully away; body language closes to the subject completely",
            "gesture":          "dismissive wave cuts the air or finger points exclusion",
            "gaze":             "refuses eye contact entirely — or holds a cold stare that gives nothing",
            "micro_expression": "face set in contemptuous stillness; the mask of total dismissal",
            "breath":           "sharp derisive exhale — close enough to a laugh to sting",
        },
    },

    # ------------------------------------------------------------------ grief
    "grief": {
        "subtle": {
            "posture":          "slight hollowing of chest; shoulders drift fractionally forward",
            "gesture":          "fingers press flat on a surface as if anchoring to the present",
            "gaze":             "eyes soften to middle distance; unfocused; the world recedes",
            "micro_expression": "inner brow corners rise; central forehead crease appears",
            "breath":           "one controlled slow exhale — the pace of the world slowing with it",
        },
        "mid": {
            "posture":          "body folds gradually forward; knees soften; standing becomes effortful",
            "gesture":          "hands press face or clasp together to prevent visible trembling",
            "gaze":             "vision blurs; blink rate irregular, fighting what's rising",
            "micro_expression": "mouth opens slightly; jaw drops; brow crushes inward at the centre",
            "breath":           "shuddering controlled inhale; holding against the break",
        },
        "explosive": {
            "posture":          "physical collapse onto surface or floor; the held shape finally abandoned",
            "gesture":          "hands grip knees or hair; body doubled; no position comfortable",
            "gaze":             "closed or staring unseeing while tears fall unchecked",
            "micro_expression": "complete facial surrender — every held muscle released at once",
            "breath":           "uncontrolled heaving; rhythm fractured; voice sounds without design",
        },
    },

    # ------------------------------------------------------------------ determined
    "determined": {
        "subtle": {
            "posture":          "spine straightens almost imperceptibly; weight settles and plants",
            "gesture":          "hands still and deliberate; one small purposeful adjustment completed",
            "gaze":             "focused forward; blink rate drops; soft focus on the objective",
            "micro_expression": "jaw sets; one small private nod; brow smooths and holds",
            "breath":           "single full breath drawn and released cleanly; rhythm steadies",
        },
        "mid": {
            "posture":          "full upright, chin fractionally raised; body commits to the direction",
            "gesture":          "purposeful stride begins or deliberate reach closes on the objective",
            "gaze":             "direct, locked on goal; obstacles noted and categorically dismissed",
            "micro_expression": "mouth closes firmly; brow level, clear, and untroubled",
            "breath":           "steady, full, silent — body oxygenated and ready",
        },
        "explosive": {
            "posture":          "body fully committed; no reserve held back; momentum released",
            "gesture":          "motion begins without hesitation; obstacle removed or overcome",
            "gaze":             "locked and tracking; nothing else registers in the visual field",
            "micro_expression": "face set with near-serenity in absolute commitment; beyond doubt",
            "breath":           "held through execution; releases with the effort",
        },
    },

    # ------------------------------------------------------------------ shocked
    "shocked": {
        "subtle": {
            "posture":          "motion pauses, one beat held exactly where it was",
            "gesture":          "hand movement stops mid-gesture, suspended",
            "gaze":             "eyes still; focus shifts suddenly to the source",
            "micro_expression": "brows rise a fraction; a half-breath catch visible in the throat",
            "breath":           "half-beat pause in respiration; the body computing",
        },
        "mid": {
            "posture":          "body goes rigid, weight stops and anchors — the freeze of processing",
            "gesture":          "hands open at sides, fingers spread; nothing gripped",
            "gaze":             "eyes fully wide, fixing on the source; no blinking",
            "micro_expression": "mouth drops open a fraction; brows reach maximum elevation",
            "breath":           "sharp audible intake held for one full beat",
        },
        "explosive": {
            "posture":          "full body recoil or total freeze; staggering backward possible",
            "gesture":          "hands fly to face or thrust outward; no coordination maintained",
            "gaze":             "fixed unblinking wide stare, whites fully exposed around iris",
            "micro_expression": "jaw dropped entirely slack; face loses all voluntary muscle control",
            "breath":           "involuntary audible gasp — then a held silence that fills the room",
        },
    },

    # ------------------------------------------------------------------ relieved
    "relieved": {
        "subtle": {
            "posture":          "fractional softening at the shoulders; a single degree of forward bow",
            "gesture":          "hand unclenches slowly; fingers extend one by one",
            "gaze":             "eyes close briefly — a private gratitude",
            "micro_expression": "brows descend from tension; lip corners soften without quite smiling",
            "breath":           "controlled slow exhalation — the release of what was being held",
        },
        "mid": {
            "posture":          "shoulders drop noticeably; chest expands on a full release",
            "gesture":          "hands press together briefly or find the nearest solid surface",
            "gaze":             "eyes close; head bows; reopens softer, slower",
            "micro_expression": "full facial softening; a small private smile appears involuntarily",
            "breath":           "audible long exhale; next inhale deep and complete",
        },
        "explosive": {
            "posture":          "body collapses forward or onto whatever surface is nearest; held shape abandoned",
            "gesture":          "hands fall open; body may grip nearest person or surface for anchoring",
            "gaze":             "eyes close tight then open wet; tears possible but not sad",
            "micro_expression": "face breaks open — laugh and sob competing on the same exhale",
            "breath":           "long shuddering exhale; laughter or crying arrives on the release",
        },
    },

    # ------------------------------------------------------------------ suspicious
    "suspicious": {
        "subtle": {
            "posture":          "weight shifts to heels; oblique angle to the subject maintained",
            "gesture":          "hands still and controlled; nothing given away in movement",
            "gaze":             "eyes narrow fractionally; head tilts five degrees",
            "micro_expression": "lower lid tightens; brow draws together subtly",
            "breath":           "imperceptibly slowed — the listening breath",
        },
        "mid": {
            "posture":          "body turns oblique, exit awareness maintained in peripheral vision",
            "gesture":          "arms cross or hands clasp behind the back; body closed",
            "gaze":             "eyes scan from target to environment and back; reading everything",
            "micro_expression": "full narrowing; jaw slightly forward; chin drops a fraction",
            "breath":           "deliberate controlled pace; pause before any response",
        },
        "explosive": {
            "posture":          "full defensive stance; back toward a wall if one is available",
            "gesture":          "hand moves to a ready position or points challenge outward",
            "gaze":             "direct hard evaluation stare; no softening offered or possible",
            "micro_expression": "face set cold; every micro-movement of the target tracked and catalogued",
            "breath":           "quiet, slow; the body already prepared for sudden action",
        },
    },

    # ------------------------------------------------------------------ desperate
    "desperate": {
        "subtle": {
            "posture":          "leans fractionally forward; energy barely contained behind controlled surface",
            "gesture":          "hands grip a surface edge; knuckles white but movement controlled",
            "gaze":             "direct pleading eye contact; held unblinking; asking",
            "micro_expression": "inner brows raised in appeal; lips part; skin tight",
            "breath":           "controlled but audibly faster; words pressed out through the strain",
        },
        "mid": {
            "posture":          "body pitches forward; personal space violated by the need",
            "gesture":          "hands reach toward subject or grasp whatever is nearest",
            "gaze":             "rapid movement between subject and environment; calculating last options",
            "micro_expression": "face openly showing the strain; the mask finally dropped",
            "breath":           "rapid shallow breathing; voice breaks at the upper register",
        },
        "explosive": {
            "posture":          "erratic; no dignity of posture remaining; body in full emergency",
            "gesture":          "hands grasp at anything; motion without plan or control",
            "gaze":             "wild, darting; no sustained focus achievable",
            "micro_expression": "face fully open; tears or screaming; the last resource spent",
            "breath":           "hyperventilating or soundless gasping; complete physical expression",
        },
    },

    # ------------------------------------------------------------------ disgusted
    "disgusted": {
        "subtle": {
            "posture":          "fractional lean back; head draws imperceptibly away from the source",
            "gesture":          "hand rises instinctively toward mouth — arrested before completing",
            "gaze":             "eyes drop away from subject; the aversion reflex",
            "micro_expression": "nose wrinkles almost imperceptibly; upper lip tightens on one side",
            "breath":           "brief breath-hold — then careful exhale through the mouth",
        },
        "mid": {
            "posture":          "full step back; body turns partially away; distance claimed",
            "gesture":          "hand covers nose or rises in warding gesture",
            "gaze":             "averted with effort; returns briefly with narrowed evaluation",
            "micro_expression": "full nose wrinkle; upper lip raised; head drawn back",
            "breath":           "audible exhale through the mouth; next breath held deliberately shallow",
        },
        "explosive": {
            "posture":          "hard recoil; body distances maximally from the source",
            "gesture":          "hands push away or cover face entirely; maximising distance",
            "gaze":             "refuses to look; eyes close or turn skyward",
            "micro_expression": "full disgust response; sounds possible — involuntary, uncontrolled",
            "breath":           "gagging reflex; mouth-breathing forced; body rejecting proximity",
        },
    },

    # ------------------------------------------------------------------ resigned
    "resigned": {
        "subtle": {
            "posture":          "slight decrease in held tension — not release, but abandonment of effort",
            "gesture":          "hands lower or spread open — the wordless 'what can be done'",
            "gaze":             "eyes drop to middle distance; unfocused acceptance settles",
            "micro_expression": "all held tension leaves the face — not peace, but absence",
            "breath":           "slow even exhale; then flat steady rhythm resumes",
        },
        "mid": {
            "posture":          "body curves; shoulders down and forward — not collapse, but acceptance",
            "gesture":          "arms drop entirely; hands open at the thighs",
            "gaze":             "gaze drops to the floor or moves to the window; nothing to face",
            "micro_expression": "lips part slightly; face settles into neutral held stillness",
            "breath":           "one long exhale; rhythm slows to resting; the body accepts its situation",
        },
        "explosive": {
            "posture":          "full physical stillness; motion stops completely; the fight simply leaves",
            "gesture":          "hands fall; body stops; resistance evaporates",
            "gaze":             "eyes close or stare at nothing; the world stops registering",
            "micro_expression": "face emptied; all effort gone; just the fact of it remaining",
            "breath":           "slow, barely-there breathing; voice might come low and flat if at all",
        },
    },

    # ------------------------------------------------------------------ defiant
    "defiant": {
        "subtle": {
            "posture":          "chin fractionally raised; feet planted almost imperceptibly wider",
            "gesture":          "hands hang loose and ready at sides — not aggressive, certain",
            "gaze":             "level direct eye contact; does not give ground, does not soften",
            "micro_expression": "jaw set; lips closed firmly; expression does not shift",
            "breath":           "steady controlled breathing; body oxygenated, prepared",
        },
        "mid": {
            "posture":          "full stance — feet wide, weight balanced; spine tall and claimed",
            "gesture":          "arms cross or hands find hips; full occupation of space",
            "gaze":             "hard unbroken eye contact; the challenge acknowledged and held",
            "micro_expression": "chin forward; brow level; one corner of the mouth almost smiles",
            "breath":           "deliberate, audible; paced slowly and with purpose",
        },
        "explosive": {
            "posture":          "body planted absolutely; maximum space occupied; immovable",
            "gesture":          "hand thrusts forward in challenge or points; no ambiguity in the gesture",
            "gaze":             "locked, unflinching; would meet any force without yielding",
            "micro_expression": "face set in absolute certainty; every muscle holds the line",
            "breath":           "sharp defiant exhale; the sound of someone who has already decided",
        },
    },

    # ------------------------------------------------------------------ neutral (fallback)
    "neutral": {
        "subtle": {
            "posture":          "easy upright; weight distributed naturally",
            "gesture":          "hands relaxed at sides or resting; no displacement activity",
            "gaze":             "present, scanning at normal pace; no heightened alertness",
            "micro_expression": "face at rest; no held expression; relaxed musculature",
            "breath":           "easy tidal breathing; unremarkable",
        },
        "mid": {
            "posture":          "attentive upright; slight forward lean of engagement",
            "gesture":          "hands active in normal communication patterns",
            "gaze":             "direct engaged eye contact; responsive",
            "micro_expression": "face shows normal social expressivity; nothing suppressed",
            "breath":           "steady, full, conversational rhythm",
        },
        "explosive": {
            "posture":          "full-body engagement; energy expressed freely",
            "gesture":          "expansive, unguarded gesture",
            "gaze":             "wide, inclusive, energised",
            "micro_expression": "open expressive face; all social signals available",
            "breath":           "animated breathing; speech rhythms accelerated",
        },
    },
}


# ---------------------------------------------------------------------------
# BODY_LANGUAGE_STATE_AFTER
# The energy_level and gaze_direction a character carries OUT of a scene.
# Used to build BodyLanguageState and propagate continuity across scenes.
# ---------------------------------------------------------------------------

BODY_LANGUAGE_STATE_AFTER: dict[str, dict[str, dict[str, str]]] = {
    "angry":      {"subtle": {"energy_level": "coiled",    "gaze_direction": "hunting"},
                   "mid":    {"energy_level": "coiled",    "gaze_direction": "hunting"},
                   "explosive":{"energy_level":"released", "gaze_direction": "forward"}},
    "scared":     {"subtle": {"energy_level": "coiled",    "gaze_direction": "scanning"},
                   "mid":    {"energy_level": "coiled",    "gaze_direction": "scanning"},
                   "explosive":{"energy_level":"released", "gaze_direction": "avoidant"}},
    "sad":        {"subtle": {"energy_level": "still",     "gaze_direction": "inward"},
                   "mid":    {"energy_level": "still",     "gaze_direction": "inward"},
                   "explosive":{"energy_level":"exhausted","gaze_direction": "inward"}},
    "happy":      {"subtle": {"energy_level": "charged",   "gaze_direction": "forward"},
                   "mid":    {"energy_level": "charged",   "gaze_direction": "forward"},
                   "explosive":{"energy_level":"released", "gaze_direction": "forward"}},
    "nervous":    {"subtle": {"energy_level": "coiled",    "gaze_direction": "scanning"},
                   "mid":    {"energy_level": "coiled",    "gaze_direction": "avoidant"},
                   "explosive":{"energy_level":"coiled",   "gaze_direction": "avoidant"}},
    "contempt":   {"subtle": {"energy_level": "still",     "gaze_direction": "avoidant"},
                   "mid":    {"energy_level": "still",     "gaze_direction": "avoidant"},
                   "explosive":{"energy_level":"still",    "gaze_direction": "avoidant"}},
    "grief":      {"subtle": {"energy_level": "still",     "gaze_direction": "inward"},
                   "mid":    {"energy_level": "exhausted", "gaze_direction": "inward"},
                   "explosive":{"energy_level":"exhausted","gaze_direction": "inward"}},
    "determined": {"subtle": {"energy_level": "coiled",    "gaze_direction": "forward"},
                   "mid":    {"energy_level": "charged",   "gaze_direction": "forward"},
                   "explosive":{"energy_level":"released", "gaze_direction": "forward"}},
    "shocked":    {"subtle": {"energy_level": "still",     "gaze_direction": "forward"},
                   "mid":    {"energy_level": "still",     "gaze_direction": "forward"},
                   "explosive":{"energy_level":"still",    "gaze_direction": "scanning"}},
    "relieved":   {"subtle": {"energy_level": "released",  "gaze_direction": "inward"},
                   "mid":    {"energy_level": "released",  "gaze_direction": "inward"},
                   "explosive":{"energy_level":"exhausted","gaze_direction": "inward"}},
    "suspicious": {"subtle": {"energy_level": "coiled",    "gaze_direction": "scanning"},
                   "mid":    {"energy_level": "coiled",    "gaze_direction": "scanning"},
                   "explosive":{"energy_level":"coiled",   "gaze_direction": "hunting"}},
    "desperate":  {"subtle": {"energy_level": "coiled",    "gaze_direction": "hunting"},
                   "mid":    {"energy_level": "charged",   "gaze_direction": "scanning"},
                   "explosive":{"energy_level":"released", "gaze_direction": "avoidant"}},
    "disgusted":  {"subtle": {"energy_level": "still",     "gaze_direction": "avoidant"},
                   "mid":    {"energy_level": "still",     "gaze_direction": "avoidant"},
                   "explosive":{"energy_level":"released", "gaze_direction": "avoidant"}},
    "resigned":   {"subtle": {"energy_level": "still",     "gaze_direction": "inward"},
                   "mid":    {"energy_level": "exhausted", "gaze_direction": "inward"},
                   "explosive":{"energy_level":"exhausted","gaze_direction": "inward"}},
    "defiant":    {"subtle": {"energy_level": "coiled",    "gaze_direction": "forward"},
                   "mid":    {"energy_level": "coiled",    "gaze_direction": "forward"},
                   "explosive":{"energy_level":"charged",  "gaze_direction": "forward"}},
    "neutral":    {"subtle": {"energy_level": "still",     "gaze_direction": "forward"},
                   "mid":    {"energy_level": "still",     "gaze_direction": "forward"},
                   "explosive":{"energy_level":"still",    "gaze_direction": "forward"}},
}
