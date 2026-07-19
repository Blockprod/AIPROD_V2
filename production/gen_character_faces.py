"""
production/gen_character_faces.py
====================================
Corpus de référence VISAGE — bloc indépendant du corpus corps.

Objectif : couvrir exhaustivement les angles de visage, expressions et
micro-expressions pour chaque personnage, avec un niveau de réalisme
indiscernable d'une production humaine.

Stratégie de prompting :
  - Utilise le portrait_brief validé par personnage (caméra, optique,
    lumière, fond, référence DOP) comme socle de chaque prompt
  - Aucune formule générique "AI art" (photorealistic, hyperdetailed…)
  - Terminologie photographique/cinématographique réelle
  - Ratio et motivation lumière explicites
  - Référence équipement (corps caméra, focale, ISO, senseur)

Deux blocs indépendants :
  ANGLES  — 7 directions × expression neutre
  EXPRESSIONS — 14 variantes × vue 3/4 face (angle canonique du portrait)

Total par personnage : 7 + 14 = 21 images
Total 5 personnages  : 105 images
Coût estimé Seedream 4.5 : ~105 × $0.04 = ~$4.20

Outputs :
  production/character_faces/{slug}/angle_{N:02d}_{label}.png
  production/character_faces/{slug}/expr_{N:02d}_{label}.png

Usage :
    python production/gen_character_faces.py --dry-run
    python production/gen_character_faces.py --character nara --dry-run
    python production/gen_character_faces.py --character nara --block angles --dry-run
    python production/gen_character_faces.py --character nara --execute   (requiert validation)
    python production/gen_character_faces.py --execute                    (tous — 105 images)
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
OUT_BASE = ROOT / "production/character_faces"
MODEL = "bytedance/seedream-4.5"
COST_PER_IMAGE_USD = 0.04

# ---------------------------------------------------------------------------
# BLOC 1 — ANGLES DE VISAGE (expression neutre dans tous les cas)
# ---------------------------------------------------------------------------
# Le framing est relatif à l'axe de la caméra.
# On précise l'angle de rotation de la tête en degrés (0 = face caméra).
# ---------------------------------------------------------------------------

FACE_ANGLES: list[dict[str, Any]] = [
    {
        "label": "front_neutral",
        "prefix": "angle",
        "idx": 0,
        "head_rotation": "facing camera directly, head perfectly centred",
        "gaze": "direct eye contact with lens, neutral alert expression",
        "framing_override": (
            "Tight portrait — from clavicles to just above the crown. "
            "Head centred at 60% of frame height. "
            "Shoulders square or slightly turned."
        ),
    },
    {
        "label": "three_quarter_left",
        "prefix": "angle",
        "idx": 1,
        "head_rotation": "head turned 40 degrees to character's right — three-quarter left view",
        "gaze": "gaze directed slightly off-lens at 35 degrees",
        "framing_override": None,  # use portrait_brief framing
    },
    {
        "label": "profile_left",
        "prefix": "angle",
        "idx": 2,
        "head_rotation": (
            "Strict LEFT profile — the character's LEFT side faces the camera. "
            "The LEFT ear is fully visible and closest to camera. "
            "The RIGHT half of the face is completely hidden behind the head. "
            "Only the LEFT eye is visible in profile. "
            "The nose points toward camera-RIGHT. "
            "Head turned exactly 90 degrees — no cheek of the opposite side visible."
        ),
        "gaze": "eyes looking straight ahead to camera-right along the profile axis",
        "framing_override": (
            "Tight portrait — face centred in frame, chin to crown visible. "
            "Camera at eye level, perfectly orthographic to the face plane."
        ),
    },
    {
        "label": "three_quarter_right",
        "prefix": "angle",
        "idx": 3,
        "head_rotation": "head turned 40 degrees to character's left — three-quarter right view",
        "gaze": "gaze directed slightly off-lens at 35 degrees to character's right",
        "framing_override": None,
    },
    {
        "label": "profile_right",
        "prefix": "angle",
        "idx": 4,
        "head_rotation": (
            "Strict RIGHT profile — the character's RIGHT side faces the camera. "
            "The RIGHT ear is fully visible and closest to camera. "
            "The LEFT half of the face is completely hidden behind the head. "
            "Only the RIGHT eye is visible in profile. "
            "The nose points toward camera-LEFT. "
            "Head turned exactly 90 degrees — no cheek of the opposite side visible."
        ),
        "gaze": "eyes looking straight ahead to camera-left along the profile axis",
        "framing_override": (
            "Tight portrait — face centred in frame, chin to crown visible. "
            "Camera at eye level, perfectly orthographic to the face plane."
        ),
    },
    {
        "label": "tilt_up_15",
        "prefix": "angle",
        "idx": 5,
        "head_rotation": "head tilted 15 degrees upward — slight upward gaze, chin elevated",
        "gaze": "eyes looking slightly upward, relaxed neutral expression",
        "framing_override": None,
    },
    {
        "label": "tilt_down_15",
        "prefix": "angle",
        "idx": 6,
        "head_rotation": "head tilted 15 degrees downward — chin slightly dropped, looking slightly down at camera",
        "gaze": "eyes looking slightly downward through brows, contained expression",
        "framing_override": None,
    },
]

# ---------------------------------------------------------------------------
# BLOC 2 — EXPRESSIONS (angle canonique du portrait validé = 3/4 face)
# ---------------------------------------------------------------------------
# Chaque entrée décrit l'état expressif avec le vocabulaire d'un directeur
# d'acteurs ou d'un photographe de plateau — jamais de formules génériques.
# ---------------------------------------------------------------------------

EXPRESSIONS: list[dict[str, Any]] = [
    {
        "label": "neutral_rest",
        "prefix": "expr",
        "idx": 0,
        "expression": (
            "Complete muscular rest — orbicularis oculi fully relaxed, zygomaticus released, "
            "jaw slightly open (2mm), lips parted at neutral position. "
            "The face before any reaction. Baseline state."
        ),
    },
    {
        "label": "alert_watchful",
        "prefix": "expr",
        "idx": 1,
        "expression": (
            "High alertness without panic — levator palpebrae raised, pupils dilated, "
            "brows in slight neutral raise, jaw clenched imperceptibly. "
            "The face of someone who has heard something they cannot yet identify. "
            "No exaggeration. Tension lives in the eyes only."
        ),
    },
    {
        "label": "intent_focus",
        "prefix": "expr",
        "idx": 2,
        "expression": (
            "Deep concentration — corrugator supercilii draws brows inward and slightly down, "
            "creating vertical furrows. Eyes narrowed 20% — not squinting, filtering. "
            "Lips compressed gently. The face of someone solving a problem under constraint."
        ),
    },
    {
        "label": "contained_fear",
        "prefix": "expr",
        "idx": 3,
        "expression": (
            "Fear suppressed by will — frontalis raises brows asymmetrically (one more than the other), "
            "upper eyelids elevated, whites of eyes visible above iris. "
            "Jaw held firmly against trembling. Lips pressed together — the seam white. "
            "A person who is frightened and cannot afford to show it."
        ),
    },
    {
        "label": "pain_contained",
        "prefix": "expr",
        "idx": 4,
        "expression": (
            "Physical or emotional pain controlled — corrugator pulls brows hard toward midline, "
            "creating sharp nasolabial compression. Orbicularis oculi squeezes upper eyelids. "
            "Lips drawn back and pressed together. A silent wince mid-recovery."
        ),
    },
    {
        "label": "contempt_cold",
        "prefix": "expr",
        "idx": 5,
        "expression": (
            "Contempt — unilateral lip corner pull (left side only) upward and inward: "
            "zygomaticus minor asymmetric activation, the precise muscular signature of contempt. "
            "Eyes steady and flat. Brows unmoved. The face of someone who has already decided."
        ),
    },
    {
        "label": "determination_jaw",
        "prefix": "expr",
        "idx": 6,
        "expression": (
            "Determination with no room for doubt — masseter visibly contracted (jaw set), "
            "mentalis slightly raised (chin skin textured), lips pressed into a flat line. "
            "Eyes forward, brows horizontal. The face of a decision that has been made."
        ),
    },
    {
        "label": "grief_suppressed",
        "prefix": "expr",
        "idx": 7,
        "expression": (
            "Grief being held back — corrugator supercilii and depressor supercilii both active, "
            "creating oblique inner-brow raising (the grief marker). "
            "Orbicularis oculi compresses lower lids. Lip corners pulled down by depressor anguli oris. "
            "On the edge of breaking — still holding."
        ),
    },
    {
        "label": "surprise_flash",
        "prefix": "expr",
        "idx": 8,
        "expression": (
            "Brief involuntary surprise — frontalis fully raised, brows high and arched symmetrically, "
            "upper eyelids at maximum raise, jaw dropped (10–15mm), "
            "lips in rounded open position. The first 200 milliseconds of surprise. "
            "Not theatrical — caught by the lens."
        ),
    },
    {
        "label": "exhaustion_deep",
        "prefix": "expr",
        "idx": 9,
        "expression": (
            "Deep exhaustion after sustained effort — ptosis of upper eyelids (partial drop), "
            "levator palpebrae partially released. Dark under-eye shadows deepened. "
            "Nasolabial folds more pronounced. Lips parted slightly, no muscle tone. "
            "The face after 72 hours without sleep."
        ),
    },
    {
        "label": "anger_suppressed",
        "prefix": "expr",
        "idx": 10,
        "expression": (
            "Anger being contained — corrugator drives brows hard down and inward, "
            "creating sharp vertical glabellar lines. Upper lip retracted slightly "
            "(levator labii superioris), nostrils flared (dilator naris). "
            "The rage of someone who cannot act on it yet."
        ),
    },
    {
        "label": "calculation_cold",
        "prefix": "expr",
        "idx": 11,
        "expression": (
            "Cold calculation — the face of someone running through options. "
            "Slight asymmetric brow compression (one brow fractionally lower), "
            "eyes in focused lateral micro-movement (thinking gaze), "
            "lips in neutral closed position. Minimal surface affect, maximum internal activity."
        ),
    },
    {
        "label": "distrust_guarded",
        "prefix": "expr",
        "idx": 12,
        "expression": (
            "Distrust and guarded assessment — orbicularis oculi narrows both eyes moderately, "
            "brows drawn fractionally in and down, asymmetric (slightly more on one side). "
            "Head position: fractionally turned away from camera (10 degrees), "
            "eyes returning to lens — the instinct to look away and the decision not to."
        ),
    },
    {
        "label": "relief_flash",
        "prefix": "expr",
        "idx": 13,
        "expression": (
            "The first instant of relief — levator labii superioris zygomaticus activates fractionally "
            "(not a smile — the ghost of one), brows relax from their held tension downward, "
            "orbicularis oculi softens, upper eyelids drop slightly with released tension. "
            "The moment after danger has passed. Lasts three seconds."
        ),
    },
]


# ---------------------------------------------------------------------------
# Helpers de construction de prompt
# ---------------------------------------------------------------------------

def _build_face_angle_prompt(
    character: dict[str, Any], angle: dict[str, Any], with_ref: bool = False
) -> str:
    pb = character.get("portrait_brief", {})
    camera = pb.get("camera", "ARRI Alexa 35, anamorphic lens, ISO 1600")
    lighting = pb.get("lighting", "")
    background = pb.get("background", "dark seamless background, shallow depth")
    dop_ref = pb.get("dop_ref", "")
    framing = angle.get("framing_override") or pb.get("framing", "tight portrait, head to shoulders")
    ref_note = (
        "Maintain exact facial identity from reference: identical bone structure, "
        "eye shape, nose, lip line, skin texture, and all distinctive features. "
        "Same person, different angle only. "
    ) if with_ref else ""

    return (
        f"{character['canonical']} "
        f"{ref_note}"
        f"VIEW: {angle['label'].upper().replace('_', ' ')}. "
        f"{angle['head_rotation']}. "
        f"CRITICAL: the head rotation described above must be strictly respected — "
        f"this is NOT the front view. "
        f"{angle['gaze']}. "
        f"Neutral expression — no performance, baseline muscular state. "
        f"Framing: {framing}. "
        f"Camera: {camera}. "
        f"Lighting: {lighting}. "
        f"Background: {background}. "
        f"On-set production still photography. "
        f"Film grain present and natural. Skin texture unretouched: visible pores, "
        f"subcutaneous texture, natural asymmetry preserved. "
        f"No compositing. No post-production smoothing. "
        f"Reference: {dop_ref}."
    )


def _build_expression_prompt(
    character: dict[str, Any], expr: dict[str, Any], with_ref: bool = False
) -> str:
    pb = character.get("portrait_brief", {})
    camera = pb.get("camera", "ARRI Alexa 35, anamorphic lens, ISO 1600")
    lighting = pb.get("lighting", "")
    background = pb.get("background", "dark seamless background, shallow depth")
    dop_ref = pb.get("dop_ref", "")
    framing = pb.get("framing", "tight portrait, face sharp from hairline to chin")
    ref_note = (
        "Maintain exact facial identity from reference: identical bone structure, "
        "eye shape, nose, lip line, skin texture, and all distinctive features. "
        "Same person, different expression only. "
    ) if with_ref else ""

    return (
        f"{character['canonical']} "
        f"{ref_note}"
        f"Expression: {expr['expression']} "
        f"Framing: {framing}. "
        f"Camera: {camera}. "
        f"Lighting: {lighting}. "
        f"Background: {background}. "
        f"On-set production still photography. "
        f"Film grain present and natural. Skin texture unretouched: visible pores, "
        f"subcutaneous texture, natural asymmetry preserved. "
        f"No compositing. No post-production smoothing. "
        f"Reference: {dop_ref}."
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
    execute: bool,
    ref_image_path: str | None = None,
) -> str | None:
    out_dir = OUT_BASE / slug
    filename = f"{item['prefix']}_{item['idx']:02d}_{item['label']}.png"
    out_path = out_dir / filename

    ref_marker = " [REF]" if ref_image_path else ""
    print(f"  [{item['prefix'].upper()} {item['idx']:02d}] {item['label']}{ref_marker} → {filename}")

    if not execute:
        print(f"       DRY-RUN : aucun appel API")
        return None

    if out_path.exists():
        print(f"       SKIP : fichier existe déjà")
        return str(out_path)

    import replicate

    api_input: dict[str, Any] = {
        "prompt": prompt,
        "size": "2K",
        "aspect_ratio": "2:3",
        "sequential_image_generation": "disabled",
    }
    if ref_image_path and Path(ref_image_path).exists():
        api_input["image_input"] = [open(ref_image_path, "rb")]
        print(f"       image_input : {Path(ref_image_path).name}")

    print(f"       Appel Seedream 4.5…")
    t0 = time.monotonic()
    last_exc: Exception | None = None

    for attempt in range(1, 6):
        try:
            output = replicate.run(MODEL, input=api_input)
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
        description="Génère le corpus de référence VISAGE — angles et expressions."
    )
    parser.add_argument("--character", help="Clé personnage (ex: nara). Tous si omis.")
    parser.add_argument(
        "--block",
        choices=["angles", "expressions", "all"],
        default="all",
        help="Bloc à générer : angles | expressions | all (défaut: all).",
    )
    parser.add_argument(
        "--only",
        help="Label exact d'un seul item à générer (ex: front_neutral, alert_watchful).",
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

    run_angles = args.block in ("angles", "all")
    run_expressions = args.block in ("expressions", "all")

    active_angles = [a for a in FACE_ANGLES if not args.only or a["label"] == args.only] if run_angles else []
    active_expressions = [e for e in EXPRESSIONS if not args.only or e["label"] == args.only] if run_expressions else []

    if args.only and not active_angles and not active_expressions:
        valid = [a["label"] for a in FACE_ANGLES] + [e["label"] for e in EXPRESSIONS]
        print(f"ERROR: label '{args.only}' inconnu. Valides :\n  " + "\n  ".join(valid), file=sys.stderr)
        return 1

    items_per_char = len(active_angles) + len(active_expressions)
    total_images = len(selection) * items_per_char
    total_cost = total_images * COST_PER_IMAGE_USD

    print("=" * 64)
    print("gen_character_faces.py — Corpus référence VISAGE")
    print("=" * 64)
    print(f"  Personnages     : {list(selection.keys())}")
    print(f"  Bloc            : {args.block}")
    if args.only:
        print(f"  Filtre --only   : {args.only}")
    if active_angles:
        print(f"  Angles visage   : {len(active_angles)}")
    if active_expressions:
        print(f"  Expressions     : {len(active_expressions)}")
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

        # Référence visuelle : front_neutral sert d'ancre pour tous les autres items
        ref_path = str(OUT_BASE / slug / "angle_00_front_neutral.png")
        ref_exists = Path(ref_path).exists()

        if active_angles:
            print(f"  [BLOC ANGLES]")
            for angle in active_angles:
                use_ref = ref_exists and angle["label"] != "front_neutral"
                prompt = _build_face_angle_prompt(character, angle, with_ref=use_ref)
                result = _generate_one(
                    slug, character, angle, prompt,
                    execute=args.execute,
                    ref_image_path=ref_path if use_ref else None,
                )
                if result:
                    generated += 1
                    # Si on vient de générer front_neutral, activer la ref pour la suite
                    if angle["label"] == "front_neutral":
                        ref_exists = True

        if active_expressions:
            print(f"  [BLOC EXPRESSIONS]")
            for expr in active_expressions:
                # Pas d'image_input pour les expressions : image_input écrase l'expression
                # et reproduit la référence à l'identique. L'identité est portée par canonical.
                prompt = _build_expression_prompt(character, expr, with_ref=False)
                result = _generate_one(
                    slug, character, expr, prompt,
                    execute=args.execute,
                    ref_image_path=None,
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
