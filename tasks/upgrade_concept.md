Voici les **fiches de poste détaillées** pour chaque métier créatif de **District Zero**, avec :

- Missions principales
- Compétences requises
- Outils IA à maîtriser
- Livrables attendus
- Niveau d’autonomie / collaboration

---

## 1. SHOWRUNNER / CRÉATEUR·TRICE

> **Statut** : Humain indispensable – visionnaire et décideur final

### Missions
- Définir l’arc narratif sur 10 épisodes (conspiration + rébellion)
- Valider chaque script, chaque dialogue clé
- Assurer la cohérence thématique, tonale et morale de la série
- Valider les références visuelles des personnages et lieux
- Décider des cliffhangers, des révélations (ex : Elian épisode 7)

### Compétences requises
- Écriture de séries (structure, personnages, sous-textes)
- Direction artistique (capacité à valider ou rejeter une image)
- Gestion d’équipe créative (même réduite)

### Outils IA
- **ChatGPT / Claude** : génération de variantes, réécriture
- **Midjourney / GPT-Image-2** : exploration visuelle rapide

### Livrables
- Bible série finalisée
- Scripts validés (10 épisodes)
- Validation finale de chaque plan clé

### Collaboration
- Travaille avec : Head Writer, Directeur Artistique, Monteur

---

## 2. HEAD WRITER (scénariste principal)

> **Statut** : Humain indispensable – second du Showrunner

### Missions
- Écrire ou superviser l’écriture de chaque épisode
- Maintenir la voix distincte de chaque personnage (Nara, Mira, Elian, Vale, Rook)
- Proposer des structures d’épisodes (actes, points de rupture)
- Réécrire les dialogues générés par IA

### Compétences requises
- Structure dramatique (3 actes / 5 actes)
- Dialogues réalistes et sous-textes
- Adaptation à la contrainte visuelle (montrer, ne pas dire)

### Outils IA
- **ChatGPT / Claude** : brainstorming, réécriture multiple
- **Notion AI** : organisation des arcs

### Livrables
- Scripts des 10 épisodes (version production)
- Fiches personnages à jour

### Collaboration
- Travaille avec : Showrunner, Dialoguiste IA (assistant)

---

## 3. DIRECTEUR ARTISTIQUE (Production Designer IA)

> **Statut** : Humain indispensable – gardien de l’univers visuel

### Missions
- Créer la bible visuelle : Brutalisme, eau, acier corrodé, teal/ambre
- Valider toutes les images de référence (personnages + lieux)
- Définir les palettes par émotion / scène
- Superviser les prompteurs pour maintenir la cohérence

### Compétences requises
- Culture d’image (cinéma, architecture dystopique)
- Sens de la lumière et de la matière
- Capacité à formuler des prompts visuels précis

### Outils IA
- **Midjourney v7** (références artistiques)
- **GPT-Image-2** (précision)
- **ComfyUI** (si fine-tuning LoRA)

### Livrables
- Bible visuelle (PDF – 50 à 100 images référencées)
- Palettes validées par scène type
- Prompt templates figés

### Collaboration
- Travaille avec : DP (image), Color Key, Prompteur·euse

---

## 4. COLOR KEY ARTIST

> **Statut** : Humain indispensable – l’émotion par la couleur

### Missions
- Définir les gammes colorimétriques par type de lieu / émotion
  - Système : teal / bleu-acier froid
  - Résistance : ambre chaud, lumière de lampe pratique
  - Révélation (épisode 8) : rouge d’alarme + bleu extérieur
- Assurer la transition colorimétrique entre les plans
- Travailler avec le DP pour les prompts d’étalonnage

### Compétences requises
- Connaissance de l’étalonnage (DaVinci Resolve ou équivalent théorique)
- Sensibilité aux ambiances (froid/oppressant vs chaud/intime)

### Outils IA
- **GPT-Image-2** (génération avec consignes couleur précises)
- **Midjourney** (exploration de teintes)

### Livrables
- Palette série (références RGB/Hex)
- Tableau de correspondances (lieu/émotion → palette)
- Prompts types intégrant l’étalonnage

### Collaboration
- Travaille avec : Directeur Artistique, DP

---

## 5. DIRECTEUR DE LA PHOTOGRAPHIE (DP / Cinématographer)

> **Statut** : Humain indispensable – vous incarnez ce rôle via les prompts

### Missions
- Définir pour chaque type de plan :
  - Optiques (focale, f/, profondeur de champ)
  - Mouvements caméra (fixe, traveling, steadycam, subjective)
  - Sources lumineuses (halogène, eau réfléchie, néon, alarme rouge)
  - Grain / texture
