---
title: "District Zero EP01 — Plan d'action technique : FROM SCRATCH"
creation: 2026-04-30 à 16:24
version: 3.0
status: actif
reference: tasks/METHODE_PRODUCTION_IA_2026.md
---

# PLAN D'ACTION — DISTRICT ZERO EP01
## Production from scratch — méthode professionnelle complète

---

## PRINCIPE FONDATEUR (SEUL ELEMENT CONSERVE)

> La session du 2026-04-30 a démontré un principe fondamental :
> **la qualité du prompt est la compétence centrale de toute la chaîne**.
>
> Le pipeline hybride FLUX.2 Pro + Flux Fill Pro v5, combiné à un prompt
> au format "document de production réel" (DOP brief, gaffer notes, références cinéma nommées),
> a produit un score ArcFace de **0.9378** — nouveau record absolu —
> pour un coût de **$0.08/shot** et un temps de **89 secondes**.
>
> Ce n'est pas un accident. C'est le résultat d'une méthode :
> remplacer le "describe what you want" par "parle comme un professionnel du cinéma".
>
> **Ce principe s'applique à tous les métiers. C'est le fil directeur de ce guide.**

---

## CE QUI EST SUPPRIME (table rase totale)

| Element | Raison |
|---------|--------|
| `_archive/` — toutes les images générées précédemment | Remplacées par de nouveaux shots avec la méthode professionnelle |
| `_archive/` — images de référence personnages et lieux | Regénérées from scratch avec DOP-grade prompts |
| Ancien système storyboard (`aiprod_adaptation.cli storyboard`) | Remplacé par `storyboard.json` écrit à la main en langage professionnel |
| `reference_pack.json` comme source de vérité | Remplacé par `characters.json` et `locations.json` DOP-grade |
| Tous les scripts de l'ancienne prod | Réécrits selon la nouvelle méthode |

**Ce qui EST conservé :**
- `pipeline/shot_pipeline.py` — le CODE du pipeline hybride v2 (ArcFace 0.9378). La méthode est validée.
- `_archive/.../district_zero_ep01_production_cut_ir.json` — l'IR JSON de l'histoire (35 shots, 11 scènes)
- `_archive/.../stories/` — les fichiers narratifs (EP01 text, visual bible)
- Le principe ci-dessus

---

## ARCHITECTURE CIBLE

**Chaîne narrative complète — du texte au shot généré :**

```
stories/
└── district_zero_ep01.fountain   <- ETAPE 0 — screenplay Fountain format
                                     source canonique narrative (sluglines,
                                     action lines, dialogues — style GoT/HG)
                                          ↓ dérive et valide ↓
production/
├── characters.json          <- 5 canoniques DOP-grade (source de vérité personnages)
├── locations.json           <- 10 descripteurs DOP-grade (source de vérité lieux)
├── storyboard.json          <- 35 shots — briefs de production (DOP, gaffer, compo)
├── dashboard.json           <- seeds, palettes hex, grade refs par scène
│
├── __init__.py              <- vide
├── dashboard.py             <- loader Python (read-only)
├── gen_character_refs.py    <- génère 1 portrait ref par personnage  [Phase A]
├── gen_location_refs.py     <- génère 1 master plate par lieu         [Phase B]
├── benchmark_characters.py  <- valide ArcFace des refs générées       [Phase B]
├── gen_shots.py             <- génère les 35 shots EP01               [Phase C]
├── gen_assembly.py          <- construit le XML EDL de montage        [Phase D, gratuit]
├── run.py                   <- CLI unifié, point d'entrée unique
└── README.md
```

**Cout de création de tous ces fichiers : $0**
Les appels API n'ont lieu que quand l'utilisateur les déclenche explicitement.

---

## ETAPE 0 — `stories/district_zero_ep01.fountain`

**Pourquoi :** C'est la leçon des scripts GoT (Benioff/Weiss) et Hunger Games.
Les action lines professionnelles *sont déjà du langage de caméra* — pas de narration,
pas de "describe what you want" — des instructions visuelles actives au présent.

Cette couche manquait. Elle est maintenant Étape 0 : la source canonique narrative
depuis laquelle tout le reste est dérivé et validé.

**Règles du format Fountain (standard industrie) :**

```
# Règles absolues
- Sluglines     : EXT./INT. LIEU — MOMENT  (tout en majuscules)
- Action lines  : présent actif, court, visuel. Jamais "on voit que" ou "on comprend que".
                  GoT : "Snow drifts across the bodies of the fallen dead."
                  District Zero : "The searchbeam sweeps. Finds nothing. Always finds nothing."
- Dialogues     : NOM PERSONNAGE centré, réplique en dessous
- Parenthétiques : (uniquement si intonation non évidente)
- Transitions   : SMASH CUT TO:, FADE TO:  — utilisées avec parcimonie
```

**Principe de conversion depuis `district_zero_ep01_production_cut.txt` :**

| Prose narrative | → | Action line Fountain |
|-----------------|---|----------------------|
| "Nara court dans le couloir" | → | "NARA sprints — wrist display pulsing amber. She's not lost. She's solving." |
| "Il y a une alarme" | → | "THE ALARM CUTS. Silence lands like a physical weight." |
| "Elian a l'air coupable" | → | "Elian's jaw tightens. He doesn't look at her when he answers." |

**Exemple — SCN_001 et SCN_002 en format Fountain complet :**

```fountain
Title: DISTRICT ZERO
Credit: Episode 01 — "The Sealed City"
Author: [Author]
Draft date: 2026-04-30


FADE IN:


EXT. DISTRICT ZERO OUTER WALL — NIGHT

Black water. A drowned city skyline — each tower a specific
shape against the dark. Not a blur. A graveyard of architecture.

A searchbeam sweeps. Cold, mechanical, 4-second arcs.
It finds nothing. It always finds nothing.

The beam crosses the water surface. The reflection holds for
a moment, then the dark swallows it.

This world is already finished. Nobody announced it.


INT. LOWER TRANSIT STACK — SERVICE CORRIDOR — NIGHT

A narrow maintenance corridor, 2.2 metres wide, running to
infinity. Riveted steel walls. Cable bundles like arteries.
A single cage lamp at the far vanishing point — the only
light source. Everything else: shadow.

NARA VOSS (late 20s, dark hair pulled back, utility jacket
worn to the body) sprints toward camera. Left leg forward.
Wrist display flashing amber below her chin.

She's not panicked. She runs here. She knows this floor.

She stops.

The wrist display: a sealed route blinks — once, twice —
then disappears. Her thumb hovers. Then captures it.

She looks at what she's just found.

She knows immediately.

At the mouth of an unmapped access corridor, she pauses.
One hand on the wall edge. Looks into the dark ahead.

Then she steps through.
```

**Fichier à créer : `stories/district_zero_ep01.fountain`**
- Convertir les 11 scènes depuis `district_zero_ep01_production_cut.txt`
- Chaque action line doit pouvoir servir de `action_brief` dans `storyboard.json`
- C'est le document de référence pour les saisons futures
- Coût : $0 — travail d'écriture uniquement

---

## ETAPE 1 — `production/characters.json`

Cinq canoniques complets, rédigés en langage de production cinématographique professionnel.
Pas de "describe what you want" — des notes de direction artistique réelles.

```json
{
  "nara": {
    "full_name": "Nara Voss",
    "role": "protagonist",
    "ref_image": null,
    "locked": false,
    "canonical": "Female protagonist of a dystopian survival thriller. Late 20s, fine balanced features, elegant defined jawline, high cheekbones. Intense intelligent eyes — exhaustion and absolute determination. Natural skin texture, visible pores, no makeup, sweat on skin. Dark hair pulled back tightly, 3-4 wet loose strands at temples pressed to skin. Dark grey tubular neck gaiter. Weathered dark olive utility jacket — left and right sleeves each have ONE plain raw-edge woven black nylon rectangle sewn directly to fabric, matte black, visible weave texture only, zero embroidery, zero print, zero text, zero logo, zero symbol. Dark charcoal tactical vest over jacket, no markings of any kind.",
    "portrait_brief": {
      "camera": "ARRI Alexa 35, Cooke Anamorphic /i 50mm T2.8, ISO 1600",
      "framing": "tight portrait, shoulders to crown, head centred at 65% height",
      "lighting": "single motivated practical — amber cage work lamp at 45deg camera-left, 2200K key. Zero fill. 8:1 ratio. Slight backlight separation from deep industrial space behind.",
      "background": "shallow-focus leaking service corridor, riveted steel walls, condensation dripping, absolute darkness beyond 3 metres",
      "dop_ref": "Roger Deakins / Sicario (2015) close-up framing"
    },
    "note": "Portrait seed: 22. Ref generated in Phase A."
  },
  "mira": {
    "full_name": "Mira Sol",
    "role": "deuteragonist",
    "ref_image": null,
    "locked": false,
    "canonical": "Female supporting character, mid-30s. Sharp angular face: prominent cheekbones, strong jaw with a healed hairline fracture scar on the left side. Natural dark olive complexion, no cosmetics, visible fatigue lines under eyes. Black hair cropped military-close on sides, 4cm length on top, unstyled and pressed flat by habit. Eyes: very dark brown near-black, steady and assessing — never uncertain. Lean, survival-conditioned frame. Scavenged tactical kit: dark grey ribbed thermal base layer, worn olive canvas utility vest with three flush external pockets (zero insignia), black cargo trousers with single thigh pocket. Leather tab on right wrist — improvised data-carry. Weight slightly forward on left foot when still — always ready.",
    "portrait_brief": {
      "camera": "ARRI Alexa 35, Cooke Anamorphic /i 50mm T2.8, ISO 1600",
      "framing": "tight portrait, shoulders to crown, head centred at 65% height",
      "lighting": "low neon-green emergency strip from below camera-left, amber trace from scavenged monitor glow camera-right. No overhead fill. 10:1 ratio. Cold industrial shadow fills 65% of frame.",
      "background": "shallow-focus underground signal exchange — hacked monitors, loose wiring bundles, humid industrial air with visible particulate in light shafts",
      "dop_ref": "Villeneuve / Blade Runner 2049 — close character lighting in underground"
    },
    "note": "Portrait seed: 66. Ref generated in Phase A."
  },
  "elian": {
    "full_name": "Elian Voss",
    "role": "supporting",
    "ref_image": null,
    "locked": false,
    "canonical": "Male character, early 50s — prototype of a man ground down by complicity. Heavy weathered face: deep horizontal forehead lines, prominent nasolabial folds, strong jaw with 4-day salt-and-pepper stubble. Dark hair with a pronounced silver streak above the right temple, pushed back without product, slightly matted at neck. Pale hazel eyes: the face carries suppressed guilt — never holds direct eye contact. Ruddy Northern European complexion, broken capillaries across the nose bridge from decades of physical work. Civilian workwear worn with institutional resignation: heavyweight charcoal wool jacket with collar frayed at both edges, round-neck black thermal underneath. Large hands, knuckles enlarged by valve maintenance. Posture: permanently hunched at the upper back — the body of a man who stopped standing straight years ago.",
    "portrait_brief": {
      "camera": "ARRI Alexa 35, Cooke Anamorphic /i 50mm T2.8, ISO 1600",
      "framing": "tight portrait, shoulders to crown, head centred at 65% height, slightly downcast",
      "lighting": "single warm practical desk lamp 2700K at 30deg camera-right — key on cheek and brow, deep shadows filling left side. No fill. Amber exterior neon seeping through small window behind — minimal separation. 6:1 ratio.",
      "background": "shallow-focus cramped apartment — stacked objects, exposed conduit, small window with condensation",
      "dop_ref": "Cuaron / Children of Men — domestic interior close framing"
    },
    "note": "Portrait seed: 44. Ref generated in Phase A."
  },
  "vale": {
    "full_name": "Commander Sarin Vale",
    "role": "antagonist",
    "ref_image": null,
    "locked": false,
    "canonical": "Military antagonist, late 40s. Face of controlled institutional menace: clean angular geometry, strong cheekbones, jaw with precisely maintained dark stubble at 1mm. Dark hair, silver-white at both temples, slicked back with visible product, immaculately maintained. Eyes: cold grey-blue irises carrying a quality of genuine absence of empathy — not cruelty, simply zero sentiment. Slightly sallow skin under cold overhead light. Posture: parade-ground rigid at all times, weight centred, arms held precisely at sides. Black tactical command uniform, no insignia except a single slim horizontal silver bar on left chest. High collar, impeccable fit. The face of a system wearing a human body.",
    "portrait_brief": {
      "camera": "ARRI Alexa 35, Cooke Anamorphic /i 50mm T2.8, ISO 800",
      "framing": "tight portrait, shoulders to crown, head centred at 65% height, slight upward gaze — looking down at viewer",
      "lighting": "cold overhead institutional fluorescent — 6500K, hard, flat on upper face. Window behind right shoulder creating cold backlight silhouette edge. No warmth anywhere. 9:1 ratio.",
      "background": "shallow-focus security operations centre — wall of monitors in cold blue glow, analysts as blurred texture",
      "dop_ref": "Fincher / The Social Network — cold corporate interior"
    },
    "note": "Portrait seed: 77. Ref generated in Phase A."
  },
  "rook": {
    "full_name": "Director Halden Rook",
    "role": "antagonist",
    "ref_image": null,
    "locked": false,
    "canonical": "Political antagonist, mid-50s. Face of curated authority: immaculate silver hair swept back with bureaucratic precision, every strand placed. Skin maintained by institutional privilege — too smooth for his age. Narrow pale blue eyes: patient, calculating, the stillness of a predator who never needs to rush. Strong jaw, patrician nose, thin controlled smile that never reaches the eyes. High-authority navy formal wear: precision-cut coat with single polished brass button, no military markings — a civilian who outranks every soldier in the room. Posture: absolute stillness, effortless authority. Never raises voice. Never rushes.",
    "portrait_brief": {
      "camera": "ARRI Alexa 35, Cooke Anamorphic /i 50mm T2.8, ISO 400",
      "framing": "tight portrait, shoulders to crown, head centred at 65% height",
      "lighting": "clean cold institutional overhead 6500K as key, slight warm practical from a desk lamp at camera-right — 3:1 ratio of cold to warm. Suggesting dual nature: public face warm, true nature cold. 5:1 overall ratio.",
      "background": "shallow-focus immaculate civic interior — marble and glass, public-address screen blurred behind",
      "dop_ref": "Deakins / Skyfall — villain interior framing"
    },
    "note": "Portrait seed: 55. Ref generated in Phase A."
  }
}
```

