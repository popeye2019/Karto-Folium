"""Initialize, migrate, import, inspect and back up the SQLite catalogue."""
import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.catalogue import Catalogue, ENTITIES, read_import


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
    # Missing labels can be recovered from sites, without inventing geographic codes.
    names = {row if isinstance(row, str) else row.get("COMMUNE") or row.get("commune") or row.get("name") for row in bundle["communes"]}
    for row in sites:
        if row.get("COMMUNE") and row["COMMUNE"] not in names:
            bundle["communes"].append({"COMMUNE": row["COMMUNE"], "CODE_INSEE": row.get("CODE_INSEE", "")})
            names.add(row["COMMUNE"])
    labels = {row if isinstance(row, str) else row.get("type") for row in bundle["types_sites"]}
    bundle["types_sites"].extend({"type": name} for name in sorted({row.get("TYPE", "") for row in sites} - labels) if name)
    references = {str(row.get("CONTRAT") or contract or "").strip() for row in sites}
    if "" in references:
        raise ValueError("Sites sans CONTRAT : indiquez explicitement --contrat pour les rattacher.")
    bundle["contrats"] = [{"REFERENCE": ref, "NOM": ref} for ref in sorted(references)]
    merged = {}
    for row in bundle["communes"]:
        if isinstance(row, str):
            row = {"COMMUNE": row}
        name = row.get("COMMUNE") or row.get("commune") or row.get("name")
        key = (row.get("CODE_INSEE") or "", name)
        merged[key] = {**merged.get(key, {}), **row}
    bundle["communes"] = list(merged.values())
    return bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    commands.add_parser("check")
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
