# Utiliser le catalogue SQLite

La règle est : un site = un contrat. Les utilisateurs, droits, notifications,
commentaires de maintenance et journaux restent en JSON dans cette évolution.
Aucune commande ci-dessous ne doit être lancée contre les données de production
avant validation de la recette.

## Préparer une copie de recette

Depuis la racine du dépôt, choisir une nouvelle base et un dossier contenant
une copie des fichiers JSON de sites. Les chemins ci-dessous sont des exemples.
Ne pas copier la base ni les données métier dans Git.

Pour créer les tables et vérifier la migration sans importer les données dans
la base cible, utiliser d'abord la commande de préparation :

```powershell
python scripts/catalogue_sqlite.py --database instance/catalogue.sqlite3 prepare --data-dir chemin/vers/copie/sites --report instance/rapport-preparation.json
```

Elle crée une base vide si nécessaire, puis effectue la simulation sur une
copie temporaire. Une base cible existante reste intacte. Le rapport indique
les six tables, leur version de schéma, les comptes actuels, les empreintes
SHA-256 des sources présentes, les comptes après simulation et les erreurs.
Le code retour vaut 0 si la migration a été vérifiée, 2 si les tables sont
prêtes mais les sources absentes ou invalides, et 1 en cas d'erreur technique
ou d'arguments incompatibles. `donnees_importees` reste faux pendant cette
préparation. Le rapport ne peut pas remplacer la base ni les fichiers sources.

Sans `--data-dir`, la préparation cherche les sources dans `app/data/sites`.
Un contrat initial peut être fourni par `--contrat`, selon la règle expliquée
ci-dessous. Les étapes séparées restent disponibles :

```powershell
python scripts/catalogue_sqlite.py --database instance/catalogue.sqlite3 init
python scripts/catalogue_sqlite.py --database instance/catalogue.sqlite3 migrate --data-dir chemin/vers/copie/sites --contrat REF-CONTRAT --dry-run
```

La migration lit `recap.json`, et, s'ils sont présents, `type_site.json`,
`communes.json` et `commune_asst_collectif.json`. Les contrats indiqués dans
les sites sont repris et créés à partir de leur référence, avec celle-ci
comme nom initial.

`--contrat REF-CONTRAT` affecte seulement les sites sans champ CONTRAT renseigné.
**Ne l'utiliser que si tous ces sites appartiennent réellement à ce contrat.**
Sinon, renseigner CONTRAT pour chaque ligne dans la copie source. Il n'y a
pas d'affectation automatique à un contrat sans cette option explicite.

Les communes ou types absents des référentiels sont récupérés depuis les noms
des sites. Aucun code géographique n'est inventé. Si une commune existe sans
code alors que le site fournit un CODE_INSEE, enrichir explicitement le
référentiel pour éviter un rapprochement ambigu.

Deux communes de même nom avec des codes INSEE distincts restent distinctes,
y compris si elles sont reconstruites depuis les seuls sites. Un même code
associé à des noms contradictoires bloque la migration. Les libellés des
contrats déjà enregistrés sont conservés lors d'une nouvelle migration.

Corriger les erreurs signalées et relancer la simulation. La première erreur
arrête le lot. Un ancien INDEX non entier, un doublon, un nom obligatoire absent
ou des coordonnées incorrectes doivent être corrigés dans la copie de recette.
La migration suppose des coordonnées WGS84 en degrés ; elle ne convertit pas
automatiquement d'anciennes coordonnées projetées.

## Importer et comparer

```powershell
python scripts/catalogue_sqlite.py --database instance/catalogue.sqlite3 migrate --data-dir chemin/vers/copie/sites --contrat REF-CONTRAT
python scripts/catalogue_sqlite.py --database instance/catalogue.sqlite3 check
```

Comparer les nombres de sites, les identifiants, communes, types, champs
complémentaires et rattachements avec la source. Les fichiers sources ne sont
ni supprimés ni modifiés. La simulation ne remplace pas cette comparaison.

## Activer dans la recette

Dans PowerShell, avant de démarrer le serveur :

