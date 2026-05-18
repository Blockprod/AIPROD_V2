Question mal posée. Reformule-la d'abord.

**"Comment m'assurer que mon projet va générer"** — tu ne peux pas t'en assurer par le code. Le code ne crée pas la qualité artistique. Il la transporte ou la détruit. La qualité vient d'avant.

La vraie question est : **"Qu'est-ce qu'un DOP de grand studio fait que tu ne fais pas encore ?"**

Voici la réponse honnête.

---

## Ce qu'un vrai DOP fait — et que ton pipeline ne fait pas encore

### 1. Il pense en lumière motivée, pas en description de lumière

Tu écris : `"cold blue-white industrial fluorescent corridor light from behind"`

Un DOP pense : *"Cette lumière existe parce qu'il y a une rangée de tubes fluorescents à 4 mètres derrière elle. Elle a une température de 6200K. Elle crée un halo sur ses cheveux mouillés. Son visage est dans l'ombre — la seule lumière sur sa joue vient du reflet du sol en métal."*

**La différence** : il part d'une réalité physique et la décrit. Toi tu décris un effet sans sa cause. Les modèles sentent cette différence.

**Action** : pour chaque shot, commence par écrire la source de lumière comme si elle existait vraiment dans l'espace. Puis décris ce qu'elle fait sur chaque surface.

---

### 2. Il a une image de référence réelle dans la tête — pas un style général

"Roger Deakins / Sicario" c'est un continent. Deakins a fait 200 plans différents dans Sicario.

Un vrai DOP dit : **plan précis, minute précise, pourquoi ce plan**.

> *"La séquence tunnel à 1h23 — le couloir noir avec les lunettes de vision nocturne. Ce plan-là. Cette compression d'espace. Cette façon dont les silhouettes perdent toute humanité dans le vert."*

**Action** : pour chaque lieu et chaque type de scène, identifie **1 plan précis** dans 1 film précis. Pas un réalisateur. Pas un film. Un plan. Intègre-le dans ton reference_pack avec timecode et description de ce qui fait ce plan.

---

### 3. Il pense à ce que la caméra **ne montre pas**

90% des images IA sont trop complètes. Tout est visible, tout est éclairé, tout est dans le cadre.

Les images qui coupent le souffle sont celles où **quelque chose d'essentiel est absent du cadre** — suggéré, deviné, hors-champ.

Lubezki dans *The Revenant* : la menace n'est jamais dans le cadre au moment où tu la ressens. Van Hoytema dans *Dunkirk* : la mer est plus terrifiante quand elle est hors-cadre.

**Action** : ajoute un champ `off_frame_tension` dans tes shots IR. Ce champ décrit ce qui n'est PAS dans l'image mais doit se sentir. Injecte-le dans le prompt comme contrainte négative d'espace.

---

### 4. Il maîtrise le **moment dans le mouvement**

Une image fixe d'un grand studio n'est jamais neutre dans le temps. Elle capture **l'instant juste avant** ou **juste après** — jamais le milieu.

Cartier-Bresson appelait ça l'instant décisif. En cinéma : le frame extrait qui raconte tout seul toute la scène.

Tes prompts décrivent des états. *"Elle regarde par-dessus son épaule."* C'est statique.

Un DOP décrit un mouvement gelé : *"Elle vient de se retourner — son poids est encore sur le pied avant, son regard a un quart de seconde d'avance sur son corps, ses épaules n'ont pas encore suivi sa tête."*

**Action** : remplace tous tes verbes d'état par des verbes de mouvement interrompu. Pas *"elle regarde"* — *"elle vient de tourner la tête, le mouvement pas encore achevé"*.

---

### 5. Il pense **matière**, pas couleur

"Teal and amber" c'est une palette. Ce n'est pas une image.

Un DOP pense : *"Le métal de ce couloir a 30 ans de corrosion. La rouille est orange sous la crasse noire. L'eau qui suinte des joints laisse des traces blanches calcaires. La lumière froide fait ressortir le bleu-vert de l'oxydation du cuivre sur les tuyaux."*

La couleur émerge de la matière. Pas l'inverse.

**Action** : pour chaque lieu, écris d'abord les matériaux et leur état de dégradation. La palette en découle. Ne commence jamais par la couleur.

---

## Ce que tu dois construire concrètement

### Le "Shot Intent Document" — une page par plan clé

Avant tout prompt, avant tout code, ce document existe :

```
SHOT INTENT — SCN_003 / SHOT_005

VÉRITÉ DRAMATIQUE
Nara comprend qu'elle ne peut plus faire confiance à Elian.
Elle ne le dit pas. Elle ne le montre pas. Mais son corps le sait avant elle.

MOMENT DANS LE TEMPS
L'instant où elle vient de finir de parler. 
Le silence vient de commencer. Elle n'a pas encore décidé quoi faire de ce silence.

SOURCE DE LUMIÈRE RÉELLE
Tube fluorescent derrière elle à gauche, 6200K, diffusé par condensation sur le plafond.
Reflet de l'écran de contrôle à droite, 4800K pulsé, 0.3 secondes de cycle.

MATIÈRE DOMINANTE
Acier galvanisé oxydé. Eau stagnante sur béton fissuré. 
Condensation sur les surfaces froides.

RÉFÉRENCE EXACTE
Children of Men — plan de Kee dans la ferme. 1h04.
La lumière qui vient de derrière. Le visage dans l'ombre. 
La révélation qui n'est pas encore arrivée mais qu'on sent dans l'air.

CE QUI N'EST PAS DANS LE CADRE
Elian. Sa présence hors-champ à droite crée la tension.
Le couloir qui s'étend derrière elle — la fuite possible.

CE QUE LE SPECTATEUR DOIT RESSENTIR
Que quelque chose vient de se terminer sans que personne ne l'ait dit.
```

**C'est ce document qui génère le prompt. Pas l'inverse.**

---

## La réponse courte

Ton pipeline est capable de transporter la qualité d'un grand studio. Il ne peut pas la créer.

Ce qui manque n'est pas dans le code. C'est **en amont** : la pensée dramatique et physique qui précède chaque image.

Construis le Shot Intent Document pour tes 5 plans les plus importants de l'épisode 1. Génère-les. Compare avec ce que tu as maintenant. La différence sera immédiatement visible — et elle te dira exactement ce que ton pipeline doit encoder pour le reste de la série.