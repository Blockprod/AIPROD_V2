"""
production/gen_location_angles.py
===================================
Génère 3 angles de référence visuelle par lieu — méthode V4 (visual bible).

  WIDE   : establishing shot, vue d'ensemble architecturale
  MEDIUM : zone intermédiaire, détails lisibles
  DETAIL : close-up extrême, élément iconique du lieu

Paramètres :
  - FLUX.1.1 Pro Ultra, raw=True, 16:9, seed fixe par lieu
  - Zéro personnage dans le frame
  - Même seed pour les 3 angles d'un même lieu

COUT : 11 lieux × 3 angles × $0.06 = $1.98
Usage : python production/gen_location_angles.py [--loc int_transit_corridor_night] [--angle wide] [--dry-run]
"""
from __future__ import annotations
import argparse, json, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.shot_pipeline import _load_env

MODEL        = "black-forest-labs/flux-1.1-pro-ultra"
COST_PER_IMG = 0.06
ANGLES       = ("wide", "medium", "detail")


def _load_env_local() -> None:
    _load_env(ROOT)


# ---------------------------------------------------------------------------
# Sanitization du canonical — supprime toute mention de présence humaine
# pour éviter que FLUX génère des figures dans les refs lieux
# ---------------------------------------------------------------------------

_HUMAN_PATTERNS = [
    "workers", "figures", "citizens", "people", "person", "human", "crowd",
    "analyst", "analysts", "vale", "nara", "mira", "elian", "rook",
    "subject", "silhouette", "presence", "presences", "standing", "seated",
    "blurred distant", "moving in organised", "as background",
    " she ", " her ", "dwarfs her", " he ", " him ", " his ", "she is", "her —",
    "figure at", "figure in",
]


def _sanitize_canonical(canonical: str) -> str:
    """Supprime les phrases contenant des références à des présences humaines."""
    import re
    sentences = re.split(r'(?<=[.!?—])\s+', canonical)
    clean = []
    for s in sentences:
        lower = s.lower()
        if any(pat in lower for pat in _HUMAN_PATTERNS):
            continue
        clean.append(s)
    return " ".join(clean)


# ---------------------------------------------------------------------------
# Contrôle des 7 paramètres photographiques — dérivé depuis canonical + lighting_brief
# ---------------------------------------------------------------------------

def _material_block(loc: dict) -> str:
    """Matière dominante + texture précise, dérivés du canonical."""
    c = loc["canonical"].lower()
    if "rivet" in c or "steel" in c:
        return (
            "Dominant material: oxidised riveted steel — rust bloom radiating from each rivet head, "
            "surface pitting 1-3mm deep, dark iron oxide film with localised orange flaking, "
            "micro-scale surface roughness Ra 50-100µm."
        )
    if "concrete" in c and ("water-stain" in c or "stain" in c or "wet" in c):
        return (
            "Dominant material: wet poured concrete — calcium bloom streaking vertical from joints, "
            "water absorption darkening surface to 60% base value, micro-pitting and aggregate exposure, "
            "matte surface with zero specular at normal incidence."
        )
    if "concrete" in c:
        return (
            "Dominant material: aged poured concrete — grey aggregate visible, hairline cracks 0.5-1mm, "
            "surface carbonation whitening, matte finish with micro-texture Ra 20-40µm."
        )
    if "glass" in c or "window" in c:
        return (
            "Dominant material: industrial glass — surface micro-scratches, grime film reducing transmission "
            "to 70%, specular highlight sharp at 95% reflectivity at grazing angle."
        )
    return (
        "Dominant material: industrial composite surface — layered paint over steel substrate, "
        "paint peeling at stress points, bare metal exposed at wear zones, surface Ra 30-60µm."
    )


