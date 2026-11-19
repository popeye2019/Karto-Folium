CREATE TABLE contrats (
    id INTEGER PRIMARY KEY,
    reference TEXT NOT NULL UNIQUE CHECK(length(trim(reference)) > 0),
    nom TEXT NOT NULL CHECK(length(trim(nom)) > 0),
    extras TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE communes (
    id INTEGER PRIMARY KEY,
    code_insee TEXT UNIQUE,
    nom TEXT NOT NULL CHECK(length(trim(nom)) > 0),
    collectif INTEGER NOT NULL DEFAULT 0 CHECK(collectif IN (0, 1)),
    extras TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX communes_nom ON communes(nom);
CREATE TABLE types_sites (
    id INTEGER PRIMARY KEY,
    libelle TEXT NOT NULL UNIQUE CHECK(length(trim(libelle)) > 0),
    icone TEXT NOT NULL DEFAULT '',
    groupe TEXT NOT NULL DEFAULT '',
    actif INTEGER NOT NULL DEFAULT 1 CHECK(actif IN (0,1)),
    cluster INTEGER NOT NULL DEFAULT 0 CHECK(cluster IN (0,1)),
    visible INTEGER NOT NULL DEFAULT 1 CHECK(visible IN (0,1)),
    echelle REAL NOT NULL DEFAULT 1 CHECK(echelle > 0),
    extras TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE contrats_communes (
    contrat_id INTEGER NOT NULL REFERENCES contrats(id) ON DELETE RESTRICT,
    commune_id INTEGER NOT NULL REFERENCES communes(id) ON DELETE RESTRICT,
    PRIMARY KEY(contrat_id, commune_id)
);
CREATE TABLE sites (
    id INTEGER PRIMARY KEY CHECK(id >= 0),
    contrat_id INTEGER NOT NULL REFERENCES contrats(id) ON DELETE RESTRICT,
    commune_id INTEGER NOT NULL REFERENCES communes(id) ON DELETE RESTRICT,
    type_site_id INTEGER NOT NULL REFERENCES types_sites(id) ON DELETE RESTRICT,
    nom TEXT NOT NULL CHECK(length(trim(nom)) > 0),
    latitude REAL CHECK(latitude BETWEEN -90 AND 90),
    longitude REAL CHECK(longitude BETWEEN -180 AND 180),
    etat TEXT NOT NULL DEFAULT 'ES',
    technologie TEXT NOT NULL DEFAULT '',
    extras TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(contrat_id, commune_id) REFERENCES contrats_communes(contrat_id, commune_id),
    CHECK((latitude IS NULL) = (longitude IS NULL))
);
CREATE INDEX sites_contrat ON sites(contrat_id);
CREATE INDEX sites_commune ON sites(commune_id);
CREATE INDEX sites_type ON sites(type_site_id);
CREATE TABLE imports (
    id INTEGER PRIMARY KEY,
    cree_le TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    origine TEXT NOT NULL,
    resume TEXT NOT NULL
);
PRAGMA user_version = 1;
