---
title: Plan d'action — Pipeline V4 (3D animé → stylisation IA)
project: District Zero — EP01+
creation: 2026-05-04 à 16:34
status: pending
---

# Pipeline V4 — Plan d'action complet

## Contexte

Le pipeline V2 actuel (FLUX P1 + FLUX Fill P2, verrouillé 2026-04-30) génère des images statiques
shot par shot. Il reste en place et opérationnel pour les épisodes existants.

La V4 est une rupture architecturale : on passe d'un pipeline de **génération d'images** à un
pipeline de **production 3D avec finition IA**. Chaque shot devient une animation Blender
stylisée frame par frame.

```
Blender (3D animé) → frames PNG → ControlNet stylisation → vidéo cinéma
```

Référence industrielle : Wonder Dynamics, Corridor Crew (productions avancées).

---

## Hardware cible

| Machine | GPU | VRAM | Statut |
|---------|-----|------|--------|
| PC actuel | GTX 1070 | 4 GB | ⚠️ Insuffisant pour ComfyUI V4 |
| Lenovo Legion Pro 7 Gen 10 AMD | RTX 5080 Laptop | 16 GB | ✅ Cible d'achat |

**Impact du passage RTX 5080 :**
- BLOC C (stylisation) passe de Replicate API (~$168/EP01) à ComfyUI local (~$0/EP01)
- Économie : ~$168 par épisode, amortissement rapide sur la série
- AnimateDiff + FLUX + ControlNet tiennent en 16 GB (avec quantization FP8 si besoin)

---

## Architecture V4

### BLOC A — Construction des assets 3D

| Outil | Usage | Coût estimé |
|-------|-------|-------------|
| Tripo3D API | Mesh personnages (GLB) — multiview_to_model | ~$1.50 (5 perso × $0.30) |
| Meshy API | Mesh décors (GLB) — image_to_model | ~$2.00 (10 décors × $0.20) |
| Mixamo (Adobe) | Auto-rigging + 2500+ animations | Gratuit (Adobe ID) |
| Blender | Assemblage scène + caméra + animation | Gratuit (local) |

**Outputs :** `nara.glb`, `mira.glb`, `elian.glb`, `vale.glb`, `rook.glb` + 10 GLB décors

**Commandes API clés :**
- Tripo3D : `multiview_to_model` avec `[front, left, back, right]` + seeds reproductibles
- Meshy : `image_to_model` depuis master plates locations existantes

### BLOC B — Rendu Blender par shot

Blender headless (Python) génère pour chaque shot :
- `frame_0001.png` → `frame_NNNN.png` (5s × 24fps = 120 frames/shot)
- Séquence `depth_map_NNNN.exr`
- Séquence `normal_map_NNNN.exr`

