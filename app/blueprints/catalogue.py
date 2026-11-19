"""Administration of the SQLite catalogue and its exchange formats."""
import csv
import io
import json
import sqlite3
import tempfile
from pathlib import Path

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for

from app.catalogue import read_import
from app.utils.auth import login_required, require_level
from app.utils.site_store import catalogue, enabled

catalogue_bp = Blueprint("catalogue", __name__, template_folder="catalogue_templates")
CATALOGUE_ADMIN_LEVEL = 5
MAX_IMPORT_BYTES = 10 * 1024 * 1024


@catalogue_bp.route("/", methods=["GET", "POST"])
@login_required
@require_level(CATALOGUE_ADMIN_LEVEL)
def manage():
    if not enabled():
        abort(404)
    if request.method == "POST":
        try:
            action = request.form.get("action")
            if action == "contract":
                reference = (request.form.get("REFERENCE") or "").strip()
                if any(c["reference"] == reference for c in catalogue().contracts()):
                    raise ValueError("Cette référence de contrat existe déjà.")
                catalogue().import_bundle({"contrats": [{"REFERENCE": reference, "NOM": request.form.get("NOM", "")}]}, source="création contrat")
                flash("Contrat créé.", "success")
            elif action in {"preview", "import"}:
                upload = request.files.get("file")
                if not upload or not upload.filename:
                    raise ValueError("Choisissez un fichier JSON ou CSV.")
                raw = upload.stream.read(MAX_IMPORT_BYTES + 1)
                if len(raw) > MAX_IMPORT_BYTES:
                    raise ValueError("Fichier trop volumineux (10 Mo maximum).")
                bundle = read_import(raw, upload.filename, request.form.get("entity", "sites"))
                summary = catalogue().import_bundle(bundle, source=Path(upload.filename).name, dry_run=action == "preview")
                message = "Simulation réussie, aucune donnée modifiée" if action == "preview" else "Import terminé"
                flash(message + " : " + ", ".join(f"{name} : {count} lignes" for name,count in summary.items()), "success")
            else:
                raise ValueError("Action inconnue.")
        except (ValueError, UnicodeError, csv.Error, sqlite3.Error) as exc:
            flash(f"Opération annulée : {exc}", "danger")
        return redirect(url_for("catalogue.manage"))
    return render_template("catalogue.html", counts=catalogue().check(), contracts=catalogue().contracts())


@catalogue_bp.route("/export")
@login_required
@require_level(CATALOGUE_ADMIN_LEVEL)
def export_data():
    if not enabled():
        abort(404)
    payload = catalogue().export_bundle()
    return send_file(io.BytesIO(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")),
                     mimetype="application/json", as_attachment=True, download_name="catalogue.json")


@catalogue_bp.route("/backup")
@login_required
@require_level(CATALOGUE_ADMIN_LEVEL)
def backup_data():
    if not enabled():
        abort(404)
    with tempfile.TemporaryDirectory(prefix="karto-backup-") as directory:
        destination = Path(directory) / "catalogue.sqlite3"
        catalogue().backup(destination)
        payload = destination.read_bytes()
    return send_file(io.BytesIO(payload), mimetype="application/vnd.sqlite3",
                     as_attachment=True, download_name="catalogue.sqlite3")
