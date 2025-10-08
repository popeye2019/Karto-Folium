from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _add_repo_to_syspath() -> None:
    # Ensure we can import from the local 'app' package when running directly
    repo_root = Path(__file__).resolve().parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Génère la carte statique des ouvrages avec options de centrage/zoom/couche."
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("app/static/global/ouvrages.html"),
        help="Chemin de sortie du fichier HTML (défaut: app/static/global/ouvrages.html)",
    )
    p.add_argument("--lat", type=float, default=None, help="Latitude de centrage")
    p.add_argument("--lon", type=float, default=None, help="Longitude de centrage")
    p.add_argument("--zoom", type=int, default=None, help="Niveau de zoom")
    p.add_argument(
        "--layer",
        type=str,
        default=None,
        help="Type/couche à activer (ex: STEP, PR, EP, ...)",
    )
    p.add_argument(
        "--exclusive",
        action="store_true",
        help="Active uniquement la couche ciblée (désactive les autres)",
    )
    return p.parse_args()


def main() -> int:
    _add_repo_to_syspath()
    from app.utils.geocarto_lib import generate_map

    args = parse_args()
    try:
        out_path = generate_map(
            output_path=args.out,
            lat=args.lat,
            lon=args.lon,
            zoom=args.zoom,
            select_layer=args.layer,
            exclusive=args.exclusive,
        )
    except Exception as exc:  # pragma: no cover
        print(f"Échec de génération: {exc}")
        return 1

    print(f"Carte générée: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