Mode rendu : EEVEE (rapide, non-photorealistic intentionnel — l'IA stylise par-dessus).

**Total frames EP01 :** 35 shots × 120 frames = 4 200 frames

### BLOC C — Stylisation frame-par-frame

| Composant | Rôle |
|-----------|------|
| ControlNet | depth_map → contraint la géométrie 3D |
| IP-Adapter | character_ref → impose l'apparence du personnage |
| FLUX / Seedream | Rendu cinématographique sur chaque frame |
| AnimateDiff | Cohérence temporelle (anti-flickering inter-frames) |

**Option A (RTX 5080 disponible) :** ComfyUI local — coût ~$0  
**Option B (GTX 1070 / en attente) :** Replicate API — coût $125–210/EP01

### BLOC D — Assembly final

| Outil | Usage |
|-------|-------|
| FFmpeg | frames PNG → `clip_shot.mp4` |
| ElevenLabs | Dialogues personnages + narration |
| Suno / Lyria 3 | Score musical |
| DaVinci Resolve | Grade colorimétrique + mix audio + export final |

---

## Budget EP01 V4

```
Assets 3D
  Tripo3D (5 personnages)         ~$1.50
  Meshy (10 décors)               ~$2.00

Multi-angle refs (Seedream 4.5)
  ~110 images × $0.04             ~$4.40

Stylisation frames
  Option A : ComfyUI local        ~$0.00
  Option B : Replicate API        ~$125–210

Audio
  ElevenLabs (dialogues)          ~$5–15

Total Option A (RTX 5080)         ~$13–23
Total Option B (GTX 1070)         ~$138–233
```

---

## Plan d'action semaine par semaine

### Pré-requis immédiats (avant de commencer)

- [ ] Confirmer Blender installé (ou installer depuis blender.org)
- [ ] Créer compte Tripo3D → https://platform.tripo3d.ai → récupérer `TRIPO3D_API_TOKEN`
- [ ] Créer compte Meshy → https://www.meshy.ai → récupérer `MESHY_API_TOKEN`
- [ ] Créer compte Mixamo → https://mixamo.com (gratuit, Adobe ID)
- [ ] Ajouter les tokens dans `.env` du projet
- [ ] (Optionnel) Acheter Legion Pro 7 Gen 10 AMD → RTX 5080 → activer ComfyUI local

---

### Semaine 1 — Setup assets 3D

**Objectif :** Avoir les 15 GLB (5 perso + 10 décors) prêts dans Blender.

**Tâches :**
- [ ] Créer `aiprod_adaptation/image_gen/tripo3d_adapter.py`
  - `multiview_to_model(front, left, back, right, seed)` → retourne `model_url`
  - `poll_task(task_id)` → attend completion
  - `download_glb(url, output_path)`
- [ ] Créer `aiprod_adaptation/image_gen/meshy_adapter.py`
  - `image_to_model(image_path, seed)` → retourne `task_id`
  - `poll_task(task_id)` → attend completion
  - `download_glb(url, output_path)`
- [ ] Créer `production/gen_character_sheets.py`
  - 8–12 angles × 5 personnages via Seedream 4.5
  - Outputs : `production/character_sheets/{slug}/angle_{N}.png`
- [ ] Créer `production/gen_location_coverage.py`
  - 5–6 angles × 10 lieux via Seedream 4.5
  - Outputs : `production/location_sheets/{slug}/angle_{N}.png`
- [ ] Créer `production/gen_3d_assets.py`
  - Orchestre Tripo3D (personnages) + Meshy (décors)
  - Outputs : `production/assets_3d/{slug}.glb`

**Ne pas déclencher avant autorisation explicite** (appels API payants).

---

### Semaine 2 — Rigging Mixamo + animation shot par shot

**Objectif :** Chaque shot Blender a ses personnages riggés et animés.

**Tâches :**
- [ ] Importer les GLB Tripo3D dans Mixamo → auto-rigging → export FBX
- [ ] Réimporter FBX dans Blender avec armature
- [ ] Créer script `pipeline/blender_render.py`
  - Blender headless Python API
  - Charge scène décor (GLB Meshy)
  - Place personnage(s) riggés (FBX Mixamo)
  - Positionne caméra selon `storyboard.json` (`shot_type`, `composition`)
  - Joue animation correspondante au `action_brief`
  - Exporte : frames PNG + depth_map EXR + normal_map EXR
- [ ] Mapper les 35 shots du storyboard vers des animations Mixamo
  - Créer `production/shot_animations.json` : `shot_id → {character, animation_clip, camera}`

---

### Semaine 3 — Pipeline stylisation ControlNet

**Objectif :** BLOC C fonctionnel sur un shot test (SCN_001_SHOT_001).

**Tâches :**
- [ ] Créer `pipeline/shot_pipeline_v4.py` (NE PAS modifier v2)
  - Entrée : `depth_map_seq/`, `character_ref.png`, `prompt_cinematic`
  - Pour chaque frame : ControlNet (depth) + IP-Adapter + FLUX
  - Sortie : `stylized_frames/frame_NNNN.png`
  - Deux backends : `ComfyUIBackend` (local) et `ReplicateBackend` (API)
- [ ] Si ComfyUI local (RTX 5080) : installer ComfyUI + nodes ControlNet + AnimateDiff
- [ ] Si Replicate : utiliser modèle `stability-ai/stable-diffusion-controlnet-depth`
- [ ] Créer `pipeline/video_pipeline.py`
  - `frames_to_clip(frames_dir, fps=24)` → FFmpeg → `clip_shot.mp4`
  - `add_audio(clip, audio_path)` → clip avec son
- [ ] Test end-to-end sur SCN_001_SHOT_001

---

### Semaine 4 — Tests + calibration cohérence temporelle

**Objectif :** Éliminer le flickering. Résultat cohérent sur 5 shots consécutifs.

**Tâches :**
- [ ] Intégrer AnimateDiff dans le BLOC C
  - Mode batch : 16 frames à la fois (fenêtre glissante)
  - Paramètre `motion_scale` à calibrer par type de shot
- [ ] Créer `production/quality_gate_v4.py`
  - Métriques : SSIM inter-frames (cible ≥0.85), cohérence visage ArcFace (≥0.85)
  - Flag automatique si flickering détecté
- [ ] Calibrer par `shot_type` :
  - `ultra_wide` / `wide` : motion_scale élevé (caméra bouge)
  - `close` / `medium` : motion_scale bas (visage stable requis)
- [ ] Tester sur SCN_001 (2 shots) + SCN_008 (4 shots rapprochés)

---

### Semaine 5 — Génération complète EP01

**Objectif :** 35 shots stylisés, 4 200 frames, clips MP4 individuels.

**Tâches :**
- [ ] Lancer `production/gen_shots_v4.py` scène par scène
  - Checkpoint automatique : reprendre depuis le dernier shot terminé
  - Log coût cumulé dans `production/metrics_v4.jsonl`
- [ ] Valider chaque shot : `quality_gate_v4.py`
- [ ] Retakes automatiques si ArcFace < 0.85 (max 3 tentatives)
- [ ] Budget tracking : ne pas dépasser $250 total sans accord

---

### Semaine 6 — Audio + assembly + grade DaVinci

**Objectif :** EP01 complet prêt pour diffusion.

**Tâches :**
- [ ] ElevenLabs : générer dialogues depuis `stories/district_zero_ep01.fountain`
  - 1 voix unique et stable par personnage (voice cloning si disponible)
- [ ] Suno / Lyria 3 : score EP01 (thème principal + 3–4 variations)
- [ ] `pipeline/assembly.py` : coller les 35 clips dans l'ordre storyboard
- [ ] Import dans DaVinci Resolve
  - Grade LUT : style cinéma dystopique (teintes froides, crush des noirs)
  - Mix audio : dialogues + score + ambiance
  - Export : H.264 1080p + ProRes 4K master

---

## Fichiers à créer (aucun existant pour V4)

```
aiprod_adaptation/image_gen/
  tripo3d_adapter.py
  meshy_adapter.py
  seedream_adapter.py          (Seedream 4.5 via Replicate)

pipeline/
  shot_pipeline_v4.py          (NE PAS modifier shot_pipeline.py v2)
  blender_render.py
  video_pipeline.py
  assembly.py

production/
  gen_character_sheets.py
  gen_location_coverage.py
  gen_3d_assets.py
  gen_shots_v4.py
  shot_animations.json
  quality_gate_v4.py
```

---

## Règles absolues (héritées du projet)

- **JAMAIS déclencher une génération sans autorisation explicite** (API payantes)
- **UNE SEULE image à la fois** pour les tests, jamais de boucle multi-seeds sans accord
- **NE PAS modifier** `pipeline/shot_pipeline.py` (v2 verrouillé 2026-04-30)
- **NE PAS modifier** `production/storyboard.json` sans discussion préalable
- ArcFace threshold : ≥0.85 obligatoire sur tous les shots avec visage
- Présenter script + coût estimé avant toute exécution

---

## Dépendances externes à installer (RTX 5080)

```
# ComfyUI (local, BLOC C)
git clone https://github.com/comfyanonymous/ComfyUI
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt

# Nodes complémentaires
ComfyUI-Manager → installer :
  - ComfyUI-Advanced-ControlNet
  - ComfyUI_IPAdapter_plus
  - ComfyUI-AnimateDiff-Evolved
  - ComfyUI_essentials

# Blender headless
pip install bpy  # ou utiliser Blender standalone avec --python flag

# Tripo3D + Meshy SDK
pip install tripo3d-client  # à vérifier sur PyPI
pip install requests        # fallback REST si pas de SDK
```

---

## Indicateurs de succès EP01 V4

| Métrique | Cible |
|----------|-------|
| Frames stylisées | 4 200 / 4 200 |
| ArcFace visages | ≥ 0.85 (moyenne) |
| SSIM inter-frames | ≥ 0.85 (anti-flickering) |
| Coût total | < $250 (Option B) / < $25 (Option A) |
| Durée EP01 | ~8 min (35 shots × 5s moy + transitions) |
| Formats export | H.264 1080p + ProRes 4K |
