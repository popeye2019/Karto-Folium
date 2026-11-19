# Migration SQLite — contrats, sites et communes

État au 19 novembre 2026 : implémentation du catalogue préparée sur la branche
`codex/architecture-sqlite-metier`. La règle confirmée est **un site = un contrat**.
Le mode JSON reste actif par défaut jusqu'à la migration explicite.
Aucune donnée de production n'a été migrée. Voir `MIGRATION_SQLITE.md`.

## Objectif

Stocker les données métier dans SQLite, avec des identifiants et relations
contrôlés. Conserver les formats JSON et CSV pour les échanges de données :
l'import doit écrire dans SQLite et ne doit pas créer une deuxième base JSON
à maintenir en parallèle.

## Constat initial dans le code

- `recap.json` contient les sites utilisés par la consultation, l'édition,
  la recherche, la maintenance et la génération Folium.
- `communes.json` alimente les choix de communes ; le code tolère actuellement
  plusieurs formats de liste.
- `type_site.json` porte les types et leurs paramètres cartographiques.
- `commune_asst_collectif.json` porte des informations de communes utilisées
  pour la carte ; ses champs réels doivent être inventoriés.
- Les contours sont lus dans des fichiers GeoJSON.
- Le module Contrat mémorise actuellement une agence et des sélections
  géographiques dans la session, sans enregistrer de contrat durable.
- Les utilisateurs possèdent un champ `Contrat`, édité sous forme de liste.
  Il faudra préciser sa signification avant d'en faire une règle d'accès.
- Les sauvegardes actuelles archivent uniquement les fichiers JSON. Elles
  devront prendre en charge SQLite avant la bascule.
- Aucun import CSV métier n'a été trouvé dans cette version du dépôt.
- Les données réelles `recap.json`, `communes.json` et `type_site.json` ne sont
  pas présentes dans cette copie locale. Les données d'essai doivent donc être
  fictives, en attendant un inventaire de recette autorisé.

## Tables réalisées

| Table | Rôle et principales colonnes |
| --- | --- |
| `communes` | `id`, `code_insee` si disponible, `nom`, références géographiques vérifiées |
| `types_sites` | `id`, `libelle`, `icone`, `groupe`, `actif`, `cluster`, `echelle`, `visible` |
| `sites` | `id` reprenant INDEX, `contrat_id`, `commune_id`, `type_site_id`, `nom`, `latitude`, `longitude`, `etat`, `technologie` |
| `contrats` | `id`, `reference` unique, `nom` |
| `contrats_communes` | Périmètre explicite d'un contrat : `contrat_id`, `commune_id` |
| `imports` | Date, origine et nombres de lignes traitées par table |

Le lien contrat-site est imposé par `sites.contrat_id NOT NULL` et une clé
étrangère. Un site ne peut pas recevoir une liste de contrats.

Le schéma versionné se trouve dans `app/catalogue_schema.sql`. Les colonnes
`extras` conservent les champs complémentaires encodés en JSON dans la base,
sans remplacer les colonnes ni les relations métier. DOCUMENTATION, les champs
de mairie et les métadonnées non encore inventoriées ne sont pas supprimés.

Un contrat peut couvrir plusieurs communes. Une commune peut être concernée
par plusieurs contrats. Les liens de périmètre ne signifient pas que tous les
sites d'une commune appartiennent automatiquement à tous ses contrats.

Un site appartient à une commune et référence un type de site. Les limites
géographiques et le caractère fini des coordonnées doivent être contrôlés.
Les anciennes lignes sans coordonnées exploitables doivent être signalées
pour correction ; aucune valeur fictive ne doit être enregistrée à leur place.

Le rattachement d'un site établit la paire contrat-commune. Réaffecter un site
ne supprime pas automatiquement les anciennes communes du périmètre du contrat.
Une paire de coordonnées absente est conservée vide, sans position fictive.
L'inventaire des sources réelles reste nécessaire avant activation.

## Identifiants et intégrité

- Utiliser des identifiants internes stables ; ne plus identifier une fiche
  par sa position dans une liste.
