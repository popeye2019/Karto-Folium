from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Dict

JsonDict = Dict[str, object]


def normalize_label(value: str) -> str:
    if not value:
        return ""
    cleaned = value.strip()
    replacements = {
        "’": "'",
        "´": "'",
        "œ": "oe",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    cleaned = cleaned.replace("'", " ")
    cleaned = cleaned.replace("/", " ")
    cleaned = cleaned.replace("-", " ")
    normalized = unicodedata.normalize("NFKD", cleaned)
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = ''.join(ch for ch in normalized if ch.isalnum() or ch.isspace())
    normalized = ' '.join(normalized.split())
    return normalized.casefold()


@dataclass
class TypeMetadata:
    type_name: str
    icon: str
    group: str
    enabled: bool = True
    cluster: bool = False
    scale: float = 1.0
    show: bool = False

    @property
    def key(self) -> str:
        return normalize_label(self.type_name)


def _read_json(path: Path) -> object:
    if not path.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def extract_commune_names(commune_records: Iterable[Dict[str, object]]) -> list[str]:
    communes: list[str] = []
    for record in commune_records:
        name = record.get("COMMUNE")
        if isinstance(name, str) and name:
            communes.append(name)
    return communes


def filter_geo_features_by_communes(
    geo: Dict[str, object], communes: Iterable[str]
) -> tuple[Dict[str, object], list[str]]:
    features = geo.get("features", [])
    if not isinstance(features, list):
        raise ValueError("Le contenu GeoJSON ne possède pas de liste 'features'.")

    communes_set = {name for name in communes if name}
    kept: list[Dict[str, object]] = []
    removed_names: list[str] = []

    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties", {})
        name = ""
        if isinstance(properties, dict):
            name = str(properties.get("nom", ""))
        if name in communes_set:
            kept.append(feature)
        else:
            removed_names.append(name)

    filtered_geo = {**geo, "features": kept}
    return filtered_geo, removed_names


def load_geo_datasets(
    base_dir: Path | str,
) -> tuple[
    Dict[str, object],
    list[Dict[str, object]],
    list[Dict[str, object]],
    list[str],
    list[str],
]:
    base_path = Path(base_dir)
    if base_path.is_file():
        base_path = base_path.parent
    data_dir = base_path / "data" / "sites"

    geo = _read_json(data_dir / "co.geojson")
    liste_ouvrages = _read_json(data_dir / "recap.json")
    liste_commune_asst_collectif = _read_json(
        data_dir / "commune_asst_collectif.json"
    )

    if not isinstance(liste_ouvrages, list):
        raise ValueError("Le fichier recap.json doit contenir une liste")
    if not isinstance(liste_commune_asst_collectif, list):
        raise ValueError(
            "Le fichier commune_asst_collectif.json doit contenir une liste"
        )
    if not isinstance(geo, dict):
        raise ValueError("Le fichier co.geojson doit contenir un objet JSON")

    communes_agglo = extract_commune_names(liste_commune_asst_collectif)
    filtered_geo, removed_names = filter_geo_features_by_communes(
        geo, communes_agglo
    )

    return (
        filtered_geo,
        liste_ouvrages,
        liste_commune_asst_collectif,
        communes_agglo,
        removed_names,
    )


def load_type_metadata(base_dir: Path | str) -> Dict[str, TypeMetadata]:
    base_path = Path(base_dir)
    if base_path.is_file():
        base_path = base_path.parent
    metadata_path = base_path / "data" / "sites" / "type_site.json"
    raw_entries = _read_json(metadata_path)
    if not isinstance(raw_entries, list):
        raise ValueError("type_site.json doit contenir une liste")

    metadata: Dict[str, TypeMetadata] = {}
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        type_name = entry.get("type")
        icon_name = entry.get("icon")
        if not type_name or not icon_name:
            continue
        meta = TypeMetadata(
            type_name=type_name,
            icon=icon_name,
            group=entry.get("group", type_name),
            enabled=bool(entry.get("enabled", True)),
            cluster=bool(entry.get("cluster", False)),
            scale=float(entry.get("scale", 1.0)),
            show=bool(entry.get("show", True)),
        )
        metadata[meta.key] = meta
    return metadata
