from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verifie la coherence entre recap.json (champ DOCUMENTATION) "
            "et les fichiers presents dans app/static/ouvrages."
        )
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("app/data/sites/recap.json"),
        help="Chemin du recap.json (defaut: app/data/sites/recap.json)",
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path("app/static/ouvrages"),
        help="Dossier des documents (defaut: app/static/ouvrages)",
    )
    parser.add_argument(
        "--show",
        type=int,
        default=30,
        help="Nombre max d'elements affiches par section (defaut: 30)",
    )
    return parser.parse_args()


def load_recap_docs(json_path: Path) -> list[str]:
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Erreur lecture JSON {json_path}: {exc}")

    if not isinstance(payload, list):
        raise SystemExit(f"Format invalide dans {json_path}: attendu une liste")

    docs: list[str] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        raw = str(row.get("DOCUMENTATION", "")).strip()
        if raw:
            docs.append(raw)
    return docs


def load_doc_files(docs_dir: Path) -> list[str]:
    if not docs_dir.is_dir():
        raise SystemExit(f"Dossier introuvable: {docs_dir}")

    files: list[str] = []
    for entry in docs_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.name.startswith("."):
            continue
        files.append(entry.name)
    return files


def print_section(title: str, values: list[str], show: int) -> None:
    print(f"{title}: {len(values)}")
    for value in values[:show]:
        print(f"- {value}")
    if len(values) > show:
        print(f"... {len(values) - show} autres")
    print("")


def main() -> int:
    args = parse_args()

    recap_docs = load_recap_docs(args.json)
    doc_files = load_doc_files(args.docs_dir)

    recap_set = set(recap_docs)
    files_set = set(doc_files)

    missing_in_folder = sorted(recap_set - files_set)
    unreferenced_in_recap = sorted(files_set - recap_set)

    duplicates = sorted([name for name, count in Counter(recap_docs).items() if count > 1])

    print("=== Verification documentation ===")
    print(f"recap.json            : {args.json}")
    print(f"dossier documentation : {args.docs_dir}")
    print(f"entrees DOCUMENTATION : {len(recap_docs)}")
    print(f"fichiers trouves      : {len(doc_files)}")
    print("")

    print_section("Documents references mais absents du dossier", missing_in_folder, args.show)
    print_section("Fichiers presents mais absents du recap", unreferenced_in_recap, args.show)
    print_section("Doublons DOCUMENTATION dans recap.json", duplicates, args.show)

    has_issues = bool(missing_in_folder or unreferenced_in_recap)
    print("RESULTAT:", "KO" if has_issues else "OK")
    return 1 if has_issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