- Rédiger le bloc stylistique commun à tous les prompts
- Assurer la cohérence lumière d’un plan à l’autre

### Compétences requises
- Culture cinéma technique (Arri Alexa, anamorphiques, etc.)
- Capacité à traduire une intention en paramètres image

### Outils IA
- **Tous les modèles** (c’est vous qui donnez les instructions)

### Livrables
- Bloc stylistique verrouillé (recopié dans chaque prompt)
- Fiches « lumière » par lieu (source dominante, direction, couleur)
- Banque de mouvements caméra décrits (prompts types)

### Collaboration
- Travaille avec : Color Key, Monteur

---

## 6. SUPERVISEUR·TRICE DES MODÈLES (LoRA / Identité personnages)

> **Statut** : Technique + créatif – garant de la cohérence faciale

### Missions
- Rassembler 15–25 images de référence par personnage principal
- Entraîner des LoRAs Flux pour Nara, Mira, Elian, Vale, Rook
- Tester et valider la fidélité des visages
- Mettre à jour les LoRAs si besoin (évolution costume, âge, blessure)

### Compétences requises
- ComfyUI / Kohya (entraînement LoRA)
- Compréhension de l’identité faciale (angles, expressions, lumières)
- Patience et rigueur (tests multiples)

### Outils IA
- **Flux + Kohya** (entraînement)
- **ComfyUI** (génération avec LoRA)
- **InsightFace** (vérification)

### Livrables
- 1 LoRA final par personnage principal
- Guide d’utilisation du LoRA (poids recommandé)

### Collaboration
- Travaille avec : Directeur Artistique, Prompteur·euse

---

## 7. PROMPTEUR·EUSE PRINCIPAL·E (Lead Prompt Engineer)

> **Statut** : Humain clé – exécute la vision en images

### Missions
- Générer toutes les images de référence (personnages + lieux)
- Générer les images de storyboard / plans de l’épisode
- Appliquer systématiquement : LoRAs + bloc stylistique + consignes de lumière
- Itérer rapidement pour obtenir la meilleure image

### Compétences requises
- Maîtrise de **GPT-Image-2** (priorité) et **Midjourney v7**
- Compréhension des paramètres (ratio, qualité, style raw)
- Capacité à décrire avec précision (émotion, angle, détail)

### Outils IA
- **GPT-Image-2** (références, précision texte)
- **Midjourney v7** (ambiances artistiques)
- **ComfyUI + Flux + LoRAs** (cohérence personnages)

### Livrables
- Banque d’images référencées par scène (SCN_001 à SCN_011…)
- Storyboard image par image (séquences)
- Prompts réutilisables pour corrections / variantes

### Collaboration
- Travaille avec : Directeur Artistique, DP, Monteur

---

## 8. MONTEUR IMAGE (Editor)

> **Statut** : Humain indispensable – le rythme et l’émotion

### Missions
- Assemble les images générées (plans, séquences)
- Crée le rythme, les ellipses, les tensions
- Gère les cliffhangers de fin d’épisode
- Propose des recuts si une séquence ne fonctionne pas

### Compétences requises
- Logiciel de montage (Premiere Pro, DaVinci Resolve, Final Cut)
- Sens du rythme et de la narration visuelle
- Capacité à travailler avec des images non encore « finies »

### Outils IA (assistance)
- **Runway ML / Pika Labs** (génération de transitions ou inserts manquants)
- **Topaz Video AI** (upscale / fluidité)

### Livrables
- Rough cut → fine cut → locked cut (10 épisodes)
- Notes pour le Cleanup Artist (artefacts à corriger)

### Collaboration
- Travaille avec : Showrunner, Cleanup Artist, Sound Designer

---

## 9. CLEANUP ARTIST (correction d’artefacts)

> **Statut** : Humain indispensable – l’œil qui traque les erreurs IA

### Missions
- Identifier et corriger les aberrations récurrentes :
  - Mains, doigts, yeux asymétriques
  - Incohérences lumineuses
  - Artefacts de compression ou de fusion
- Uniformiser la qualité entre les plans

### Compétences requises
- Photoshop avancé (ou équivalent)
- Connaissance des outils IA de retouche (inpainting, outpainting)
- Patience et précision

### Outils IA
- **Photoshop Generative Fill**
- **ComfyUI Inpainting**
- **Krita + AI** (open source)

### Livrables
- Plans corrigés (remplacent les générations brutes)
- Guide des erreurs fréquentes pour améliorer les prompts

### Collaboration
- Travaille avec : Monteur, Prompteur·euse

---

## 10. SOUND DESIGNER

