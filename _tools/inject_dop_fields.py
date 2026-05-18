"""
_tools/inject_dop_fields.py
============================
Injecte les 3 champs DOP-grade manquants dans storyboard.json :
  - reference_exact   : plan précis (film + timecode + pourquoi ce plan)
  - off_frame_tension : ce qui n'est pas dans le cadre mais doit se sentir
  - material_state    : matières dominantes + état de dégradation

Usage : python _tools/inject_dop_fields.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORYBOARD = ROOT / "production" / "storyboard.json"

# ---------------------------------------------------------------------------
# CONTENU DOP PAR SHOT
# ---------------------------------------------------------------------------
DOP_FIELDS: dict[str, dict[str, str]] = {
    "SCN_001_SHOT_001": {
        "reference_exact": (
            "Blade Runner 2049 (Deakins, 2017) — 0:02:10, opening dry lake establishing shot. "
            "Empty frame held long enough to feel geological. The camera finds scale before it "
            "finds anything human. The architecture is the subject."
        ),
        "off_frame_tension": (
            "The functioning city on the other side of the wall — warm, organised, "
            "hidden. The wall is not protecting anyone inside; it is hiding something outside."
        ),
        "material_state": (
            "Salt-crusted concrete face, 25m high. Rebar tips emerging through wall base — "
            "oxidised red-brown, tips blunted by 20 years of salt corrosion. Black oily water "
            "at base: iridescent surface film, white foam churning at impact zone. Drowned tower "
            "facades above: dark tide-mark stain at mid-height, salt line. Broken window frames "
            "visible — steel lintels rusted through, glass gone. Each tower individually distinct."
        ),
    },
    "SCN_001_SHOT_002": {
        "reference_exact": (
            "Blade Runner 2049 (Deakins, 2017) — 0:55:20, exterior patrol sweep sequence. "
            "The beam as the state's indifferent eye — it finds nothing, it was never looking "
            "for anything. The light source is the only subject in the frame."
        ),
        "off_frame_tension": (
            "The mechanical operator of the searchbeam — unseen, above. "
            "The thousands below who have learned not to look up when the beam passes."
        ),
        "material_state": (
            "Concrete wall face and black water surface. Water: oily, beam reflection breaking "
            "into horizontal streaks on wave crests, specular at normal incidence. "
            "3-degree Dutch tilt reveals: concrete erosion line at frame base, rebar corrosion "
            "running diagonally. Between beam passes: absolute black water surface, no reflected light."
        ),
    },
    "SCN_002_SHOT_001": {
        "reference_exact": (
            "Sicario (Deakins, 2015) — 0:17:45, opening corridor approach, FBI. "
            "The corridor depth as dread geometry — movement toward camera compresses "
            "the space rather than opening it. The vanishing point is the threat."
        ),
        "off_frame_tension": (
            "The sealed route that blinks and disappears — visible on her wrist display "
            "but not yet in the frame. The system that sealed it, somewhere above, "
            "already aware she found it."
        ),
        "material_state": (
            "Corroded riveted steel walls — each rivet head with rust bloom radiating 3-5cm, "
            "orange-brown against black oxide base. Cable tray bundles overhead: dense black PVC "
            "conduit, corrosion at metal saddle contact points. Wet concrete floor: standing puddles "
            "2-5mm deep, light oil sheen, boot tread marks visible in the grime. "
            "Pipe joints: white mineral deposits at seams, rust streaks below each joint."
        ),
    },
    "SCN_002_SHOT_002": {
        "reference_exact": (
            "Arrival (Villeneuve / Bradford Young, 2016) — 0:42:00, close on Louise's hands "
            "with the heptapod material. The information held in human hands that changes "
            "everything — the moment of comprehension before action. The object is the subject."
        ),
        "off_frame_tension": (
            "The sealed route that just disappeared — visible to us on the display, "
            "already erased from the official system. The gap between what she saw "
            "and what the record will show."
        ),
        "material_state": (
            "Wrist display: matte-black polymer housing, machined aluminium micro-bezel, "
            "OLED panel — 0.5mm pixel pitch, amber emission. Nara's forearm: weathered skin, "
            "faint salt residue from running sweat, tendon visible under tension. "
            "Display strap: worn nylon, slight fraying at buckle edge."
        ),
    },
    "SCN_002_SHOT_003": {
        "reference_exact": (
            "Children of Men (Lubezki / Cuarón, 2006) — 0:52:00, Bexhill checkpoint threshold. "
            "The decision to cross into forbidden space captured at the last moment before "
            "commitment — the foot already forward, the body's weight already committed."
        ),
        "off_frame_tension": (
            "What is in the unmapped corridor — the system does not know, which means nobody "
            "has mapped it, which means something is there that was not meant to be found. "
            "The darkness is not empty."
        ),
        "material_state": (
            "Steel wall edge at threshold: cold-rolled steel, mill scale surface, edge rust "
            "starting at cut face, no protective coating. Unmapped corridor entrance: absolute "
            "darkness, zero reflective surfaces readable. Her jacket: damp at collar from run "
            "sweat, fabric pulled slightly by the hand on the wall edge."
        ),
    },
    "SCN_003_SHOT_001": {
        "reference_exact": (
            "Sicario (Deakins, 2015) — 1:23:15, sub-tunnel approach with night vision. "
            "The figure made small against overwhelming architecture — the human being as a "
            "detail in an industrial composition. The scale is the argument."
        ),
        "off_frame_tension": (
            "The cause of the alarm — not yet visible, in the pipes themselves, deeper in "
            "the system. The thing that is wrong is already happening. Solving this valve "
            "changes nothing about the source."
        ),
        "material_state": (
            "Cast iron manifold surfaces: 30 years of industrial oxide accumulation — "
            "black carbon layer over dark brown rust. Flanged pipes: bolt-head rust halos, "
            "white mineral deposits at gasket seams, bolt faces showing tool-mark wear. "
            "Valve wheels: orange rust streaks at spokes, grip arcs worn to bare metal. "
            "Floor: oil-stained concrete, pooled condensation, boot tread marks in accumulated grime."
        ),
    },
    "SCN_003_SHOT_002": {
        "reference_exact": (
            "Sicario (Deakins, 2015) — 0:19:50, close on Kate Macer's face after the highway "
            "operation. The moment when the crisis ends and the deeper dread begins — "
            "the face absorbing what just happened before it decides what it means."
        ),
        "off_frame_tension": (
            "The valve chamber continuing to operate behind her — problem solved, "
            "system unchanged. Whatever was sealed is still sealed. The alarm was the symptom, "
            "not the disease."
        ),
        "material_state": (
            "Her face: sweat on forehead and upper lip, strobe-flash revealing individual pore "
            "texture under hard light, salt residue from exertion visible at hairline. "
            "Hands: dark rust transfer on palms from the valve wheel grip, visible on skin. "
            "Eyes: iris detail accessible in hard strobe — pupils contracting to adjust."
        ),
    },
    "SCN_003_SHOT_003": {
        "reference_exact": (
            "Prisoners (Deakins, 2013) — 0:31:00, interrogation room realisation shot. "
            "The cold institutional light that transforms a routine moment into evidence "
            "of something enormous. The flat white that leaves nowhere to hide."
        ),
        "off_frame_tension": (
            "The worker walking away — unaware of what he just said. "
            "The Central Authority office somewhere above, where the maintenance update "
            "was signed. The person who signed it."
        ),
        "material_state": (
            "Institutional overhead fluorescent: flat white 5000K, revealing the chamber's "
            "mundane reality — ordinary maintenance space, not the emergency zone. "
            "Her jacket: wet patches at armpits and lower back from physical effort, "
            "jacket fabric darkened at contact points. Wrist display: the only warm "
            "surface in the cold white space."
        ),
    },
    "SCN_004_SHOT_001": {
        "reference_exact": (
            "Blade Runner 2049 (Deakins, 2017) — 0:23:00, Joe in the apartment with Joi. "
            "The cramped domestic space under amber practical light — intimacy as a kind "
            "of trap. The warmth that makes the cold truth worse when it arrives."
        ),
        "off_frame_tension": (
            "Elian's past — outside the frame, in what he does not say yet. "
            "The apartment door at left — what will come through it later tonight."
        ),
        "material_state": (
            "Cramped apartment: worn laminate table surface — edge peeling, water ring stains "
            "from years of mugs. Amber desk lamp: yellowed plastic shade, warm-orange light "
            "with visible heat discolouration at the shade crown. Apartment walls: condensation "
            "staining at ceiling corners, paint flaking at window frame. Table surface: "
            "objects of a shared life, placed too close together."
        ),
    },
    "SCN_004_SHOT_002": {
        "reference_exact": (
            "Prisoners (Deakins, 2013) — 1:47:00, Hugh Jackman looking away when he delivers "
            "the moral reckoning line. Looking away because he cannot look at what he's done — "
            "the eyes finding the wall, not the person who deserves the answer."
        ),
        "off_frame_tension": (
            "Nara — at right, out of frame, receiving this. Her face deciding what it means. "
            "The years of the secret that is now in the room between them."
        ),
        "material_state": (
            "Elian's face: broken capillaries at nose bridge and cheeks — years of whatever "
            "he drinks in this apartment. Desk lamp edge-light: revealing skin texture, "
            "follicle detail at jaw, the small signs of a life lived in regret. "
            "His collar: fraying at the seam. Shoulder: a slight forward set that has become permanent."
        ),
    },
    "SCN_005_SHOT_001": {
        "reference_exact": (
            "1984 (1984, Michael Radford / Roger Deakins) — party rally sequence. "
            "The single figure dwarfed by the projected leader — scale as political argument, "
            "architecture as ideology made concrete. The citizen reduced to texture."
        ),
        "off_frame_tension": (
            "Nara — invisible somewhere in this crowd, unaware she is already under "
            "passive watch. The anonymous mass that she will soon have to choose to act "
            "for, or abandon."
        ),
        "material_state": (
            "Marble atrium floor: polished pale grey — reflective surface showing inverted "
            "citizen movement below, cold cyan-blue cast from the screen wall above. "
            "Screen wall: institutional aluminium frame, flat-panel emissive surface, "
            "cold cyan wash on all upturned faces below it. Citizens: hundreds of dark "
            "coats, heads slightly down — the posture of compliance."
        ),
    },
    "SCN_005_SHOT_002": {
        "reference_exact": (
            "Zero Dark Thirty (Chastain / Bigelow, 2012) — surveillance screen sequence, 0:44:00. "
            "The predator watching from above who has already made the decision before speaking it. "
            "The calm that precedes a very long game."
        ),
        "off_frame_tension": (
            "Nara — in the crowd below, the thread he has just identified. "
            "Already committed to letting her run. The aide who is about to hear "
            "'don't stop her' and understand for the first time that Vale has a different agenda."
        ),
        "material_state": (
            "Glass balcony railing: tempered structural glass, 15mm thick, clean — "
            "bureaucratic cleanliness that signals power through the absence of wear. "
            "Vale's suit: dark charcoal fine weave, no visible wear. Tablet: brushed aluminium "
            "edge, matte screen. His hands: completely still, no micro-movement."
        ),
    },
    "SCN_006_SHOT_001": {
        "reference_exact": (
            "Blade Runner 2049 (Deakins, 2017) — 1:10:40, underground archive sequence. "
            "The person reading information that changes the map of the world — "
            "the table as a site of revelation. The data as a physical object with weight."
        ),
        "off_frame_tension": (
            "The market vendors who can see this — and who know better than to look. "
            "The surveillance camera at the upper corner, just out of focus. "
            "Vale's passive watch, already in place."
        ),
        "material_state": (
            "Market table surface: scratched clear acrylic over illuminated base, "
            "amber underglow through years of surface abrasion — each scratch catching "
            "and scattering the amber light. Mira's hands: oil stains at fingernail bases, "
            "callus on right index fingertip from circuit work, skin dry from solvents. "
            "Archived data: projected cyan line-weight infrastructure drawings on table surface."
        ),
    },
    "SCN_006_SHOT_002": {
        "reference_exact": (
            "Sicario (Deakins, 2015) — 1:02:00, Kate and Alejandro in the car at the border. "
            "Two people calculating mutual risk, the camera holding them in equal frame "
            "without choosing a side. The calculation is the scene."
        ),
        "off_frame_tension": (
            "The surveillance question — whether they are being watched right now, "
            "by Vale's passive watch order. What that moment of observation looks like "
            "from the security operations centre."
        ),
        "material_state": (
            "Cold blue infrastructure map between them: projected light source casting "
            "blue shadows under their jawlines, removing the warmth from both faces. "
            "Both faces: the blue is flattening — it makes the calculation visible, "
            "removes the human ambiguity. Market depth behind: amber and cyan practicals, "
            "atmospheric haze from a hundred other conversations."
        ),
    },
    "SCN_007_SHOT_001": {
        "reference_exact": (
            "Zero Dark Thirty (2012) — CIA operations room sequence, 0:44:00. "
            "The space of strategic observation — the room where watching is the action. "
            "The near-silhouette against screens as the ultimate expression of institutional power."
        ),
        "off_frame_tension": (
            "Nara and Mira in the tunnel system below — represented as two data points "
            "on the schematic, not yet identified as individuals. The city they are moving through, "
            "invisible from this room."
        ),
        "material_state": (
            "Display wall: dozens of LCD panels flush-mounted, black bezels, cold cyan-blue "
            "emission washing all analyst faces from the front. Console desks: brushed aluminium "
            "trim, wire management visible underneath, analyst personal items absent — "
            "institutional space that discourages personhood. Floor: dark grey linoleum, "
            "perfectly maintained, reflective under display light."
        ),
    },
    "SCN_007_SHOT_002": {
        "reference_exact": (
            "Zero Dark Thirty (2012) — CIA director cold-light scene, 0:58:00. "
            "The face that does not perform emotion because emotion is not relevant "
            "to the decision being made. The cold blue that reads as absence."
        ),
        "off_frame_tension": (
            "The analyst who will hear 'don't stop her' and understand what it implies. "
            "The decision Vale has already made before this scene begins — "
            "Nara as a tool he intends to use."
        ),
        "material_state": (
            "Vale's face: angular bone structure, no softness. Cold display-blue fills "
            "the frontal plane — no shadow side, no warmth. Clean-shaven, no texture, "
            "no history visible on the skin. His tie: perfectly knotted, unmoved. "
            "The display wall behind: dozens of data points, each one a life."
        ),
    },
    "SCN_008_SHOT_001": {
        "reference_exact": (
            "The Road (Javier Aguirresarobe, 2009) — underground passage sequence. "
            "Two figures in a space the world has forgotten — the tunnel as the world's "
            "discarded past. Low-angle green light making the familiar grotesque."
        ),
        "off_frame_tension": (
            "The surface city directly above — the weight of the entire district pressing "
            "down on this forgotten space. The people above who do not know this exists beneath them. "
            "The system that forgot to seal it."
        ),
        "material_state": (
            "Old concrete tunnel walls: 50+ years of mineral accumulation — white calcium "
            "carbonate deposits at every crack, brown iron oxide vertical streaks. Track bed: "
            "ballast gravel, abandoned decades, moss growing in damp zones. Green emergency "
            "strip casing: cracked yellow-aged plastic, corrosion at mounting brackets. "
            "Pipe bundles on wall: asbestos lagging on older sections, newer PVC on repairs."
        ),
    },
    "SCN_008_SHOT_002": {
        "reference_exact": (
            "Children of Men (Lubezki / Cuarón, 2006) — generator scene in the hideout, 1:05:00. "
            "Hands that know machinery — the tactile relationship with old technology "
            "in an emergency. The confidence of someone who has always talked to machines."
        ),
        "off_frame_tension": (
            "The mechanism behind the wall — the access it is about to unlock. "
            "The thing on the other side that does not know it is about to be opened. "
            "Decades of whatever has been accumulating in that chamber."
        ),
        "material_state": (
            "Control panel face: Bakelite housing, cracked at corner from decades of thermal "
            "cycling — brown plastic gone yellow-beige with age. Toggle switches: chrome "
            "plating pitted, black plastic knobs worn smooth at contact. OLED gauges: "
            "anachronistic modern display installed into original housing — new amber "
            "light through old apertures. Mira's hands on the panel: her oil stains "
            "transferred to the Bakelite surface."
        ),
    },
    "SCN_008_SHOT_003": {
        "reference_exact": (
            "Sicario (Deakins, 2015) — 1:23:15, overwatch position, tunnel approach. "
            "The figure providing professional stillness against the threat of the dark. "
            "The silence of an expert waiting — not frozen, ready."
        ),
        "off_frame_tension": (
            "The armed unit already in motion — not yet in the tunnel, audible as radio "
            "clicks. The silence of the dark passage is the form the threat takes "
            "before it has a face."
        ),
        "material_state": (
            "Her face in green emergency light: skin appears cold and blue-green — "
            "the natural warmth reversed. Wet hair: individual strands catching green "
            "reflection at the tips. The dark passage behind her: absolute black, "
            "no surface texture visible, no depth cue. The contrast is the threat."
        ),
    },
    "SCN_008_SHOT_004": {
        "reference_exact": (
            "Ex Machina (Rob Hardy, 2014) — 0:35:00, access panel discovery. "
            "The moment of comprehension when a system reveals something it was designed "
            "to conceal — the face reading the information faster than it can process "
            "the implications."
        ),
        "off_frame_tension": (
            "The gate itself — somewhere in the wall beyond this tunnel, heavy steel, "
            "sealed for decades. What is in the access chamber it guards. "
            "The identifier that should not exist in any official system."
        ),
        "material_state": (
            "Panel display: old CRT-era UI conventions on the new OLED — green phosphor "
            "character aesthetic on amber hardware. Gate unlock indicator: single green "
            "LED, 3mm diameter point-source, casting a tiny hard shadow of itself on the "
            "panel face. Her face: amber panel glow now joined by the cold green point — "
            "mixed-light moment, two temperatures competing on one cheek."
        ),
    },
    "SCN_009_SHOT_001": {
        "reference_exact": (
            "Children of Men (Lubezki / Cuarón, 2006) — 1:37:00, ship revelation at end. "
            "The light growing through an industrial structure — the world outside arriving "
            "as a physical presence before it becomes legible. Two small figures against "
            "the scale of the discovery."
        ),
        "off_frame_tension": (
            "The functioning city beyond the wall — not yet visible, present only as "
            "growing light through the gap. The decades of suppressed knowledge about "
            "its existence. The people who built the lie and are still maintaining it."
        ),
        "material_state": (
            "Observation chamber walls: cast iron rib structure, heavy industrial paint over "
            "40 years of thermal cycles — blistered at heat sources, cracked at stress points, "
            "dark red oxide showing through failed paint. Mechanical shutters: layered steel "
            "slats, each surface corroded and salt-pitted from exterior exposure. "
            "The opening gap: raw weathered steel edge, condensation staining at the sill "
            "from years of temperature differential."
        ),
    },
    "SCN_009_SHOT_002": {
        "reference_exact": (
            "Children of Men (Lubezki / Cuarón, 2006) — 1:38:20, Kee's face during the ceasefire. "
            "The face receiving information that rewrites the entire context of a life — "
            "not the dramatic reaction, the quiet one. The diagnosis before the feeling."
        ),
        "off_frame_tension": (
            "The functioning city directly to camera-right — the lights, the vehicles, "
            "the organised life she was told was dead. Present in the light on her face "
            "before it becomes a visible subject."
        ),
        "material_state": (
            "Nara's face: wet, cold — water drops on skin catching the new exterior light. "
            "This light quality is different from anything she has been lit by before — "
            "harder, bluer, coming from distance rather than a practical. "
            "Eyes: iris catching the cold exterior grey-blue, pupils beginning to adjust "
            "from the tunnel dark. Her jaw: still carrying the tension of the sprint."
        ),
    },
    "SCN_009_SHOT_003": {
        "reference_exact": (
            "Chinatown (Vilmos Zsigmond, 1974) — 1:30:00, water infrastructure reveal. "
            "The industrial machinery of a systemic crime, in plain sight, running continuously. "
            "The horror is not dramatic — it is mundane. The machinery just runs."
        ),
        "off_frame_tension": (
            "The lower sectors — where these pipes terminate. The people there who are "
            "receiving what these pumps deliver. The slow accumulation of what "
            "this infrastructure has been doing for decades."
        ),
        "material_state": (
            "Industrial pump housings: heavy grey cast iron, mounting bolts showing orange "
            "rust halos, grease fittings black with accumulated grime, drain plugs seized. "
            "Pipe bundles descending through floor: 15cm diameter flanged steel, corrosion "
            "at every flange joint, old paint cracking away in sheets. Floor grating: "
            "diamond-plate steel, rust visible in the raised diamond texture, water "
            "pooled in the low points."
        ),
    },
    "SCN_009_SHOT_004": {
        "reference_exact": (
            "Sicario (Deakins, 2015) — 0:18:30, team extraction after the house. "
            "Tactical urgency in red light — the movement that cannot be hesitated over. "
            "One person not ready to leave. One person already leaving."
        ),
        "off_frame_tension": (
            "The exterior world now closing off behind the reversing shutters — "
            "the last seconds of seeing it. The security unit already dispatched "
            "to their location, now minutes away."
        ),
        "material_state": (
            "Red alarm wash: all metal surfaces now crimson — the same corroded iron "
            "and paint transformed by single-frequency red light. Their jackets: "
            "wet fabric appearing dark crimson under the wash, texture suppressed. "
            "Shutter motors: visible in background beginning to reverse — heavy mechanical "
            "motion, steel slats moving against decades of static corrosion."
        ),
    },
    "SCN_010_SHOT_001": {
        "reference_exact": (
            "Sicario (Deakins, 2015) — 1:24:00, extraction sprint under fire. "
            "Handheld that does not lose axis — urgency without chaos. "
            "The blast doors as the percussive rhythm of pursuit, one per second."
        ),
        "off_frame_tension": (
            "The armed unit behind — not yet visible, audible as radio clicks and boot "
            "cadence. The blast doors sealing behind them one by one, eliminating "
            "retreat. The only direction is forward."
        ),
        "material_state": (
            "Service spine under alarm: corroded tunnel now transformed by red light and "
            "blast door impact dust — mineral wall deposits catching red, blast door sparks "
            "showing raw iron interior on each slam. Smoke: fine concrete particulate "
            "hanging in red ambient, visibility 8-10 metres. Their jackets: "
            "dust accumulation on shoulders from the impacts."
        ),
    },
    "SCN_010_SHOT_002": {
        "reference_exact": (
            "Sicario (Deakins, 2015) — 1:20:00, cartel roadblock silhouettes. "
            "Figures reduced to tactical geometry by backlight — threat without face, "
            "power without identity. The silhouette as the ultimate expression of institutional force."
        ),
        "off_frame_tension": (
            "Nara and Mira ahead — already through the blast door, already gone. "
            "The unit does not know this yet. Vale's voice over comms is already "
            "at odds with the unit's mission."
        ),
        "material_state": (
            "Armed unit tactical kit: all light-absorbing surfaces — matte black equipment, "
            "no reflective material visible. Weapon lights: 3000-lumen tungsten-equivalent, "
            "cutting through dust as solid beams with visible particulate scatter in the "
            "light column. Dust cloud: fine concrete powder suspended in the tunnel atmosphere, "
            "2-3 metres of effective visibility reduction."
        ),
    },
    "SCN_010_SHOT_003": {
        "reference_exact": (
            "Heat (Dante Spinotti, 1995) — split extraction sequence. "
            "Two people executing separate escape routes with zero communication — "
            "the professional trust that requires no goodbye. "
            "The decision made and executed without a word."
        ),
        "off_frame_tension": (
            "Where the duct leads — Mira's exit route, the one she mapped that Nara "
            "does not know about. Whether they will meet again. "
            "What Mira knows about the duct system that makes her certain this works."
        ),
        "material_state": (
            "Side duct opening: 60x60cm galvanised steel duct, 20 years of condensation "
            "and dust at the opening — dark moisture ring staining the wall around the aperture. "
            "Duct interior: absolute dark, no reflective surface readable. "
            "Mira's jacket: dark fabric showing the duct edge contact as a grey dust transfer "
            "on her shoulder as she enters."
        ),
    },
    "SCN_010_SHOT_004": {
        "reference_exact": (
            "Sicario (Deakins, 2015) — 1:25:10, blast door final. "
            "The escape by exactly the minimum possible margin — the door sealing as "
            "the frame closes. The threat contained not by distance but by one centimetre "
            "of armoured steel."
        ),
        "off_frame_tension": (
            "The armed unit on the other side — four seconds behind. "
            "The silence on her side of the door after it seals. "
            "Whatever Vale is saying into the comms that the unit cannot hear."
        ),
        "material_state": (
            "Blast door: heavy armoured steel, hydraulic seals, door face showing decades "
            "of use — scored metal at the edge where it seats, hydraulic fluid traces at "
            "the seam. The narrowing gap: raw steel edge, sparks at the friction point. "
            "Her jacket: fabric-on-steel contact leaving a grey smear on the door edge "
            "as she passes through."
        ),
    },
    "SCN_011_SHOT_001": {
        "reference_exact": (
            "Blade Runner 2049 (Deakins, 2017) — 0:08:30, Joe returns to his apartment at predawn. "
            "The figure lit only at the edge by cold ambient blue — face in shadow, "
            "carrying what cannot be put down. The apartment as a place that will "
            "never be the same again."
        ),
        "off_frame_tension": (
            "The tactical unit in the corridor outside — not yet arrived. "
            "The predawn silence that is actually a countdown. "
            "Elian, awake, waiting in the dark behind her."
        ),
        "material_state": (
            "Nara's jacket: soaked at shoulders and upper back — fabric darkened, "
            "dripping at the hem. Hair: matted wet to temples and neck, water running "
            "along the jawline. Skin: water drops catching the cold blue window light "
            "as point-source highlights. The apartment door: worn paint at lock height, "
            "use marks around the handle — a door that has been opened thousands of times."
        ),
    },
    "SCN_011_SHOT_002": {
        "reference_exact": (
            "No Country for Old Men (Deakins, 2007) — 1:45:00, Sheriff Bell in the hotel room. "
            "The face of a man who has arrived at the place he always feared he would arrive — "
            "the recognition of an inevitability. Cold ambient. Near-dark. No warmth."
        ),
        "off_frame_tension": (
            "What Elian has been carrying for years — the knowledge she has just confirmed. "
            "The apartment chair he has been sitting in all night, waiting for her "
            "to either come back or not come back."
        ),
        "material_state": (
            "Elian's face: cold predawn blue making his age visible in a way the amber "
            "desk lamp did not — deeper hollows under the eyes, the grey in his temples "
            "visible. He has been awake all night: the slight inflation of the lower "
            "eyelid, the jaw held slightly open with fatigue. His collar: rumpled, "
            "the night showing on him."
        ),
    },
    "SCN_011_SHOT_003": {
        "reference_exact": (
            "Children of Men (Lubezki / Cuarón, 2006) — 1:04:00, Kee in the farmhouse. "
            "The revelation held in the face, not acted. The light from behind, "
            "the face in the resulting shadow — the internal event on the skin's surface. "
            "No reaction. Just absorption."
        ),
        "off_frame_tension": (
            "Elian — at left out of frame, having just said the words. "
            "The years of the lie he carried. What it cost him. What it cost her "
            "without her knowing it was being paid."
        ),
        "material_state": (
            "Nara's face: water still on skin — individual drops catching cold blue edge "
            "light as tiny bright points. Single wet strands of hair beginning to "
            "separate from the wet press, catching blue at the tips. Her eyes: "
            "the cold blue that has replaced all amber warmth — the warmth is "
            "structurally gone from this scene. Everything is blue now."
        ),
    },
    "SCN_011_SHOT_004": {
        "reference_exact": (
            "Munich (Janusz Kaminski / Spielberg, 2005) — 1:20:00, the document handoff. "
            "The physical transfer of evidence as a moral act — the hands that carry "
            "the object are carrying the consequence. Cold light. No ceremony."
        ),
        "off_frame_tension": (
            "What is on the drive — the proof, the names, the crime documented. "
            "The weight of it in his unsteady hands. "
            "The moment he decided to keep it rather than destroy it."
        ),
        "material_state": (
            "Elian's hands: unsteady — the slight tremor visible in the cold blue light, "
            "joint knuckles showing age, veins prominent under thin skin. "
            "The encrypted drive: hard matte-black polymer, machined aluminium contacts, "
            "50x25mm, government-spec construction — dense, heavy for its size. "
            "His jacket interior lining: worn at the pocket seam where the drive has "
            "lived for however long he has been carrying it."
        ),
    },
    "SCN_011_SHOT_005": {
        "reference_exact": (
            "Blade Runner 2049 (Deakins, 2017) — 1:55:00, K and Ana Stelline. "
            "The handoff between two people who understand they will not see each other again — "
            "the object as the only possible form of what cannot be said."
        ),
        "off_frame_tension": (
            "The unit outside — minutes away. The life they had before tonight, "
            "in this apartment, already ended without a formal moment of ending. "
            "The four instructions she will carry out of here."
        ),
        "material_state": (
            "Two faces in equal cold blue — the apartment's warmth architecturally neutralised "
            "by the predawn light. The space between them: the width of the table, "
            "the width of what cannot be repaired. The drive in her wet hands: "
            "water transferring from her skin to the polymer surface, marking it."
        ),
    },
    "SCN_011_SHOT_006": {
        "reference_exact": (
            "No Country for Old Men (Deakins, 2007) — 1:20:00, motel corridor floor, "
            "the shadow under the door. The threat that has already arrived, "
            "present as geometry before it becomes physical. "
            "The most frightening thing Deakins ever filmed is a shadow."
        ),
        "off_frame_tension": (
            "The people casting the shadow — the tactical unit, their equipment, their intention. "
            "They are already at the door. They have already decided what they are doing."
        ),
        "material_state": (
            "Door lock housing: brushed aluminium face plate, worn finish at thumb-contact "
            "areas, mounting screw heads slightly corroded. Door base gap: thin — "
            "institutional grey corridor tile visible, cold white unit tactical lighting "
            "casting a bright stripe. The shadow on that stripe: darker than the gap "
            "around it, a precise geometric interruption."
        ),
    },
    "SCN_011_SHOT_007": {
        "reference_exact": (
            "Children of Men (Lubezki / Cuarón, 2006) — 0:00:30, the coffee shop explosion. "
            "The calm before the detonation — the frame holding the ordinary space "
            "in the last seconds before it ceases to exist. "
            "Then: white. The most violent cut is silence followed by overexposure."
        ),
        "off_frame_tension": (
            "Episode 2 — everything that will follow from this moment. "
            "The series. The city that does not know what is about to be done in its name."
        ),
        "material_state": (
            "Wide apartment: all surfaces reduced to silhouette and edge by cold predawn "
            "blue — every material distinction collapsed to outline. Door: closed, "
            "institutional, unremarkable — the last seconds of its existence as a door. "
            "Then: shaped charge detonation — the door face becomes a white luminance "
            "event, all material information erased in a single frame."
        ),
    },
}


EYELINES: dict[str, str] = {
    "SCN_001_SHOT_001": "N/A — environment shot, no character",
    "SCN_001_SHOT_002": "N/A — environment shot, no character",
    "SCN_002_SHOT_001": "screen-right toward vanishing point — focused, not looking at camera",
    "SCN_002_SHOT_002": "downward — toward wrist display, brow slightly furrowed",
    "SCN_002_SHOT_003": "screen-right into unmapped corridor — looking into darkness, not at camera",
    "SCN_003_SHOT_001": "downward toward valve wheel — effort, not looking up",
    "SCN_003_SHOT_002": "upward, straight ahead — just released valve, head lifting",
    "SCN_003_SHOT_003": "downward toward wrist display — processing, not engaging worker",
    "SCN_004_SHOT_001": "screen-left toward Elian, slightly downward toward the map on the table",
    "SCN_004_SHOT_002": "screen-left toward wall — not at Nara, not at camera",
    "SCN_005_SHOT_001": "N/A — environment shot, no character",
    "SCN_005_SHOT_002": "downward toward atrium floor — not at aide, not at camera",
    "SCN_006_SHOT_001": "downward toward display surface — tracing the route",
    "SCN_006_SHOT_002": "screen-right toward Mira — level, holding eye contact, not blinking",
    "SCN_007_SHOT_001": "N/A — environment shot, no character",
    "SCN_007_SHOT_002": "screen-left toward display wall — slightly off-axis from camera",
    "SCN_008_SHOT_001": "screen-right toward tunnel depth — leading, not looking back",
    "SCN_008_SHOT_002": "downward toward control panel — reading gauges, intent",
    "SCN_008_SHOT_003": "screen-left toward dark passage — overwatch, unblinking",
    "SCN_008_SHOT_004": "downward toward panel, then lifting to middle distance as gate unlocks",
    "SCN_009_SHOT_001": "screen-right toward opening shutters — both characters silhouetted",
    "SCN_009_SHOT_002": "screen-right toward exterior light — wide eyes, not blinking",
    "SCN_009_SHOT_003": "downward toward pump machinery — following the pipes",
    "SCN_009_SHOT_004": "screen-right — last look toward exterior, being pulled left",
    "SCN_010_SHOT_001": "straight ahead toward camera — sprint, forward urgency",
    "SCN_010_SHOT_002": "N/A — environment shot, no character",
    "SCN_010_SHOT_003": "screen-left — one look back before entering duct",
    "SCN_010_SHOT_004": "straight ahead — diving through closing door, no time to look anywhere",
    "SCN_011_SHOT_001": "downward — head slightly bowed, carrying the weight of what she saw",
    "SCN_011_SHOT_002": "screen-left toward Nara — reading her face, not speaking",
    "SCN_011_SHOT_003": "screen-right toward Elian — holding eye contact, absorbing the confession",
    "SCN_011_SHOT_004": "downward toward his own hands — shame, offering the drive without looking up",
    "SCN_011_SHOT_005": "screen-right toward Elian — receiving the instructions, not yet responding",
    "SCN_011_SHOT_006": "N/A — object shot, no character present",
    "SCN_011_SHOT_007": "screen-left toward door — both characters, the last look before breach",
}


def main() -> None:
    data = json.loads(STORYBOARD.read_text(encoding="utf-8"))
    updated = 0
    skipped = 0
    for shot in data["shots"]:
        sid = shot["shot_id"]
        if sid in DOP_FIELDS:
            fields = DOP_FIELDS[sid]
            # Only write if not already present (idempotent)
            for key, val in fields.items():
                if key not in shot or not shot[key]:
                    shot[key] = val
                    updated += 1
                else:
                    skipped += 1
        else:
            # Ensure the keys exist even if empty (schema consistency)
            for key in ("reference_exact", "off_frame_tension", "material_state"):
                if key not in shot:
                    shot[key] = ""

        # Eyeline — idempotent
        eyeline_val = EYELINES.get(sid, "")
        if "eyeline" not in shot or not shot["eyeline"]:
            shot["eyeline"] = eyeline_val
            updated += 1
        else:
            skipped += 1

    STORYBOARD.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✓ storyboard.json mis à jour — {updated} champs écrits, {skipped} déjà présents.")


if __name__ == "__main__":
    main()
