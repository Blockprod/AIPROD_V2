---
modele: sonnet-4.6
mode: ask
contexte: codebase
produit: tasks/audits/resultats/audit_determinism_aiprod.md
derniere_revision: 2026-04-20
creation: 2026-04-20 à 17:56
---

#codebase

Tu es un expert en systèmes déterministes et reproductibilité de pipelines de données.
Tu réalises un audit EXCLUSIVEMENT sur le déterminisme byte-level d'AIPROD_V2.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Réfléchis profondément étape par étape avant
de produire ta sortie. Explore d'abord, planifie
ensuite, puis exécute.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà :
  tasks/audits/resultats/audit_determinism_aiprod.md

Si trouvé, affiche :
"⚠️ Audit déterminisme existant détecté :
 Fichier : tasks/audits/resultats/audit_determinism_aiprod.md
 Date    : [date modification]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit déterminisme existant. Démarrage..."

─────────────────────────────────────────────
DÉFINITION
─────────────────────────────────────────────
Un pipeline est DÉTERMINISTE BYTE-LEVEL si :
  run_pipeline(text, title) == run_pipeline(text, title)
toujours, quelle que soit la machine, l'heure, l'ordre des imports.

─────────────────────────────────────────────
BLOC 1 — SOURCES DE RANDOMNESS
─────────────────────────────────────────────
Recherche dans TOUT le code source (core/, models/, engine.py, main.py) :
- import random / from random import
- uuid.uuid4() / uuid1()
- random.shuffle / random.choice / random.sample
- os.urandom / secrets.token_hex
- hashlib (si la valeur sert à nommer un champ)

Pour chaque occurrence : fichier:ligne + évaluation de l'impact

─────────────────────────────────────────────
BLOC 2 — DÉPENDANCES TEMPORELLES
─────────────────────────────────────────────
- import datetime / from datetime import
- time.time() / time.monotonic()
- datetime.now() / datetime.utcnow()
- Utilisation pour nommer ou ordonner des éléments

─────────────────────────────────────────────
BLOC 3 — COLLECTIONS NON ORDONNÉES
─────────────────────────────────────────────
- Utilisation de set() avec itération ultérieure (for x in set_var)
- dict.keys() / .values() itéré sans sorted() (Python 3.7+ = ordonné par insertion, OK si insertion order garantie)
- Counter.most_common() vs Counter.elements()

─────────────────────────────────────────────
BLOC 4 — TRI IMPLICITE
─────────────────────────────────────────────
- sorted() sans key explicite sur des objets non-strings
- Tri de scènes ou shots qui détruirait l'ordre d'insertion de Pass1
- list.sort() in-place non prévu

─────────────────────────────────────────────
BLOC 5 — TEST DE DÉTERMINISME
─────────────────────────────────────────────
- Cherche test_json_byte_identical dans test_pipeline.py
- Le test compare-t-il bytes ou str ?
- Méthode : deux appels run_pipeline() → json.dumps() → comparaison ?
- Est-il inclus dans la suite CI ?

─────────────────────────────────────────────
FORMAT DE SORTIE
─────────────────────────────────────────────
# AUDIT DÉTERMINISME — AIPROD_V2 — [DATE]
## Verdict : DÉTERMINISTE ✅ / NON DÉTERMINISTE ❌ / À VÉRIFIER ⚠️
## Résumé exécutif
## BLOC 1 — Sources de randomness
## BLOC 2 — Dépendances temporelles
## BLOC 3 — Collections non ordonnées
## BLOC 4 — Tri implicite
## BLOC 5 — Test de déterminisme
## Problèmes identifiés
| ID | Sévérité | Fichier:ligne | Description | Impact |
## Recommandations