def _shadow_block(loc: dict) -> str:
    """Dureté et géométrie des ombres, dérivées de la source de lumière dominante."""
    l = loc["lighting_brief"].lower()
    if "single" in l or "18k" in l or "hmi" in l or "cage" in l:
        return (
            "Shadow quality: hard-edged, single dominant source — penumbra under 2mm at 1 metre distance. "
            "Shadow terminator follows surface geometry exactly. "
            "Deep shadow density at 2% IRE in unlit zones."
        )
    if "fluorescent" in l or "strip" in l or "led strip" in l:
        return (
            "Shadow quality: soft linear source — penumbra 15-25mm, shadow transitions gradual over 3cm. "
            "Multiple overlapping shadow planes from parallel tubes. "
            "Shadow density 8% IRE minimum — never pure black."
        )
    if "search" in l or "beam" in l or "sweeping" in l:
        return (
            "Shadow quality: moving directional source — shadow edges shift with beam. "
            "Hard penumbra 1mm during beam passage, returns to full black between sweeps. "
            "Beam edge creates knife-sharp shadow terminator on architectural surfaces."
        )
    return (
        "Shadow quality: motivated practical sources — shadow density proportional to distance from key. "
        "Shadow terminator follows surface normals. No ambient fill. Minimum shadow density 3% IRE."
    )


def _reflection_block(loc: dict) -> str:
    """Spécularité et reflets, dérivés des surfaces mentionnées dans le canonical."""
    c = loc["canonical"].lower()
    l = loc["lighting_brief"].lower()
    parts = []
    if "water" in c and ("black" in c or "churning" in c or "crashing" in c):
        parts.append(
            "Black water surface: sharp inverted mirror reflection of search beam — "
            "95% specular at normal incidence, reflection breaks into streaks on wave crests."
        )
    elif "puddle" in c or "wet floor" in c or ("floor" in c and "wet" in c):
        parts.append(
            "Wet floor specular: elongated point-source reflection streak — "
            "mirror-sharp at centre, feathering to 40% at edges, "
            "surface reflection reveals overhead structure."
        )
    if "rivet" in c or "steel" in c or "metal" in c:
        parts.append(
            "Metal surface specularity: dull diffuse highlight on oxide film — "
            "broad 15% reflectivity, highlight size 3-5cm, "
            "no mirror reflection, surface micro-facets scatter incident light."
        )
    if "glass" in c or "window" in c:
        parts.append(
            "Glass reflection: environment mirroring at 80% — "
            "visible inverted scene geometry in glazing, "
            "specular hotspot at key light angle."
        )
    if not parts:
        parts.append(
            "Surface specularity: matte industrial finish — diffuse reflection only, "
            "5% maximum reflectivity, no specular highlight."
        )
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Axe de prise de vue, intention d'exposition, bokeh anamorphique
# Dérivés depuis lighting_brief — une seule fonction pour les 3
# ---------------------------------------------------------------------------

def _optics_block(loc: dict) -> str:
    """
    Retourne 3 paramètres optiques DOP :
      - axe caméra/source (contre-jour / trois-quarts / frontal)
      - intention d'exposition (ombres ou hautes lumières)
      - bokeh anamorphique oval
    """
    l = loc["lighting_brief"].lower()

    # --- Axe caméra ---
    if "vanishing point" in l or "single" in l and "ahead" in l:
        # Source dans l'axe caméra — pur contre-jour
        axis = (
            "Camera shooting directly toward key light source — pure contre-jour. "
            "Subject architecture silhouetted against light. "
            "Hard backlight edge on all vertical surfaces."
        )
    elif "key from upper-left" in l or "key light from upper-left" in l or "upper-left" in l:
        # Source trois-quarts avant gauche
        axis = (
            "Camera shooting three-quarter angle, key light at 45 degrees camera-left. "
            "Lit side of architecture faces camera. Shadow side falls right."
        )
    elif "overhead" in l or "fluorescent" in l:
        # Source au-dessus — axe vertical, caméra horizontale
        axis = (
            "Camera shooting horizontally, light source directly overhead. "
            "Top surfaces fully lit, vertical surfaces in shadow. "
            "Strong shadow pools directly below structural elements."
        )
    elif "sweep" in l or "search" in l or "beam" in l:
        # Source balayante — contre-jour intermittent
        axis = (
            "Camera shooting into the sweep path of moving light beams — "
            "periodic contre-jour when beam crosses lens axis. "
            "Architecture silhouetted during beam passage, returns to black between sweeps."
        )
    else:
        axis = (
            "Camera shooting three-quarter angle to dominant light source. "
            "Lit and shadow planes both visible."
        )

    # --- Intention d'exposition ---
    if "no fill" in l or "ratio 15:1" in l or "ratio 9:1" in l or "ratio 8:1" in l:
        # Ratio élevé — exposer pour les lumières, écraser les ombres
        expose = (
            "Exposed for highlights — practical light sources at 70% IRE, "
            "shadow zones crushed to 2-4% IRE, no detail recovery in blacks."
        )
    elif "ratio 6:1" in l or "ratio 4:1" in l:
        expose = (
            "Exposed for midtones — key areas at 50% IRE, "
            "shadow detail retained at 15% IRE minimum."
        )
    else:
        expose = (
            "Exposed for shadow detail — key source at 85% IRE, "
            "shadow zones at 8-12% IRE, texture visible in darkest areas."
        )

    # --- Bokeh anamorphique ---
    bokeh = (
        "Out-of-focus light sources render as vertical oval ellipses — "
        "anamorphic bokeh, height 2× width. "
        "Bokeh edges soft with slight chromatic aberration fringe."
    )

    return f"{axis} {expose} {bokeh}"


