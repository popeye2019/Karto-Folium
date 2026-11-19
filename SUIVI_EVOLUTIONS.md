# Suivi des évolutions Karto-Folium

## 19 novembre 2026 — Catalogue SQLite

- Demande : migrer le catalogue avec imports JSON/CSV ; règle confirmée :
  un site appartient à un seul contrat.
- Base locale propre, identique à GitHub `main`, commit
  `b42aaf1a05911098013805c385026fd676145b46` avant préparation.
- Branche séparée : `codex/architecture-sqlite-metier`.
- Schéma relationnel, catalogue transactionnel, commande de migration avec
  simulation, imports JSON/CSV, export et sauvegarde/restauration ajoutés.
- Consultation, recherche, édition, types, contrats, maintenance et Folium
  raccordés au catalogue actif ; identifiants d'édition stables en mode SQL.
- Page de gestion des données et contrat obligatoire dans les formulaires.
- 144 tests réussis, dont 29 nouveaux cas SQLite ; essai Folium réel sans
  `recap.json` et essai navigateur sur données fictives réussis.
- Mode JSON conservé par défaut ; aucune bascule de production ni migration
  des données réelles, absentes du dépôt local. Comptes, journaux,
  notifications et commentaires restent en JSON dans ce périmètre.
- Avant activation : inventorier les sources réelles, renseigner les contrats
  manquants, simuler, comparer les comptes et tester en recette.
- Détails dans `ARCHITECTURE_SQLITE.md` et `MIGRATION_SQLITE.md`.

## 19 novembre 2026 — Fiabiliser la saisie des coordonnées GPS

Demande : améliorer le site et poursuivre ses évolutions par des changements
vérifiables, sur une branche séparée et présentés dans une Pull Request.

État initial : le dossier de travail ne contenait que les consignes AGENTS.MD.
Le dépôt a été cloné dans `Karto-Folium/`. La copie obtenue était propre et
identique à `origin/main`, commit `6910fbe16631555cc4ac4a4a167703e5f0ce72df`.
Aucune issue ni Pull Request ouverte n'a été trouvée lors de cette vérification.

Branche : `codex/fiabiliser-coordonnees-sites`.

### Problèmes corrigés

- À l'ajout, une latitude ou longitude non numérique faisait échouer le
  réaffichage du formulaire après validation.
- Les valeurs `NaN`, infinies et hors limites géographiques pouvaient être
  acceptées à l'enregistrement.
- À la modification, les coordonnées n'étaient pas contrôlées et une ancienne
  coordonnée incorrecte pouvait empêcher l'ouverture de la fiche.
- Le champ TECHNOLOGIE était perdu lors du réaffichage d'un ajout invalide.

### Comportement obtenu

- Contrôle côté serveur des latitudes entre -90 et 90 et des longitudes entre
  -180 et 180, bornes incluses ; refus des valeurs non finies.
- Message par coordonnée incorrecte ; aucune écriture du fichier des sites
  lorsque ces contrôles échouent.
- Conservation des champs saisis pour permettre leur correction.
- Centre de carte de secours à 46.5 / 2.5 si la paire de coordonnées est invalide,
  y compris pour une requête directe vers la carte.
- Les anciennes fiches contenant des coordonnées incorrectes restent ouvrables
  pour correction. Aucune migration automatique des données n'est effectuée.

### Vérifications

- Avant changement : `python -m pytest -q` — 66 tests réussis.
- Après changement : `python -m pytest -q` — 115 tests réussis, dont 49 nouveaux
  cas sur les coordonnées, les saisies conservées et le centre de carte.
- `python scripts/verify_routes.py` — protections statiques présentes et
  redirections anonymes vers `/auth/` confirmées pour les huit parcours vérifiés.
- Essai navigateur local avec données fictives et Folium 0.16.0 réel : saisie
  d'une latitude texte, message de validation, conservation du nom et de la
  technologie, affichage de la carte avec le centre de secours.
- Les tests automatiques emploient le substitut Folium prévu par le projet ;
  l'essai navigateur complète cette vérification. Aucun essai en production.

### Points restant à traiter

- Améliorer l'affichage des formulaires sur petits écrans : le titre, le
  formulaire et la carte occupent actuellement trois cellules d'une grille
  à deux colonnes, ce qui réduit inutilement la largeur disponible.
- Étudier des messages de validation persistants près des champs : les alertes
  globales disparaissent actuellement après cinq secondes.
- Mettre en place les vérifications automatiques dans GitHub Actions selon la
  recommandation du README.
- Vérifier les données réelles et les parcours métier dans un environnement de
  recette avant toute mise en production.

La fusion dans `main` et le déploiement restent soumis à l'accord du propriétaire.
