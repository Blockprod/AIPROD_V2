# Manual Retake Package — Nara — SCN_002_SHOT_001

Base shot to edit:
- `source_shot_base.png`

Reference photo to upload as Reference Photo:
- `nara_reference_photo.png`

Why this package exists:
- The automated `images.edit` run preserved the corridor and costume, but failed on the two critical constraints: exact face identity and critical facial focus.
- This package switches to the operator workflow that fits the request better: GPT-Image-2 manual edit with a reference photo, then a manual re-upload pass to lock the face and sharpness.

Source image facts:
- Base shot: `1536x1024`
- Reference photo: `1536x1024`
- Target framing for this manual retake: `16:9`
- Target finish: high quality, final frame intended for 4K delivery

Recommended operator flow:
1. Upload `source_shot_base.png` as the image to edit.
2. Add `nara_reference_photo.png` as the Reference Photo.
3. Paste the full text from `prompt_pass_1_identity_and_focus.txt`.
4. Generate several variants and keep only the one that best matches Nara's exact face.
5. Re-upload the best result from pass 1 together with `nara_reference_photo.png`.
6. Paste the full text from `prompt_pass_2_reupload_lock.txt`.
7. Select the result only if the face remains exact when zooming to 100%.

Validation gate:
- Same woman as the reference photo, immediately recognizable.
- Both eyes sharp at 100% zoom.
- Nose, mouth, jawline, hairline and skin texture consistent with the reference.
- No glam pass, no beauty retouch, no waxy skin.
- Same corridor, same red practical lighting, same running pose, same costume.
- No scene redesign and no camera reframing.