---

## ETAPE 2 — `production/locations.json`

Dix descripteurs DOP-grade. Chaque lieu est décrit comme un gaffer le ferait avant un tournage.
Ces descripteurs remplacent les prompts génériques de `reference_pack.json`.

```json
{
  "ext_outer_wall_night": {
    "scene_ids": ["SCN_001"],
    "slug": "EXT. DISTRICT ZERO OUTER WALL — NIGHT",
    "ref_image": null,
    "seed": 11,
    "canonical": "Monumental seawall at night — concrete face 25 metres high, water-stained, corroded steel reinforcement bars visible at base. Black churning water crashing against the wall base, catching searchbeam reflections. Behind the wall and above it: the drowned megacity skyline — Art Deco and Brutalist towers individually distinct, hundreds of dark windows, structural ribs, water-stain tide marks halfway up every facade. Each tower readable separately even at distance. Salt mist. Search beams sweeping in slow mechanical arcs from elevated positions.",
    "lighting_brief": "Search beams: HMI 18K on motorised pan heads — cold 5600K, sweeping 4-second arcs. Building facades: practical LED strips at distant window grids — warm amber pinpoints. Water surface: picking up every beam reflection, black glass between sweeps. No fill light, no ambient warmth. Contrast ratio 15:1.",
    "camera": "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 1600, 180deg shutter",
    "colour": {"dominant": "#0A1520", "accent": "#2060C0", "blacks": "#060A0F"},
    "dop_ref": "Roger Deakins / Blade Runner 2049 (2017) — exterior water sequence"
  },
  "int_transit_corridor_night": {
    "scene_ids": ["SCN_002"],
    "slug": "INT. LOWER TRANSIT STACK — SERVICE CORRIDOR — NIGHT",
    "ref_image": null,
    "seed": 22,
    "canonical": "Narrow maintenance corridor, 2.2m wide, extreme vanishing-point perspective to infinity. Corroded riveted steel walls — each rivet head individually textured with rust bloom. Dense cable tray bundles running the full length at 2m height, conduit packed in layers of 3-4. Wet concrete floor: puddles reflecting the single light source at the far end. Broken pipe joint mid-corridor releasing a horizontal steam jet that catches the backlight. Overhead: darkness. The single cage tungsten lamp at the far vanishing point is the only visible light source. Everything else in shadow.",
    "lighting_brief": "Key: single cage tungsten work lamp at vanishing point 30m ahead — 2850K, 500W, generating circular warm glow that falls off sharply to full shadow on both sides. Practical: amber LED accent strips at ankle height on left wall — 2200K, 15% intensity. Ambient: cool blue reflection from wet floor — 6500K bounce from an unseen source behind camera. Ratio 8:1.",
    "camera": "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 1600, 180deg shutter",
    "colour": {"dominant": "#1C2B35", "accent": "#B8600A", "blacks": "#0A0F12"},
    "dop_ref": "Roger Deakins / Sicario (2015) — sub-tunnel approach sequence"
  },
  "int_pressure_valve_chamber_night": {
    "scene_ids": ["SCN_003"],
    "slug": "INT. PRESSURE VALVE CHAMBER — NIGHT",
    "ref_image": null,
    "seed": 33,
    "canonical": "Cathedral-scale industrial chamber — ceiling lost in darkness 15m above. Wall-to-wall pressure valve assembly: cast iron manifolds, 40cm diameter flanged pipes in arrays, valves with large wheel handles showing orange rust streaks. Scale crushing: human figures at 10% of frame height. Steam vent active — horizontal white jet at 2m height catches overhead fluorescent light. Emergency alarm strobe: white pulse cycling at 2Hz — hard shadows snapping across metal surfaces. Workers in worn coveralls visible as blurred distant figures.",
    "lighting_brief": "Alarm strobe: white 5600K, cycling at 0.5Hz — spikes to 20:1 on each flash. Base: overhead emergency fluorescent strips — green-white 5000K wash at 15% intensity between flashes. Industrial practical: amber halogen on valve gauges — 2700K pin sources. Steam backlit by fluorescent overhead — diffused glow. Base ratio 6:1, alarm flash 12:1.",
    "camera": "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 800, 180deg shutter",
    "colour": {"dominant": "#1A2215", "accent": "#E8F040", "blacks": "#0A0D08"},
    "dop_ref": "Denis Villeneuve / Arrival (2016) — interior industrial scale"
  },
  "int_voss_apartment_night": {
    "scene_ids": ["SCN_004"],
    "slug": "INT. VOSS APARTMENT — LOWER STACK — LATE NIGHT",
    "ref_image": null,
    "seed": 44,
    "canonical": "Cramped single-room apartment in a lower stack block. Walls: peeling paint over exposed concrete, improvised shelving of salvaged planks, stacked containers, tools. Ceiling: exposed pipe bundles running diagonally, single wire-hung practical lamp (amber, cloth-shade). Narrow window with condensation on the glass — neon glow bleeding through from building exterior. Floor: worn linoleum, random objects. Furniture: repurposed industrial crates as seating, one salvaged chair. Everything dense and layered — the visual language of survival.",
    "lighting_brief": "Key: practical desk lamp 2700K at camera-right — small, warm, only 60W equivalent. Creating intimate amber circle within larger darkness. Fill: zero. Ambient: amber neon exterior seeping through window behind — barely 1% contribution, just separation. Deep shadows fill 70% of frame. Ratio 6:1.",
    "camera": "ARRI Alexa 35, Cooke Anamorphic /i 50mm T2.8, ISO 1600, 180deg shutter",
    "colour": {"dominant": "#1E1510", "accent": "#C87820", "blacks": "#0C0A07"},
    "dop_ref": "Alfonso Cuaron / Children of Men (2006) — domestic late-night interior"
  },
  "int_civic_atrium_morning": {
    "scene_ids": ["SCN_005"],
    "slug": "INT. CIVIC ATRIUM — DISTRICT ZERO CENTRAL CORE — MORNING",
    "ref_image": null,
    "seed": 55,
    "canonical": "Vast civic atrium: polished white marble floor 80m across. High glass ceiling — diffused grey morning sky visible above. Monumental propaganda screens 12m tall on the east wall — precise sans-serif typography, institutional imagery. Steel and glass balconies on three levels above ground floor. Ground floor: streams of citizens moving in organised patterns — hundreds of figures, dense but orderly. Upper balcony (level 2): glass-and-steel railing, Vale's observation position. The architecture expresses control through immaculate emptiness and scale.",
    "lighting_brief": "Key: diffused daylight through high glass ceiling — overcast 6000K, flat overhead. Ground: marble bounce adding subtle fill from below. Upper balcony: harder shaft of directional daylight through narrower window — 4:1 ratio on Vale. No warm practicals. Clean, clinical, oppressive perfection. Overall ratio 3:1 in atrium, 5:1 on balcony.",
    "camera": "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 400, 180deg shutter",
    "colour": {"dominant": "#C8D0D0", "accent": "#D4AF6A", "blacks": "#1A1A18"},
    "dop_ref": "Roger Deakins / Skyfall (2012) — Silva's island interior architecture"
  },
  "int_black_market_sublevel_day": {
    "scene_ids": ["SCN_006"],
    "slug": "INT. BLACK MARKET EXCHANGE — VENTILATION SUBLEVEL — DAY",
    "ref_image": null,
    "seed": 66,
    "canonical": "Underground ventilation sublevel converted into an illegal signal market. Dense: vendor stalls made from scavenged server racks, cable-draped canopies, stacked monitors at varying heights. Ceiling: exposed ventilation ductwork — rectangular 60cm ducts running in a grid, with dust-covered grilles admitting thin grey daylight shafts. Wiring bundles looping between stall uprights. Neon signs in improvised Cyrillic-adjacent lettering — cyan and amber. Ground: bare concrete, moisture seeping from walls. 40+ people as background — specific details, not a crowd blur.",
    "lighting_brief": "Primary: amber LED strips under stall tables — 2000K, warm, from below creating uplight on vendor faces. Neon: cyan signage one side, amber the other — strong colour clash at 2m height. Daylight: thin grey shafts from ventilation grilles above — 6000K, narrow, cutting through haze. Result: warm amber foreground, colour neon mid, cold grey from above. Ratio 7:1.",
    "camera": "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 1600, 180deg shutter",
    "colour": {"dominant": "#2A1A0A", "accent": "#E8890A", "blacks": "#0F0A05"},
    "dop_ref": "Denis Villeneuve / Blade Runner 2049 (2017) — underground market"
  },
  "int_security_ops_center_day": {
    "scene_ids": ["SCN_007"],
    "slug": "INT. SECURITY OPERATIONS CENTER — DAY",
    "ref_image": null,
    "seed": 77,
    "canonical": "Control room occupying a converted upper-level space. Wall of displays: 12 screens in 4×3 grid showing live city schematic, sector heat maps, movement tracking. Displays: dark glass, cold blue-cyan glow. Analyst stations in rows: 8 workstations, all facing the wall display. Overhead: strip lighting dimmed to 10%. One large window behind analysts: cold grey exterior view providing backlight silhouette separation. Vale's position: standing 2m back from the display wall, arms behind back — the only person not seated.",
    "lighting_brief": "Key: screen glow — cold cyan-blue 6500K washing analysts from front. Overhead: dimmed to near-zero — 10% of rated output. Window: cold grey exterior backlight providing rim on analysts. Vale backlit — near-silhouette with cold edge. Zero warm sources. Ratio 9:1 in shadows, 3:1 on illuminated analyst faces.",
    "camera": "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 800, 180deg shutter",
    "colour": {"dominant": "#0D1B2A", "accent": "#00C8FF", "blacks": "#080C10"},
    "dop_ref": "David Fincher / The Social Network (2010) — ops room cold interior"
  },
  "int_service_spine_night": {
    "scene_ids": ["SCN_008", "SCN_010"],
    "slug": "INT. SEALED SERVICE SPINE — NIGHT",
    "ref_image": null,
    "seed": 88,
    "canonical": "Underground maintenance tunnel buried in the city's structural skeleton. Symmetrical bilateral composition with extreme central vanishing point. Wooden plank walls with horizontal steel crossbeam supports every 2m — aged wood, mineral deposits, surface rust. Corroded iron pipe bundles along both lower walls at floor level. Two parallel narrow-gauge railway tracks in dust-covered concrete floor. Emergency floor-level fluorescent strips at intervals on right wall — green-tinted 4000K, receding into atmospheric fog. Ancient relay control panel on left wall at mid-point: amber OLED backlit gauges, physical toggle switches, brass identification plaques. Absolute darkness beyond 8 metres ahead.",
    "lighting_brief": "Key: floor-level emergency fluorescent strips at right wall — green 4000K, extremely low angle, creating long horizontal shadows. Control panel: amber OLED back-glow 2700K — only visible warm source at close range. Fog/atmosphere: micro-particles in tunnel air scattering floor strips. Overhead: zero light — absolute ceiling darkness. Ratio 12:1. ISO pushed — visible grain.",
    "camera": "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 3200, 180deg shutter",
    "colour": {"dominant": "#0A150A", "accent": "#40B040", "blacks": "#050805"},
    "dop_ref": "Roger Deakins / Sicario (2015) — sub-tunnel NVG sequence"
  },
  "int_observation_chamber": {
    "scene_ids": ["SCN_009"],
    "slug": "INT. EXTERNAL OBSERVATION CHAMBER — CONTINUOUS",
    "ref_image": null,
    "seed": 99,
    "canonical": "Industrial observation chamber at massive scale — the hidden truth of the wall's interior. Pumping machinery filling the walls: large hydraulic cylinders, corroded copper piping with verdigris, pressure gauges, metal walkways at multiple heights. A bank of mechanical shutters across the outer wall: steel slats 30cm wide, hinged, motorised — currently opening. Through the opening shutters: the impossible view — organised lights in the far distance, the outside world that was declared dead. Red alarm ceiling strip flooding the chamber — 360-degree wall wash. Two competing light sources at war.",
    "lighting_brief": "Red alarm: ceiling strip — 2700K red, wall-washing all interior surfaces. Through shutters: cold grey-blue exterior ambient — 7000K, growing stronger as shutters open. Interior vs exterior war: warm red vs cold blue-grey at the shutter threshold. Ratio 8:1 inside. Alarm active.",
    "camera": "ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 800, 180deg shutter",
    "colour": {"dominant": "#1A0505", "accent": "#FF2010", "blacks": "#0A0202"},
    "dop_ref": "Alfonso Cuaron / Children of Men (2006) — revelation exterior light"
  },
  "int_voss_apartment_predawn": {
    "scene_ids": ["SCN_011"],
    "slug": "INT. VOSS APARTMENT — PRE-DAWN",
    "ref_image": null,
    "seed": 121,
    "canonical": "Same apartment as SCN_004, but now pre-dawn. The practical desk lamp is off — dead. The single window admits the only light: cold pre-dawn blue, 4500K, a thin horizontal bar of grey-blue across the floor and lower walls. The rest of the apartment is in near-absolute darkness. Objects are shapes, not details. Two human presences in the room — revealed only by the cold exterior light edge on hair and shoulder. Then: the door at frame-right begins to fracture at the lock housing — first the paint chips, then the frame splinters.",
    "lighting_brief": "Pre-dawn exterior: 4500K cold blue through small window — single source, extremely low intensity. Acts as ambient wash from one direction only. No practicals. Faces: near-darkness, detail only from cold exterior bounce. Ratio 15:1. Then: door detonation — practical explosion flash, white 5600K, 1/24sec burst. Absolute contrast with dread silence before it.",
    "camera": "ARRI Alexa 35, Cooke Anamorphic /i 50mm T2.8, ISO 3200, 180deg shutter",
    "colour": {"dominant": "#12100E", "accent": "#6080C0", "blacks": "#080706"},
    "dop_ref": "Roger Deakins / No Country for Old Men (2007) — pre-dawn interior, dread before violence"
  }
}
```

