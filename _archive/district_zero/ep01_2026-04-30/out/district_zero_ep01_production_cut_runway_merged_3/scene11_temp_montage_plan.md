# Scene 11 Temporary Montage Plan

Objective:
- keep scene 11 reviewable now without paying for new generations
- preserve story comprehension until Runway can regenerate the 3 missing opening shots

Available sources:
- final working timeline: `out/district_zero_ep01_production_cut_runway_merged_3/production.json`
- generated video clips already usable: `SCN_011_SHOT_004` to `SCN_011_SHOT_007`
- fallback stills already available at no extra cost: `SCN_011_SHOT_001` to `SCN_011_SHOT_003` inside `out/district_zero_ep01_production_cut_openai/storyboard.json` via embedded `image_b64`

Editorial premise:
- do not restructure scene 11
- keep the original 3-second slots and exact start times
- replace only the missing visual layer for shots 001 to 003
- keep shots 004 to 007 exactly as they are in the current merged Runway build

Temporary cut map:

1. `109s` to `112s` - `SCN_011_SHOT_001`
   - intended beat: Nara returns home soaked and shaken
   - temporary visual: use the OpenAI storyboard still for `SCN_011_SHOT_001`
   - move: slow digital push from `100%` to `106%`
   - transition in: `6` frame fade up from black
   - transition out: hard cut

2. `112s` to `115s` - `SCN_011_SHOT_002`
   - intended beat: Elian reads her face and understands the secret is exposed
   - temporary visual: use the OpenAI storyboard still for `SCN_011_SHOT_002`
   - move: subtle push from `100%` to `103%`
   - transition in: hard cut from shot 001 placeholder
   - transition out: hard cut

3. `115s` to `118s` - `SCN_011_SHOT_003`
   - intended beat: Nara recoils as the truth lands between them
   - temporary visual: use the OpenAI storyboard still for `SCN_011_SHOT_003`
   - move: tighter push from `100%` to `108%`
   - transition in: hard cut
   - transition out: hard cut to `SCN_011_SHOT_004`

4. `118s` to `130s` - keep generated Runway clips unchanged
   - `SCN_011_SHOT_004`: encrypted drive handoff
   - `SCN_011_SHOT_005`: boots outside the door
   - `SCN_011_SHOT_006`: door detonates inward
   - `SCN_011_SHOT_007`: smash cut to black

Why this cut works:
- the missing material is only the emotional setup of the scene
- still-image placeholders preserve all three narrative beats in order
- the scene regains continuity before the already-generated action escalation begins at `118s`
- tomorrow's regenerated clips can drop into the same time slots with no timeline ripple

Recommended review expectation:
- judge story clarity, pacing, and escalation from `118s` onward normally
- treat `109s` to `118s` as a storyboard-based emotional bridge, not final motion quality
- note whether the emotional logic of the scene opening is readable before replacement

Replacement rule for tomorrow:
- when the retry succeeds, replace the three placeholder still segments one-for-one at the same timecodes
- do not retime scene 11 unless the regenerated clips come back with durations different from `3s`