> **Statut** : Humain indispensable – l’âme sonore du district

### Missions
- Créer l’ambiance sonore de District Zero :
  - Eau qui frappe, clapotis lointain
  - Résonance métallique, vibration des Épines Dorsales
  - Brouilleurs, alarmes, chuchotements numériques
  - Silences oppressants
- Construire des « textures » sonores par lieu (Mur, Atrium, Marché noir)

### Compétences requises
- Logiciel audio (Pro Tools, Reaper, Ableton)
- Culture du design sonore (cinéma, jeu vidéo)
- Capacité à raconter sans image

### Outils IA (assistance)
- **ElevenLabs** (voix off, murmures)
- **Stable Audio** (génération de nappes)
- **Krotos** (bruitages interactifs)

### Livrables
- Banque d’ambiances sonores par lieu
- Pistes sonores brutes par épisode
- Pistes finales pour mixage

### Collaboration
- Travaille avec : Monteur, Mixeur, Compositeur

---

## 11. MIXEUR AUDIO (Re-recording Mixer)

> **Statut** : Humain indispensable – l’équilibre final

### Missions
- Équilibrer dialogues, ambiances, bruitages et musique
- Livrer un mix 5.1 ou Atmos pour plateforme
- Assurer la conformité loudness (Netflix, Apple TV+)
- Travailler la spatialisation (immersion)

### Compétences requises
- Console de mixage / DAW (Pro Tools)
- Connaissance des normes broadcast
- Oreille fine et endurance

### Outils IA (assistance)
- **iZotope RX** (nettoyage advanced)
- **Audiolabs** (automatisation assistée)

### Livrables
- Masters audio des 10 épisodes (stéréo + 5.1)
- Documentation technique

### Collaboration
- Travaille avec : Sound Designer, Compositeur

---

## 12. COMPOSITEUR·TRICE (musique originale)

> **Statut** : Idéalement humain – l’émotion qui n’existe pas encore en IA

### Missions
- Écrire le thème principal de District Zero
- Créer des variations par personnage / tension
- Produire 20–30 minutes de musique originale par épisode (selone budget)
- S’adapter au montage final

### Compétences requises
- Composition orchestrale / électronique
- Culture cinéma (thrillers dystopiques : Johan Söderqvist, Cliff Martinez)
- Capacité à travailler sous contrainte de délai

### Outils IA (assistance ou remplacement low-cost)
- **Suno / Udio** (génération de thèmes, ambiance)
- **AIVA** (musique algorithmique)

### Livrables
- Thème principal (2mn)
- Leitmotivs par personnage
- Pistes musicales par épisode

### Collaboration
- Travaille avec : Showrunner, Monteur, Mixeur

---

## RÉCAPITULATIF – 12 MÉTIERS CRÉATIFS POUR DISTRICT ZERO

| # | Métier | Humain indispensable | Peut être assisté / remplacé IA |
|---|--------|---------------------|--------------------------------|
| 1 | Showrunner | ✅ Oui | ❌ Non |
| 2 | Head Writer | ✅ Oui | Assistant (LLM) |
| 3 | Directeur Artistique | ✅ Oui | ❌ Non |
| 4 | Color Key Artist | ✅ Oui | Assistant (génération) |
| 5 | DP (image) | ✅ Oui (vous) | ❌ Non |
| 6 | Superviseur LoRA | ✅ Oui | ❌ Non (technique) |
| 7 | Prompteur·euse principal | ✅ Oui | ❌ Non |
| 8 | Monteur | ✅ Oui | ❌ Non |
| 9 | Cleanup Artist | ✅ Oui | Outils IA d’assistance |
| 10 | Sound Designer | ✅ Oui | Assistant (ElevenLabs, etc.) |
| 11 | Mixeur | ✅ Oui | Assistant (RX) |
| 12 | Compositeur | Recommandé | IA possible (Suno/Udio) |

---

## 🎯 TAILLE D’ÉQUIPE CRÉATIVE RECOMMANDÉE

| Option | Effectif | Remarque |
|--------|----------|----------|
| **Équipe minimale viable** | 6 personnes | Showrunner, Directeur Artistique, DP (vous), Prompteur, Monteur, Sound Designer (tout en un) |
| **Équipe confortable (recommandée)** | 10–12 personnes | Tous les métiers ci-dessus, sans chevauchement forcé |
| **Équipe premium** | 15–18 | Avec un vrai compositeur, un 2e prompteur, un assistant monteur |

---

Voulez-vous maintenant :
- un **organigramme** (qui reporte à qui) ?
- un **budget estimatif** par poste ?
- un **calendrier de production** intégrant ces métiers ?