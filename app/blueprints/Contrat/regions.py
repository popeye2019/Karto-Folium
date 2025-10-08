"""Blueprint serving interactive maps for regions and departments."""

from __future__ import annotations

import os

import folium
from flask import Blueprint, render_template, url_for

from app.utils.utils_json import load_json_file

region_bp = Blueprint("region", __name__, template_folder="templates")

REGION_FILE = "./app/data/geojson/region2020.geojson"
DEPARTMENT_FILE = "./app/data/geojson/dept2020.geojson"


@region_bp.route("/")
def home():
    """Display the entry point for the region map."""
    return render_template("regions_home.html")


@region_bp.route("/map")
def map_view():
    """Render the folium map containing clickable regions."""
    geojson_data = load_json_file(REGION_FILE)

    region_map = folium.Map(location=[45.0, 2.0], zoom_start=6)

    for feature in geojson_data["features"]:
        properties = feature["properties"]
        name = properties.get("libgeo", "Inconnu")
        region_id = properties.get("reg", "Inconnu")

        popup = folium.Popup(
            f'<a href="{url_for("region.region_details", region_id=region_id)}">Voir {name}</a>'
        )
        folium.GeoJson(
            feature,
            popup=popup,
            tooltip=name,
            highlight_function=lambda _: {"fillColor": "green"},
        ).add_to(region_map)

    map_path = os.path.join("app", "static", "map.html")
    region_map.save(map_path)

    return render_template("regions_select.html", map_path=map_path)


@region_bp.route("/region/<region_id>")
def region_details(region_id: str):
    """List the departments associated with a region."""
    departments_data = load_json_file(DEPARTMENT_FILE)

    departments = [
        feature["properties"]
        for feature in departments_data["features"]
        if feature["properties"].get("reg") == region_id
    ]

    return render_template("region_select_details.html", region_id=region_id, departements=departments)