# ---------------------------------------------------------------------------
# Profondeur atmosphérique (wide uniquement)
# ---------------------------------------------------------------------------

def _atmosphere_block(loc: dict) -> str:
    """Plans de profondeur distincts par désaturation et décalage chromatique."""
    c = loc["canonical"].lower()
    l = loc["lighting_brief"].lower()
    if "mist" in c or "haze" in c or "fog" in c or "steam" in c or "salt" in c:
        return (
            "Atmospheric depth layers: foreground 100% colour saturation and sharpness, "
            "mid-ground at 70% saturation with slight cool shift +10 blue, "
            "background at 40% saturation desaturated toward blue-grey, "
            "far background dissolving into salt haze at 20% saturation."
        )
    if "corridor" in c or "narrow" in c or "tunnel" in c:
        return (
            "Atmospheric depth: dense air — foreground fully sharp, "
            "mid-corridor at 85% saturation with slight amber scatter from practical, "
            "far end dissolving into warm haze at 50% saturation around vanishing light."
        )
    return (
        "Atmospheric depth: subtle aerial perspective — "
        "foreground fully sharp, background shifted +5 blue, "
        "distant elements at 80% saturation."
    )


# ---------------------------------------------------------------------------
# Précision photographique par lieu — 7 paramètres à l'échelle du wide master
# Lumière · Matière · Texture · Ombres · Reflets · Profondeur de champ · Grain
# ---------------------------------------------------------------------------

