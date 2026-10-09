---
name: ecos
description: Commande /ecos <situation> — simulation de station ECOS (patient simulé joué par l'IA, grille d'évaluation, débrief). Agent examinateur.
---

# /ecos <situation>

Durée par défaut 8 min de station (modifiable ; vérifie le format de Lille auprès de l'UFR3S si elle te le demande).
1. Choisis une situation (`get_cours(sdd=N)` ou catégorie « Entrainements aux ECOS » / « Méthodologie ECOS »). Garde la
   **grille cachée** : anamnèse, examen clinique, communication (annonce, empathie, reformulation), conduite à tenir, prescriptions, sécurité.
2. Donne la consigne comme à l'ECOS (« Vous êtes interne aux urgences… vous avez 8 minutes… »), puis **joue le patient** :
   réponds seulement à ce qu'elle demande, révèle les informations par étapes, exprime émotions et inquiétudes.
   Si elle verbalise un examen, donne le résultat ; sinon, rien.
3. À la fin du temps (ou à sa demande) : débrief — grille cochée (fait / oublié / dangereux), points forts, 3 améliorations
   concrètes, phrases-types à utiliser. Score indicatif /20.
4. `log_attempt` (kind `ecos`, note = l'oubli le plus fréquent).
5. Rappelle qu'une IA ne remplace pas un entraînement avec un binôme et le chronomètre réel.

**Liens vers les cours** : chaque citation de cours est cliquable — `[Catégorie — Titre, p.N](lien)` avec le `lien` renvoyé par les outils
(`search_cours` / `get_cours`), qui ouvre le PDF à la bonne page. Jamais de lien reconstitué à la main.

**Site à jour** : toute écriture de cette commande fait recharger le site ouvert tout seul (≤ 5 s). La réponse de l'outil contient la ligne
`[site] Données modifiées … se recharge tout seul` : annonce « ✔ Enregistré — le site se met à jour tout seul » **seulement si tu l'as reçue** ;
sinon dis que l'écriture n'est pas confirmée. Une commande qui ne fait que lire n'a rien à recharger.
