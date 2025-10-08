"""Blueprint dedicated to listing, editing, and creating site records."""

from __future__ import annotations

from typing import Any
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.utils.utils_json import (
    get_field_names,
    get_next_index,
    load_json_file as load_data,
    save_json_file as save_data,
)
from app.utils.auth import login_required, require_level
from app.utils.geocarto_lib import generate_map

DATA_FILE = "./app/data/sites/recap.json"
TYPE_FILE = "./app/data/sites/type_site.json"
COMMUNES_FILE = "./app/data/sites/communes.json"
DEFAULT_SITE_STATES = ("ES", "HS")
edit_sites_bp = Blueprint("edit_sites", __name__, template_folder="templates")






def _get_communes_list() -> list[str]:
    """Return the list of communes from the dedicated JSON file."""
    try:
        raw_communes = load_data(COMMUNES_FILE)
    except FileNotFoundError:
        current_app.logger.warning("Commune file missing: %s", COMMUNES_FILE)
        data = load_data(DATA_FILE)
        raw_communes = [
            str(record.get("COMMUNE", "")).strip() for record in data if record.get("COMMUNE")
        ]
    except Exception as exc:
        current_app.logger.warning("Unable to read commune file: %s", exc)
        data = load_data(DATA_FILE)
        raw_communes = [
            str(record.get("COMMUNE", "")).strip() for record in data if record.get("COMMUNE")
        ]
    else:
        if isinstance(raw_communes, dict):
            raw_communes = raw_communes.values()
        extracted: list[str] = []
        for value in raw_communes:
            if isinstance(value, dict):
                label = value.get("commune") or value.get("name") or value.get("COMMUNE")
                if label:
                    extracted.append(str(label).strip())
            else:
                extracted.append(str(value).strip())
        raw_communes = extracted

    communes = [item for item in raw_communes if item]
    return sorted(dict.fromkeys(communes), key=str.upper)
def _get_site_types() -> list[str]:
    """Return the list of available site types from the canonical source."""
    try:
        types = load_data(TYPE_FILE)
    except FileNotFoundError:
        current_app.logger.warning("Site type file missing: %s", TYPE_FILE)
        data = load_data(DATA_FILE)
        types = [str(record.get("TYPE", "")).strip() for record in data if record.get("TYPE")]
    except Exception as exc:
        current_app.logger.warning("Unable to read site type file: %s", exc)
        data = load_data(DATA_FILE)
        types = [str(record.get("TYPE", "")).strip() for record in data if record.get("TYPE")]
    else:
        if isinstance(types, dict):
            types = types.values()
        extracted: list[str] = []
        for value in types:
            if isinstance(value, dict):
                label = value.get('type')
                if label:
                    extracted.append(str(label).strip())
            else:
                extracted.append(str(value).strip())
        types = [item for item in extracted if item]
    return sorted(dict.fromkeys(types))



def _get_site_states() -> tuple[str, ...]:
    """Return the list of valid site states from configuration or defaults."""
    raw_states = current_app.config.get("SITE_ETATS", DEFAULT_SITE_STATES)

    if isinstance(raw_states, str):
        candidates = [item.strip() for item in raw_states.split(",") if item.strip()]
    elif isinstance(raw_states, (list, tuple, set)):
        candidates = [str(item).strip() for item in raw_states if str(item).strip()]
    else:
        candidates = []

    return tuple(candidates) or DEFAULT_SITE_STATES


def _normalize_state(value: str | None, allowed_states: tuple[str, ...]) -> str:
    """Return a valid state value, defaulting to the first allowed option."""
    if value is None:
        value = ""

    cleaned = value.strip()
    for state in allowed_states:
        if cleaned.upper() == state.upper():
            return state
    return allowed_states[0]


@edit_sites_bp.route("/")
def list_records():
    """Display the list of registered sites along with available fields."""
    data = load_data(DATA_FILE)
    fields = get_field_names(data)

    return render_template("liste_sites.html", fields=fields, records=data, types=_get_site_types())


@edit_sites_bp.route("/edit/<int:record_index>", methods=["GET", "POST"])
def edit_record(record_index: int):
    """Edit the site identified by ``record_index``."""
    data = load_data(DATA_FILE)
    if record_index < 0 or record_index >= len(data):
        flash("Enregistrement introuvable.", "danger")
        return redirect(url_for("edit_sites.list_records"))

    site_states = _get_site_states()
    site_types = _get_site_types()
    communes = _get_communes_list()
    record_data = data[record_index]

    if request.method == "POST":
        selected_type = (request.form.get("TYPE") or record_data.get("TYPE", "")).strip()
        if site_types and selected_type not in site_types:
            flash("TYPE hors liste.", "danger")
            latitude_default = float(str(record_data.get("LAT", "")).strip() or 46.5)
            longitude_default = float(str(record_data.get("LONG", "")).strip() or 2.5)
            record = dict(record_data)
            record["TYPE"] = selected_type or record_data.get("TYPE", "")
            return render_template(
                "edit_record.html",
                record=record,
                index=record_index,
                lat0=latitude_default,
                lon0=longitude_default,
                site_states=site_states,
                site_types=site_types,
                communes=communes,
            )

        normalized_state = _normalize_state(
            (request.form.get("ETAT") or record_data.get("ETAT")),
            site_states,
        )

        for field, previous_value in record_data.items():
            if field == "INDEX":
                continue
            if field == "ETAT":
                record_data[field] = normalized_state
                continue
            if field == "TYPE":
                record_data[field] = selected_type or previous_value
                continue
            record_data[field] = request.form.get(field, previous_value)

        if "ETAT" not in record_data:
            record_data["ETAT"] = normalized_state
        if "TYPE" not in record_data:
            record_data["TYPE"] = selected_type or ""

        save_data(DATA_FILE, data)
        flash("Enregistrement mis a jour avec succes.", "success")
        return redirect(url_for("edit_sites.list_records"))

    latitude_default = float(str(record_data.get("LAT", "")).strip() or 46.5)
    longitude_default = float(str(record_data.get("LONG", "")).strip() or 2.5)

    record = dict(record_data)
    if not record.get("ETAT"):
        record["ETAT"] = site_states[0]

    current_app.logger.info(
        "Editing record index=%s lat=%s lon=%s", record_index, latitude_default, longitude_default
    )

    return render_template(
        "edit_record.html",
        record=record,
        index=record_index,
        lat0=latitude_default,
        lon0=longitude_default,
        site_states=site_states,
        site_types=site_types,
        communes=communes,
    )