_PRECISION_MASTER: dict[str, str] = {
    "ext_outer_wall_night": (
        "Light: HMI 18K search beams 5600K — hard-edged volumetric shafts visible in salt mist, no fill, ratio 15:1. "
        "Material: calcium-bloom concrete wall, tide-stain at 8m height, rust-bleed streaks from rebar. "
        "Water: black mirror surface broken into white foam at crests, 95% specular on flat sections. "
        "Shadows: 2% IRE in unlit wall zones, no recovery. "
        "Focus: wall surface sharp at 8m, tower background progressively soft."
    ),
    "int_transit_corridor_night": (
        "Light: single cage tungsten 2850K at vanishing point 30m — circular warm halo, sharp falloff to shadow, ratio 8:1. "
        "Material: riveted steel walls — rust bloom pattern visible at corridor scale, wet concrete floor. "
        "Puddle: elongated lamp reflection streak, mirror-sharp centre. "
        "Steam jet mid-corridor: white horizontal plume catching backlight. "
        "Shadows: full black beyond 5m from lamp. Focus: corridor floor sharp, walls sharp, lamp in slight bokeh."
    ),
    "int_pressure_valve_chamber_night": (
        "Light: alarm strobe 5600K white — hard shadows snap across manifolds at each flash, ratio 12:1. "
        "Base: green-white fluorescent 5000K at 15% between flashes. "
        "Material: cast iron manifolds — grey oxide surface, flange bolts in arrays. "
        "Steam jet: white horizontal plume at 2m height backlit by fluorescent. "
        "Shadows: multiple overlapping planes from strobe. Scale: ceiling lost at 15m in darkness."
    ),
    "int_voss_apartment_night": (
        "Light: practical wire-hung lamp 2700K — amber cone falls on central table, radius 80cm, ratio 6:1. "
        "Counter: cold exterior neon 4500K through condensation-fogged window at frame-left — teal-blue separation on far wall, 2% intensity. "
        "Two temperatures never mixing. Material: peeling paint over concrete — curl shadows, salvaged plank shelving dense with folded papers. "
        "Table: central focal point, scarred wood surface, clear and lit. "
        "Shadows: 65% of frame at 2-4% IRE. "
        "Texture: worn linoleum floor, cloth lamp shade translucency. Focus: table and lamp zone sharp."
    ),
    "int_civic_atrium_morning": (
        "Light: diffused overcast 6000K through glass ceiling — flat even overhead, marble bounce from below, ratio 3:1. "
        "Material: polished white marble — reflection of ceiling geometry visible, slight yellow warmth in stone. "
        "Scale: 80m across — figures at ground scale imply authority by proportion. "
        "Shadows: soft-edged, 15% IRE minimum, no hard shadow anywhere. "
        "Focus: marble floor foreground sharp, far wall soft. Glass ceiling structure visible above."
    ),
    "int_black_market_sublevel_day": (
        "Light: amber LED uplighting 2000K from below stalls — upward shadows on cable bundles. "
        "Cyan neon left, amber neon right — colour clash at 2m height. "
        "Grey daylight shafts 6000K from ventilation grilles above — narrow, dust-visible, ratio 7:1. "
        "Material: bare concrete walls, moisture seep stains. Server rack stalls: steel and oxidised plastic. "
        "Focus: stall foreground sharp, background dense and layered."
    ),
    "int_security_ops_center_day": (
        "Light: 12 screens cyan-blue 6500K — washing analyst faces from front. "
        "Overhead at 10% — near-zero ceiling fill. Cold grey window backlight providing rim separation. "
        "Vale: near-silhouette, cold edge light on shoulder only, ratio 9:1. "
        "Material: dark glass screens — cyan UI glow reflected in screen surfaces. "
        "Focus: analysts in mid-ground sharp, Vale at edge in slight compression."
    ),
    "int_service_spine_night": (
        "Light: floor-level emergency strips green 4000K right wall — extreme low angle, long horizontal shadows. "
        "Control panel amber OLED 2700K — only warm source, mid-distance. Fog: micro-particles scattering strips. "
        "Material: wooden plank walls, mineral deposits on horizontal steel crossbeams. "
        "Track rails: dust-covered, catching strip light at grazing angle. "
        "Focus: floor and near wall sharp, tracks receding to fog at 8m. Ceiling: absolute black."
    ),
    "int_observation_chamber": (
        "Light: red alarm ceiling strip 2700K — 360-degree wall wash, warm red on all interior surfaces. "
        "Through shutters: cold grey-blue exterior 7000K — growing stronger as shutters open, ratio 8:1. "
        "Material: corroded copper piping — verdigris bloom, green-turquoise oxidation. Hydraulic cylinders: grey oxide. "
        "Steel shutters: 30cm slats, motorised — threshold between two worlds. "
        "Focus: shutter threshold sharp, machinery foreground sharp, exterior depth soft."
    ),
    "int_voss_apartment_predawn": (
        "Light: cold pre-dawn blue 4500K through small window — single thin horizontal bar across floor. "
        "No other source. All surfaces above bar in near-absolute darkness, ratio 15:1. "
        "Material: objects as shapes only — no surface detail in shadow, form-light only at bar threshold. "
        "Door at frame-right: door gap underlighting from corridor — thin warm line. "
        "Focus: bar of light on floor sharp, all else in darkness. Zero fill."
    ),
}