- Conserver `INDEX` comme identifiant de provenance pour reprendre les liens
  existants et détecter les doublons à l'import.
- Conserver les codes INSEE comme texte, notamment pour les zéros initiaux.
- Ne pas fusionner deux communes simplement parce qu'elles portent le même nom.
  Une correspondance ambiguë doit apparaître dans le rapport d'import.
- Activer et vérifier les clés étrangères sur chaque connexion.
- Définir les contraintes d'unicité sur les identifiants métier confirmés.
- Refuser la suppression d'une commune ou d'un type encore référencé.
- Utiliser des requêtes paramétrées et des transactions pour les écritures.

## Parcours d'import JSON et CSV

1. Lire et valider le format, les en-têtes et les champs attendus.
2. Transformer chaque ligne vers un modèle commun indépendant du format source.
3. Contrôler identifiants, coordonnées, doublons et correspondances métier.
4. En simulation, afficher les nombres de lignes traitées par table et la
   première erreur, avec sa table et son numéro de ligne.
5. Effectuer les écritures validées dans une transaction. Une erreur ne doit
   pas laisser une migration partiellement appliquée.
6. Fournir le résultat et les comptes par table. Un nouvel import identique
   ne doit pas dupliquer les données.

L'import CSV doit gérer explicitement l'encodage, le séparateur et les champs
contenant des séparateurs ou des retours à la ligne. Les champs absents lors
d'une mise à jour ne doivent pas effacer implicitement les valeurs existantes.

## État de réalisation

- Réalisé : schéma, catalogue transactionnel et tests d'intégrité.
- Réalisé : imports JSON/CSV, simulation et journal des imports réussis.
- Réalisé : raccordement de consultation, édition, recherche, maintenance,
  types, contrats et génération Folium au catalogue actif.
- Réalisé : identifiants stables d'édition et contrat obligatoire en mode SQL.
- Réalisé : export JSON cohérent, sauvegarde SQLite et restauration vers une
  nouvelle base ; les fichiers existants ne sont jamais écrasés.
- Réalisé : interface `/catalogue/` de niveau 5 et module Contrats persistant
  de niveau 3. Les formulaires sites conservent leur niveau 4.
- Restant avant activation : inventaire et recette sur les données réelles,
  rattachement explicite des sites sans contrat et comparaison avec les sources.

Le basculement ne doit pas être fait seulement dans le formulaire d'édition :
tous les lecteurs et rédacteurs des mêmes données doivent utiliser la même
source. Les GeoJSON peuvent rester des fichiers cartographiques s'ils ne
servent pas de stockage métier modifiable.

Les utilisateurs, droits, notifications et journaux constituent un autre
périmètre de migration ; leur stockage JSON doit rester clairement identifié
tant qu'ils ne sont pas eux aussi raccordés à SQLite.

## Vérifications réalisées

- Reprise de tous les champs et identifiants de provenance.
- Relations communes-types-sites-contrats et refus des références orphelines.
- Gestion des communes homonymes et des identifiants manquants.
- Imports JSON/CSV équivalents, répétition sans doublon et annulation sur erreur.
- Ajout et modification d'un site, affichage et recherche, génération de carte.
- Compatibilité des autorisations existantes et tests anonymes.
- Sauvegarde SQLite et restauration d'une copie cohérente.
- Suite de tests existante, complétée par les scénarios de migration.

Résultat : **144 tests réussis**, dont 29 nouveaux cas SQLite. Un essai avec
Folium réel a généré une carte contenant le site SQL sans `recap.json`. Dans
le navigateur, création d'un contrat puis changement du contrat d'un site,
confirmé après réouverture de la fiche, sur données fictives.

Les sauvegardes SQLite et JSON sont distinctes, ce qui est indiqué dans
l'interface. Le module Contrats historique reste inchangé en mode JSON.
Les champs Contrat des comptes ne deviennent pas une nouvelle règle d'accès.

La fusion et le déploiement ne sont pas autorisés par ce document.