@edit_sites_bp.route("/add", methods=["GET", "POST"])
def add_record():
    """Create a new site entry."""
    data = load_data(DATA_FILE)
    site_states = _get_site_states()
    site_types = _get_site_types()

    communes = _get_communes_list()

    next_index = get_next_index(DATA_FILE)

    if request.method == "POST":
        commune = (request.form.get("COMMUNE") or "").strip()
        name = (request.form.get("NOM") or "").strip()
        site_type = (request.form.get("TYPE") or "").strip()
        latitude_raw = (request.form.get("LAT") or "").strip()
        longitude_raw = (request.form.get("LONG") or "").strip()
        etat_raw = (request.form.get("ETAT") or "").strip()

        errors = _validate_request(
            commune,
            name,
            site_type,
            communes,
            site_types,
            latitude_raw,
            longitude_raw,
            etat_raw,
            site_states,
        )
        if errors:
            for message in errors:
                flash(message, "danger")

            record = {
                "INDEX": str(next_index),
                "COMMUNE": commune,
                "NOM": name,
                "TYPE": site_type,
                "LAT": latitude_raw,
                "LONG": longitude_raw,
                "ETAT": _normalize_state(etat_raw, site_states),
            }
            return render_template(
                "add_record.html",
                record=record,
                communes=communes,
                site_types=site_types,
                site_states=site_states,
                lat0=float(latitude_raw) if latitude_raw else 46.5,
                lon0=float(longitude_raw) if longitude_raw else 2.5,
            )

        latitude = float(latitude_raw)
        longitude = float(longitude_raw)
        etat_value = _normalize_state(etat_raw or site_states[0], site_states)

        new_record: dict[str, Any] = {field: "" for field in get_field_names(data) or []}
        new_record.update(
            {
                "INDEX": str(next_index),
                "COMMUNE": commune,
                "NOM": name,
                "TYPE": site_type,
                "LAT": f"{latitude:.14f}",
                "LONG": f"{longitude:.14f}",
                "ETAT": etat_value,
            }
        )

        for field_name in request.form.keys():
            if field_name not in new_record:
                new_record[field_name] = request.form.get(field_name, "")

        data.append(new_record)
        save_data(DATA_FILE, data)
        flash("Site ajoute.", "success")
        return redirect(url_for("edit_sites.list_records"))

    record = {"INDEX": str(next_index), "ETAT": site_states[0]}
    return render_template(
        "add_record.html",
        record=record,
        communes=communes,
        site_types=site_types,
        site_states=site_states,
        lat0=46.5,
        lon0=2.5,
    )


@edit_sites_bp.route("/regenerate-map", methods=["POST"])
@login_required
@require_level(4)
def regenerate_map():
    """Regenerate the static map HTML and save to static/global/ouvrages.html."""
    try:
        app_dir = Path(current_app.root_path)
        output_path = app_dir / "static" / "global" / "ouvrages.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        generate_map(output_path)
    except Exception as exc:  # pragma: no cover
        current_app.logger.exception("Map generation failed: %s", exc)
        flash("Échec de la régénération de la carte.", "danger")
    else:
        flash("Carte régénérée avec succès.", "success")
    return redirect(url_for("edit_sites.list_records"))




def _validate_request(
    commune: str,
    name: str,
    site_type: str,
    communes: list[str],
    site_types: list[str],
    latitude_raw: str,
    longitude_raw: str,
    etat_raw: str,
    site_states: tuple[str, ...],
) -> list[str]:
    """Validate form values and return a list of error messages."""
    errors: list[str] = []

    if not commune:
        errors.append("COMMUNE obligatoire.")
    elif communes and commune not in communes:
        errors.append("COMMUNE hors liste.")

    if not name:
        errors.append("NOM obligatoire.")

    if not site_type:
        errors.append("TYPE obligatoire.")
    elif site_types and site_type not in site_types:
        errors.append("TYPE hors liste.")

    try:
        float(latitude_raw)
        float(longitude_raw)
    except ValueError:
        errors.append("LAT/LONG obligatoires via la carte.")

    if etat_raw and etat_raw.upper() not in {state.upper() for state in site_states}:
        errors.append("ETAT hors liste.")

    return errors
