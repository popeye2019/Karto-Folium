"""Single source for catalogue reads; JSON is retained for pre-migration installations."""
from pathlib import Path

from flask import current_app, has_app_context

from app.catalogue import Catalogue
from app.utils import utils_json


def enabled():
    return has_app_context() and current_app.config.get("CATALOGUE_STORAGE", "json") == "sqlite"


def catalogue():
    return Catalogue(current_app.config["CATALOGUE_DATABASE"])


def load_json_file(path):
    """Preserve existing record shapes while reading migrated data from SQL."""
    name = Path(path).name
    if enabled():
        store = catalogue()
        if name == "recap.json":
            return store.sites()
        if name == "type_site.json":
            return store.types()
        if name == "communes.json":
            return store.communes()
        if name == "commune_asst_collectif.json":
            return store.communes(collective=True)
    return utils_json.load_json_file(path)


def save_json_file(path, data):
    if enabled():
        if Path(path).name == "type_site.json":
            return catalogue().replace_types(data)
        if Path(path).name in {"recap.json", "communes.json", "commune_asst_collectif.json"}:
            raise ValueError("Utilisez une écriture ciblée du catalogue SQLite.")
    return utils_json.save_json_file(path, data)


def get_next_index(path):
    return catalogue().next_index() if enabled() else utils_json.get_next_index(path)


def validate_site(record):
    if not enabled():
        return []
    try:
        catalogue().import_bundle({"sites": [record]}, source="validation formulaire", dry_run=True)
    except ValueError as exc:
        return [str(exc)]
    return []