---

## ETAPE 3 — `production/storyboard.json`

**Quoi :** Le storyboard complet — 35 shots avec des briefs de production DOP-grade.
Ce fichier est la source de vérité pour `gen_shots.py`.
Chaque shot est une instruction de tournage, pas une description.

**Format d'un shot (nouvelle méthode) :**

```json
{
  "shot_id": "SCN_002_SHOT_001",
  "scene_id": "SCN_002",
  "location_key": "int_transit_corridor_night",
  "characters": ["nara"],
  "primary_character": "nara",
  "shot_type": "wide",
  "camera_movement": "follow",
  "camera_spec": "32mm anamorphic, T2.3, ISO 1600, handheld",
  "composition": "Nara occupies lower-left third, head at 60% frame height. Corridor vanishing point at right third. Her forward motion creates depth.",
  "action_brief": "Mid-sprint, left leg forward, wrist display flashing amber pressure alert from below — face lit in amber pulse rhythm. Controlled urgency, not panic.",
  "lighting_context": "Amber cage lamp backlight from 30m ahead. Wrist display amber fill from below on each pulse. Deep shadow on right side.",
  "emotion_intent": "Determined competence. This is her environment — she runs here, she knows this corridor.",
  "duration_sec": 5,
  "state_override": null,
  "audio_brief": "Boots on steel grating at run pace. Distant mechanical hum of corridor systems. Wrist display amber beep — once, twice, then gone."}
```

**Contenu complet — 35 shots :**

