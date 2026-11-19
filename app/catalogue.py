"""Relational catalogue and transactional JSON/CSV imports, independent of Flask."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
import tempfile
from contextlib import closing, contextmanager
from pathlib import Path

from app.utils.coordinates import parse_coordinate

SCHEMA_VERSION = 1
SITE_COLUMNS = {"INDEX", "NOM", "COMMUNE", "CODE_INSEE", "TYPE", "LAT", "LONG", "ETAT", "TECHNOLOGIE", "CONTRAT"}
ENTITIES = ("contrats", "communes", "types_sites", "sites")
SITE_QUERY = """SELECT s.*, c.nom commune, c.code_insee, t.libelle type, k.reference contrat
    FROM sites s JOIN communes c ON c.id=s.commune_id
    JOIN types_sites t ON t.id=s.type_site_id JOIN contrats k ON k.id=s.contrat_id"""


def label(value) -> str:
    if isinstance(value, (list, dict, tuple, set)):
        raise ValueError("Une valeur simple est attendue pour ce champ.")
    return "" if value is None else str(value).strip()


def read_import(raw: bytes, filename: str, entity: str = "sites") -> dict:
    """Read UTF-8 JSON bundles or CSV tables without guessing business relations."""
    if entity not in ENTITIES:
        raise ValueError("Table d'import inconnue.")
    text = raw.decode("utf-8-sig")
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        payload = json.loads(text)
        if isinstance(payload, list):
            return {entity: payload}
        if isinstance(payload, dict) and payload and set(payload) <= set(ENTITIES):
            return payload
        raise ValueError("JSON attendu : liste de lignes ou objet contrats/communes/types_sites/sites.")
    if suffix == ".csv":
        try:
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text, newline=""), dialect=dialect)
        headers = reader.fieldnames
        if not headers or any(not label(h) for h in headers) or len(set(headers)) != len(headers):
            raise ValueError("En-têtes CSV absents, vides ou dupliqués.")
        rows = list(reader)
        if any(None in row or any(v is None for v in row.values()) for row in rows):
            raise ValueError("Nombre de colonnes CSV incorrect.")
        return {entity: rows}
    raise ValueError("Seuls les fichiers JSON et CSV sont acceptés.")


class Catalogue:
    def __init__(self, path):
        self.path = Path(path).resolve()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            with self.connect():
                return
        # SQLite's exclusive create protects an existing catalogue from reinitialization.
        self.path.touch(exist_ok=False)
        try:
            with closing(sqlite3.connect(self.path)) as connection:
                connection.executescript(Path(__file__).with_name("catalogue_schema.sql").read_text(encoding="utf-8"))
        except Exception:
            self.path.unlink(missing_ok=True)
            raise

    @contextmanager
    def connect(self):
        if not self.path.is_file():
            raise ValueError("Catalogue SQLite absent : initialisez et importez les données avant activation.")
        connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                raise ValueError("Version du catalogue SQLite non prise en charge.")
            with connection:
                yield connection
        finally:
            connection.close()

    def contracts(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("""SELECT k.id,k.reference,k.nom,
                (SELECT COUNT(*) FROM sites s WHERE s.contrat_id=k.id) site_count,
                (SELECT COUNT(*) FROM contrats_communes cc WHERE cc.contrat_id=k.id) commune_count
                FROM contrats k ORDER BY k.reference""")]

    def contract_records(self):
        with self.connect() as db:
            return [{**json.loads(r["extras"]), "REFERENCE": r["reference"], "NOM": r["nom"]}
                    for r in db.execute("SELECT * FROM contrats ORDER BY id")]

    def communes(self, collective=False):
        with self.connect() as db:
            query = "SELECT * FROM communes" + (" WHERE collectif = 1" if collective else "") + " ORDER BY id"
            return [{**json.loads(r["extras"]), "COMMUNE": r["nom"], "CODE_INSEE": r["code_insee"] or ""} for r in db.execute(query)]

    def types(self):
        with self.connect() as db:
            return [self._type_dict(r) for r in db.execute("SELECT * FROM types_sites ORDER BY id")]

    @staticmethod
    def _type_dict(r):
        return {**json.loads(r["extras"]), "type": r["libelle"], "icon": r["icone"],
                "group": r["groupe"], "enabled": bool(r["actif"]), "cluster": bool(r["cluster"]),
                "show": bool(r["visible"]), "scale": r["echelle"]}

    def sites(self):
        with self.connect() as db:
            return [self._site_dict(r) for r in db.execute(SITE_QUERY + " ORDER BY s.id")]

    @staticmethod
    def _site_dict(r):
        return {**json.loads(r["extras"]), "INDEX": str(r["id"]), "NOM": r["nom"],
                     "COMMUNE": r["commune"], "CODE_INSEE": r["code_insee"] or "", "TYPE": r["type"],
                     "LAT": "" if r["latitude"] is None else str(r["latitude"]),
                     "LONG": "" if r["longitude"] is None else str(r["longitude"]),
                "ETAT": r["etat"], "TECHNOLOGIE": r["technologie"], "CONTRAT": r["contrat"]}

    def next_index(self):
        with self.connect() as db:
            return db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM sites").fetchone()[0]

    @staticmethod
    def _required(row, key):
        value = label(row.get(key))
        if not value:
            raise ValueError(f"{key} obligatoire.")
        return value

    def _contract(self, db, row):
        reference = self._required(row, "REFERENCE")
        existing = db.execute("SELECT * FROM contrats WHERE reference=?", (reference,)).fetchone()
        name = label(row.get("NOM")) or (existing["nom"] if existing else reference)
        extras = {**(json.loads(existing["extras"]) if existing else {}), **{k:v for k,v in row.items() if k not in {"REFERENCE", "NOM"}}}
        db.execute("""INSERT INTO contrats(reference, nom, extras) VALUES(?,?,?)
            ON CONFLICT(reference) DO UPDATE SET nom=excluded.nom, extras=excluded.extras""", (reference, name, json.dumps(extras, ensure_ascii=False)))

    def _commune(self, db, row):
        if isinstance(row, str):
            row = {"COMMUNE": row}
        name = label(row.get("COMMUNE") or row.get("commune") or row.get("name"))
        if not name:
            raise ValueError("COMMUNE obligatoire.")
        code = label(row.get("CODE_INSEE")) or None
        if code:
            existing = db.execute("SELECT * FROM communes WHERE code_insee=?", (code,)).fetchone()
        else:
            candidates = db.execute("SELECT * FROM communes WHERE nom=?", (name,)).fetchall()
            if len(candidates) > 1:
                raise ValueError(f"Commune ambiguë : {name}. CODE_INSEE requis.")
            existing = candidates[0] if candidates else None
        extras = {**(json.loads(existing["extras"]) if existing else {}), **{k:v for k,v in row.items() if k not in {"COMMUNE", "commune", "name", "CODE_INSEE", "COLLECTIF"}}}
        raw = row.get("COLLECTIF", existing["collectif"] if existing else 0)
        if label(raw).lower() not in {"0", "1", "true", "false", "oui", "non"}:
            raise ValueError("COLLECTIF : booléen invalide.")
        collective = int(label(raw).lower() in {"1", "true", "oui"})
        values = (code or (existing["code_insee"] if existing else None), name, collective, json.dumps(extras, ensure_ascii=False))
        if existing:
            db.execute("UPDATE communes SET code_insee=?, nom=?, collectif=?, extras=? WHERE id=?", (*values, existing["id"]))
        else:
            db.execute("INSERT INTO communes(code_insee,nom,collectif,extras) VALUES(?,?,?,?)", values)

    def _type(self, db, row):
        if isinstance(row, str):
            row = {"type": row}
        name = self._required(row, "type")
        existing = db.execute("SELECT * FROM types_sites WHERE libelle=?", (name,)).fetchone()
        extras = {**(self._type_dict(existing) if existing else {}), **{k:v for k,v in row.items() if k != "type"}}
        for key in ("enabled", "cluster", "show"):
            if key in extras and not isinstance(extras[key], (str, bool, int)):
                raise ValueError(f"{key} : booléen invalide.")
            if key in extras and isinstance(extras[key], int) and extras[key] not in {0, 1}:
                raise ValueError(f"{key} : booléen invalide.")
            if key in extras and isinstance(extras[key], str):
                if extras[key].lower() not in {"true", "false", "0", "1", "oui", "non"}:
                    raise ValueError(f"{key} : booléen invalide.")
                extras[key] = extras[key].lower() in {"true", "1", "oui"}
        if "scale" in extras:
            from math import isfinite
            try:
                scale = float(extras["scale"])
            except (ValueError, TypeError, OverflowError):
                raise ValueError("Échelle du type invalide.") from None
            if not isfinite(scale) or scale <= 0:
                raise ValueError("Échelle du type invalide.")
            extras["scale"] = scale
        others = {k:v for k,v in extras.items() if k not in {"type", "icon", "group", "enabled", "cluster", "show", "scale"}}
        db.execute("""INSERT INTO types_sites(libelle,icone,groupe,actif,cluster,visible,echelle,extras)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(libelle) DO UPDATE SET icone=excluded.icone,
            groupe=excluded.groupe,actif=excluded.actif,cluster=excluded.cluster,
            visible=excluded.visible,echelle=excluded.echelle,extras=excluded.extras""",
            (name, label(extras.get("icon")), label(extras.get("group")) or name,
             bool(extras.get("enabled", True)), bool(extras.get("cluster", False)),
             bool(extras.get("show", True)), extras.get("scale", 1), json.dumps(others, ensure_ascii=False)))

    def _site(self, db, row, default_contract=None):
        raw_index = self._required(row, "INDEX")
        if not raw_index.isdecimal():
            raise ValueError("INDEX doit être un entier positif ou nul.")
        index = int(raw_index)
        if index > 9223372036854775807:
            raise ValueError("INDEX dépasse la capacité SQLite.")
        existing = db.execute(SITE_QUERY + " WHERE s.id=?", (index,)).fetchone()
        previous = self._site_dict(existing) if existing else {}
        row = {**previous, **row}
        name = self._required(row, "NOM")
        commune = self._required(row, "COMMUNE")
        code = label(row.get("CODE_INSEE"))
        candidates = db.execute("SELECT id,nom FROM communes WHERE " + ("code_insee=?" if code else "nom=?"), (code or commune,)).fetchall()
        if len(candidates) != 1 or candidates[0]["nom"] != commune:
            raise ValueError(f"Commune inconnue ou ambiguë : {commune}. Vérifiez CODE_INSEE.")
        type_name = self._required(row, "TYPE")
        site_type = db.execute("SELECT id FROM types_sites WHERE libelle=?", (type_name,)).fetchone()
        contract_ref = label(row.get("CONTRAT")) or label(default_contract)
        contract = db.execute("SELECT id FROM contrats WHERE reference=?", (contract_ref,)).fetchone()
        if not site_type or not contract:
            raise ValueError("TYPE ou CONTRAT inconnu. Importez les référentiels d'abord.")
        lat, lon = label(row.get("LAT")), label(row.get("LONG"))
        latitude = parse_coordinate(lat.replace(",", "."), 90) if lat or lon else None
        longitude = parse_coordinate(lon.replace(",", "."), 180) if lat or lon else None
        extras = json.dumps({k:v for k,v in row.items() if k not in SITE_COLUMNS}, ensure_ascii=False)
        db.execute("INSERT OR IGNORE INTO contrats_communes VALUES(?,?)", (contract[0], candidates[0][0]))
        db.execute("""INSERT INTO sites(id,contrat_id,commune_id,type_site_id,nom,latitude,longitude,etat,technologie,extras)
            VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET contrat_id=excluded.contrat_id,
            commune_id=excluded.commune_id,type_site_id=excluded.type_site_id,nom=excluded.nom,
            latitude=excluded.latitude,longitude=excluded.longitude,etat=excluded.etat,
            technologie=excluded.technologie,extras=excluded.extras""",
            (index, contract[0], candidates[0][0], site_type[0], name, latitude, longitude,
             label(row.get("ETAT")) or "ES", label(row.get("TECHNOLOGIE")), extras))

    def import_bundle(self, bundle, *, source="import", default_contract=None, dry_run=False):
        if not isinstance(bundle, dict) or not bundle or not set(bundle) <= set(ENTITIES):
            raise ValueError("Tables d'import invalides.")
        summary = {}
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for entity in ENTITIES:
                if entity not in bundle:
                    continue
                rows = bundle[entity]
                if not isinstance(rows, list):
                    raise ValueError(f"{entity} doit être une liste.")
                seen = set()
                for position, row in enumerate(rows, 1):
                    if not isinstance(row, dict) and not (entity in {"communes", "types_sites"} and isinstance(row, str)):
                        raise ValueError(f"{entity}, ligne {position} : objet attendu.")
                    if isinstance(row, dict):
                        key = label(row.get({"contrats":"REFERENCE", "communes":"CODE_INSEE", "types_sites":"type", "sites":"INDEX"}[entity]))
                        if entity == "sites" and key.isdecimal():
                            key = str(int(key))
                        if key and key in seen:
                            raise ValueError(f"{entity}, ligne {position} : identifiant dupliqué {key}.")
                        seen.add(key)
                    try:
                        if entity == "sites":
                            self._site(db, row, default_contract)
                        else:
                            getattr(self, {"contrats":"_contract", "communes":"_commune", "types_sites":"_type"}[entity])(db, row)
                    except (ValueError, sqlite3.IntegrityError) as exc:
                        raise ValueError(f"{entity}, ligne {position} : {exc}") from exc
                summary[entity] = len(rows)
            db.execute("INSERT INTO imports(origine,resume) VALUES(?,?)", (source, json.dumps(summary)))
            if dry_run:
                db.rollback()
        return summary

    def save_site(self, row, *, new=False):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if new:
                row = {**row, "INDEX": str(db.execute("SELECT COALESCE(MAX(id),0)+1 FROM sites").fetchone()[0])}
            self._site(db, row)

    def replace_types(self, rows):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for row in rows:
                self._type(db, row)
            labels = [r["type"] for r in rows]
            for existing in db.execute("SELECT id,libelle FROM types_sites").fetchall():
                if existing["libelle"] not in labels:
                    db.execute("DELETE FROM types_sites WHERE id=?", (existing["id"],))

    def backup(self, destination):
        target = Path(destination)
        if target.resolve() == self.path or target.exists():
            raise ValueError("La destination de sauvegarde doit être un nouveau fichier.")
        target.touch(exist_ok=False)
        try:
            with self.connect() as source:
                with closing(sqlite3.connect(target)) as output:
                    source.backup(output)
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def export_bundle(self):
        """Read all export tables from a consistent SQLite snapshot."""
        with tempfile.TemporaryDirectory(prefix="karto-export-") as directory:
            snapshot = Path(directory) / "catalogue.sqlite3"
            self.backup(snapshot)
            copy = Catalogue(snapshot)
            communes = copy.communes()
            collective = {(r["CODE_INSEE"], r["COMMUNE"]) for r in copy.communes(collective=True)}
            for row in communes:
                row["COLLECTIF"] = (row["CODE_INSEE"], row["COMMUNE"]) in collective
            return {"contrats": copy.contract_records(), "communes": communes,
                    "types_sites": copy.types(), "sites": copy.sites()}

    def check(self):
        with self.connect() as db:
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok" or db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Intégrité du catalogue incorrecte.")
            return {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in (*ENTITIES, "contrats_communes")}