```powershell
$env:CATALOGUE_STORAGE = 'sqlite'
$env:CATALOGUE_DATABASE = (Resolve-Path 'instance/catalogue.sqlite3').Path
python run.py
```

Sur un serveur, configurer ces variables dans son environnement et redémarrer
selon la procédure d'exploitation habituelle. Le script ne modifie aucun
service. Le mode initial reste JSON tant que ces variables ne sont pas configurées.

Vérifier : connexion, liste et recherche, création et édition d'un site, choix
du contrat, maintenance et carte. La régénération demande aussi les GeoJSON
et icônes déjà nécessaires au site.

La page **Contrats et données du site** est accessible depuis l'accueil au
niveau 5 : import, simulation, export JSON et sauvegarde. Le module Contrats
reste au niveau 3 ; l'édition des sites conserve le niveau 4.

## Formats d'échange

Exemple JSON complet :

```json
{
  "contrats": [{"REFERENCE": "C1", "NOM": "Contrat exemple"}],
  "communes": [{"COMMUNE": "Commune exemple", "CODE_INSEE": "01001"}],
  "types_sites": [{"type": "STEP", "icon": "step.png", "enabled": true}],
  "sites": [{"INDEX": "1", "NOM": "Station exemple", "COMMUNE": "Commune exemple", "CODE_INSEE": "01001", "TYPE": "STEP", "CONTRAT": "C1", "LAT": "45.2", "LONG": "1.2", "ETAT": "ES"}]
}
```

Exemple CSV de sites (référentiels importés au préalable) :

```csv
INDEX;NOM;COMMUNE;CODE_INSEE;TYPE;CONTRAT;LAT;LONG;ETAT
1;Station exemple;Commune exemple;01001;STEP;C1;45.2;1.2;ES
```

Import en ligne de commande :

```powershell
python scripts/catalogue_sqlite.py --database instance/catalogue.sqlite3 import chemin/fichier.json --dry-run
python scripts/catalogue_sqlite.py --database instance/catalogue.sqlite3 import chemin/sites.csv --entity sites
```

Pour une liste JSON ou un CSV, `--entity` accepte `contrats`, `communes`,
`types_sites` ou `sites`. En-têtes : `REFERENCE,NOM` pour les contrats,
`COMMUNE,CODE_INSEE,COLLECTIF` pour les communes, `type,icon,group,enabled,cluster,show,scale`
pour les types. Booléens CSV : true/false, 1/0 ou oui/non. UTF-8 avec ou sans BOM ;
séparateurs virgule, point-virgule ou tabulation. La page limite les fichiers
à 10 Mo. Les identifiants présents sont mis à jour ; les champs absents sont
conservés. Une erreur annule tout le fichier.

## Sauvegarder et restaurer

La sauvegarde JSON historique ne contient pas le catalogue SQLite. Utiliser
le bouton **Sauvegarder SQLite** ou :

```powershell
python scripts/catalogue_sqlite.py --database instance/catalogue.sqlite3 backup chemin/nouvelle-sauvegarde.sqlite3
```

La sauvegarde utilise l'API SQLite pour une copie cohérente. La destination
doit être nouvelle ; aucun fichier existant n'est écrasé. Sauvegarder aussi
les utilisateurs, journaux et fichiers PDF/images selon leur procédure habituelle.

Pour restaurer, arrêter la recette, puis copier la sauvegarde validée vers une
**nouvelle base**, jamais par-dessus la base active :

```powershell
python scripts/catalogue_sqlite.py --database instance/catalogue-restaure.sqlite3 restore chemin/sauvegarde.sqlite3
python scripts/catalogue_sqlite.py --database instance/catalogue-restaure.sqlite3 check
```

Configurer ensuite CATALOGUE_DATABASE vers cette base et redémarrer la recette.
Conserver la base précédente jusqu'à vérification.

Un retour au mode JSON est possible avant toute écriture SQL en réutilisant
les sources conservées. Après des écritures SQL, ces sources sont anciennes :
ne pas revenir simplement au mode JSON sous peine de perdre les changements
récents. Privilégier une restauration SQLite vérifiée. L'export JSON complet
permet une réimportation SQLite ; ce n'est pas une restauration automatique
vers l'ancienne arborescence de fichiers JSON.
