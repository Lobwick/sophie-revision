---
name: cartes
description: Commande /cartes — ajoute de nouvelles cartes ou corrige des cartes existantes à partir d'un texte collé ou d'un JSON. Aperçu avant écriture, motif et sources pour toute correction, doublons refusés, un seul commit annulable.
---

# /cartes — ajouter ou corriger des cartes

Entrée : texte libre (« Q : … R : … », liste, tableau, CSV) ou JSON. Tu **transformes** l'entrée en liste de cartes, tu **vérifies**, tu montres un
**aperçu**, puis — seulement après son « oui » — tu écris. **Jamais de contenu inventé** : une réponse manquante se demande.

## 1. Comprendre ce qu'elle veut
- **Ajouter** : cartes sans `id`. **Corriger** : cartes qui désignent une carte existante (elle cite l'id, ou décrit la carte).
- Retrouver une carte : `find_cards(query, deck?)` → propose les 1-3 candidates (id, question, réponse) et demande laquelle. Ne corrige jamais une
  carte « à peu près » identifiée.
- Paquet (`deck`) : clé parmi `quiz_options` (cardio, pneumo, infectio, neuro, nephro, endoc, hge, hemato, cancero, gyneco, pediatrie, psy, urgences,
  transversal, dermato_rhumato, ophtalmo, orl, cmf, reanimation, geriatrie_mpr). Ambigu → demande.

## 2. Format
```json
{"cartes": [
  {"deck": "cardio", "rang": "A", "question": "…?", "answer": "…", "tags": ["SCA"], "sources": ["[Cardiologie — SCA, p.23](/pdf/…?page=23)"]},
  {"id": "cardio-002", "answer": "…", "motif": "Pourquoi", "sources": ["[…](…)"]}
]}
```
Une carte = **un fait atomique** (question courte, réponse courte). Un texte qui en mélange plusieurs → propose de le découper, ne coupe pas seul.
JSON déjà au bon format : valide-le tel quel, sans le réécrire.

## 3. Vérifier avant d'écrire (règles communes : aucune supposition)
Pour chaque carte médicale (surtout chiffres, seuils, délais, doses) : `search_cours` + `get_cours` pour confronter au cours ; recherche web sur source officielle
si le point évolue (`recherche-sources`). Résultat : concordant / divergent / non vérifiable — **dis-le carte par carte**. Ajoute en `sources` les
citations `[Catégorie — Titre, p.N](lien)` (lien fourni par les outils). Si le cours contredit sa carte, montre les deux et laisse-la décider.

## 4. Aperçu puis écriture
1. `save_cards(apercu=true, cartes=[…])` → montre un tableau : action (ajoutée / modifiée / corrigée), id, **avant → après**, avertissements.
2. Demande confirmation (une ligne). Sans « oui » explicite : n'écris rien.
3. `save_cards(cartes=[…])` : tout ou rien (une carte invalide annule le lot), **un seul commit** (annulable avec `undo_last_change`).
Règles de l'outil : une carte **du deck** ne se corrige qu'avec un `motif` ; l'original n'est jamais effacé (affiché comme « ancienne version ») ;
une carte **perso** se modifie en place (l'historique git garde l'ancienne) ; une question déjà présente est refusée comme **doublon**.

## 5. Terminer
Résume : N ajoutées, N modifiées, N corrigées, ce qui a été refusé et pourquoi. Puis : **« ✔ Enregistré — le site se met à jour tout seul. »**
Seulement si la réponse de l'outil contient la ligne `[site] Données modifiées … se recharge tout seul` ; sinon dis que l'écriture n'est pas confirmée.
Les nouvelles cartes sont « nouvelles » à réviser (onglet **Cartes**) ; propose `/quiz` pour les tester.

**Liens vers les cours** : chaque citation de cours est cliquable — `[Catégorie — Titre, p.N](lien)` avec le `lien` renvoyé par les outils.
