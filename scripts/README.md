Scripts
=======

verify_routes.py
-----------------

But
- Analyse les blueprints Flask et liste toutes les routes avec leur niveau d’accès.
- Optionnellement, lance une vérification runtime (anonyme) pour confirmer que les routes protégées redirigent bien vers `/auth/`.

Usage
- Tableau lisible:
  - python scripts/verify_routes.py
- Export JSON:
  - python scripts/verify_routes.py --json

Détails
- L’analyse statique utilise l’AST Python pour récupérer:
  - `file`, `rule` (chemin), `func`, `methods`, `login_required`, `level`.
- La vérification runtime crée l’app via `create_app()` et fait des requêtes GET sur un petit ensemble de routes
  courantes; elle “stub” `folium` et `babel.dates` si non installés.

Intégration aux tests
- Le test `tests/test_route_protection.py` fait deux vérifications automatiques:
  1) AST: chaque route (hors auth et backups) doit avoir `@login_required` ET `@require_level(...)`.
  2) Runtime: les endpoints clés renvoient `302` vers `/auth/` pour un client anonyme.
- Lancer les tests:
  - pytest -q

Notes
- Le script et les tests n’installent aucune dépendance externe; ils simulent `folium`/`babel` si nécessaire
  uniquement pour permettre l’import de l’application.