```json
{
  "title": "District Zero EP01 — Storyboard DOP-grade v1.0",
  "total_shots": 35,
  "scenes_axis": {
    "SCN_001": {"axis": "N/A — no characters", "note": ""},
    "SCN_002": {"axis": "Nara moves right-to-left (toward camera)", "note": "Single character — axis fixed by movement direction"},
    "SCN_003": {"axis": "Nara faces valve panel (screen-right)", "note": ""},
    "SCN_004": {"axis": "Nara right / Elian left — 180° line on table between them", "note": "Do NOT cross for 2-shot cuts"},
    "SCN_005": {"axis": "Vale on upper balcony faces atrium floor (screen-down)", "note": "POV from balcony down = OK. POV from floor up = OK. No crossing."},
    "SCN_006": {"axis": "Mira left / Nara right — 180° line on the display between them", "note": ""},
    "SCN_007": {"axis": "Vale faces display wall (screen-left)", "note": "Analyst POVs: all facing screen = same direction"},
    "SCN_008": {"axis": "Characters move left-to-right (into tunnel depth)", "note": ""},
    "SCN_009": {"axis": "Shutters at screen-right — characters face right toward exterior light", "note": "Cutaway to exterior: match eyeline direction"},
    "SCN_010": {"axis": "Sprint direction: left-to-right away from pursuit (pursuit enters from screen-right)", "note": "CRITICAL: maintain for chase logic. Nara always escaping screen-left."},
    "SCN_011": {"axis": "Nara right / Elian left — IDENTICAL to SCN_004", "note": "CRITICAL: same apartment, same axis. Door at screen-left. Match SCN_004 for continuity."}
  },
  "shots": [
    {
      "shot_id": "SCN_001_SHOT_001",
      "scene_id": "SCN_001",
      "location_key": "ext_outer_wall_night",
      "characters": [],
      "primary_character": null,
      "shot_type": "ultra_wide",
      "camera_movement": "static",
      "camera_spec": "32mm anamorphic, T2.3, ISO 1600, tripod low, 30cm off ground",
      "composition": "Seawall occupies lower third. Drowned skyline fills upper 65% — individual towers distinct. Black water in extreme foreground as mirror. Searchbeam sweeping mid-frame.",
      "action_brief": "Black water churning against the seawall base. Searchbeam cutting left-to-right. Drowned city skyline static and dead behind. An establishing shot that says: this world is already finished.",
      "lighting_context": "Single 18K HMI searchbeam sweeping. Amber window-grid points in drowned city. Black water surface catching each beam pass.",
      "emotion_intent": "Dread as beauty. The apocalypse has already happened and nobody announced it.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_001_SHOT_002",
      "scene_id": "SCN_001",
      "location_key": "ext_outer_wall_night",
      "characters": [],
      "primary_character": null,
      "shot_type": "medium",
      "camera_movement": "static",
      "camera_spec": "32mm anamorphic, T2.3, ISO 1600, tripod, slight Dutch tilt 3deg",
      "composition": "Searchbeam source at upper-right. Beam crossing mid-frame left to right. Water surface occupying lower 35%. 3-degree Dutch tilt.",
      "action_brief": "Searchbeam sweeping across the water surface in a slow, mechanical arc. Prison-yard rhythm. The beam finds nothing — it always finds nothing.",
      "lighting_context": "HMI searchbeam as moving key. Water reflecting the beam passing over it. Between passes: near-total darkness.",
      "emotion_intent": "The city is a prison and the guards don't need to see faces to maintain control.",
      "duration_sec": 3
    },
    {
      "shot_id": "SCN_002_SHOT_001",
      "scene_id": "SCN_002",
      "location_key": "int_transit_corridor_night",
      "characters": ["nara"],
      "primary_character": "nara",
      "shot_type": "wide",
      "camera_movement": "follow_handheld",
      "camera_spec": "32mm anamorphic, T2.3, ISO 1600, handheld follow at running pace",
      "composition": "Nara lower-left third, head at 60% height. Corridor vanishing point holds right-centre. Her forward motion creates depth. Amber wrist display pulse visible at hip level.",
      "action_brief": "Mid-sprint, left leg forward. Wrist display flashing amber pressure alert below her chin on each pulse — rhythm of urgency. She's not lost, she's solving a problem at running speed.",
      "lighting_context": "Backlight: amber cage lamp 30m ahead. Wrist display: amber pulse from below on each flash. Steam jet at mid-corridor catching backlight. Face in partial shadow, lit only on pulse.",
      "emotion_intent": "Controlled competence in motion. This is her environment — she runs here, she knows this floor.",
      "duration_sec": 5
    },
    {
      "shot_id": "SCN_002_SHOT_002",
      "scene_id": "SCN_002",
      "location_key": "int_transit_corridor_night",
      "characters": ["nara"],
      "primary_character": "nara",
      "shot_type": "close",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 1600, tripod",
      "composition": "Wrist display occupies centre-frame. Her face above in shallow focus, expression readable. Corridor in deep bokeh behind.",
      "action_brief": "She stops. A sealed route blinks on the map display — 2 seconds — then blinks off and disappears. Her thumb hovers, then captures the image. The gesture is precise, practiced.",
      "lighting_context": "Wrist display glow as key — amber-orange, from below. Corridor cage lamp as backlight at distance. Face: display glow only.",
      "emotion_intent": "The moment of discovery. She notices what she wasn't meant to notice — and she knows immediately.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_002_SHOT_003",
      "scene_id": "SCN_002",
      "location_key": "int_transit_corridor_night",
      "characters": ["nara"],
      "primary_character": "nara",
      "shot_type": "medium",
      "camera_movement": "static",
      "camera_spec": "32mm anamorphic, T2.3, ISO 1600, tripod",
      "composition": "Nara left third, pausing at junction. The unmapped corridor entrance dark at right two-thirds. Threshold composition: she is at the edge of the known world.",
      "action_brief": "She pauses at the mouth of an unmapped access corridor. One step forward, one hand on the wall edge. Looking into darkness. Then she steps through.",
      "lighting_context": "Corridor cage lamp from behind — creates her silhouette against the unmapped darkness ahead. Zero light in the unmapped section. Threshold lighting.",
      "emotion_intent": "The choice. She could turn back. She doesn't.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_003_SHOT_001",
      "scene_id": "SCN_003",
      "location_key": "int_pressure_valve_chamber_night",
      "characters": ["nara"],
      "primary_character": "nara",
      "shot_type": "medium_wide",
      "camera_movement": "static",
      "camera_spec": "32mm anamorphic, T2.3, ISO 800, tripod",
      "composition": "Nara at lower-left third against the valve assembly — machinery filling the frame at 80% height behind her. Workers as distant blurred figures at right background. Alarm strobe creating hard flash-shadows.",
      "action_brief": "Both hands on a valve wheel, turning hard against pressure. Feet braced, body weight forward. Alarm strobing. The machinery dwarfs her — she is tiny against the industrial scale.",
      "lighting_context": "Alarm strobe: white pulse at 0.5Hz — each flash slamming hard shadows across metal surfaces. Base: green-white emergency fluorescent at 15% between flashes. Steam backlit by overhead. Her face: strobe-lit in flash, dark between.",
      "emotion_intent": "Physical competence against overwhelming scale. She is small in this space but she knows what to do.",
      "duration_sec": 5,
      "audio_brief": "ALARM: 110dB industrial klaxon cycling at 0.5Hz. Hydraulic pressure groaning through the manifolds. Steam jet hiss at mid-register. Metal valve wheel grinding under load. Then the alarm CUTS — sudden silence hits like a physical impact."
    },
    {
      "shot_id": "SCN_003_SHOT_002",
      "scene_id": "SCN_003",
      "location_key": "int_pressure_valve_chamber_night",
      "characters": ["nara"],
      "primary_character": "nara",
      "shot_type": "close",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 800, tripod",
      "composition": "Tight on Nara's face — centre-frame. The moment the alarm cuts. Her head rising, expression changing.",
      "action_brief": "The alarm dies. Silence. Her hands release the valve. She looks up. The chamber returns to white fluorescent work light. She checks the wrist display.",
      "lighting_context": "Post-alarm: white overhead fluorescent — harsh, flat, institutional. The colour warmth of the alarm is gone. Cold industrial white.",
      "emotion_intent": "From crisis to clarity. The immediate danger is gone. The deeper problem just became visible.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_003_SHOT_003",
      "scene_id": "SCN_003",
      "location_key": "int_pressure_valve_chamber_night",
      "characters": ["nara"],
      "primary_character": "nara",
      "shot_type": "medium",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 800, tripod",
      "composition": "Nara slightly right-of-centre, wrist display raised. Worker visible at left edge, turning away. Space between them deliberate — she is already somewhere else mentally.",
      "action_brief": "She looks at the hidden route on her wrist display while a worker mentions the maintenance update was signed by Central Authority. She understands: this is not a technical error.",
      "lighting_context": "White institutional overhead. Wrist display amber glow on her face from below — only warm element in the frame.",
      "emotion_intent": "The realisation. The maintenance error was not an error.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_004_SHOT_001",
      "scene_id": "SCN_004",
      "location_key": "int_voss_apartment_night",
      "characters": ["nara", "elian"],
      "primary_character": "nara",
      "shot_type": "medium",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 1600, tripod",
      "composition": "Nara right, Elian left. Wrist display between them catching both faces in amber glow. Cramped apartment filling the space around them. Both in profile — facing each other across the small table.",
      "action_brief": "Nara places the captured map route in front of her father. His eyes drop to it. He freezes. A long beat. Then his jaw tightens.",
      "lighting_context": "Desk lamp as key — amber 2700K, from right. Wrist display additional amber fill between them. Deep shadow filling apartment behind. Both faces partly lit, partly in shadow.",
      "emotion_intent": "He recognises what he's seeing. He has seen this before, under different circumstances.",
      "duration_sec": 5
    },
    {
      "shot_id": "SCN_004_SHOT_002",
      "scene_id": "SCN_004",
      "location_key": "int_voss_apartment_night",
      "characters": ["elian"],
      "primary_character": "elian",
      "shot_type": "close",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 1600, tripod",
      "composition": "Tight on Elian's face — centre-frame. The dialogue is over. He is looking slightly left of camera — not at her, at the wall. The weight of the secret.",
      "action_brief": "He says: 'Because in this city, hidden doors are never just doors.' He doesn't look at her when he says it. He looks away. He has always known this moment would come.",
      "lighting_context": "Desk lamp from right — amber key on his cheek and brow. Left side in deep shadow. The broken capillaries on his nose visible under the warm light.",
      "emotion_intent": "Suppressed knowledge breaking to the surface. He has been carrying this for years.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_005_SHOT_001",
      "scene_id": "SCN_005",
      "location_key": "int_civic_atrium_morning",
      "characters": [],
      "primary_character": null,
      "shot_type": "ultra_wide",
      "camera_movement": "static",
      "camera_spec": "32mm anamorphic, T2.3, ISO 400, tripod high angle",
      "composition": "Atrium floor fills lower 60% — hundreds of citizens as textured movement. Giant propaganda screen at far wall. Glass balcony visible at upper-right. The authority architecture framing everything.",
      "action_brief": "Director Rook addresses the district from the giant screens — his face 10 metres tall, voice echoing in the marble space. Citizens move through below in patterns that suggest choreography, not freedom.",
      "lighting_context": "Diffused morning daylight through glass ceiling — cold, flat, institutional. Screen glow adding cold blue to the citizens below. The warmth of humanity has been architecturally removed.",
      "emotion_intent": "Scale as control. The citizen is made small by design.",
      "duration_sec": 5
    },
    {
      "shot_id": "SCN_005_SHOT_002",
      "scene_id": "SCN_005",
      "location_key": "int_civic_atrium_morning",
      "characters": ["vale"],
      "primary_character": "vale",
      "shot_type": "medium",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 400, tripod",
      "composition": "Vale at centre-frame on the glass balcony, slightly elevated. Glass railing in foreground bokeh. Atrium floor and citizens visible as deep background. The aide at right edge, smaller frame.",
      "action_brief": "An aide hands Vale a security alert tablet. He reads it — his expression does not change. He says 'Put her under passive watch' without taking his eyes from the atrium floor. The aide hesitates. Vale has already stopped listening.",
      "lighting_context": "Directional window light from right — harder key than atrium floor, 5:1 ratio. Cold 6000K. No warmth on Vale. The atrium crowd below: flat diffused, 3:1.",
      "emotion_intent": "A predator identifying a thread. No urgency — he has time. He has all the time.",
      "duration_sec": 5
    },
    {
      "shot_id": "SCN_006_SHOT_001",
      "scene_id": "SCN_006",
      "location_key": "int_black_market_sublevel_day",
      "characters": ["mira", "nara"],
      "primary_character": "mira",
      "shot_type": "medium",
      "camera_movement": "static",
      "camera_spec": "32mm anamorphic, T2.3, ISO 1600, tripod",
      "composition": "Mira left-of-centre, bent over the display spread. Nara right edge. Market activity behind and around them — ambient movement of traders and buyers. Neon cyan and amber lighting separating them from background.",
      "action_brief": "Mira studies Nara's stolen map and lays it over archived infrastructure data. Her finger traces a route. A new path appears: leading toward the outer wall. She doesn't smile — she calculates.",
      "lighting_context": "Amber LED under-table glow as key on Mira's face — warm, from below. Neon cyan trace from left wall catching Nara's cheek. Market depth: amber and cyan contrast behind. Atmospheric haze.",
      "emotion_intent": "Mira is reading the city the way engineers read structural drawings. This is her language.",
      "duration_sec": 5
    },
    {
      "shot_id": "SCN_006_SHOT_002",
      "scene_id": "SCN_006",
      "location_key": "int_black_market_sublevel_day",
      "characters": ["mira", "nara"],
      "primary_character": "nara",
      "shot_type": "close",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 1600, tripod",
      "composition": "Two-shot, tight. Mira slightly behind and right, Nara in foreground left. Both looking at the display between them. The question about survival hanging in the space.",
      "action_brief": "Mira says: 'The better question is whether you survive after I do.' Nara holds Mira's look. Neither blinks. A decision is being made in this silence.",
      "lighting_context": "Display glow as fill on both faces — cold blue from the infrastructure map. Market amber from behind as separation light.",
      "emotion_intent": "Two people calculating each other's risk. Both reaching the same conclusion at the same speed.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_007_SHOT_001",
      "scene_id": "SCN_007",
      "location_key": "int_security_ops_center_day",
      "characters": [],
      "primary_character": null,
      "shot_type": "wide",
      "camera_movement": "static",
      "camera_spec": "32mm anamorphic, T2.3, ISO 800, tripod",
      "composition": "Wall of monitors fills left two-thirds of frame — live city schematic with moving data points. Analysts at stations in middle ground. Vale standing 2m back, arms behind, barely visible — near-silhouette against the display wall.",
      "action_brief": "Live city schematic tracks a movement signature converging on the outer sectors. Analysts update coordinates without speaking. Vale watches — and does not give the order to intercept.",
      "lighting_context": "Screen wall: cold cyan-blue 6500K key on all analyst faces — from the front. Overhead near-zero. Vale: backlit only — cold edge from exterior window. Near-silhouette.",
      "emotion_intent": "The watcher watching. He chooses not to act — which is itself an action.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_007_SHOT_002",
      "scene_id": "SCN_007",
      "location_key": "int_security_ops_center_day",
      "characters": ["vale"],
      "primary_character": "vale",
      "shot_type": "close",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 800, tripod",
      "composition": "Tight on Vale — centre-frame. The display wall's cold blue glow on his face. Window rim-light behind. He faces camera slightly off-axis.",
      "action_brief": "He says: 'If she reaches the gate, I want to know what she thinks she saw.' A pause. 'Don't stop her.' His eyes remain on the display. His decision is already made.",
      "lighting_context": "Display wall: cold cyan-blue face-front light. Window cold backlight behind. Ratio 9:1. No warmth on his face anywhere.",
      "emotion_intent": "Calculation wearing a face. He is not suppressing emotion — he genuinely has none about this.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_008_SHOT_001",
      "scene_id": "SCN_008",
      "location_key": "int_service_spine_night",
      "characters": ["nara", "mira"],
      "primary_character": "nara",
      "shot_type": "wide",
      "camera_movement": "static",
      "camera_spec": "32mm anamorphic, T2.3, ISO 3200, tripod",
      "composition": "Extreme vanishing-point perspective with Nara left-of-centre foreground, Mira smaller at right mid-ground — both descending into the tunnel depth. Floor-level green emergency strips creating long horizontal shadows.",
      "action_brief": "Nara and Mira move through the tunnel — Nara first, one hand on the pipe bundle at the wall. Mira three steps behind. Both moving without hesitation — they've committed to this.",
      "lighting_context": "Floor-level green fluorescent strips at right wall — green 4000K up-light from extreme low angle. Amber control panel glow at mid-distance. Deep darkness ahead. Their faces lit green from below.",
      "emotion_intent": "Two people descending into the city's hidden skeleton. The tunnel has been here for decades — waiting.",
      "duration_sec": 5
    },
    {
      "shot_id": "SCN_008_SHOT_002",
      "scene_id": "SCN_008",
      "location_key": "int_service_spine_night",
      "characters": ["mira"],
      "primary_character": "mira",
      "shot_type": "close",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 3200, tripod",
      "composition": "Mira close, slightly right-of-centre — hands at the control panel, face lit by the amber OLED glow from below. Nara out-of-focus at left behind her, watching the dark passage.",
      "action_brief": "Mira powers up the buried control panel. Capacitor whine. Relay clicks. Amber gauges lighting up one by one. Her face intent — reading the system.",
      "lighting_context": "Control panel amber OLED glow — the only warm light in the tunnel. Lighting her face from directly below. Green floor strips provide cold ambient fill from behind.",
      "emotion_intent": "She's talked to machines like this her whole life. This one is just older.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_008_SHOT_003",
      "scene_id": "SCN_008",
      "location_key": "int_service_spine_night",
      "characters": ["nara"],
      "primary_character": "nara",
      "shot_type": "close",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 3200, tripod",
      "composition": "Tight on Nara — facing camera, watching the dark passage behind them. Her face in green under-light. The darkness behind her is the threat.",
      "action_brief": "Nara watches the dark passage while Mira works. She says nothing. She is counting something — footsteps, seconds. She doesn't like being in the open.",
      "lighting_context": "Green floor strips as key — cold from below, long shadows upward. Amber panel glow as very faint warm bounce from behind.",
      "emotion_intent": "Tactical awareness. She is providing overwatch while Mira works. Professional.",
      "duration_sec": 3
    },
    {
      "shot_id": "SCN_008_SHOT_004",
      "scene_id": "SCN_008",
      "location_key": "int_service_spine_night",
      "characters": ["mira"],
      "primary_character": "mira",
      "shot_type": "close",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 3200, tripod",
      "composition": "On Mira's hands at the panel, then pulling to her face as the gate-unlock mechanism sounds.",
      "action_brief": "The system identifies an external containment access route. Mira reads the identifier. Her expression shifts — this is not what she expected. She unlocks the gate. A deep mechanical clunk.",
      "lighting_context": "Panel amber glow. The gate-unlock indicator light: a single green LED point-source adding a cold green catch-light in her eyes.",
      "emotion_intent": "She expected a maintenance access. What she's found is something that shouldn't exist.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_009_SHOT_001",
      "scene_id": "SCN_009",
      "location_key": "int_observation_chamber",
      "characters": ["nara", "mira"],
      "primary_character": "nara",
      "shot_type": "wide",
      "camera_movement": "static",
      "camera_spec": "32mm anamorphic, T2.3, ISO 800, tripod, low position",
      "composition": "Nara and Mira small at left foreground — dwarfed by the chamber's machinery and scale. The shutters filling the right two-thirds, beginning to open. Light bleeding through the growing gap.",
      "action_brief": "Ancient mechanical shutters begin to open — motor strain, steel groaning. The gap widens. Cold grey-blue light from outside grows. Both characters are silhouetted against the opening.",
      "lighting_context": "Red alarm: ceiling wash — all interior surfaces red. Opening shutters: cold exterior grey-blue growing stronger. Two-source war: warm red interior vs cold exterior revelation.",
      "emotion_intent": "The world they were told was dead is lighting up in front of them. The revelation is not dramatic — it is quiet and devastating.",
      "duration_sec": 5
    },
    {
      "shot_id": "SCN_009_SHOT_002",
      "scene_id": "SCN_009",
      "location_key": "int_observation_chamber",
      "characters": ["nara"],
      "primary_character": "nara",
      "shot_type": "close",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 800, tripod",
      "composition": "Tight on Nara's face — centre-frame. The exterior light source at camera-right, cold and growing. Her expression transitioning from caution to disbelief.",
      "action_brief": "She sees organised lights far beyond the wall. Ordered grid. Moving vehicles. She says 'They lied.' She says it very quietly, like a diagnosis.",
      "lighting_context": "Cold grey-blue exterior light from right as key — 7000K, hard edge on right cheek. Red alarm wash from above as fill — very faint, orange-red bounce. The exterior light wins.",
      "emotion_intent": "The specific, precise texture of realising your entire life was built on a lie. Not anger — not yet.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_009_SHOT_003",
      "scene_id": "SCN_009",
      "location_key": "int_observation_chamber",
      "characters": ["nara"],
      "primary_character": "nara",
      "shot_type": "medium",
      "camera_movement": "static",
      "camera_spec": "32mm anamorphic, T2.3, ISO 800, tripod",
      "composition": "Nara at right, the pumping machinery at left filling half the frame. She is looking down at what the machinery is connected to — the pipe bundles leading down through the floor.",
      "action_brief": "She sees industrial pumps in the wall structure. The pipes lead down — down to the lower sectors. She understands what the infrastructure is for. Poison in the water. Hidden in plain sight.",
      "lighting_context": "Red alarm ceiling wash — machinery all red. Cold exterior through shutters behind her. Her face: caught between both sources.",
      "emotion_intent": "The second blow. The first was discovering the lie. The second is understanding the crime.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_009_SHOT_004",
      "scene_id": "SCN_009",
      "location_key": "int_observation_chamber",
      "characters": ["nara", "mira"],
      "primary_character": "mira",
      "shot_type": "medium",
      "camera_movement": "static",
      "camera_spec": "32mm anamorphic, T2.3, ISO 800, tripod",
      "composition": "Mira pulling Nara by the arm toward the tunnel entrance. Both in red alarm wash. The shutters beginning to close behind them.",
      "action_brief": "The silent alarm floods the chamber red. Mira grabs Nara's arm: 'We need to go. Now.' Nara takes one last look at the outside lights before being pulled back into the tunnel.",
      "lighting_context": "Full red alarm wash — all surfaces crimson. Exterior light now closing as shutters begin to reverse.",
      "emotion_intent": "The urgency is Mira's — cold and tactical. The grief is Nara's — she hasn't finished looking.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_010_SHOT_001",
      "scene_id": "SCN_010",
      "location_key": "int_service_spine_night",
      "characters": ["nara", "mira"],
      "primary_character": "nara",
      "shot_type": "wide_handheld",
      "camera_movement": "follow_handheld_fast",
      "camera_spec": "32mm anamorphic, T2.3, ISO 3200, handheld at sprint",
      "composition": "Nara left, Mira right, both sprinting toward camera. Blast doors slamming sequentially behind them — depth collapsing in the pursuit.",
      "action_brief": "Security shutters slam down the corridor behind them — sequential, one every second, getting closer. Both sprinting at full speed, ducking under the last shutter. Pure kinetic energy.",
      "lighting_context": "Red alarm from above. Blast door sparks: white burst on each slam. Weapon-mounted lights from behind — cold 5600K sweeping. Smoke and dust scattering all sources.",
      "emotion_intent": "Pursuit. The machinery of the state, now in motion.",
      "duration_sec": 5
    },
    {
      "shot_id": "SCN_010_SHOT_002",
      "scene_id": "SCN_010",
      "location_key": "int_service_spine_night",
      "characters": [],
      "primary_character": null,
      "shot_type": "wide",
      "camera_movement": "static",
      "camera_spec": "32mm anamorphic, T2.3, ISO 3200, tripod at far end",
      "composition": "Armed units at the far tunnel entrance — silhouetted against bright HMI backlight from the corridor junction behind them. They advance in formation, weapon lights sweeping.",
      "action_brief": "Armed units pour into the shaft entrance at the far end. Tactical movement, weapon lights cutting through dust. Vale's voice over comms: 'Nara Voss. Stop running. The truth is not what you think it is.'",
      "lighting_context": "HMI backlight from junction behind — silhouetting the unit figures. Weapon lights from units sweeping toward camera. Dust scattering all sources.",
      "emotion_intent": "The state's precision against human panic. They are not rushing — they've already won, they just don't know it yet.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_010_SHOT_003",
      "scene_id": "SCN_010",
      "location_key": "int_service_spine_night",
      "characters": ["mira"],
      "primary_character": "mira",
      "shot_type": "medium",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 3200, tripod",
      "composition": "Mira at a side-duct opening at right — one arm reaching in, one foot already inside. She looks back once, then disappears.",
      "action_brief": "Mira finds the side duct — she knows this infrastructure, she mapped it. She goes. No goodbye. Tactical.",
      "lighting_context": "Red alarm. Weapon lights sweeping past the duct opening — brief flash of cold light across her as she enters.",
      "emotion_intent": "She's not abandoning Nara — she's covering a different escape route. She expects Nara to understand.",
      "duration_sec": 3
    },
    {
      "shot_id": "SCN_010_SHOT_004",
      "scene_id": "SCN_010",
      "location_key": "int_service_spine_night",
      "characters": ["nara"],
      "primary_character": "nara",
      "shot_type": "medium",
      "camera_movement": "static",
      "camera_spec": "32mm anamorphic, T2.3, ISO 3200, tripod",
      "composition": "Nara at a blast door that is closing — she slips through the narrowing gap as weapon lights reach her position. The door closes. She is gone.",
      "action_brief": "She dives through the closing blast door — barely. The door slams. The weapon lights reach the door surface — too late.",
      "lighting_context": "Red alarm. Weapon lights from behind. The closing blast door: sparks at the seam. Then dark.",
      "emotion_intent": "Escape. By the minimum possible margin.",
      "duration_sec": 3
    },
    {
      "shot_id": "SCN_011_SHOT_001",
      "scene_id": "SCN_011",
      "location_key": "int_voss_apartment_predawn",
      "characters": ["nara"],
      "primary_character": "nara",
      "shot_type": "medium",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 3200, tripod",
      "composition": "Nara entering through the apartment door — centre-frame, backlit by the faint pre-dawn blue from the window. Soaked, shaking slightly. The apartment in near-darkness around her.",
      "action_brief": "She returns home — wet, shaken, changed. She closes the door quietly behind her. She is carrying something enormous and trying not to show it.",
      "lighting_context": "Pre-dawn cold blue from window — the only source. Lighting her silhouette edge, not her face. Her face in near-total darkness.",
      "emotion_intent": "She has just seen the world she lives in for what it actually is. Everything that comes next begins here.",
      "duration_sec": 5,
      "state_override": "Dark hair wet and plastered to neck and temples. Jacket soaked through at shoulders and back. Skin: water drops catching blue light. Fatigue in jaw and shoulders. Slight visible tremor.",
      "audio_brief": "Door latch — barely audible. Distant city ambient bleeding through walls. Her breathing, slowing."
    },
    {
      "shot_id": "SCN_011_SHOT_002",
      "scene_id": "SCN_011",
      "location_key": "int_voss_apartment_predawn",
      "characters": ["elian"],
      "primary_character": "elian",
      "shot_type": "close",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 3200, tripod",
      "composition": "Tight on Elian's face as he sees her. He has been awake, waiting. His expression when he reads her face.",
      "action_brief": "Elian sees her face and knows. He doesn't speak. He doesn't need to. The secret he has carried for years has just walked through the door.",
      "lighting_context": "Cold pre-dawn window light from frame-right. His face: cool blue edge on the left cheek, near-darkness on the right.",
      "emotion_intent": "Recognition. He always knew this day was coming. He hoped it wouldn't be this soon.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_011_SHOT_003",
      "scene_id": "SCN_011",
      "location_key": "int_voss_apartment_predawn",
      "characters": ["nara"],
      "primary_character": "nara",
      "shot_type": "close",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 3200, tripod",
      "composition": "Tight on Nara — she has just heard it. The revelation about her father's role. Her face absorbing it.",
      "action_brief": "She recoils — not physically, internally. He says 'I helped design part of the flow control system.' The truth lands between them. She doesn't look away.",
      "lighting_context": "Cold blue from window. Both faces in the same cold light. No warmth. The warmth is gone.",
      "emotion_intent": "Betrayal and love fighting at the same moment. She doesn't know which will win.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_011_SHOT_004",
      "scene_id": "SCN_011",
      "location_key": "int_voss_apartment_predawn",
      "characters": ["elian"],
      "primary_character": "elian",
      "shot_type": "medium",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 3200, tripod",
      "composition": "Elian producing an encrypted drive from inside his jacket — holds it out to her. His face: this is the only act of courage he has left.",
      "action_brief": "He gives her the encrypted drive. His hands are not steady. He says: 'If they take me, this is the only thing that proves the system was built this way.'",
      "lighting_context": "Cold pre-dawn blue. His hands in slightly better light than his face — the drive in a thin cold beam.",
      "emotion_intent": "Atonement, not absolution. He knows it's too late for forgiveness. He's doing it anyway.",
      "duration_sec": 4
    },
    {
      "shot_id": "SCN_011_SHOT_005",
      "scene_id": "SCN_011",
      "location_key": "int_voss_apartment_predawn",
      "characters": ["nara", "elian"],
      "primary_character": "nara",
      "shot_type": "medium",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 3200, tripod",
      "composition": "Two-shot — Elian giving the instructions, Nara receiving them. The space between them: the width of what cannot be repaired.",
      "action_brief": "He says: 'Go to the freight tunnels. Find the relay called Lantern. Ask for Mira Sol. Open the city.' She takes the drive. Holds it. Her face: this is not what she wanted from him.",
      "lighting_context": "Cold pre-dawn shared light. Equal on both faces. Neither in shadow — no one hiding from the other now.",
      "emotion_intent": "The handoff of a mission that will consume what remains of both their lives.",
      "duration_sec": 5
    },
    {
      "shot_id": "SCN_011_SHOT_006",
      "scene_id": "SCN_011",
      "location_key": "int_voss_apartment_predawn",
      "characters": [],
      "primary_character": null,
      "shot_type": "close",
      "camera_movement": "static",
      "camera_spec": "50mm anamorphic, T2.8, ISO 3200, tripod on apartment door",
      "composition": "Extreme close — the apartment door lock housing. A thin line of corridor light under the door. Then: a shadow moving under the door. Then a second shadow.",
      "action_brief": "Tactical boots in the corridor outside — heard, then the shadow confirmed under the door. Heavy, deliberate, multiple pairs. Closing distance.",
      "lighting_context": "Interior pre-dawn blue. Corridor: cold white unit lighting under the door gap — a thin warning stripe.",
      "emotion_intent": "The last seconds. The knock that doesn't knock.",
      "duration_sec": 3
    },
    {
      "shot_id": "SCN_011_SHOT_007",
      "scene_id": "SCN_011",
      "location_key": "int_voss_apartment_predawn",
      "characters": ["nara", "elian"],
      "primary_character": "nara",
      "shot_type": "wide",
      "camera_movement": "static",
      "camera_spec": "32mm anamorphic, T2.3, ISO 3200, tripod wide, capturing both figures and the door",
      "composition": "Wide — both characters frame-right, door frame-left. The scale of the threat against the intimacy of the people. Then the door detonates.",
      "action_brief": "The door explodes inward. White flash. SMASH CUT TO BLACK. End of Episode 1.",
      "lighting_context": "Pre-dawn blue throughout. Then: door detonation — white flash, 1/24sec, burning out the frame. Then absolute black.",
      "emotion_intent": "End of the world they knew. Beginning of everything that follows.",
      "duration_sec": 3,
      "audio_brief": "SILENCE — 2 seconds of absolute silence before the breach. Then: DOOR DETONATION — shaped charge, immediate and overwhelming. White noise. SMASH CUT TO BLACK — silence again, total. End of episode."
    }
  ]
}
```

