"""Initialize, migrate, import, inspect and back up the SQLite catalogue."""
import argparse
import csv
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.catalogue import Catalogue, ENTITIES, label, read_import

SOURCE_FILES = ("recap.json", "communes.json", "type_site.json", "commune_asst_collectif.json")


def merge_communes(rows):
    """Merge complementary commune metadata without conflating homonymous places."""
    merged = {}
    code_names = {}
    for position, row in enumerate(rows, 1):
        if isinstance(row, str):
            row = {"COMMUNE": row}
        if not isinstance(row, dict):
            raise ValueError(f"Communes, ligne {position} : objet ou nom attendu.")
        name = label(row.get("COMMUNE") or row.get("commune") or row.get("name"))
        code = label(row.get("CODE_INSEE"))
        if not name:
            raise ValueError(f"Communes, ligne {position} : COMMUNE obligatoire.")
        if code and code in code_names and code_names[code] != name:
            raise ValueError(f"CODE_INSEE {code} associé à plusieurs noms de commune.")
        if code:
            code_names[code] = name
        key = (code, name)
        merged[key] = {**merged.get(key, {}), **row, "COMMUNE": name, "CODE_INSEE": code}
    return list(merged.values())


def migration_bundle(directory, contract):
    directory = Path(directory)
    sites = json.loads((directory / "recap.json").read_text(encoding="utf-8-sig"))
    if not isinstance(sites, list) or not all(isinstance(row, dict) for row in sites):
        raise ValueError("recap.json doit être une liste d'objets.")
    bundle = {"sites": sites}
    for entity, filename in (("communes", "communes.json"), ("types_sites", "type_site.json")):
        path = directory / filename
        rows = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else []
        if isinstance(rows, dict):
            rows = list(rows.values())
        if not isinstance(rows, list):
            raise ValueError(f"{filename} doit contenir une liste.")
        bundle[entity] = rows
    collective = directory / "commune_asst_collectif.json"
    if collective.exists():
        rows = json.loads(collective.read_text(encoding="utf-8-sig"))
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("commune_asst_collectif.json doit être une liste d'objets.")
        bundle["communes"].extend({**row, "COLLECTIF": True} for row in rows)
    # Recover references only from explicit source values, keeping homonyms distinct.
    bundle["communes"] = merge_communes(bundle["communes"])
    for row in sites:
        name = label(row.get("COMMUNE"))
        code = label(row.get("CODE_INSEE"))
        matches = [r for r in bundle["communes"] if r["COMMUNE"] == name]
        if code and any(not r["CODE_INSEE"] for r in matches):
            raise ValueError(f"Complétez CODE_INSEE dans le référentiel de la commune {name}.")
        if name and ((code and not any(r["CODE_INSEE"] == code for r in matches)) or not matches):
            bundle["communes"].append({"COMMUNE": name, "CODE_INSEE": code})
    bundle["communes"] = merge_communes(bundle["communes"])
    labels = set()
    for row in bundle["types_sites"]:
        if not isinstance(row, (str, dict)):
            raise ValueError("type_site.json : objet ou libellé attendu.")
        labels.add(label(row if isinstance(row, str) else row.get("type")))
    bundle["types_sites"].extend({"type": name} for name in sorted({label(row.get("TYPE")) for row in sites} - labels) if name)
    references = {label(row.get("CONTRAT")) or label(contract) for row in sites}
    if "" in references:
        raise ValueError("Sites sans CONTRAT : indiquez explicitement --contrat pour les rattacher.")
    # Omit NOM to preserve the name of contracts already created in the catalogue.
    bundle["contrats"] = [{"REFERENCE": ref} for ref in sorted(references)]
    return bundle


def prepare_migration(store, directory, contract=None):
    """Create tables and validate source migration on an isolated database snapshot."""
    store.initialize()
    directory = Path(directory).resolve()
    report = {
        "base": str(store.path),
        "tables_pretes": True,
        "migration_verifiee": False,
        "donnees_importees": False,
        "comptes_actuels": store.check(),
        "sources": [],
        "erreurs": [],
    }
    with store.connect() as connection:
        report["schema_version"] = connection.execute("PRAGMA user_version").fetchone()[0]
        report["tables"] = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for filename in SOURCE_FILES:
        path = directory / filename
        source = {"fichier": filename, "present": path.is_file()}
        if source["present"]:
            raw = path.read_bytes()
            source.update(octets=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        report["sources"].append(source)
    try:
        data = migration_bundle(directory, contract)
        with tempfile.TemporaryDirectory(prefix="karto-migration-check-") as temporary:
            snapshot = Path(temporary) / "catalogue.sqlite3"
            store.backup(snapshot)
            scratch = Catalogue(snapshot)
            report["lignes_sources"] = scratch.import_bundle(data, source="préparation migration", default_contract=contract)
            report["comptes_apres_simulation"] = scratch.check()
        report["migration_verifiee"] = True
    except (ValueError, OSError, sqlite3.Error) as exc:
        report["erreurs"].append(str(exc))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    commands.add_parser("check")
    preparation = commands.add_parser("prepare", help="Créer les tables et contrôler une migration sur une copie temporaire")
    preparation.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "app" / "data" / "sites")
    preparation.add_argument("--contrat")
    preparation.add_argument("--report", type=Path, required=True)
    imp = commands.add_parser("import")
    imp.add_argument("file", type=Path)
    imp.add_argument("--entity", choices=ENTITIES, default="sites")
    imp.add_argument("--dry-run", action="store_true")
    imp.add_argument("--contrat")
    migration = commands.add_parser("migrate")
    migration.add_argument("--data-dir", type=Path, required=True)
    migration.add_argument("--contrat")
    migration.add_argument("--dry-run", action="store_true")
    backup = commands.add_parser("backup")
    backup.add_argument("destination", type=Path)
    restore = commands.add_parser("restore")
    restore.add_argument("source", type=Path)
    args = parser.parse_args(argv)
    store = Catalogue(args.database)
    try:
        if args.command == "init":
            store.initialize()
            result = store.check()
        elif args.command == "prepare":
            # A report must not replace the database or any source file.
            report_path = args.report.resolve()
            protected = {store.path, *((args.data_dir / name).resolve() for name in SOURCE_FILES)}
            if report_path in protected:
                raise ValueError("Le rapport doit être distinct de la base et des fichiers sources.")
            result = prepare_migration(store, args.data_dir, args.contrat)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["migration_verifiee"] else 2
        elif args.command == "check":
            result = store.check()
        elif args.command == "backup":
            store.backup(args.destination)
            result = {"sauvegarde": str(args.destination)}
        elif args.command == "restore":
            original = Catalogue(args.source)
            original.check()
            original.backup(args.database)
            result = store.check()
        else:
            if args.command == "migrate":
                bundle = migration_bundle(args.data_dir, args.contrat)
            else:
                bundle = read_import(args.file.read_bytes(), args.file.name, args.entity)
            result = store.import_bundle(bundle, source=str(args.data_dir if args.command == "migrate" else args.file),
                                         default_contract=args.contrat, dry_run=args.dry_run)
            result["simulation"] = args.dry_run
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, csv.Error, sqlite3.Error) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