_PRECISION_MASTER_FALLBACK = (
    "Light: motivated practical sources only, no ambient fill. "
    "Material: industrial surfaces — aged, worn, specific. "
    "Shadows: ratio proportional to scene intent. Focus: foreground sharp, background in context."
)


def _precision_master(loc_key: str) -> str:
    """Bloc de précision photographique 7-paramètres à l'échelle du wide master."""
    return _PRECISION_MASTER.get(loc_key, _PRECISION_MASTER_FALLBACK)


# ---------------------------------------------------------------------------
#
# Principe clé : image_prompt (Redux) porte la scène, la palette, l'atmosphère.
# Le texte ouvre sur le narrative_beat (intention dramatique du script),
# puis la directive créative (cadrage original), puis les paramètres techniques.
# ---------------------------------------------------------------------------

# 30 directives créatives — 10 lieux × 3 angles
# Tirées du script district_zero_ep01.fountain — fidélité narrative absolue
_CREATIVE_COMPOSITIONS: dict[str, dict[str, str]] = {
    "ext_outer_wall_night": {
        "wide": (
            "Lens 15cm above black water surface — the wall is not background, it is the sky. "
            "Camera tilted up 10 degrees: towers dissolve into salt haze at upper frame edge. "
            "Searchbeam slashes frame upper-right to upper-left — cold 5600K, finds nothing, exits."
        ),
        "medium": (
            "Frame locked on the tide-mark at 12-metre height: the waterline that erased everything below it. "
            "Vertical rust-stain streaks as a thirty-year timeline. One corroded rebar in critical focus."
        ),
        "detail": (
            "Single rebar section: corroded to lace. Rust bloom radiating from the structural anchor — "
            "three centimetres of iron carrying thirty years of salt water. This is the evidence."
        ),
    },
    "int_transit_corridor_night": {
        "wide": (
            "Perfect bilateral symmetry — camera axis locked on corridor centreline at hip height. "
            "Walls mirror exactly. The single cage lamp at the vanishing point is the only subject — "
            "the only destination. The corridor implies a journey that cannot end."
        ),
        "medium": (
            "Camera pressed hard against the right wall at a lateral angle — "
            "cable bundles crush the left third of frame. Centre-frame: steam jet catching backlight. "
            "The broken pipe breathes."
        ),
        "detail": (
            "Single rivet head in extreme macro: corroded, rust-bloom radiating 4cm. "
            "The same rivet reflected inverted in the puddle below — "
            "two surfaces of the same world, touching."
        ),
    },
    "int_pressure_valve_chamber_night": {
        "wide": (
            "Extreme low angle — lens at floor level. The valve array ascends into darkness "
            "like an inverted city skyline. The strobe flash: incoming from overhead, "
            "white edge on every manifold surface, hard shadows slamming across metal."
        ),
        "medium": (
            "Frame: a single valve wheel, 60cm diameter, surface worn smooth at every grip point. "
            "Rust streak descending from a cracked flange seal. "
            "The gauge below: a reading nobody has reset."
        ),
        "detail": (
            "Pressure gauge close: cracked glass, needle frozen at an arbitrary reading. "
            "Rust bloom at the pivot. The machine continued after the humans stopped watching."
        ),
    },
    "int_voss_apartment_night": {
        "wide": (
            "Camera wedged into far corner — extreme wide, geometry compressed. "
            "The practical lamp at camera-right: a small amber sun in a room that stopped hoping. "
            "Cold neon bleeds through the condensation-fogged window at frame-left. "
            "Two temperatures. One room. No solution."
        ),
        "medium": (
            "Frame: the practical lamp and its amber cone against absolute darkness. "
            "The lamp is not incidental. The lamp is the entire argument for staying."
        ),
        "detail": (
            "Condensation on the window glass — a city's breath made visible. "
            "Through the haze: a neon fragment, colour without meaning, warmth without source."
        ),
    },
    "int_civic_atrium_morning": {
        "wide": (
            "Camera at glass-ceiling height pointing straight down — figures 80 metres below "
            "become a controlled pattern on marble. Choreography made visible from above. "
            "Scale as argument. Architecture as authority."
        ),
        "medium": (
            "Frame: the propaganda screen's lower-left corner — ROOK's face at 12-metre scale, "
            "floor reflection distorting the image below. The monument to repetition."
        ),
        "detail": (
            "Polished marble floor close: surface carrying the faintest trace of ten thousand footstep paths — "
            "worn smooth by ordered movement. The ghost of coercion made material."
        ),
    },
    "int_black_market_sublevel_day": {
        "wide": (
            "Camera below stall table height — neon signs at eye level cutting across frame: "
            "amber from left, cyan from right. Grey daylight shafts punch down from grilles above. "
            "Three colour temperatures. Zero order."
        ),
        "medium": (
            "Frame: two hands meeting over a spread display map — "
            "amber neon from below-left, cyan neon from right. "
            "The map between them: the scene's only subject. Faces obscured."
        ),
        "detail": (
            "Neon sign transformer close: heat-cracked casing, exposed copper wiring, "
            "amber glow from a single exposed filament. Function outlasting design."
        ),
    },
    "int_security_ops_center_day": {
        "wide": (
            "Camera at analyst level — cold screen-glow washes faces from the front. "
            "Vale at frame-right: near-silhouette, cold window light edging his shoulder. "
            "He is not watching the same thing as everyone else."
        ),
        "medium": (
            "Frame: Vale's back and twelve monitors ahead of him. "
            "His reflection ghosted in the dark glass between two screens. "
            "The room watches. He observes."
        ),
        "detail": (
            "One monitor edge: a movement-signature coordinate fading from the display. "
            "An analyst's fingertip hovering below — not pressing. "
            "The decision has already been made elsewhere."
        ),
    },
    "int_service_spine_night": {
        "wide": (
            "Perfect symmetry — camera on centreline. Emergency floor strips recede into green-tinted fog. "
            "Track rails converge at infinity. The darkness ahead is not empty — it is a destination."
        ),
        "medium": (
            "Frame: the ancient relay panel at mid-corridor — "
            "amber OLED gauges lighting one by one. Physical toggle switches. Brass identification plaques. "
            "The panel has been here longer than anyone who might need it."
        ),
        "detail": (
            "Floor-level emergency strip close: green 4000K raking across a dust-covered rail surface. "
            "Mineral deposit crystals catch the light at micro-scale — the geometry of neglect."
        ),
    },
    "int_observation_chamber": {
        "wide": (
            "Camera behind hydraulic machinery — lens peers through steel framework "
            "at the opening shutters. Through the gap: organised lights in the far distance. "
            "The impossible view, framed by corrosion."
        ),
        "medium": (
            "Frame: the shutter threshold — warm red interior at left, cold grey-blue exterior growing at right. "
            "The exact line where the lie ends."
        ),
        "detail": (
            "Corroded copper pipe junction close: verdigris bloom in green and turquoise, "
            "decades of oxidation. The infrastructure that was maintained — by someone, for something."
        ),
    },
    "int_voss_apartment_predawn": {
        "wide": (
            "Camera at floor level — the thin horizontal bar of cold blue light IS the horizon. "
            "Everything above: forms and shadows. The room has changed overnight."
        ),
        "medium": (
            "Frame: the door at frame-right. Under the gap: cold corridor light, "
            "then a shadow, then a second shadow. The silence before the door detonates inward."
        ),
        "detail": (
            "Door lock housing close: paint around the cylinder freshly stressed, "
            "hairline fractures radiating outward. The metal that is about to yield. One second before."
        ),
    },
}