---

## ETAPE 4 — `production/dashboard.json`

Identique à la v2.0 — seeds, palettes, DOP refs. Le seed convention N×11 est verrouillé.
*(contenu inchangé — voir v2.0 ou lire directement depuis locations.json qui contient les mêmes données)*

Simplification : `dashboard.json` ne duplique plus `locations.json` — il ne contient que les seeds et les chemins vers les master plates générées.

```json
{
  "SCN_001": {"seed": 11, "location_key": "ext_outer_wall_night", "master_plate_path": null},
  "SCN_002": {"seed": 22, "location_key": "int_transit_corridor_night", "master_plate_path": null},
  "SCN_003": {"seed": 33, "location_key": "int_pressure_valve_chamber_night", "master_plate_path": null},
  "SCN_004": {"seed": 44, "location_key": "int_voss_apartment_night", "master_plate_path": null},
  "SCN_005": {"seed": 55, "location_key": "int_civic_atrium_morning", "master_plate_path": null},
  "SCN_006": {"seed": 66, "location_key": "int_black_market_sublevel_day", "master_plate_path": null},
  "SCN_007": {"seed": 77, "location_key": "int_security_ops_center_day", "master_plate_path": null},
  "SCN_008": {"seed": 88, "location_key": "int_service_spine_night", "master_plate_path": null},
  "SCN_009": {"seed": 99, "location_key": "int_observation_chamber", "master_plate_path": null},
  "SCN_010": {"seed": 110, "location_key": "int_service_spine_night", "master_plate_path": null},
  "SCN_011": {"seed": 121, "location_key": "int_voss_apartment_predawn", "master_plate_path": null}
}
```

