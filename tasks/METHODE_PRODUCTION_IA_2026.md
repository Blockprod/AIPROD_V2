---
title: "District Zero — Guide opérationnel de production IA"
subtitle: "Méthodes verrouillées, limites réelles, roadmap par métier"
creation: 2026-04-30 à 16:11
version: 1.0
status: référence de production
---

# DISTRICT ZERO — GUIDE OPÉRATIONNEL DE PRODUCTION IA 2026

> **Principe** : Ce document n'est pas un manifeste théorique.
> C'est un guide de terrain, construit à partir de tests réels, de coûts mesurés
> et de résultats validés sur le pipeline de District Zero.
> Chaque section distingue ce qui est **prouvé**, ce qui est **bloqué**, et ce qui est **en chemin**.

---

## TABLE DES MATIÈRES

1. [Philosophie générale](#1-philosophie-générale)
2. [Showrunner / Créateur](#2-showrunner--créateur)
3. [Head Writer](#3-head-writer)
4. [Directeur Artistique](#4-directeur-artistique)
5. [Color Key Artist](#5-color-key-artist)
6. [Directeur de la Photographie](#6-directeur-de-la-photographie--dp)
7. [Superviseur Modèles / Identité](#7-superviseur-modèles--identité-personnages)
8. [Prompteur·euse principal·e](#8-prompteureuse-principale)
9. [Monteur Image](#9-monteur-image)
10. [Cleanup Artist](#10-cleanup-artist)
11. [Sound Designer](#11-sound-designer)
12. [Mixeur Audio](#12-mixeur-audio)
13. [Compositeur·trice](#13-compositeurtrice)
14. [Stack technologique consolidé](#14-stack-technologique-consolidé)
15. [Coûts de production estimés](#15-coûts-de-production-estimés)
16. [Roadmap 6-18 mois](#16-roadmap-6-18-mois)

---

## 1. PHILOSOPHIE GÉNÉRALE

### Le principe qui a tout changé

La session du 2026-04-30 a démontré un principe fondamental :
**la qualité du prompt est la compétence centrale de toute la chaîne**.

Le pipeline hybride FLUX.2 Pro + Flux Fill Pro v5, combiné à un prompt
au format "document de production réel" (DOP brief, gaffer notes, références cinéma nommées),
a produit un score ArcFace de **0.9378** — nouveau record absolu —
pour un coût de **$0.08/shot** et un temps de **89 secondes**.

Ce n'est pas un accident. C'est le résultat d'une méthode :
remplacer le "describe what you want" par "parle comme un professionnel du cinéma".

**Ce principe s'applique à tous les métiers. C'est le fil directeur de ce guide.**

### Règle d'or transversale

> Pour chaque métier, la question n'est pas "quel outil IA utiliser ?"
> mais "comment formuler la commande comme un expert métier le ferait ?"

Un script écrit comme un showrunner de HBO obtient de meilleurs résultats d'un LLM
qu'un script demandé comme une tâche scolaire.
Un brief son écrit comme un sound designer de film obtient de meilleures nappes de Stable Audio
qu'une description vague.

### Niveaux d'automatisation (référentiel)

| Niveau | Définition |
|--------|-----------|
| **L0** | Humain fait tout, IA absente ou anecdotique |
| **L1** | IA assiste (génère des variantes, humain sélectionne et valide) |
| **L2** | IA exécute selon un protocole verrouillé, humain supervise |
| **L3** | IA exécute et s'auto-valide (métriques objectives), humain valide le livrable final |
| **L4** | IA exécute et livre (humain valide seulement en exception) |

En 2026, aucun métier créatif n'est au L4. La cible réaliste pour District Zero est **L2-L3** selon le métier.

---

## 2. SHOWRUNNER / CRÉATEUR

### Ce qui est possible (L1)

- **Bible série** : Claude Sonnet 4+ ou GPT-4o génèrent des bibles de qualité si briefés avec la structure narrative, les thèmes, les contraintes de production. La bible District Zero existante (10 épisodes, arc Nara/Vale, ton Villeneuve) a été produite avec assistance LLM.
- **Variantes de révélation** : pour chaque twist narratif (ex: Elian épisode 7), le LLM peut générer 5-10 variantes structurées en quelques secondes — le showrunner choisit.
- **Cohérence thématique check** : un LLM peut relire un script et signaler les contradictions avec la bible ("dans l'épisode 3, Nara dit X — cela contredit ce qui est établi en épisode 1").
- **Pitch documents** : génération automatique de loglines, synopses de vente, one-pagers.

### Ce qui ne l'est pas encore

- **La vision** : aucun LLM ne peut décider que la série doit ressembler à Sicario et non à Blade Runner. C'est une décision esthétique et personnelle.
- **L'arbitrage créatif** : choisir entre deux bonnes idées contradictoires nécessite une position morale et artistique que le showrunner seul détient.
- **La cohérence sur 10 épisodes** : les LLMs perdent le fil sur de très longues fenêtres de contexte. Les contradictions subtiles entre épisodes 1 et 9 passent inaperçues.
- **La validation finale** : personne d'autre que le showrunner ne peut dire "cette image représente District Zero".

### Méthode recommandée

```
WORKFLOW SHOWRUNNER + IA
─────────────────────────
1. Showrunner écrit la bible "noyau dur" (10-15 pages) à la main
2. LLM (Claude) développe chaque épisode en outline détaillé
3. Showrunner lit, corrige, valide ou rejette chaque outline
4. LLM raffine selon les corrections
5. Cycle itératif — showrunner garde la main sur chaque décision narrative
```

**Prompt template showrunner** :
> "Tu es script editor senior chez HBO. La bible de la série est ci-jointe.
> Écris l'outline de l'épisode 3 en respectant : [contraintes précises].
> Signale toute contradiction avec la bible. Propose 2 variantes pour le cliffhanger."

### Niveau actuel : L1 — cible : L1 (permanent)

---

## 3. HEAD WRITER

### Ce qui est possible (L1-L2)

- **Structure d'épisode** : LLM génère le découpage en actes, les scènes pivots, les points de retournement. Qualité : bonne à excellente si la bible est injectée en contexte.
- **Dialogues draft** : Claude Sonnet / GPT-4o génèrent des dialogues de niveau "bonne télévision". Ils nécessitent une révision humaine pour les moments clés (révélations, confrontations émotionnelles).
- **Voix des personnages** : un LLM fine-tuné sur des transcriptions de dialogues existants peut maintenir une voix spécifique. Sans fine-tuning, il tend à uniformiser.
- **"Script doctoring"** : donner un script existant + "réécris cette scène en rendant Nara plus froide et plus économe en mots" — LLM excelle à ça.

### Ce qui ne l'est pas encore

- **Cohérence de voix sur 10 épisodes** : sans fine-tuning ou mémoire longue, la voix de Nara à l'épisode 8 dérivera légèrement de l'épisode 1. Subtil mais réel.
- **Le sous-texte** : LLM écrit ce qui est dit. Le non-dit, le geste qui remplace le mot, la pause qui en dit plus que la réplique — c'est humain.
- **L'unicité stylistique** : un head writer humain a une voix. Un LLM a une moyenne.

### Méthode recommandée

**Structure de brief pour chaque scène :**
```
PERSONNAGES : [liste + état émotionnel au début de scène]
OBJECTIF DRAMATIQUE : [ce que la scène doit accomplir]
INFORMATION À TRANSMETTRE : [ce que le spectateur doit savoir après]
CONTRAINTE TONALE : [exemple de série ou de film comme référence]
LONGUEUR : [en pages estimées]
INTERDITS : [ce que Nara ne dirait jamais / ce qui casserait la cohérence]
```

### Niveau actuel : L1-L2 — cible : L2

---

## 4. DIRECTEUR ARTISTIQUE

### Ce qui est possible (L1)

- **Concept art / mood boards** : Midjourney v7 ou FLUX.2 Pro génèrent des images de référence de haute qualité pour les lieux (Mur, Atrium, Marché noir, couloirs du Transit Stack).
- **Exploration de palettes** : générer 20-30 variantes d'ambiance pour un même lieu en quelques minutes — impossible manuellement.
- **Bible visuelle image** : constitution d'une bibliothèque de 50-100 images référencées par type de lieu, heure, émotion — réalisable en une journée.
- **Templates de prompt** : le directeur artistique peut figer des blocs de description architecturale réutilisables dans tous les prompts de la série.

### Ce qui ne l'est pas encore

- **La direction** : décider que District Zero ressemble à Sicario et non à Dune nécessite une culture d'image que l'IA ne possède pas.
- **La cohérence visuelle automatique** : deux images générées avec le même prompt ne sont jamais identiques. La cohérence requiert un système de seeds, de LoRAs ou de templates verrouillés.
- **La validation créative** : l'IA ne sait pas si une image est "juste" pour la série — c'est une décision humaine.

### Méthode recommandée

```
SYSTÈME DE VERROUILLAGE VISUEL
───────────────────────────────
1. Pour chaque type de lieu : 1 "image maître" générée et validée
2. Cette image maître → extraire le bloc stylistique exact (architecture, matière, lumière)
3. Ce bloc stylistique → copié/collé dans TOUS les prompts de ce lieu
4. Seed fixe par lieu (comme notre SCN002_SEED = 42)
5. Résultat : cohérence visuelle garantie entre tous les shots d'une même scène
```

**Livrables concrets à produire :**

| Livrable | Outil | Temps estimé |
|---------|-------|-------------|
| Image maître par lieu (11 scènes EP01) | FLUX.2 Pro | 2h |
| Palette hex par lieu | Manuel + LLM | 1h |
| Bloc stylistique par lieu | LLM depuis image maître | 1h |
| Bible visuelle PDF | Assemblage | 2h |

### Niveau actuel : L1 — cible : L2

---

## 5. COLOR KEY ARTIST

### Ce qui est possible (L1-L2)

- **Palette hex par scène** : définir et verrouiller les codes couleur dans les prompts (comme fait en v2 : `#1C2B35` steel-blue dominant, `#B8600A` amber accent, `#0A0F12` lifted blacks).
- **Intentions de grade en language naturel** : "Sicario tunnel sequence — Roger Deakins" est compris par FLUX.2 Pro et Flux Fill Pro. C'est une référence grade complète en 5 mots.
- **Cohérence cross-scène** : en injectant les mêmes hex codes + référence cinéma dans chaque prompt, le grade reste cohérent sans post-production.

### Ce qui ne l'est pas encore

- **Grade automatique post-génération** : il n'existe pas encore d'outil qui regrade automatiquement une image générée vers une palette cible avec fidélité au niveau d'un coloriste humain.
- **Continuité exacte entre plans** : deux images générées avec le même grade cible peuvent avoir des teintes légèrement différentes sur les zones de transition.
- **Étalonnage final broadcast** : la conformité Netflix/Apple TV+ (Rec.2020, HDR, loudness video) nécessite DaVinci Resolve et un humain.

### Méthode recommandée

**Tableau de bord colorimétrique District Zero :**

```
LIEU                    | DOMINANT      | ACCENT        | BLACKS    | REF CINÉMA
────────────────────────┼───────────────┼───────────────┼───────────┼─────────────────────────
Transit Stack (nuit)    | #1C2B35 steel | #B8600A amber | #0A0F12   | Sicario tunnel / Deakins
Atrium Système          | #0D1B2A navy  | #C8F0FF cyan  | #080C10   | Blade Runner 2049 / Deakins
Marché noir             | #2A1A0A brown | #E8890A amber | #0F0A05   | Children of Men / Lubezki
Upper Levels            | #F0EDE0 cream | #D4AF6A gold  | #1A1510   | 1984 Orwell / cold clean
Extérieur (au-delà mur) | #4A6E5A green | #8AAAA0 grey  | #151A15   | Annihilation / Garland
```

Chaque ligne = bloc couleur à coller dans le prompt du lieu concerné.

### Niveau actuel : L2 (via prompts) — cible : L3 (avec post-grade automatisé)

---

## 6. DIRECTEUR DE LA PHOTOGRAPHIE (DP)

### Ce qui est possible — PROUVÉ (L3)

**C'est le métier le plus avancé du pipeline. La preuve est dans les chiffres.**

Pipeline verrouillé `pipeline/shot_pipeline.py` :
- **FLUX.2 Pro** (master plate, seed fixe par scène) + **Flux Fill Pro v5** (face inpainting)
- Score ArcFace : **0.9378** (record absolu, validé 2026-04-30)
- Coût : **$0.08/shot** ($0.03 P1 + $0.05 P2)
- Temps : **89 secondes/shot**
- Résolution native : 1344×768 → upscale 2x → **2688×1536**

**Ce qui est maîtrisé :**
- Optiques (focal length, T-stop, squeeze anamorphique, oval bokeh)
- Sources lumineuses (Kelvin précis : 2850K/2200K/6500K)
- Ratio de contraste (chiaroscuro 8:1)
- Composition (règle des tiers, vanishing point, leading lines)
- Grain cinéma (film grain vs digital noise)
- Mouvement (motion blur contrôlé sur extrémités)
- Référence cinéma directe (Roger Deakins, Sicario, Denis Villeneuve)

**Bloc stylistique verrouillé (à inclure dans chaque prompt) :**
```
ARRI Alexa 35, Cooke Anamorphic /i 32mm T2.3, ISO 1600, 180° shutter, 24fps.
Oval out-of-focus highlights, horizontal lens flare streak from practical.
Natural 35mm film grain — visible in shadows, organic texture, not digital noise.
Roger Deakins / Sicario (2015) visual language.
```

### Ce qui ne l'est pas encore

- **Mouvement de caméra** : traveling, steadycam, caméra à l'épaule — les modèles text-to-image sont fixes par définition. Runway Gen4 / Kling 2.0 adressent partiellement ce point mais pas à la qualité de fidélité faciale actuelle (0.9378).
- **Cohérence de l'axe caméra entre plans** : un champ/contrechamp cohérent (règle des 180°) nécessite une coordination manuelle ou un système de contraintes non disponible en génération libre.
- **Raccord de lumière exacte** : la lumière varie légèrement entre deux appels API même avec seed identique pour P2.

### Roadmap DP

| Horizon | Capacité | Outil probable |
|---------|---------|---------------|
| 3 mois | Zoom-in / zoom-out simple | Runway Gen4 Video |
| 6 mois | Traveling simple (avant/arrière) | Kling 2.0 ou Wan 2.1 |
| 12 mois | Mouvements complexes avec fidélité faciale | Modèle hybride (pas encore disponible) |

### Niveau actuel : L3 (images fixes) / L1 (mouvement) — cible : L3 total sur 12 mois

---

## 7. SUPERVISEUR MODÈLES / IDENTITÉ PERSONNAGES

### Ce qui est possible — PROUVÉ (L3)

**La question "LoRA ou inpainting ?" est tranchée par les résultats :**

| Méthode | ArcFace | Coût | Temps | Verdict |
|--------|--------|------|-------|--------|
| Seedream 4.5 (ref image) | 0.566 | $0.04 | 45s | Rejeté |
| Flux Fill Pro v5 seul | 0.925 | $0.05 | 20s | Excellent |
| **Pipeline hybride v2** | **0.9378** | **$0.08** | **89s** | **Standard de production** |
| LoRA fine-tunée (théorique) | ~0.95+ | $0/shot (coût training) | variable | Non testé |

**Conclusion opérationnelle :**
Le pipeline d'inpainting avec référence (Flux Fill Pro v5) donne **0.9378 sans LoRA**.
L'entraînement LoRA est une option d'amélioration, pas une nécessité immédiate.

**Ce qui est opérationnel aujourd'hui :**
- 1 image de référence par personnage → ArcFace 0.93+ garanti
- Scoring automatique InsightFace buffalo_l (validation objective)
- Masque elliptique automatique (détection bbox face → expand 1.15)
- Référence : `nara_hero_ref_01.png` → self-similarity ArcFace = 1.0

**Ce qui sera disponible avec LoRA :**
- Cohérence du costume (pas seulement du visage)
- Angles de profil difficiles (3/4 dos)
- Expressions extrêmes (cri, pleurs)

### Workflow LoRA (si décidé)

```
ENTRAÎNEMENT LORA PERSONNAGE
─────────────────────────────
1. Collecter 15-25 images de référence (angles variés, éclairages variés)
2. Pré-traitement : crop 512×512, centré sur le visage, fond neutre
3. Entraînement : Kohya SS sur Flux Dev (1500-2000 steps, LR 1e-4)
4. Validation : batch de 50 générations → score ArcFace médian > 0.90
5. Verrouillage : poids LoRA + trigger word → dans pipeline/ comme constante
6. Rebenchmark systématique si la ref image du personnage change
```

### Niveau actuel : L3 (inpainting) — cible : L3+ (inpainting + LoRA pour profils difficiles)

---

## 8. PROMPTEUR·EUSE PRINCIPALE

### Ce qui est possible — SYSTÈME VERROUILLÉ (L2-L3)

Le rôle du prompteur est maintenant **partiellement encodé dans le code**.

Le module `pipeline/shot_pipeline.py` contient :
- `SceneP1Params` : dataclass structurée pour paramétrer chaque scène
- `build_p1_prompt()` : constructeur de prompt DOP-grade (format JSON document de production)
- `build_p2_prompt()` : constructeur Flux Fill Pro avec NARA_CANONICAL verrouillé
- `LOCKED_NARA_CANONICAL` : description pixel-parfaite du personnage (gelée)

**Pour générer un shot, le prompteur remplit la dataclass, pas un prompt libre :**

```python
SceneP1Params(
    scene_id="SCN_004",
    episode="Episode 01",
    location_slug="INT. ATRIUM SYSTÈME — UPPER LEVEL — DAY",
    location_desc="...",          # bloc architectural (depuis image maître)
    lighting_desc="...",          # brief DOP (depuis Color Key tableau)
    colour_desc="...",            # palette hex (depuis Color Key tableau)
    composition="...",            # position sujet, vanishing point
    subject_action="...",         # action précise de Nara
    seed=12,                      # seed fixe pour cette scène
)
```

**Ce principe est la conséquence directe de la méthode DOP-grade :**
au lieu d'un prompteur qui improvise, un prompteur qui remplit un formulaire structuré
avec des données issues d'un tableau de bord de production.

### Ce qui ne l'est pas encore

- **Itération automatique** : générer 5 variantes et choisir automatiquement la meilleure. Aujourd'hui c'est $0.08 × N variantes. Nécessite un scoring visuel automatique au-delà d'ArcFace (composition, éclairage, artefacts).
- **Détection d'artefacts automatique** : mains incorrectes, doigts fusionnés, yeux asymétriques — non détectés automatiquement aujourd'hui.

### Niveau actuel : L2 (formulaire structuré) — cible : L3 (scoring visuel automatique)

---

## 9. MONTEUR IMAGE

### Ce qui est possible (L1)

- **Assembly cut** : disposer les images dans l'ordre narratif est une tâche de structure. L'IA peut proposer un découpage basé sur le script.
- **Identification des plans manquants** : à partir d'un storyboard et d'une banque d'images, un LLM peut lister les raccords manquants.
- **Transition IA** : Runway Gen4 ou Kling 2.0 peuvent générer une image ou séquence de transition entre deux plans fixes (morphing, insert, coupe raccord).

### Ce qui ne l'est pas encore

- **Le rythme** : la cadence des coupes, l'ellipse, la respiration entre deux plans — c'est l'instinct du monteur. Non automatisable.
- **L'émotion** : choisir de garder 3 secondes de silence après une révélation plutôt que de couper directement — c'est une décision narrative humaine.
- **La cohérence narrative** : un monteur détecte que deux plans successifs se contredisent visuellement. Aucun outil n'automatise ce contrôle en 2026.

### Workflow recommandé

```
MONTAGE DISTRICT ZERO — WORKFLOW HYBRIDE
──────────────────────────────────────────
Phase 1 — Paper edit (IA) :
  LLM lit le script → génère liste ordonnée de plans + durées estimées

Phase 2 — Assembly (humain) :
  Monteur assemble dans Premiere/Resolve avec les images générées

Phase 3 — Gap fill (IA) :
  Pour chaque coupe manquante → Runway Gen4 génère l'insert

Phase 4 — Fine cut (humain) :
  Rythme, émotion, cliffhanger → décision humaine exclusive
```

### Niveau actuel : L1 — cible : L2 dans 6 mois (avec génération vidéo 2-3s fiable)

---

## 10. CLEANUP ARTIST

### Ce qui est possible (L2)

- **Inpainting ciblé** : Flux Fill Pro peut corriger une main, un arrière-plan incohérent, un bord de masque visible — à condition que le masque soit dessiné manuellement (ou semi-auto).
- **Watermark removal** : automatisé dans le pipeline actuel (`_remove_watermark()` — inpainting cv2 zone bas-droite).
- **Upscale + sharpening** : automatisé (`_upscale_2x()` — LANCZOS4 ×2 + unsharp mask 1.4/0.4).
- **Photoshop Generative Fill** : pour les corrections ponctuelles sur des éléments complexes (doigts, yeux), Photoshop 2026 donne de bons résultats sur des zones < 10% du cadre.

### Ce qui ne l'est pas encore

- **Détection automatique d'artefacts** : aucun outil ne scanne une image et liste "main gauche : 6 doigts — œil droit : légèrement asymétrique" de manière fiable en 2026.
- **Correction automatique sans masque manuel** : l'inpainting requiert un masque précis. La définition du masque reste manuelle.

### Pipeline cleanup recommandé

```
CLEANUP AUTOMATISÉ (ce qui existe aujourd'hui)
────────────────────────────────────────────────
✓ Watermark bottom-right → cv2.inpaint (automatique dans pipeline/)
✓ Upscale 2x → LANCZOS4 + unsharp (automatique dans pipeline/)
✓ Correction visage → Flux Fill Pro (semi-automatique, masque auto)

CLEANUP MANUEL (nécessaire aujourd'hui)
────────────────────────────────────────
✗ Mains / doigts → Photoshop Generative Fill (masque manuel)
✗ Background incohérences → Outpainting ciblé (masque manuel)
✗ Lumière border → Photoshop Spot Healing (manuel)
```

### Niveau actuel : L2 (partiel) — cible : L3 (détection automatique dans 12 mois)

---

## 11. SOUND DESIGNER

### Ce qui est possible (L1-L2)

- **Ambiances procedurales** : Stable Audio / AudioLDM 2 génèrent des nappes sonores de qualité correcte (eau, métal, grondement mécanique) sur description textuelle.
- **Effets spécifiques** : ElevenLabs Sound Effects génère des effets sur description ("metallic gate closing in a reverberant concrete space").
- **Voix off / murmures** : ElevenLabs voix clonée peut générer des lignes de dialogue ou de narration en une voix cohérente.
- **Ambiances par lieu** : le tableau de bord colorimétrique peut s'étendre avec un équivalent sonore par lieu.

**Tableau de bord sonore District Zero :**

```
LIEU                  | AMBIANCE                           | OUTILS
──────────────────────┼────────────────────────────────────┼──────────────────
Transit Stack         | Eau + résonance métallique + vapeur | Stable Audio
Atrium Système        | Hum électronique + pas sur métal   | Stable Audio + EL
Marché noir           | Foule filtrée + radio parasitée    | Stable Audio
Couloirs supérieurs   | Silence + climatisation + tension  | ElevenLabs SFX
Extérieur (au-delà)   | Vent + nature étrangère + vide     | Stable Audio
```

### Ce qui ne l'est pas encore

- **Cohérence sur 10 épisodes** : les modèles de génération audio n'ont pas de mémoire inter-session. La même description peut produire deux ambiances légèrement différentes.
- **Spatialisation** : générer directement en 5.1 ou Atmos — inexistant en 2026.
- **Foley précis** : le son d'un pas sur du métal rouillé mouillé, à 3h du matin, avec une légère réverbération de 1.2 secondes — ce niveau de précision est humain.

### Niveau actuel : L1-L2 — cible : L2 (bibliothèque verrouillée par lieu, générée une fois)

---

## 12. MIXEUR AUDIO

### Ce qui est possible (L1)

- **Nettoyage automatisé** : iZotope RX 11 (machine learning) — suppression bruit de fond, correction dé-esser, égalisation auto. Qualité broadcast.
- **Loudness auto** : outils de normalisation automatique (LUFS cible -23 EBU R128 ou -14 LUFS Spotify) — automatique en 2026.
- **Stem separation** : Demucs / Spleeter — séparer dialogue, musique, effets d'une piste mixée. Utile pour corriger sans re-mixer.

### Ce qui ne l'est pas encore

- **Le mix artistique final** : équilibrer dialogue/ambiance/musique pour servir la narration — c'est une décision dramaturgique, pas technique.
- **La spatialisation Atmos** : objectiver le placement d'un objet sonore dans l'espace 3D d'une salle Dolby Atmos — humain indispensable.
- **Conformité broadcast finale** : la certification Netflix/Apple TV+ requiert un ingénieur son humain et un système de contrôle qualité certifié.

### Niveau actuel : L1 (assistance) — cible : L2 (pré-mix automatisé sur pistes séparées)

---

## 13. COMPOSITEUR·TRICE

### Ce qui est possible (L1)

- **Thèmes exploratoires** : Suno v4 / Udio génèrent des variantes thématiques en quelques secondes sur description ("dark minimalist orchestral theme, cello and electronics, reminiscent of Johan Söderqvist, tense and cold, 2m30").
- **Nappes d'ambiance** : qualité acceptable pour underscore non-mélodique (tension, attente, désespoir). Difficilement distinguable d'une production humaine économique.
- **Leitmotivs exploratoires** : générer 10-15 variations d'un motif de 4 notes pour explorer les options — 15 minutes avec Suno vs 2 jours avec un compositeur.

### Ce qui ne l'est pas encore

- **Cohérence du leitmotiv sur 10 épisodes** : un motif de 4 notes attribué à Nara doit évoluer subtilement au fil des épisodes pour refléter son arc. Les LLMs audio n'ont pas cette mémoire narrative.
- **Synchronisation précise** : composer sur une image avec des cuts à l'image précise — les outils IA audio ne reçoivent pas la vidéo comme contrainte en temps réel.
- **L'émotion unique** : le thème de District Zero doit être mémorable, reconnaissable, attaché à l'univers. L'IA produit du "plausible" — pas du "inoubliable".

### Recommandation

**Approche hybride fortement conseillée :**
1. Suno/Udio → 20-30 variantes exploratoires → le showrunner sélectionne la direction
2. Compositeur humain (même junior) → développe et orchestre le thème sélectionné
3. Suno/Udio → variations économiques pour les scènes secondaires
4. Humain → thème principal, scènes emotionnellement critiques (révélation Elian, finale)

**Coût estimé** : compositeur humain pour 30% des scènes + Suno pour 70% = budget divisé par 3.

### Niveau actuel : L1 (exploration) — cible : L1-L2 (thèmes secondaires automatisés)

---

## 14. STACK TECHNOLOGIQUE CONSOLIDÉ

### Outils opérationnels aujourd'hui (testés, coûts connus)

| Outil | Usage | Coût | Fiabilité |
|-------|-------|------|-----------|
| **FLUX.2 Pro** (Replicate) | Master plate décor, seed fixe | $0.03/scène | ★★★★★ |
| **Flux Fill Pro v5** (Replicate) | Face inpainting | $0.05/shot | ★★★★★ |
| **InsightFace buffalo_l** | Scoring ArcFace, validation objectve | Gratuit | ★★★★★ |
| **Claude Sonnet 4+** | Scripts, bibles, dialogues, prompts | ~$0.01-0.05/appel | ★★★★☆ |
| **OpenCV LANCZOS4** | Upscale 2x + unsharp | Gratuit | ★★★★★ |
| **ElevenLabs** | SFX, voix | $0.18/1000 chars | ★★★★☆ |
| **Stable Audio** | Ambiances musicales | ~$0.01/génération | ★★★☆☆ |
| **iZotope RX 11** | Nettoyage audio | Licence one-time | ★★★★★ |

### Outils en surveillance (prometteurs, non encore testés sur District Zero)

| Outil | Usage potentiel | Statut |
|-------|----------------|--------|
| **Runway Gen4 Video** | Plans 2-3s avec cohérence faciale | À tester — $0.08/shot |
| **Kling 2.0** | Mouvements caméra courts | À tester |
| **Wan 2.1** | Open source video, contrôle accru | À tester |
| **Kohya SS + Flux Dev** | LoRA personnages | Prêt si besoin (ArcFace > 0.94 cible) |
| **ComfyUI** | Workflow complexe, chaining | En réserve |
| **GPT-Image-2** | Images avec texte précis, objets | À tester sur wrist display |

### Outils rejetés

| Outil | Raison du rejet | Score obtenu |
|-------|----------------|-------------|
| **Seedream 4.5** | Inspiration visage, pas préservation | ArcFace 0.566 |

---

## 15. COÛTS DE PRODUCTION ESTIMÉS

### Par shot (pipeline verrouillé)

```
1 shot = $0.08  ($0.03 FLUX.2 Pro + $0.05 Flux Fill Pro)
Temps  = 89 secondes
Output = 1344×768 (1x) + 2688×1536 (2x upscalé)
```

### Par épisode (estimation District Zero EP01 — 11 scènes)

```
Master plates décor (11 scènes × $0.03)          =   $0.33
  → réutilisables pour tous les shots de la scène
Shots Nara (estimation 18 shots × $0.05)          =   $0.90
Shots autres personnages (estimation 20 × $0.05)  =   $1.00
Variantes / retakes (20% overhead)                =   $0.45
────────────────────────────────────────────────────────────
TOTAL IMAGE EP01 (estimation)                     ≈   $2.70

Audio (Stable Audio + ElevenLabs)                 ≈   $5.00
LLM (scripts, prompts, corrections)              ≈   $3.00
────────────────────────────────────────────────────────────
TOTAL PRODUCTION EP01 (images + son + LLM)       ≈  $10-15
```

### Par saison (10 épisodes)

```
Images  : ~$27
Audio   : ~$50
LLM     : ~$30
────────────
TOTAL   : ~$100-150 pour une saison complète
```

> Ces coûts n'incluent pas les licences logicielles (Premiere, DaVinci, iZotope)
> ni le temps humain. Ils couvrent uniquement les appels API de génération.

---

## 16. ROADMAP 6-18 MOIS

### Horizon 3 mois — Immédiatement actionnable

- [ ] **Générer les 11 master plates de EP01** (seeds fixés, $0.33 total)
- [ ] **Constituer le tableau de bord Production** (seeds, palettes hex, blocs stylistiques par scène)
- [ ] **Pipeline CLI** : wrapper de `run_shot()` en ligne de commande (`python -m pipeline.run --scene SCN_002 --shot SHOT_001`)
- [ ] **Bibliothèque sonore EP01** : ambiances par lieu via Stable Audio (générer une fois, réutiliser)
- [ ] **Test Runway Gen4 Video** : évaluer fidélité faciale sur un shot 2-3s

### Horizon 6 mois — Capacités élargies

- [ ] **Mouvement caméra** : si Runway Gen4 ou Kling 2.0 atteignent ArcFace > 0.85, intégrer dans le pipeline
- [ ] **LoRA Nara** (si besoin) : si profils difficiles (profil 3/4 dos) sont nécessaires — entraînement Kohya
- [ ] **Scoring visuel automatique** : détection artefacts (mains, yeux) via vision model — éviter le cleanup manuel
- [ ] **Script LLM fine-tuné** : fine-tuner un LLM léger sur la bible + les scripts existants pour maintenir la voix des personnages
- [ ] **EP01 complet** : tous les shots générés, assembly cut prêt

### Horizon 12-18 mois — Ambition production complète

- [ ] **EP02 à EP05** en utilisant la méthode verrouillée, itération sur les apprentissages de EP01
- [ ] **Cohérence inter-épisodes** : système de vérification automatique des raccords visuels (personnages, costumes, décors) entre épisodes
- [ ] **Mix audio semi-automatique** : pipeline Reaper + iZotope + Stable Audio pour pré-mix par épisode
- [ ] **Thème musical** : si budget permet, compositeur humain pour le thème principal — reste du score via Suno/AIVA

---

## CONCLUSION OPÉRATIONNELLE

### Ce que nous avons prouvé

1. **Le prompt DOP-grade est la clé** — un prompt structuré comme un document de production professionnel produit des résultats de qualité professionelle.
2. **Le pipeline hybride est le standard** — FLUX.2 Pro (décor) + Flux Fill Pro (visage) à $0.08/shot est la méthode de production pour les personnages humains.
3. **La cohérence est une discipline, pas un accident** — seeds fixés, palettes hex verrouillées, blocs stylistiques copiés-collés : c'est le travail réel du DP sur ce pipeline.
4. **Le scoring objectif est indispensable** — ArcFace permet de comparer des méthodes sans débat subjectif. Chaque changement de pipeline doit être rebenchmarké.

### Ce qui reste humain, pour toujours

- **La vision** (showrunner)
- **Le jugement créatif** (directeur artistique)
- **Le sous-texte narratif** (head writer)
- **Le rythme émotionnel** (monteur)
- **Le son que l'on n'a pas encore imaginé** (sound designer)

### La règle d'or finale

> Un outil IA ne remplace pas un métier.
> Il remplace les tâches répétitives de ce métier,
> pour que le professionnel puisse se concentrer sur ce que seul un humain peut faire.
