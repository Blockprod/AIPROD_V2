"""
production/gen_character_bodies.py
====================================
Corpus de référence CORPS — bloc indépendant du corpus visage.

Objectif : couvrir les postures, dynamiques et angles pour chaque
personnage, avec un niveau de précision anatomique et vestimentaire
indiscernable d'une production humaine.

Stratégie de prompting :
  - Aucune formule générique "AI art" (photorealistic, hyperdetailed…)
  - Terminologie de photographie de production réelle
  - Spécifications caméra/optique/éclairage explicites
  - Description anatomique précise de la posture (angle articulaire,
    distribution du poids, axe du bassin, axe des épaules)
  - Description du costume complète issue du canonical
  - Référence DOP inspirée des validations portrait (cohérence visuelle)

Deux blocs indépendants :
  TURNAROUND — 8 angles × posture neutre debout (A-pose ajusté)
  POSTURES   — 7 postures clé × vue 3/4 canonique

Total par personnage : 8 + 7 = 15 images
Total 5 personnages  : 75 images
Coût estimé Seedream 4.5 : ~75 × $0.04 = ~$3.00

Outputs :
  production/character_bodies/{slug}/turn_{N:02d}_{label}.png
  production/character_bodies/{slug}/pose_{N:02d}_{label}.png

Usage :
    python production/gen_character_bodies.py --dry-run
    python production/gen_character_bodies.py --character nara --dry-run
    python production/gen_character_bodies.py --character nara --block turnaround --dry-run
    python production/gen_character_bodies.py --character nara --execute   (requiert validation)
    python production/gen_character_bodies.py --execute                    (tous — 75 images)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHARACTERS_FILE = ROOT / "production/characters.json"
OUT_BASE = ROOT / "production/character_bodies"
MODEL = "bytedance/seedream-4.5"
COST_PER_IMAGE_USD = 0.04

# ---------------------------------------------------------------------------
# Setup lumière et caméra communs pour le corpus corps
# ---------------------------------------------------------------------------
# Les portraits sont définis avec des lumières cinématographiques motivées
# (pratique, directionnelle). Pour le corpus corps, on utilise une lumière
# de référence contrôlée — mais sans les termes "studio white background"
# qui produisent une esthétique AI générique.
# ---------------------------------------------------------------------------

_BODY_CAMERA = (
    "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.2, ISO 800. "
    "Camera at eye level of the character. Full frame."
)

_BODY_LIGHTING = (
    "Production reference lighting: large 6×6 diffused HMI as key from 45 degrees camera-left, "
    "soft negative fill on the right, subtle hair separation from a 650W fresnel behind. "
    "4:1 key-to-fill ratio. Slight shadow underfoot. "
    "Background: pure seamless mid-light-grey cyclorama, evenly lit, no hotspot."
)

_BODY_PHOTOG_NOTES = (
    "On-set costume and anatomy reference photography for production design. "
    "Shot on set with production lighting rig. Not a composite. "
    "Film grain at box speed. No retouching. Fabric texture preserved — weave, wear, stitching visible. "
    "Full-body visible head to toe with 8% clearance on all sides. "
    "Anatomical accuracy: proportions, weight distribution, and joint positions physically plausible."
)

# ---------------------------------------------------------------------------
# BLOC 1 — TURNAROUND CORPS (posture debout neutre, 8 angles)
# ---------------------------------------------------------------------------
# Posture de référence : debout, décontracté mais présent.
# Légèrement différent de l'A-pose pure — plus naturel, moins mécanique.
# Bras tombant naturellement le long du corps, mains détendues.
# ---------------------------------------------------------------------------

BODY_ANGLES: list[dict[str, Any]] = [
    {
        "label": "front",
        "prefix": "turn",
        "idx": 0,
        "rotation": "Character facing camera directly — 0 degrees rotation.",
        "stance": (
            "Neutral standing: weight distributed equally on both feet, hip-width stance. "
            "Arms hanging naturally at sides, hands relaxed open. "
            "Head level, gaze directed at lens."
        ),
    },
    {
        "label": "front_three_quarter_left",
        "prefix": "turn",
        "idx": 1,
        "rotation": "Character rotated 45 degrees to character's right — three-quarter front-left.",
        "stance": (
            "Neutral standing: weight distributed equally on both feet, hip-width stance. "
            "Arms hanging naturally at sides. Head follows body axis — "
            "not turned back to camera."
        ),
    },
    {
        "label": "profile_left",
        "prefix": "turn",
        "idx": 2,
        "rotation": "Character rotated 90 degrees — strict left profile to camera.",
        "stance": (
            "Neutral standing: weight distributed equally, shoulder over hip over ankle alignment. "
            "Arms at sides. Head in profile, nose pointing camera-right."
        ),
    },
    {
        "label": "back_three_quarter_left",
        "prefix": "turn",
        "idx": 3,
        "rotation": "Character rotated 135 degrees — three-quarter back-left, back mostly visible.",
        "stance": (
            "Neutral standing. Arms at sides. "
            "Head follows body axis, not turned to camera."
        ),
    },
    {
        "label": "back",
        "prefix": "turn",
        "idx": 4,
        "rotation": "Character facing directly away from camera — 180 degrees rotation.",
        "stance": (
            "Neutral standing. Arms at sides. "
            "Head level, looking away. Back, shoulders, and rear silhouette fully visible."
        ),
    },
    {
        "label": "back_three_quarter_right",
        "prefix": "turn",
        "idx": 5,
        "rotation": "Character rotated 225 degrees — three-quarter back-right.",
        "stance": (
            "Neutral standing. Arms at sides. "
            "Head follows body axis, not turned to camera."
        ),
    },
    {
        "label": "profile_right",
        "prefix": "turn",
        "idx": 6,
        "rotation": "Character rotated 270 degrees — strict right profile to camera.",
        "stance": (
            "Neutral standing: weight distributed equally, shoulder over hip over ankle. "
            "Arms at sides. Head in profile, nose pointing camera-left."
        ),
    },
    {
        "label": "front_three_quarter_right",
        "prefix": "turn",
        "idx": 7,
        "rotation": "Character rotated 315 degrees — three-quarter front-right.",
        "stance": (
            "Neutral standing. Arms at sides. "
            "Head follows body axis — not turned back to camera."
        ),
    },
]

# ---------------------------------------------------------------------------
# BLOC 2 — POSTURES CLÉS (vue 3/4 canonique, éclairage production)
# ---------------------------------------------------------------------------
# Chaque posture est décrite avec précision anatomique :
# — axe du bassin et des épaules, distribution du poids,
# — position des membres, tension musculaire visible.
# Le contexte narratif sert à ancrer l'intention corporelle.
# ---------------------------------------------------------------------------

BODY_POSTURES: list[dict[str, Any]] = [
    {
        "label": "idle_weight_shift",
        "prefix": "pose",
        "idx": 0,
        "rotation": "Three-quarter front view, character rotated 30 degrees to camera's left.",
        "posture": (
            "Standing at rest with weight transferred onto right leg: right hip elevated 3cm, "
            "left leg extended with heel on floor, left knee soft. "
            "Pelvis tilted 8 degrees right. Shoulders compensate with left shoulder fractionally higher. "
            "Arms hang loosely — left arm slightly forward, right arm back. "
            "The body of someone waiting with habitual patience."
        ),
    },
    {
        "label": "alert_forward_lean",
        "prefix": "pose",
        "idx": 1,
        "rotation": "Three-quarter front view, character rotated 20 degrees to camera's right.",
        "posture": (
            "Standing with a forward lean of 12 degrees from vertical: "
            "weight shifted onto the balls of both feet, heels fractionally raised. "
            "Pelvis neutral, spine elongated, shoulders pulled back and down. "
            "Arms slightly forward and away from body — hands at hip level, ready. "
            "Neck extended forward of sternum — the preparedness lean."
        ),
    },
    {
        "label": "tactical_crouch",
        "prefix": "pose",
        "idx": 2,
        "rotation": "Three-quarter front-left view, character rotated 40 degrees.",
        "posture": (
            "Low tactical crouch: knees bent at approximately 110 degrees, "
            "hips dropped to mid-thigh level of a standing position. "
            "Weight on both feet, balls of feet carrying most load. "
            "Torso angled 25 degrees forward from vertical. "
            "Right arm raised — hand at chest level, bracing. "
            "Left arm extended for balance. Head elevated above torso, eyes forward."
        ),
    },
    {
        "label": "walking_mid_stride",
        "prefix": "pose",
        "idx": 3,
        "rotation": "Three-quarter front-left view, character walking toward camera at oblique angle.",
        "posture": (
            "Mid-stride walking: right leg extended forward, heel-strike contact, "
            "left leg behind with toe-off push. Pelvis rotated 10 degrees right (walking rotation). "
            "Opposite shoulder rotation: right shoulder back, left shoulder forward. "
            "Arms in natural walking swing — opposite to leg. "
            "The specific gait consistent with the character's build and habitual tension."
        ),
    },
    {
        "label": "seated_contained",
        "prefix": "pose",
        "idx": 4,
        "rotation": "Three-quarter front view, 30 degrees from camera.",
        "posture": (
            "Seated on the edge of a surface (not sinking into it — readiness retained). "
            "Feet flat on floor, knees at 90 degrees, thighs parallel to ground. "
            "Spine upright with a natural lumbar curve — not slumped. "
            "Forearms resting on thighs, hands hanging or loosely clasped. "
            "Shoulders relaxed but not collapsed. The controlled rest of someone who stays ready."
        ),
    },
    {
        "label": "turning_mid_rotation",
        "prefix": "pose",
        "idx": 5,
        "rotation": "Camera catches character mid-turn — torso facing 60 degrees off-camera, head turned back to lens.",
        "posture": (
            "Mid-turn: lower body rotated away from camera (hips at 60 degrees), "
            "upper body counter-rotated (torso at 30 degrees), head turned fully back to camera at 0 degrees. "
            "Strong spinal twist at thoracic level. "
            "Weight on the foot in the direction of travel. "
            "Arms follow the turn — one forward, one trailing."
        ),
    },
    {
        "label": "under_load_carrying",
        "prefix": "pose",
        "idx": 6,
        "rotation": "Three-quarter front view, camera slightly below character's eye level.",
        "posture": (
            "Standing under load: spine compressed slightly — a reduction of natural height. "
            "Shoulders rounded forward under weight. "
            "Neck pushed forward of its neutral position over the sternum. "
            "Feet planted wider than hip-width for stability. "
            "Arms positioned as if carrying or bracing a load — tension visible in trapezius and deltoid. "
            "The body bearing something heavy, physical or otherwise."
        ),
    },
]


# ---------------------------------------------------------------------------
# Helpers de construction de prompt
# ---------------------------------------------------------------------------

def _build_turn_prompt(character: dict[str, Any], angle: dict[str, Any]) -> str:
    return (
        f"{character['canonical']} "
        f"{angle['rotation']} "
        f"{angle['stance']} "
        f"Camera: {_BODY_CAMERA}. "
        f"Lighting: {_BODY_LIGHTING}. "
        f"{_BODY_PHOTOG_NOTES}"
    )


def _build_posture_prompt(character: dict[str, Any], pose: dict[str, Any]) -> str:
    return (
        f"{character['canonical']} "
        f"{pose['rotation']} "
        f"Posture: {pose['posture']} "
        f"Camera: {_BODY_CAMERA}. "
        f"Lighting: {_BODY_LIGHTING}. "
        f"{_BODY_PHOTOG_NOTES}"
    )


def _load_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _seed_for(character: dict[str, Any], offset: int) -> int:
    base: int = character.get("validated_seed") or _parse_portrait_seed(character)
    return base * 1000 + offset


def _parse_portrait_seed(character: dict[str, Any]) -> int:
    note: str = character.get("note", "")
    for token in note.split():
        if token.isdigit():
            return int(token)
    return 42


def _generate_one(
    slug: str,
    character: dict[str, Any],
    item: dict[str, Any],
    prompt: str,
    seed_offset: int,
    execute: bool,
) -> str | None:
    out_dir = OUT_BASE / slug
    filename = f"{item['prefix']}_{item['idx']:02d}_{item['label']}.png"
    out_path = out_dir / filename

    print(f"  [{item['prefix'].upper()} {item['idx']:02d}] {item['label']} → {filename}")

    if not execute:
        print(f"       DRY-RUN : aucun appel API")
        return None

    if out_path.exists():
        print(f"       SKIP : fichier existe déjà")
        return str(out_path)

    import replicate

    seed = _seed_for(character, seed_offset)
    print(f"       Appel Seedream 4.5 (seed={seed})…")
    t0 = time.monotonic()
    last_exc: Exception | None = None

    for attempt in range(1, 6):
        try:
            output = replicate.run(
                MODEL,
                input={
                    "prompt": prompt,
                    "size": "2K",
                    "aspect_ratio": "2:3",
                    "sequential_image_generation": "disabled",
                },
            )
            break
        except Exception as exc:
            last_exc = exc
            wait = 20 * attempt
            print(f"       [WARN] tentative {attempt}/5 échouée : {exc}")
            time.sleep(wait)
    else:
        raise RuntimeError("Seedream 4.5 — 5 tentatives échouées") from last_exc

    elapsed = time.monotonic() - t0
    url = str(output[0]) if isinstance(output, list) else str(output)
    print(f"       {elapsed:.1f}s — URL: {url[:60]}…")

    out_dir.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as resp:
        out_path.write_bytes(resp.read())
    print(f"       Sauvegardé : {out_path}")
    return str(out_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Génère le corpus de référence CORPS — turnaround et postures."
    )
    parser.add_argument("--character", help="Clé personnage (ex: nara). Tous si omis.")
    parser.add_argument(
        "--block",
        choices=["turnaround", "postures", "all"],
        default="all",
        help="Bloc à générer : turnaround | postures | all (défaut: all).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Déclenche les appels API (payants). Sans ce flag : dry-run.",
    )
    parser.add_argument("--allow-cloud", action="store_true", help="Allow legacy paid cloud generation.")
    args = parser.parse_args()

    _load_env()

    characters: dict[str, Any] = json.loads(CHARACTERS_FILE.read_text(encoding="utf-8"))
    if args.character:
        if args.character not in characters:
            print(
                f"ERROR: personnage '{args.character}' inconnu. "
                f"Valides : {list(characters)}",
                file=sys.stderr,
            )
            return 1
        selection = {args.character: characters[args.character]}
    else:
        selection = characters

    run_turn = args.block in ("turnaround", "all")
    run_poses = args.block in ("postures", "all")

    items_per_char = (len(BODY_ANGLES) if run_turn else 0) + (len(BODY_POSTURES) if run_poses else 0)
    total_images = len(selection) * items_per_char
    total_cost = total_images * COST_PER_IMAGE_USD

    print("=" * 64)
    print("gen_character_bodies.py — Corpus référence CORPS")
    print("=" * 64)
    print(f"  Personnages     : {list(selection.keys())}")
    print(f"  Bloc            : {args.block}")
    if run_turn:
        print(f"  Angles turnaround : {len(BODY_ANGLES)}")
    if run_poses:
        print(f"  Postures clés   : {len(BODY_POSTURES)}")
    print(f"  Total images    : {total_images}")
    print(f"  Coût estimé     : ${total_cost:.2f}")
    print(f"  Mode            : {'EXECUTE' if args.execute else 'DRY-RUN'}")
    print()

    if args.execute and not args.allow_cloud:
        print("Cloud generation blocked. Add --allow-cloud to acknowledge Replicate spend.", file=sys.stderr)
        return 1

    if args.execute and not os.environ.get("REPLICATE_API_TOKEN"):
        print("ERROR: REPLICATE_API_TOKEN manquant dans .env", file=sys.stderr)
        return 1

    generated = 0
    for slug, character in selection.items():
        print(f"── {slug} ({character['full_name']}) ──")

        if run_turn:
            print(f"  [BLOC TURNAROUND]")
            for angle in BODY_ANGLES:
                prompt = _build_turn_prompt(character, angle)
                result = _generate_one(slug, character, angle, prompt, angle["idx"], execute=args.execute)
                if result:
                    generated += 1

        if run_poses:
            print(f"  [BLOC POSTURES]")
            for pose in BODY_POSTURES:
                prompt = _build_posture_prompt(character, pose)
                result = _generate_one(
                    slug, character, pose, prompt,
                    200 + pose["idx"],
                    execute=args.execute,
                )
                if result:
                    generated += 1

        print()

    print("=" * 64)
    if args.execute:
        print(f"  Terminé : {generated}/{total_images} images générées")
        print(f"  Coût réel estimé : ${generated * COST_PER_IMAGE_USD:.2f}")
    else:
        print(f"  DRY-RUN terminé.")
        print(f"  → Passer --execute pour générer.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