---

## ETAPE 4bis — `production/grade.json`

**Quoi :** Document de grade d'épisode — le "show look" transversal qui garantit la cohérence chromatique entre SCN_001 et SCN_011.
Inspiré des fiches Look Development proposées par DNEG, ILM et les DPs de référence.
Chargé par `gen_location_refs.py` et `gen_shots.py` pour injecter le look de show dans chaque prompt de génération.

```json
{
  "show_look": {
    "reference": "Roger Deakins / Blade Runner 2049 (2017) + Sicario (2015) + Children of Men (2006)",
    "grade_intent": "Desaturated cold teals and deep blacks throughout. Warm amber practicals as the only warmth — always motivated, never decorative. Crushed blacks below 5% IRE. Highlights rolled off above 80%. No blown-out whites except intentional flash events.",
    "global_palette": {
      "black_floor": "#05080A",
      "shadow_mid": "#0D1520",
      "skin_key_warm": "#C87840",
      "cold_ambient": "#1A2B3C",
      "accent_warm": "#B86010",
      "accent_cold": "#2060A0"
    },
    "forbidden": [
      "Saturated colours (>30% saturation except motivated neon signs)",
      "Overhead fill light — zero ambient fills in interiors",
      "Warm daylight >4000K unless it is a motivated practical",
      "HDR-style blown highlights"
    ]
  },
  "per_scene_grade": {
    "SCN_001": "Cold and near-black — searchbeam only warm exception. Dominant #0A1520.",
    "SCN_002": "Amber warm dominant — single cage lamp in distance. Dominant #1C2B35.",
    "SCN_003": "Green-white strobe — most aggressive contrast in episode. Dominant #1A2215.",
    "SCN_004": "Amber intimate — smallest warmest space in episode. Dominant #1E1510.",
    "SCN_005": "Cold clinical — no warmth permitted. Dominant #C8D0D0.",
    "SCN_006": "Amber/cyan dual — visual chaos of the underground. Dominant #2A1A0A.",
    "SCN_007": "Cold cyan — coldest space in episode. Dominant #0D1B2A.",
    "SCN_008": "Green teal — tunnel, NVG register. Dominant #0A150A.",
    "SCN_009": "Red warm vs cold blue — war of two sources at the threshold. Dominant #1A0505.",
    "SCN_010": "Red alarm + cold weapon lights — pursuit palette. Dominant #0A150A.",
    "SCN_011": "Cold blue pre-dawn — stripping warmth from the apartment. Dominant #12100E."
  }
}
```

**Coût : $0 — création uniquement**

---

## ETAPE 5 — `production/dashboard.py`

Loader Python — lit les 3 fichiers sources (characters, locations, storyboard, dashboard).

```python
# production/dashboard.py
from __future__ import annotations
import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent

def _load(name: str) -> dict:
    return json.loads((_DIR / name).read_text(encoding="utf-8"))

def load_scene(scene_id: str) -> dict:
    data = _load("dashboard.json")
    if scene_id not in data:
        raise KeyError(f"Scene '{scene_id}' not found in dashboard.json")
    scene = data[scene_id]
    scene["location"] = load_location(scene["location_key"])
    return scene

def load_all_scenes() -> dict:
    dash = _load("dashboard.json")
    locs = _load("locations.json")
    for sid, scene in dash.items():
        scene["location"] = locs[scene["location_key"]]
    return dash

def load_all_characters() -> dict:
    return _load("characters.json")

def load_character(char_id: str) -> dict:
    data = _load("characters.json")
    if char_id not in data:
        raise KeyError(f"Character '{char_id}' not found in characters.json")
    return data[char_id]

def load_location(location_key: str) -> dict:
    data = _load("locations.json")
    if location_key not in data:
        raise KeyError(f"Location '{location_key}' not found in locations.json")
    return data[location_key]

def load_storyboard() -> list[dict]:
    return _load("storyboard.json")["shots"]

def load_shot_brief(shot_id: str) -> dict:
    shots = {s["shot_id"]: s for s in load_storyboard()}
    if shot_id not in shots:
        raise KeyError(f"Shot '{shot_id}' not found in storyboard.json")
    return shots[shot_id]

def update_master_plate_path(scene_id: str, path: str) -> None:
    data = _load("dashboard.json")
    data[scene_id]["master_plate_path"] = path
    (_DIR / "dashboard.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def update_character_ref(char_id: str, path: str) -> None:
    data = _load("characters.json")
    data[char_id]["ref_image"] = path
    (_DIR / "characters.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
```

---

## ETAPE 6 — `production/gen_character_refs.py`

**Phase A — $0.03 × 5 = $0.15**
Génère un portrait de référence par personnage via FLUX.2 Pro avec DOP-grade portrait brief.
Les refs générées remplacent tout ce qui était dans `_archive/`.

```python
"""
production/gen_character_refs.py
=================================
Génère les portraits de référence pour chaque personnage via FLUX.2 Pro.
Source: characters.json -> portrait_brief (DOP-grade, pas de "describe what you want")

COUT : 5 personnages × $0.03 = $0.15
Usage : python production/gen_character_refs.py [--char nara] [--dry-run]
"""
from __future__ import annotations
import argparse, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.shot_pipeline import LOCKED_MODEL_P1, LOCKED_PARAMS, LOCKED_COST_P1, _load_env, _download
from production.dashboard import load_all_characters, update_character_ref
import cv2


def build_portrait_prompt(char_id: str, char: dict) -> str:
    pb = char["portrait_brief"]
    canonical = char["canonical"]
    seed_note = char.get("note", "")
    return (
        f'{{"character_canonical": "{canonical}", '
        f'"camera": "{pb["camera"]}", '
        f'"framing": "{pb["framing"]}", '
        f'"lighting": "{pb["lighting"]}", '
        f'"background": "{pb["background"]}", '
        f'"dop_ref": "{pb["dop_ref"]}", '
        f'"production_note": "Photorealistic, no illustration, no painting. Natural skin texture. '
        f'Exact canonical costume and appearance — zero deviation. {seed_note}"}}'
    )


def run(filter_chars: list[str], dry_run: bool) -> None:
    _load_env(ROOT)
    characters = load_all_characters()
    targets = filter_chars if filter_chars else list(characters.keys())
    targets = [c for c in targets if c in characters]

    cost = len(targets) * LOCKED_COST_P1
    print(f"\nPortraits à générer : {len(targets)} — coût estimé : ${cost:.2f}")

    if dry_run:
        for cid in targets:
            char = characters[cid]
            print(f"  {cid} | {char['full_name']} | seed={char['note'].split('seed: ')[1].split('.')[0] if 'seed:' in char.get('note','') else 'N/A'}")
        print("\n[DRY-RUN] Aucun appel API.")
        return

    import replicate
    out_dir = ROOT / "production/character_refs"
    out_dir.mkdir(parents=True, exist_ok=True)

    total_cost = 0.0
    for cid in targets:
        char = characters[cid]
        prompt = build_portrait_prompt(cid, char)
        seed_str = char.get("note", "")
        seed = int(seed_str.split("seed: ")[1].split(".")[0]) if "seed:" in seed_str else 42
        print(f"\n[{cid}] {char['full_name']} — seed={seed} — appel FLUX.2 Pro...")
        t0 = time.monotonic()
        out = replicate.run(
            LOCKED_MODEL_P1,
            input={
                "prompt": prompt,
                "aspect_ratio": "1:1",
                "resolution": LOCKED_PARAMS["p1_resolution"],
                "seed": seed,
                "output_format": LOCKED_PARAMS["p1_output_format"],
                "output_quality": LOCKED_PARAMS["p1_output_quality"],
                "safety_tolerance": LOCKED_PARAMS["p1_safety_tolerance"],
            },
        )
        elapsed = time.monotonic() - t0
        img = _download(str(out))
        out_path = out_dir / f"{cid}_ref.png"
        cv2.imwrite(str(out_path), img)
        update_character_ref(cid, str(out_path))
        total_cost += LOCKED_COST_P1
        print(f"  Sauvegardé : {out_path.name} ({img.shape[1]}×{img.shape[0]}) — {elapsed:.1f}s — ${total_cost:.2f} cumulé")

    print(f"\nTerminé. {len(targets)} portraits. Coût : ${total_cost:.2f}")
    print("ETAPE SUIVANTE : python production/run.py benchmark --dry-run")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--char", nargs="*", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.char, args.dry_run)
```

---

## ETAPE 7 — `production/gen_location_refs.py`

**Phase B — $0.03 × 10 = $0.30**
Génère un master plate par lieu avec DOP-grade prompt et seed fixe.

