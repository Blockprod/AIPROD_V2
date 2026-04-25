# Episode Temporary Rough Cut Status

Objective:
- build a no-cost full-episode review cut from the current merged Runway build
- reuse the existing 32 generated Runway clips
- replace only the 3 missing clips with storyboard-based placeholders

Artifacts:
- helper script: `artifacts/create_episode_temp_rough_cut.py`
- target output: `out/district_zero_ep01_production_cut_runway_merged_3/episode_temp_rough_cut.mp4`

Render command:

```powershell
.\venv\Scripts\Activate.ps1
python artifacts/create_episode_temp_rough_cut.py
```

Current behavior of the helper:
- downloads each existing Runway clip
- normalizes clips to the production resolution and fps
- generates silent placeholder videos from storyboard stills for the 3 missing shots
- concatenates the 35 segments into one silent MP4 review cut

Known state at creation time:
- current merged production: `35` clips total
- missing visual clips: `3`
- production duration: `130s`
- production resolution: `3840x2160`
- production fps: `24`

Practical note:
- the first full render can take time because it downloads and re-encodes the full 4K episode locally
- if the output file is not yet present, the process may still be assembling intermediate segments