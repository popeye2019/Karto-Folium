# carto_flask_v9-CHATGPT

Ce projet affiche des données JSON sur une carte avec des icônes différentes suivant les objets.

Vérifications d'accès et routes
-------------------------------

Pour garantir que toutes les routes non-auth sont protégées par `@login_required` et `@require_level(...)`,
des outils sont fournis côté scripts et tests.

- Lancer la vérification par script (liste les routes et niveaux) :
  - `python scripts/verify_routes.py`
  - `python scripts/verify_routes.py --json` (export JSON)

- Lancer les tests automatiques (AST + runtime anonymes → 302 vers `/auth/`) :
  - `pytest -q`

CI (recommandé)
---------------

Intégrez ces commandes dans votre pipeline pour éviter toute régression :

- `python scripts/verify_routes.py` (optionnel mais utile en log)
- `pytest -q`

Notes
-----

- Les scripts/tests font un “stub” minimal de `folium`/`babel` pour pouvoir importer l’app sans dépendances
  lors d’une simple vérification des routes. En environnement applicatif, installez les dépendances réelles
  (voir `requirements.txt`).