```python
"""
production/gen_location_refs.py
================================
Génère un master plate de référence pour chaque lieu via FLUX.2 Pro.
Source: locations.json -> canonical + lighting_brief + colour + dop_ref (DOP-grade)

COUT : 10 lieux × $0.03 = $0.30
Usage : python production/gen_location_refs.py [--loc int_transit_corridor_night] [--dry-run]
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.shot_pipeline import (
    SceneP1Params, build_p1_prompt,
    LOCKED_MODEL_P1, LOCKED_PARAMS, LOCKED_COST_P1, _load_env, _download,
)
from production.dashboard import load_location, update_master_plate_path
import cv2

# Maps scene_id to location_key for update_master_plate_path
import json as _json
def _scene_to_location_map(root: Path) -> dict[str, str]:
    dash = _json.loads((root / "production/dashboard.json").read_text(encoding="utf-8"))
    result = {}
    for sid, val in dash.items():
        lk = val["location_key"]
        if lk not in result:
            result[lk] = sid
    return result


def build_location_prompt(loc_key: str, loc: dict, grade: dict) -> str:
    colour = loc["colour"]
    show_look = grade["show_look"]["grade_intent"]
    forbidden = "; ".join(grade["show_look"]["forbidden"])
    return (
        f'{{"location_canonical": "{loc["canonical"]}", '
        f'"lighting_brief": "{loc["lighting_brief"]}", '
        f'"colour_grade": "Dominant {colour["dominant"]}, accent {colour["accent"]}, deep blacks {colour["blacks"]}. '
        f'Grade reference: {loc["dop_ref"]}. Show look: {show_look}. Forbidden: {forbidden}.", '
        f'"camera": "{loc["camera"]}", '
        f'"production_note": "Photorealistic, ARRI film grain, anamorphic, no people, environment only. '
        f'Maximum cinematic quality. Inspired by {loc["dop_ref"]}. Zero digital-art aesthetics."}}'
    )


def run(filter_locs: list[str], dry_run: bool) -> None:
    _load_env(ROOT)
    locs_data = _json.loads((ROOT / "production/locations.json").read_text(encoding="utf-8"))
    targets = filter_locs if filter_locs else list(locs_data.keys())
    targets = [l for l in targets if l in locs_data]
    s2l = _scene_to_location_map(ROOT)

    grade = _json.loads((ROOT / "production/grade.json").read_text(encoding="utf-8"))
    cost = len(targets) * LOCKED_COST_P1
    print(f"\nMaster plates à générer : {len(targets)} lieux — coût estimé : ${cost:.2f}")

    if dry_run:
        for lk in targets:
            loc = locs_data[lk]
            print(f"  {lk} | seed={loc['seed']} | scènes={loc['scene_ids']}")
        print("\n[DRY-RUN] Aucun appel API.")
        return

    import replicate
    out_dir = ROOT / "production/location_refs"
    out_dir.mkdir(parents=True, exist_ok=True)
    total_cost = 0.0

    for lk in targets:
        loc = locs_data[lk]
        prompt = build_location_prompt(lk, loc, grade)
        print(f"\n[{lk}] seed={loc['seed']} — appel FLUX.2 Pro...")
        t0 = time.monotonic()
        out = replicate.run(
            LOCKED_MODEL_P1,
            input={
                "prompt": prompt,
                "aspect_ratio": LOCKED_PARAMS["p1_aspect_ratio"],
                "resolution": LOCKED_PARAMS["p1_resolution"],
                "seed": loc["seed"],
                "output_format": LOCKED_PARAMS["p1_output_format"],
                "output_quality": LOCKED_PARAMS["p1_output_quality"],
                "safety_tolerance": LOCKED_PARAMS["p1_safety_tolerance"],
            },
        )
        elapsed = time.monotonic() - t0
        img = _download(str(out))
        out_path = out_dir / f"{lk}_master.png"
        cv2.imwrite(str(out_path), img)

        # Update dashboard pour la première scène utilisant ce lieu
        if lk in s2l:
            update_master_plate_path(s2l[lk], str(out_path))

        # Update locations.json avec le ref_image généré
        locs_data[lk]["ref_image"] = str(out_path)
        (ROOT / "production/locations.json").write_text(
            _json.dumps(locs_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        total_cost += LOCKED_COST_P1
        print(f"  Sauvegardé : {out_path.name} — {elapsed:.1f}s — ${total_cost:.2f} cumulé")

    print(f"\nTerminé. {len(targets)} master plates. Coût : ${total_cost:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--loc", nargs="*", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.loc, args.dry_run)
```

---

## ETAPE 8 — `production/benchmark_characters.py`

**Phase B (suite) — $0**
Valide les scores ArcFace des refs générées. Identifie les personnages à retaker avant la prod.

```python
"""
production/benchmark_characters.py
====================================
Valide les scores ArcFace des portraits de référence générés.
Lance une auto-comparaison intra-personnage si plusieurs angles générés.

COUT : $0 (ArcFace local, InsightFace buffalo_l)
Usage : python production/benchmark_characters.py [--char nara] [--verbose]
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.shot_pipeline import _score_arcface, _get_largest_face
from production.dashboard import load_all_characters, update_character_ref
import cv2

TARGET_SCORE = 0.85


def run(filter_chars: list[str], verbose: bool) -> None:
    characters = load_all_characters()
    targets = filter_chars if filter_chars else list(characters.keys())
    targets = [c for c in targets if c in characters]

    print(f"\n{'='*55}")
    print(f"  BENCHMARK ARCFACE — Portraits de référence")
    print(f"{'='*55}")

    passed, failed = [], []
    for cid in targets:
        char = characters[cid]
        ref_path = char.get("ref_image")
        if not ref_path or not Path(ref_path).exists():
            print(f"  {cid:<10} | MANQUANT — lancer gen_character_refs.py d'abord")
            failed.append(cid)
            continue
        img = cv2.imread(ref_path)
        if img is None:
            print(f"  {cid:<10} | ERREUR lecture image")
            failed.append(cid)
            continue
        face = _get_largest_face(img)
        if face is None:
            print(f"  {cid:<10} | AUCUN VISAGE DETECTE — retake requis")
            failed.append(cid)
            continue
        score = _score_arcface(face, face)
        status = "OK" if score >= TARGET_SCORE else "RETAKE"
        mark = "✓" if score >= TARGET_SCORE else "!!"
        print(f"  {cid:<10} | score={score:.4f} | {mark} {status}")
        if score >= TARGET_SCORE:
            passed.append(cid)
        else:
            failed.append(cid)

    print(f"\n  Résultat : {len(passed)} OK / {len(failed)} à retaker")
    if failed:
        print(f"  Retakes   : {', '.join(failed)}")
        print(f"  Commande  : python production/run.py char-refs --char {' '.join(failed)}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--char", nargs="*", default=[])
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    run(args.char, args.verbose)
```

---

## ETAPE 9 — `production/gen_shots.py`

**Phase C — ~$2.80 (35 shots × $0.08 avg)**
Version réécrite : lit `storyboard.json` comme source des briefs de shot.
Zéro action hard-codée dans le script.

```python
"""
production/gen_shots.py
========================
Génère les 35 shots de EP01 via le pipeline hybride v2.
Source de vérité : storyboard.json (DOP-grade shot briefs)
                   characters.json (canoniques personnages)
                   locations.json  (DOP-grade lieux)

COUT EP01 complet : ~$2.80 (35 shots avec personnages, ~$0.08 chacun)
Usage : python production/gen_shots.py [--scene SCN_002] [--shot SCN_002_SHOT_001] [--dry-run]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.shot_pipeline import run_shot, SceneP1Params, _load_env
from production.dashboard import load_scene, load_character, load_location, load_shot_brief

METRICS = ROOT / "production/shots/metrics.jsonl"


def build_scene_params(shot: dict, scene_cfg: dict, location: dict, grade: dict) -> SceneP1Params:
    colour = location["colour"]
    state = shot.get("state_override") or "canonical appearance"
    scene_grade = grade["per_scene_grade"].get(shot["scene_id"], "")
    return SceneP1Params(
        scene_id=shot["scene_id"],
        episode="Episode 01",
        location_slug=location["slug"],
        location_desc=location["canonical"],
        lighting_desc=location["lighting_brief"],
        colour_desc=(
            f"Dominant: {colour['dominant']}. Accent: {colour['accent']}. "
            f"Blacks: {colour['blacks']}. Grade reference: {location['dop_ref']}. "
            f"Show look: {grade['show_look']['grade_intent']} Scene grade: {scene_grade}."
        ),
        composition=shot["composition"],
        subject_action=shot["action_brief"],
        seed=scene_cfg["seed"],
        extra_notes=(
            f"Camera spec: {shot['camera_spec']}. Emotion: {shot['emotion_intent']}. "
            f"Character state: {state}."
        ),
    )


def run(filter_scene: str | None, filter_shot: str | None, dry_run: bool) -> None:
    _load_env(ROOT)
    storyboard = json.loads((ROOT / "production/storyboard.json").read_text(encoding="utf-8"))["shots"]
    grade = json.loads((ROOT / "production/grade.json").read_text(encoding="utf-8"))

    shots_to_run = []
    for shot in storyboard:
        if filter_scene and shot["scene_id"] != filter_scene:
            continue
        if filter_shot and shot["shot_id"] != filter_shot:
            continue
        shots_to_run.append(shot)

    cost = sum(0.08 if s["primary_character"] else 0.03 for s in shots_to_run)
    print(f"\nShots à générer : {len(shots_to_run)} — coût estimé : ${cost:.2f}")

    if dry_run:
        for shot in shots_to_run:
            char = shot.get("primary_character") or "env-only"
            print(f"  {shot['shot_id']} | {char:<12} | {shot['shot_type']:<18} | {shot['action_brief'][:60]}")
        print(f"\n  Total estimé : ${cost:.2f}")
        print("\n[DRY-RUN] Aucun appel API.")
        return

    METRICS.parent.mkdir(parents=True, exist_ok=True)
    import time
    total_cost = 0.0

    for shot in shots_to_run:
        scene_cfg = load_scene(shot["scene_id"])
        location = load_location(shot["location_key"])
        out_dir = ROOT / f"production/shots/{shot['scene_id']}/{shot['shot_id']}"
        char_id = shot.get("primary_character")

        if char_id:
            char = load_character(char_id)
            ref_path = char.get("ref_image")
            if not ref_path or not Path(ref_path).exists():
                print(f"  !! {shot['shot_id']} — ref manquante pour '{char_id}'. Lancer gen_character_refs.py.")
                continue
            params = build_scene_params(shot, scene_cfg, location, grade)
            result = run_shot(
                scene_params=params,
                shot_id=shot["shot_id"],
                ref_img=Path(ref_path),
                out_dir=out_dir,
                p2_scene_env=location["lighting_brief"][:200],
                p2_subject_action=shot["action_brief"],
                root=ROOT,
            )
            entry = {
                "shot_id": shot["shot_id"],
                "scene_id": shot["scene_id"],
                "character": char_id,
                "arcface_score": result.score_1x,
                "cost": result.cost_total,
                "elapsed": result.elapsed_total,
                "result_1x": str(result.result_1x),
                "result_2x": str(result.result_2x),
                "flag_retake": result.score_1x < 0.85,
            }
            total_cost += result.cost_total
            score_str = f"score={result.score_1x:.4f}"
        else:
            # Shot environnement seulement — copie du master plate lieu (déjà généré en Phase B)
            import shutil
            location_ref = ROOT / f"production/location_refs/{shot['location_key']}_master.png"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / "shot_1x.png"
            if location_ref.exists():
                shutil.copy2(str(location_ref), str(out_path))
                score_str = "env-only (master plate copié)"
                flag = False
            else:
                score_str = "env-only (master plate MANQUANT — lancer location-refs d'abord)"
                flag = True
            entry = {
                "shot_id": shot["shot_id"],
                "scene_id": shot["scene_id"],
                "character": None,
                "result_1x": str(out_path) if location_ref.exists() else None,
                "flag_retake": flag,
                "note": score_str,
            }

        with open(METRICS, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"  {shot['shot_id']} | {score_str} | ${total_cost:.2f} cumulé")

    print(f"\nTerminé. Coût total : ${total_cost:.2f}")
    print("Rapport : python production/run.py report")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", default=None)
    parser.add_argument("--shot", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.scene, args.shot, args.dry_run)
```

---

## ETAPE 10 — `production/run.py` (CLI unifié)

