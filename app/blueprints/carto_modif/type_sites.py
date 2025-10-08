
"""Blueprint to manage site type metadata (list, create, edit, delete)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    send_from_directory,
    abort,
)

from app.utils.utils_json import (
    load_json_file as load_data,
    save_json_file as save_data,
)
from app.utils.import_fichier import save_upload, UploadError
from app.utils.auth import login_required, require_level

TYPE_FILE = "./app/data/sites/type_site.json"
DATA_FILE = "./app/data/sites/recap.json"
ICON_DIR = (Path(__file__).resolve().parent.parent.parent / "data" / "icones")


type_sites_bp = Blueprint("type_sites", __name__, template_folder="templates")


def _load_types() -> List[Dict[str, Any]]:
    type_data = load_data(TYPE_FILE)
    if not isinstance(type_data, list):
        raise ValueError("type_site.json must contain a list of objects")
    return [dict(item) for item in type_data]


def _save_types(types: List[Dict[str, Any]]) -> None:
    save_data(TYPE_FILE, types)


def _list_icons() -> List[str]:
    if not ICON_DIR.exists():
        current_app.logger.warning("Icon directory missing: %s", ICON_DIR)
        return []
    icon_names = [
        p.name
        for p in ICON_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg"}
    ]
    return sorted(icon_names, key=str.lower)


def _type_in_use(type_label: str) -> bool:
    data = load_data(DATA_FILE)
    if not isinstance(data, list):
        return False
    for record in data:
        if isinstance(record, dict) and str(record.get("TYPE", "")) == type_label:
            return True
    return False


def _validate_payload(payload: Dict[str, Any], *, editing: bool = False) -> List[str]:
    errors: List[str] = []
    type_label = str(payload.get("type", "")).strip()
    icon_name = str(payload.get("icon", "")).strip()
    scale_raw = str(payload.get("scale", "1"))

    if not editing and not type_label:
        errors.append("Le champ TYPE est obligatoire.")
    if not icon_name:
        errors.append("L'icone est obligatoire.")
    elif icon_name not in _list_icons():
        errors.append("L'icone sélectionnée est introuvable.")

    try:
        scale_value = float(scale_raw)
        if scale_value <= 0:
            raise ValueError
    except ValueError:
        errors.append("La valeur d'échelle doit être un nombre positif.")

    return errors


def _form_payload(existing: Dict[str, Any] | None = None) -> Dict[str, Any]:
    base = existing.copy() if existing else {}
    base.update(
        {
            "type": (request.form.get("type") or base.get("type", "")).strip(),
            "group": (request.form.get("group") or base.get("group", "")).strip(),
            "icon": (request.form.get("icon") or base.get("icon", "")).strip(),
            "enabled": bool(request.form.get("enabled")),
            "cluster": bool(request.form.get("cluster")),
            "show": bool(request.form.get("show")),
        }
    )
    try:
        base["scale"] = float(request.form.get("scale") or base.get("scale", 1.0))
    except (TypeError, ValueError):
        base["scale"] = base.get("scale", 1.0)
    return base


def _render_form(
    template: str,
    *,
    mode: str,
    type_payload: Dict[str, Any],
    index: int | None = None,
):
    icon_choices = _list_icons()
    return render_template(
        template,
        mode=mode,
        type_payload=type_payload,
        icon_choices=icon_choices,
        index=index,
    )



@type_sites_bp.route("/upload-icon", methods=["POST"])
@login_required
@require_level(1)
def upload_type_icon():
    file = request.files.get("icon_file")
    if not file or not file.filename:
        flash("Aucun fichier sélectionné.", "danger")
        return redirect(url_for("type_sites.list_type_sites"))
    try:
        destination = save_upload(file, category="image", target_dir=ICON_DIR)
    except UploadError as exc:
        current_app.logger.warning("Type icon upload refused: %s", exc)
        flash(str(exc), "danger")
        return redirect(url_for("type_sites.list_type_sites"))
    flash(f"Icône ajoutée: {destination.name}", "success")
    return redirect(url_for("type_sites.list_type_sites"))


@type_sites_bp.route("/icon/<path:filename>")
def type_icon(filename: str):
    safe_path = ICON_DIR / filename
    if not safe_path.is_file():
        current_app.logger.debug("Icon file not found: %s", safe_path)
        abort(404)
    return send_from_directory(ICON_DIR, filename)


@type_sites_bp.route("/")
def list_type_sites():
    types = _load_types()
    usage_counters: Dict[str, int] = {}
    data = load_data(DATA_FILE)
    if isinstance(data, list):
        for record in data:
            if isinstance(record, dict):
                label = str(record.get("TYPE", ""))
                if label:
                    usage_counters[label] = usage_counters.get(label, 0) + 1
    return render_template(
        "type_sites_list.html",
        types=types,
        usage_counters=usage_counters,
    )


@type_sites_bp.route("/add", methods=["GET", "POST"])
def add_type_site():
    type_payload: Dict[str, Any] = {
        "type": "",
        "group": "",
        "icon": "",
        "enabled": True,
        "cluster": False,
        "scale": 1.0,
        "show": True,
    }

    if request.method == "POST":
        type_payload = _form_payload()
        errors = _validate_payload(type_payload)
        existing_types = [item.get("type", "") for item in _load_types()]
        if type_payload["type"] in existing_types:
            errors.append("Ce TYPE existe déjà.")

        if errors:
            for message in errors:
                flash(message, "danger")
            return _render_form("type_sites_form.html", mode="add", type_payload=type_payload)

        types = _load_types()
        types.append(type_payload)
        _save_types(types)
        flash("Type ajouté avec succès.", "success")
        return redirect(url_for("type_sites.list_type_sites"))

    return _render_form("type_sites_form.html", mode="add", type_payload=type_payload)


@type_sites_bp.route("/edit/<int:type_index>", methods=["GET", "POST"])
def edit_type_site(type_index: int):
    types = _load_types()
    if type_index < 0 or type_index >= len(types):
        flash("Type introuvable.", "danger")
        return redirect(url_for("type_sites.list_type_sites"))

    type_payload = types[type_index]

    if request.method == "POST":
        updated_payload = _form_payload(existing=type_payload)
        errors = _validate_payload(updated_payload, editing=True)

        if errors:
            for message in errors:
                flash(message, "danger")
            return _render_form(
                "type_sites_form.html", mode="edit", type_payload=updated_payload, index=type_index
            )

        types[type_index].update(updated_payload)
        _save_types(types)
        flash("Type mis à jour avec succès.", "success")
        return redirect(url_for("type_sites.list_type_sites"))

    return _render_form("type_sites_form.html", mode="edit", type_payload=type_payload, index=type_index)


@type_sites_bp.route("/delete/<int:type_index>", methods=["GET", "POST"])
def delete_type_site(type_index: int):
    types = _load_types()
    if type_index < 0 or type_index >= len(types):
        flash("Type introuvable.", "danger")
        return redirect(url_for("type_sites.list_type_sites"))

    type_payload = types[type_index]
    type_label = type_payload.get("type", "")

    if request.method == "POST":
        if _type_in_use(type_label):
            flash("Impossible de supprimer: le type est utilisé dans recap.json.", "danger")
            return redirect(url_for("type_sites.list_type_sites"))

        # Icône conservée pour permettre une réutilisation future.
        types.pop(type_index)
        _save_types(types)
        flash("Type supprimé (icône conservée).", "success")
        return redirect(url_for("type_sites.list_type_sites"))

    can_delete = not _type_in_use(type_label)
    return render_template(
        "type_sites_confirm_delete.html",
        type_payload=type_payload,
        can_delete=can_delete,
        index=type_index,
    )