_CREATIVE_FALLBACK: dict[str, str] = {
    "wide":   "Camera position chosen for maximum spatial impact — familiar geometry made strange.",
    "medium": "The singular object that carries the scene's narrative weight — isolated, unambiguous.",
    "detail": "Surface as biography — material evidence of the world's history compressed into frame.",
}


def _creative_composition(loc_key: str, angle: str) -> str:
    """Directive de composition créative — par lieu et par angle.
    Tirée du script, fidèle à la narration. Pas mécanique — intentionnelle.
    """
    return _CREATIVE_COMPOSITIONS.get(loc_key, _CREATIVE_FALLBACK).get(angle, _CREATIVE_FALLBACK[angle])


def _build_wide(loc_key: str, loc: dict, grade: dict) -> str:
    dop = loc["dop_ref"]
    camera = loc.get("camera", "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 1600")
    light_key = loc["lighting_brief"].split(".")[0].strip() + "."
    beat = loc.get("narrative_beat", "")
    beat_str = f"{beat} " if beat else ""
    return (
        f"{beat_str}"
        f"Wide establishing. {loc['slug']}. Empty scene, no people. "
        f"{_creative_composition(loc_key, 'wide')} "
        f"{light_key} "
        f"{_optics_block(loc)} "
        f"{camera}. Focus plane 8 metres. "
        "Anamorphic horizontal flares on practicals. "
        f"Kodak Vision3 500T EI 1000 — silver halide grain, natural halation. {dop}."
    )