```python
"""
production/run.py
==================
CLI unifié de production District Zero EP01 — méthode professionnelle v3.0

PHASES DE PRODUCTION :
  Phase A : python production/run.py char-refs [--char nara] [--dry-run]    $0.15
  Phase B : python production/run.py location-refs [--dry-run]              $0.30
  Phase B2: python production/run.py benchmark [--char nara]                $0
  Phase C : python production/run.py shots [--scene SCN_002] [--dry-run]    ~$2.80
  Phase D : python production/run.py retakes [--dry-run]                    variable
  Phase E : python production/run.py assembly [--fps 24]                    $0
  Rapport : python production/run.py report
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def cmd_char_refs(args):
    from production.gen_character_refs import run
    run(filter_chars=args.char or [], dry_run=args.dry_run)


def cmd_location_refs(args):
    from production.gen_location_refs import run
    run(filter_locs=args.loc or [], dry_run=args.dry_run)


def cmd_benchmark(args):
    from production.benchmark_characters import run
    run(filter_chars=args.char or [], verbose=args.verbose)


def cmd_shots(args):
    from production.gen_shots import run
    run(filter_scene=args.scene, filter_shot=args.shot, dry_run=args.dry_run)


def cmd_report(args):
    metrics_path = ROOT / "production/shots/metrics.jsonl"
    if not metrics_path.exists():
        print("Aucune métrique — aucun shot généré pour l'instant.")
        return
    rows = [json.loads(l) for l in metrics_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    total_cost = sum(r.get("cost", 0) for r in rows)
    flagged = [r for r in rows if r.get("flag_retake")]
    scores = [r["arcface_score"] for r in rows if r.get("arcface_score")]
    bar = "=" * 55
    print(f"\n{bar}")
    print(f"  RAPPORT DE PRODUCTION EP01")
    print(f"{bar}")
    print(f"  Shots générés  : {len(rows)}")
    if scores:
        print(f"  Score ArcFace  : min={min(scores):.4f}  max={max(scores):.4f}  moy={sum(scores)/len(scores):.4f}")
    print(f"  A retaker      : {len(flagged)}")
    print(f"  Coût total     : ${total_cost:.2f}")
    print(f"{bar}\n")
    for r in flagged:
        print(f"  !! RETAKE : {r['shot_id']} — score={r.get('arcface_score', 'n/a'):.4f}")


def cmd_retakes(args):
    metrics_path = ROOT / "production/shots/metrics.jsonl"
    if not metrics_path.exists():
        print("Aucune métrique.")
        return
    rows = [json.loads(l) for l in metrics_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    flagged = [r["shot_id"] for r in rows if r.get("flag_retake")]
    if not flagged:
        print("Aucun shot à retaker.")
        return
    from production.gen_shots import run
    for shot_id in flagged:
        scene_id = shot_id.rsplit("_SHOT_", 1)[0]
        run(filter_scene=scene_id, filter_shot=shot_id, dry_run=args.dry_run)


def cmd_assembly(args):
    from production.gen_assembly import run
    run(fps=args.fps)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="production/run.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cr = sub.add_parser("char-refs", help="Phase A — génère portraits référence personnages")
    p_cr.add_argument("--char", nargs="*")
    p_cr.add_argument("--dry-run", action="store_true")

    p_lr = sub.add_parser("location-refs", help="Phase B — génère master plates lieux")
    p_lr.add_argument("--loc", nargs="*")
    p_lr.add_argument("--dry-run", action="store_true")

    p_bm = sub.add_parser("benchmark", help="Phase B2 — valide ArcFace des refs")
    p_bm.add_argument("--char", nargs="*")
    p_bm.add_argument("--verbose", action="store_true")

    p_sh = sub.add_parser("shots", help="Phase C — génère les shots EP01")
    p_sh.add_argument("--scene", default=None)
    p_sh.add_argument("--shot", default=None)
    p_sh.add_argument("--dry-run", action="store_true")

    sub.add_parser("report", help="Rapport de production")

    p_rt = sub.add_parser("retakes", help="Phase D — régénère les shots flaggés")
    p_rt.add_argument("--dry-run", action="store_true")

    p_asm = sub.add_parser("assembly", help="Phase E — assemble rough cut EP01")
    p_asm.add_argument("--fps", type=int, default=24)

    args = parser.parse_args()
    {
        "char-refs": cmd_char_refs,
        "location-refs": cmd_location_refs,
        "benchmark": cmd_benchmark,
        "shots": cmd_shots,
        "report": cmd_report,
        "retakes": cmd_retakes,
        "assembly": cmd_assembly,
    }[args.cmd](args)
```

---

## ETAPE 11 — `production/README.md`

```markdown
# Production — District Zero EP01 — Méthode professionnelle v3.0

## Principe
Chaque prompt est un document de production cinématographique réel.
Pas de "describe what you want" — des notes de DP, de gaffer, de directeur artistique.
Ce principe a produit un score ArcFace de 0.9378 — record validé le 2026-04-30.

## Sources de vérité
| Fichier | Contient |
|---------|---------|
| `characters.json` | 5 canoniques DOP-grade + portrait_brief par personnage |
| `locations.json` | 10 descripteurs DOP-grade + lighting_brief + colour par lieu |
| `storyboard.json` | 35 shots — briefs de production complets (state_override + audio_brief) |
| `dashboard.json` | seeds, location_keys, chemins master plates générées |
| `grade.json` | Show look transversal — grade d'épisode + per_scene_grade |

## Phases de production

### Phase A — Portraits référence ($0.15)
python production/run.py char-refs --dry-run
python production/run.py char-refs

### Phase B — Master plates lieux ($0.30)
python production/run.py location-refs --dry-run
python production/run.py location-refs

### Phase B2 — Validation ArcFace ($0)
python production/run.py benchmark

### Phase C — Shots EP01 (~$2.80)
python production/run.py shots --dry-run
python production/run.py shots --scene SCN_002          # une scène
python production/run.py shots --shot SCN_002_SHOT_001  # un shot
python production/run.py shots                          # tout EP01

### Rapport
python production/run.py report

### Phase D — Retakes (variable)
python production/run.py retakes --dry-run
python production/run.py retakes

### Phase E — Rough cut assembly ($0)
python production/run.py assembly        # 24fps par défaut
python production/run.py assembly --fps 30

## Conventions
- seed = N×11 : SCN_001→11, SCN_002→22 ... SCN_011→121
- ArcFace target : ≥ 0.85 en 1x (record 0.9378 Nara)
- metrics.jsonl : chaque shot tracé immédiatement après génération
- Ne jamais modifier pipeline/shot_pipeline.py sans rebenchmark ArcFace
- Ne jamais générer des shots avant que les refs personnages soient validées (Phase B2 OK)
- grade.json doit exister avant Phase B et Phase C (chargé dans les prompts)
- Convention de nommage outputs : `DZ_EP01_{SCN_ID}_{SHOT_ID}_v001.png` (géré automatiquement)

## Coût total EP01
| Phase | Opération | Coût |
|-------|-----------|------|
| A | 5 portraits référence | $0.15 |
| B | 10 master plates lieux | $0.30 |
| C | 35 shots EP01 | ~$2.80 |
| D | Retakes estimés 20% | ~$0.56 |
| E | Rough cut assembly | $0 |
| **Total** | | **~$3.81** |
```

---

## ETAPE 12 — `production/gen_assembly.py`

**Phase E — $0 (ffmpeg local)**
Assemble les shots générés en rough cut avec les durées de `storyboard.json`.
Produit `production/assembly/DZ_EP01_rough_cut_v001.mp4`.

**Prérequis :** ffmpeg installé — `winget install ffmpeg` si absent.

```python
"""
production/gen_assembly.py
===========================
Assemble les shots de EP01 en rough cut via ffmpeg.
Source: storyboard.json (duration_sec), production/shots/ (images générées)

COUT : $0 — ffmpeg local
Usage : python production/run.py assembly [--fps 24]
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(fps: int = 24) -> None:
    storyboard = json.loads((ROOT / "production/storyboard.json").read_text(encoding="utf-8"))["shots"]
    out_dir = ROOT / "production/assembly"
    out_dir.mkdir(parents=True, exist_ok=True)

    filelist_path = out_dir / "filelist.txt"
    lines: list[str] = []
    missing: list[str] = []

    for shot in storyboard:
        # Priorité : shot_2x > shot_1x > master plate lieu (env-only)
        candidates = [
            ROOT / f"production/shots/{shot['scene_id']}/{shot['shot_id']}/shot_2x.png",
            ROOT / f"production/shots/{shot['scene_id']}/{shot['shot_id']}/shot_1x.png",
        ]
        found = next((p for p in candidates if p.exists()), None)
        if not found:
            missing.append(shot["shot_id"])
            continue
        lines.append(f"file '{found.as_posix()}'")
        lines.append(f"duration {shot['duration_sec']}")

    if missing:
        print(f"\n  !! {len(missing)} shots manquants :")
        for sid in missing[:10]:
            print(f"     - {sid}")
        if len(missing) > 10:
            print(f"     ... et {len(missing) - 10} autres")

    if not lines:
        print("Aucun shot disponible — lancer Phase C d'abord.")
        return

    filelist_path.write_text("\n".join(lines), encoding="utf-8")
    out_path = out_dir / "DZ_EP01_rough_cut_v001.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(filelist_path),
        "-vf", (
            f"fps={fps},"
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        str(out_path),
    ]
    print(f"\nAssemblage — {len(lines) // 2} shots — fps={fps} — sortie : {out_path.name}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Rough cut généré : {out_path}")
    else:
        print(f"Erreur ffmpeg :\n{result.stderr[-500:]}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fps", type=int, default=24)
    run(fps=parser.parse_args().fps)
```

**Coût : $0**

---

## RECAPITULATIF — ORDRE D'EXECUTION

### Fichiers à créer ($0)

```
┌──────┬─────────────────────────────────────────┬────────────┬────────┐
│  0   │ stories/district_zero_ep01.fountain     │ Écriture   │ $0     │
│      │  ← SOURCE NARRATIVE CANONIQUE           │ Fountain   │        │
│      │    (Étape 0 — avant tout le reste)       │            │        │
├──────┼─────────────────────────────────────────┼────────────┼────────┤
│  1   │ production/__init__.py                  │ vide       │ $0     │
│  2   │ production/characters.json              │ JSON       │ $0     │
│  3   │ production/locations.json               │ JSON       │ $0     │
│  4   │ production/storyboard.json              │ JSON       │ $0     │
│  5   │ production/dashboard.json               │ JSON       │ $0     │
│ 4b   │ production/grade.json                   │ JSON       │ $0     │
│  6   │ production/dashboard.py                 │ Python     │ $0     │
│  7   │ production/gen_character_refs.py        │ Python     │ $0     │
│  8   │ production/gen_location_refs.py         │ Python     │ $0     │
│  9   │ production/benchmark_characters.py      │ Python     │ $0     │
│ 10   │ production/gen_shots.py                 │ Python     │ $0     │
│ 11   │ production/run.py                       │ Python CLI │ $0     │
│ 12   │ production/README.md                    │ Docs       │ $0     │
│ 13   │ production/gen_assembly.py              │ Python     │ $0     │
├──────┼─────────────────────────────────────────┼────────────┼────────┤
│      │ TOTAL CREATION INFRASTRUCTURE           │            │ $0     │
└──────┴─────────────────────────────────────────┴────────────┴────────┘
```

### Validation avant toute production ($0)

```powershell
venv\Scripts\Activate.ps1

# Vérification manuelle Season Bible (OBLIGATOIRE avant Phase A — coût $0)
# Ouvrir stories/district_zero_season1_bible.md et confirmer :
# ✓ Chaque personnage dans characters.json correspond à la description dans la bible
# ✓ Chaque lieu dans locations.json est référencé dans la bible de saison
# ✓ Les arcs EP01 ne contredisent pas la bible de saison
# Si divergence : corriger characters.json / locations.json AVANT toute génération

# Vérifier structure complète
python production/run.py char-refs --dry-run
python production/run.py location-refs --dry-run
python production/run.py shots --dry-run

# Si tous les dry-runs passent sans erreur : infrastructure validée
```

### Lancement production (dans cet ordre, jamais dans le désordre)

```powershell
python production/run.py char-refs       # Phase A — $0.15
python production/run.py benchmark       # Phase B2 — $0 — VALIDATION OBLIGATOIRE
python production/run.py location-refs   # Phase B — $0.30
python production/run.py shots           # Phase C — ~$2.80
python production/run.py report          # Rapport
python production/run.py retakes         # Phase D — si nécessaire
python production/run.py assembly        # Phase E — rough cut $0
```

