"""Blueprint exposing metadata such as available user fields."""

from __future__ import annotations

from flask import Blueprint, current_app, render_template

from app.utils.utils_json import get_field_names, load_json_file as load_data

DATA_FILE = "./app/data/users/users.json"

champs_bp = Blueprint("champs_sites", __name__, template_folder="templates")


@champs_bp.route("/")
def display_fields():
    """Display the JSON field names available for user records."""
    current_app.logger.info("Rendering fields list")
    data = load_data(DATA_FILE)
    fields = get_field_names(data)
    return render_template("champs.html", fields=fields)
