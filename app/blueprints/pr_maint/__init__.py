"""Maintenance module for managing interventions on recap.json sites."""

from __future__ import annotations

from datetime import datetime
import json
from math import radians, cos, sin, asin, sqrt
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.utils.auth import login_required, require_level
from app.utils.utils_json import load_json_file as load_data

pr_maint_bp = Blueprint("pr_maint", __name__, template_folder="templates")

RECUP_FILE = Path("./app/data/sites/recap.json")
COMMENT_FILE = Path("./app/data/maintenance/commentaire.json")
MAINTENANCE_ACCESS_LEVEL = 3


DISTANCE_THRESHOLD_METERS = 2000.0
_EARTH_RADIUS_METERS = 6_371_000


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, (lat1, lon1, lat2, lon2))
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return _EARTH_RADIUS_METERS * c


def _load_comments() -> list[dict[str, object]]:
    if not COMMENT_FILE.exists():
        return []
    try:
        return json.loads(COMMENT_FILE.read_text(encoding="utf-8")) or []
    except json.JSONDecodeError:
        return []


def _save_comments(entries: list[dict[str, object]]) -> None:
    COMMENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    COMMENT_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")






@pr_maint_bp.route("/")
@login_required
@require_level(MAINTENANCE_ACCESS_LEVEL)
def maintenance_home():
    data = load_data(str(RECUP_FILE))
    if not isinstance(data, list):
        data = []

    comments = _load_comments()
    recent_comments: list[dict[str, object]] = []
    if isinstance(comments, list):
        def sort_key(entry: dict[str, object]) -> datetime:
            raw_date = entry.get("date")
            if isinstance(raw_date, str):
                try:
                    return datetime.strptime(raw_date, "%d/%m/%y %H:%M:%S")
                except ValueError:
                    pass
            return datetime.min

        recent_comments = sorted(comments, key=sort_key, reverse=True)[:10]

    return render_template(
        "pr_maint_home.html",
        sites=data,
        site_count=len(data),
        recent_comments=recent_comments,
    )

@pr_maint_bp.route("/geolocalisation")
@login_required
@require_level(MAINTENANCE_ACCESS_LEVEL)
def localisation_page():
    return render_template("recup_gps.html")


@pr_maint_bp.route("/recherche")
@login_required
@require_level(MAINTENANCE_ACCESS_LEVEL)
def search_post():
    latitude = request.args.get("latitude")
    longitude = request.args.get("longitude")
    zone = request.args.get("zone")

    if not latitude or not longitude:
        flash("Coordonnées GPS manquantes.", "danger")
        return redirect(url_for("pr_maint.localisation_page"))

    try:
        user_lat = float(latitude)
        user_lon = float(longitude)
    except ValueError:
        flash("Coordonnées GPS invalides.", "danger")
        return redirect(url_for("pr_maint.localisation_page"))

    data = load_data(str(RECUP_FILE))
    candidate_sites = []
    if isinstance(data, list):
        for index, site in enumerate(data):
            try:
                site_lat = float(site.get("LAT", site.get("lat", 0)))
                site_lon = float(site.get("LONG", site.get("lon", 0)))
            except (TypeError, ValueError):
                continue
            if site_lat == 0 and site_lon == 0:
                continue
            distance = haversine_distance(user_lat, user_lon, site_lat, site_lon)
            if distance <= DISTANCE_THRESHOLD_METERS:
                candidate_sites.append({
                    "INDEX": site.get("INDEX", index),
                    "TYPE": site.get("TYPE", ""),
                    "NOM": site.get("NOM", ""),
                    "COMMUNE": site.get("COMMUNE", ""),
                    "distance": round(distance, 1),
                })

    candidate_sites.sort(key=lambda s: s["distance"])

    if len(candidate_sites) == 1:
        site = candidate_sites[0]
        return render_template(
            "pr_maint_search_result.html",
            latitude=latitude,
            longitude=longitude,
            zone=zone,
            site=site,
            multiple=False,
        )

    return render_template(
        "pr_maint_search_result.html",
        latitude=latitude,
        longitude=longitude,
        zone=zone,
        candidate_sites=candidate_sites,
        multiple=True,
    )



@pr_maint_bp.route("/interventions", methods=["POST"])
@login_required
@require_level(MAINTENANCE_ACCESS_LEVEL)
def create_intervention():
    emplacement_raw = (request.form.get("emplacement") or "").strip()
    commentaire = (request.form.get("commentaire") or "").strip()
    site_label = (request.form.get("site_label") or "").strip()

    if not commentaire:
        flash("Le commentaire est obligatoire.", "danger")
        return redirect(url_for("pr_maint.maintenance_home"))

    try:
        emplacement = int(emplacement_raw)
    except ValueError:
        flash("Emplacement invalide.", "danger")
        return redirect(url_for("pr_maint.maintenance_home"))

    user = session.get("user", {})
    utilisateur = f"{user.get('prenom', '')} {user.get('nom', '')}".strip() or "Utilisateur inconnu"

    entries = _load_comments()
    next_id = max((int(entry.get("id", 0)) for entry in entries), default=0) + 1
    now = datetime.now().strftime("%d/%m/%y %H:%M:%S")

    entries.append(
        {
            "id": next_id,
            "date": now,
            "emplacement": emplacement,
            "commentaire": commentaire,
            "utilisateur": utilisateur,
            "site": site_label,
        }
    )

    _save_comments(entries)
    flash("Intervention enregistrée.", "success")
    return redirect(url_for("pr_maint.maintenance_home"))
