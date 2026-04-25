# District Zero EP01 Runway Review

Current review build:
- video: `out/district_zero_ep01_production_cut_runway_merged_3/video.json`
- production timeline: `out/district_zero_ep01_production_cut_runway_merged_3/production.json`
- metrics: `out/district_zero_ep01_production_cut_runway_merged_3/metrics.json`

Status:
- generated clips: 32 / 35
- missing clips: 3 / 35
- total duration: 130 seconds
- estimated cumulative Runway video cost: 6.05 USD

Usable now at no additional provider cost:
- review all 32 generated clips
- assemble a first local cut with 3 temporary gaps in scene 11
- prepare notes on the missing emotional beats before the next retry window

Remaining missing shots:

1. `SCN_011_SHOT_001`
   - duration: 3s
   - prompt: `Nara returns home soaked and shaken, in INT. VOSS APARTMENT - PRE-DAWN.`

2. `SCN_011_SHOT_002`
   - duration: 3s
   - prompt: `Elian sees her face and knows the secret is gone, in INT. VOSS APARTMENT - PRE-DAWN.`

3. `SCN_011_SHOT_003`
   - duration: 3s
   - prompt: `Nara recoils as the truth lands between them, in INT. VOSS APARTMENT - PRE-DAWN.`

Pragmatic montage note:
- the only missing material is the opening emotional exchange of scene 11
- shots `SCN_011_SHOT_004` to `SCN_011_SHOT_007` are already available
- this means the cut is structurally usable, but the scene opens late unless placeholders are inserted

Retry readiness:
- prepared script: `artifacts/retry_runway_scene11_remaining.py`
- expected inputs already present in `out/`
- target outputs will be written to `out/district_zero_ep01_production_cut_runway_retry_failed_final/` and `out/district_zero_ep01_production_cut_runway_merged_final/`