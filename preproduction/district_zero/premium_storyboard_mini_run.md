# District Zero Premium Mini Run

This is the cheapest meaningful paid storyboard validation for District Zero right now.

Why these 5 shots:
- `SCN_002_SHOT_001`: Nara identity lock in the corridor.
- `SCN_003_SHOT_001`: Nara inside a heavy industrial set with workers.
- `SCN_008_SHOT_001`: two-character frame in the sealed service spine.
- `SCN_009_SHOT_001`: premium world-reveal environment shot.
- `SCN_011_SHOT_001`: emotional acting and pre-dawn apartment mood.

No-cost probe first:

```powershell
venv\Scripts\Activate.ps1
venv\Scripts\python.exe -m aiprod_adaptation.cli storyboard `
  --input out/district_zero_ep01_production_cut_ir.json `
  --output out/district_zero_ep01_premium_critical_probe_null.json `
  --image-adapter null `
  --reference-pack preproduction/district_zero/reference_pack.json `
  --shot-id SCN_002_SHOT_001 `
  --shot-id SCN_003_SHOT_001 `
  --shot-id SCN_008_SHOT_001 `
  --shot-id SCN_009_SHOT_001 `
  --shot-id SCN_011_SHOT_001
```

Paid storyboard run:

```powershell
venv\Scripts\Activate.ps1
venv\Scripts\python.exe -m aiprod_adaptation.cli storyboard `
  --input out/district_zero_ep01_production_cut_ir.json `
  --output out/district_zero_ep01_premium_critical_storyboard_v1.json `
  --image-adapter openai `
  --reference-pack preproduction/district_zero/reference_pack.json `
  --shot-id SCN_002_SHOT_001 `
  --shot-id SCN_003_SHOT_001 `
  --shot-id SCN_008_SHOT_001 `
  --shot-id SCN_009_SHOT_001 `
  --shot-id SCN_011_SHOT_001
```

Practical note:
- `storyboard` writes one JSON file at the exact `--output` path.

Review gate before any video spend:
- Nara must stay recognizable in all Nara-led frames.
- Corridor, valve chamber, service spine, and observation chamber must each feel like distinct premium sets.
- `SCN_008_SHOT_001` is the deciding frame for whether Mira needs a hero reference before a larger paid batch.
- `SCN_011_SHOT_001` is the deciding frame for whether the current pre-dawn apartment prompt is emotionally strong enough.