def _build_medium(loc_key: str, loc: dict, grade: dict) -> str:
    dop = loc["dop_ref"]
    camera_base = loc.get("camera", "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 1600")
    camera_medium = camera_base.replace("32mm", "50mm").replace("50mm T2.3", "50mm T2.8")
    light_key = loc["lighting_brief"].split(".")[0].strip() + "."
    beat = loc.get("narrative_beat", "")
    beat_str = f"{beat} " if beat else ""
    return (
        f"{beat_str}"
        f"Medium. {loc['slug']}. Empty scene, no people. "
        f"{_creative_composition(loc_key, 'medium')} "
        f"{light_key} "
        f"{_optics_block(loc)} "
        f"{camera_medium}. Focus plane 2.5 metres — surface razor-sharp, background in bokeh. "
        f"Kodak Vision3 500T EI 1000 — silver halide grain, natural halation. {dop}."
    )


def _build_detail(loc_key: str, loc: dict, grade: dict) -> str:
    camera_detail = loc.get("camera", "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 1600")
    camera_detail = camera_detail.replace("32mm", "100mm").replace("50mm T2.8", "100mm")
    dop = loc["dop_ref"]
    light_key = loc["lighting_brief"].split(".")[0].strip() + "."
    return (
        f"{_creative_composition(loc_key, 'detail')} "
        f"{loc['slug']}. Extreme macro, no people. "
        f"Raking light 10 degrees to surface — micro-relief fully revealed. {light_key} "
        f"{_material_block(loc)} "
        f"{_shadow_block(loc)} "
        f"{_reflection_block(loc)} "
        f"{_optics_block(loc)} "
        f"{camera_detail}. Focus plane 40 centimetres — 3cm sharp layer, all else dissolved. "
        f"Kodak Vision3 500T EI 1000 — microscopic silver grain on texture. {dop}."
    )


PROMPT_BUILDERS = {
    "wide":   _build_wide,
    "medium": _build_medium,
    "detail": _build_detail,
}


# ---------------------------------------------------------------------------

