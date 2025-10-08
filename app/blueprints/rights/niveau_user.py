"""Blueprint managing the access level definitions."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.utils.auth import login_required, require_level
from app.utils.utils_json import load_json_file as read_json
from app.utils.utils_json import save_json_file as write_json

rights_bp = Blueprint("user_rights", __name__, template_folder="templates")

DATA_FILE = "./app/data/users/droits.json"


@rights_bp.route("/")
@login_required
@require_level(1)
def index():
    """List the access levels and their definitions."""
    data = read_json(DATA_FILE)
    return render_template("rights_list.html", data=data)


@rights_bp.route("/edit/<int:niveau>", methods=["GET", "POST"])
@login_required
@require_level(5)
def edit(niveau: int):
    """Edit an access level definition by its integer id."""
    if 1 <= niveau <= 5:
        flash(f"Le niveau {niveau} est protege et ne peut pas etre modifie.", "warning")
        return redirect(url_for("user_rights.index"))

    data = read_json(DATA_FILE)
    record = next((item for item in data if item["Niveau"] == niveau), None)
    if record is None:
        return "Niveau introuvable", 404

    if request.method == "POST":
        record["Definition"] = request.form["definition"]
        write_json(DATA_FILE, data)
        flash(f"Niveau {niveau} modifie avec succes.", "success")
        return redirect(url_for("user_rights.index"))

    return render_template("rights_edit.html", record=record)


@rights_bp.route("/add", methods=["GET", "POST"])
@login_required
@require_level(5)
def add_right():
    """Create a brand new access level."""
    rights = read_json(DATA_FILE)
    if request.method == "POST":
        try:
            niveau = int(request.form.get("niveau"))
        except (TypeError, ValueError):
            flash("Le niveau doit etre un entier.", "danger")
            return redirect(request.url)

        definition = request.form.get("definition", "").strip()
        if any(right["Niveau"] == niveau for right in rights):
            flash(f"Le niveau {niveau} existe deja.", "warning")
            return redirect(request.url)

        rights.append({"Niveau": niveau, "Definition": definition})
        write_json(DATA_FILE, rights)
        flash(f"Niveau {niveau} ajoute avec succes.", "success")
        return redirect(url_for("user_rights.index"))

    return render_template("rights_edit.html", record=None)


@rights_bp.route("/delete/<int:niveau>", methods=["POST"])
@login_required
@require_level(5)
def delete(niveau: int):
    """Delete an access level when it is not protected."""
    if 1 <= niveau <= 5:
        flash(f"Le niveau {niveau} est protege et ne peut pas etre supprime.", "warning")
        return redirect(url_for("user_rights.index"))

    data = read_json(DATA_FILE)
    data = [item for item in data if item["Niveau"] != niveau]
    write_json(DATA_FILE, data)
    flash(f"Niveau {niveau} supprime avec succes.", "success")
    return redirect(url_for("user_rights.index"))
