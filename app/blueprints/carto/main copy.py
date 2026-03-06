"""Dashboard blueprint displaying the main application home page."""

from __future__ import annotations

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from app.utils.auth import login_required, require_level
from app.utils.import_fichier import save_upload, UploadError
from app.utils.utils_json import load_json_file

main_bp = Blueprint("main", __name__, template_folder="templates")
SITE_DATA_PATH = "./app/data/sites/recap.json"


@main_bp.route("/")
@login_required
@require_level(1)
def home():
    """Render the authenticated home page."""
    user = session.get("user")
    current_app.logger.debug("Rendering main home page for user %s", user.get("login") if user else "anonymous")

    return render_template(
        "main.html",
        current_app=current_app,
        user=user,
    )


@main_bp.get("/site-search")
@login_required
@require_level(1)
def site_search():
    """Return matching sites for the autocomplete on the home page."""
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify({"results": []})

    def _safe_float(value):
        try:
            return float(str(value).replace(",", "."))
        except Exception:
            return None

    try:
        data = load_json_file(SITE_DATA_PATH)
    except FileNotFoundError:
        current_app.logger.error("Fichier recap.json introuvable pour la recherche.")
        return jsonify({"results": [], "error": "Fichier recap.json introuvable."}), 500
    except Exception as exc:  # pragma: no cover - defensive logging
        current_app.logger.warning("Lecture recap.json impossible pour la recherche: %s", exc)
        return jsonify({"results": [], "error": "Recherche indisponible pour le moment."}), 500

    if not isinstance(data, list):
        return jsonify({"results": [], "error": "Format de donnees invalide."}), 500

    needle = query.lower()
    matches: list[dict[str, object]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        nom = str(entry.get("NOM", ""))
        commune = str(entry.get("COMMUNE", ""))
        site_type = str(entry.get("TYPE", ""))
        lat = _safe_float(entry.get("LAT"))
        lon = _safe_float(entry.get("LONG"))
        if needle in nom.lower() or needle in commune.lower() or needle in site_type.lower():
            gmaps_url = None
            map_url = None
            if lat is not None and lon is not None:
                gmaps_url = f"https://www.google.com/maps/dir//{lat},{lon}/@{lat},{lon},17z"
                map_url = f"{url_for('static', filename='global/ouvrages.html')}?lat={lat}&lon={lon}&zoom=16"
                if site_type:
                    map_url += f"&layer={site_type}"
            matches.append(
                {
                    "index": entry.get("INDEX"),
                    "nom": nom,
                    "commune": commune,
                    "type": site_type,
                    "lat": lat,
                    "lon": lon,
                    "gmaps_url": gmaps_url,
                    "map_url": map_url,
                }
            )
        if len(matches) >= 20:
            break

    return jsonify({"results": matches})


@main_bp.route("/upload-test-icon", methods=["POST"])
@login_required
@require_level(1)
def upload_test_icon():
    file = request.files.get("icon_file")
    if not file or not file.filename:
        flash("Aucun fichier sélectionné.", "danger")
        return redirect(url_for("main.home"))

    try:
        destination = save_upload(file, category="image", target_dir="app/data/icones")
    except UploadError as exc:
        current_app.logger.warning("Upload icon refused: %s", exc)
        flash(str(exc), "danger")
        return redirect(url_for("main.home"))

    flash(f"Icône enregistrée: {destination.name}", "success")
    return redirect(url_for("main.home"))