def run(filter_locs: list[str], filter_angles: list[str], dry_run: bool, force: bool = False) -> None:
    _load_env_local()

    import os
    token = os.environ.get("REPLICATE_API_TOKEN", "")
    if not token and not dry_run:
        print("ERROR: REPLICATE_API_TOKEN non défini", file=sys.stderr)
        sys.exit(1)

    locs_data  = json.loads((ROOT / "production/locations.json").read_text(encoding="utf-8"))
    grade      = json.loads((ROOT / "production/grade.json").read_text(encoding="utf-8"))
    out_dir    = ROOT / "production/location_refs"

    targets = filter_locs if filter_locs else list(locs_data.keys())
    targets = [lk for lk in targets if lk in locs_data]
    angles  = filter_angles if filter_angles else list(ANGLES)
    angles  = [a for a in angles if a in ANGLES]

    total_imgs = len(targets) * len(angles)
    print(f"\nAngles à générer : {len(targets)} lieux × {len(angles)} angles = {total_imgs} images")
    print(f"Coût estimé : ${total_imgs * COST_PER_IMG:.2f}")
    print(f"Angles : {angles}")
    print(f"Lieux  : {targets}")

    if dry_run:
        for lk in targets:
            loc = locs_data[lk]
            for angle in angles:
                prompt = PROMPT_BUILDERS[angle](lk, loc, grade)
                print(f"\n  [{lk}] [{angle}] seed={loc['seed']}")
                print(f"  Prompt ({len(prompt)} chars) : {prompt[:120]}...")
        print("\n[DRY-RUN] Aucun appel API.")
        return

    import replicate
    out_dir.mkdir(parents=True, exist_ok=True)
    total_cost = 0.0

    for lk in targets:
        loc = locs_data[lk]
        seed = loc["seed"]

        for angle in angles:
            out_path = out_dir / f"{lk}_{angle}.png"
            if out_path.exists() and not force:
                print(f"  [{lk}] [{angle}] déjà existant — skip (--force pour régénérer)")
                # Update refs_angles dans le JSON quand même
                locs_data[lk].setdefault("refs_angles", {})[angle] = str(out_path)
                locs_data[lk].setdefault("refs_angles_prompts", {})[angle] = "(already existed — prompt not regenerated)"
                continue

            prompt = PROMPT_BUILDERS[angle](lk, loc, grade)
            # Respecte le rate limit Replicate (6 req/min si crédit < $5)
            if total_cost > 0:
                time.sleep(11)

            print(f"\n[{lk}] [{angle}] seed={seed} — appel FLUX Ultra + Redux...")
            t0 = time.monotonic()

            # image_prompt = master validé — ancre la palette, l'atmosphère, le style
            master_path = Path(loc["ref_image"])
            api_input: dict = {
                "prompt":                prompt,
                "aspect_ratio":          "16:9",
                "output_format":         "png",
                "output_quality":        100,
                "safety_tolerance":      5,
                "raw":                   True,
                "seed":                  seed,
            }
            if master_path.exists():
                import base64
                img_b64 = base64.b64encode(master_path.read_bytes()).decode()
                api_input["image_prompt"]          = f"data:image/png;base64,{img_b64}"
                api_input["image_prompt_strength"] = 0.25

            output = replicate.run(MODEL, input=api_input)
            elapsed = time.monotonic() - t0

            url = getattr(output, "url", None)
            if callable(url):
                url = url()
            else:
                url = str(output)

            with urllib.request.urlopen(url, timeout=60) as resp:
                img_bytes = resp.read()

            # Upscale → 4K UHD (3840×2160) via LANCZOS4 + unsharp mask
            import cv2
            import numpy as np
            arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            img_4k = cv2.resize(img, (3840, 2160), interpolation=cv2.INTER_LANCZOS4)
            blur = cv2.GaussianBlur(img_4k, (0, 0), 1.0)
            img_4k = cv2.addWeighted(img_4k, 2.4, blur, -1.4, 0)
            cv2.imwrite(str(out_path), img_4k, [cv2.IMWRITE_PNG_COMPRESSION, 3])

            total_cost += COST_PER_IMG
            print(f"  Sauvegardé : {out_path.name} (3840×2160) — {elapsed:.1f}s — ${total_cost:.2f} cumulé")

            # Update locations.json — image path + prompt persisté
            locs_data[lk].setdefault("refs_angles", {})[angle] = str(out_path)
            locs_data[lk].setdefault("refs_angles_prompts", {})[angle] = prompt
            (ROOT / "production/locations.json").write_text(
                json.dumps(locs_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    print(f"\nTerminé. {total_imgs} images. Coût total : ${total_cost:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Génère 3 angles de référence visuelle par lieu (visual bible V4)"
    )
    parser.add_argument("--loc",   nargs="*", default=[], help="Filtrer par lieu(x)")
    parser.add_argument("--angle", nargs="*", default=[], choices=list(ANGLES),
                        help="Filtrer par angle(s) : wide medium detail")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force",   action="store_true", help="Régénère même si le fichier existe")
    args = parser.parse_args()
    run(args.loc, args.angle, args.dry_run, args.force)
