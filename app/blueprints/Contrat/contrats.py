"""Blueprint handling contract creation based on geo selections."""

from __future__ import annotations

from typing import Iterable

from flask import Blueprint, redirect, render_template, request, session, url_for

from app.utils.utils_json import load_json_file

contrats_bp = Blueprint("contrats", __name__, template_folder="templates")

REGION_FILE = "./app/data/geojson/region2020.geojson"
DEPARTMENT_FILE = "./app/data/geojson/dept2020.geojson"


@contrats_bp.route("/liste", methods=["GET", "POST"])
def list_regions():
    """Display available regions and collect selected entries."""
    geojson_data = load_json_file(REGION_FILE)
    regions = _extract_regions(geojson_data["features"])

    if request.method == "POST":
        selected_regions = request.form.getlist("regions")
        agency_name = request.form.get("agency", "").strip()

        if not agency_name:
            return "Le nom de l'agence est obligatoire.", 400

        parsed_regions = _parse_selected_regions(selected_regions)
        session["selected_regions"] = parsed_regions
        session["agency_name"] = agency_name

        return redirect(url_for("contrats.select_departments"))

    return render_template("contrat_region.html", regions=regions)


@contrats_bp.route("/departments", methods=["GET", "POST"])
def select_departments():
    """Display departments that belong to the previously selected regions."""
    departments_data = load_json_file(DEPARTMENT_FILE)
    selected_regions = session.get("selected_regions", [])
    selected_codes = {str(region["code"]) for region in selected_regions}

    departments = [
        feature["properties"]
        for feature in departments_data["features"]
        if not selected_codes or str(feature["properties"].get("reg")) in selected_codes
    ]

    if request.method == "POST":
        selected_departments = request.form.getlist("departments")
        session["selected_departments"] = selected_departments
        return redirect(url_for("contrats.list_regions"))

    return render_template("departments.html", departments=departments)


def _extract_regions(features: Iterable[dict]) -> list[dict[str, int | str]]:
    """Return a simplified region list from geojson features."""
    regions: list[dict[str, int | str]] = []
    for feature in features:
        properties = feature.get("properties", {})
        name = properties.get("libgeo", "Inconnu")
        code = properties.get("reg", "Inconnu")
        regions.append({"name": name, "code": code})
    return regions


def _parse_selected_regions(selected_regions: Iterable[str]) -> list[dict[str, int | str]]:
    """Parse the ``name;code`` representation returned by the form."""
    parsed: list[dict[str, int | str]] = []
    for region in selected_regions:
        if ";" not in region:
            continue
        name, code_str = region.split(";", maxsplit=1)
        if not code_str.isdigit():
            continue
        parsed.append({"name": name, "code": int(code_str)})
    return parsed
