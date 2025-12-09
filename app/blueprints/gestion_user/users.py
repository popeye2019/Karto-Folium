"""Blueprint responsible for user administration tasks."""

from __future__ import annotations

import uuid
import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    send_file,
    url_for,
)
from werkzeug.security import generate_password_hash

from app.utils.auth import login_required, require_level
from app.utils.utils_json import load_json_file as load_json
from app.utils.utils_json import save_json_file as save_json

USER_FILE = "./app/data/users/users.json"
SAVE_USERS_FILE = "./app/data/users/users.json"
RIGHTS_FILE = "./app/data/users/droits.json"

users_bp = Blueprint("users", __name__, template_folder="templates")

def _data_dir() -> Path:
    """Absolute path to the data directory."""
    return Path(current_app.root_path) / "data"


@users_bp.route("/")
@login_required
@require_level(5)
def list_users():
    """Display the list of registered users."""
    users = load_json(USER_FILE)
    current_app.logger.info("Listing users")

    user_session = session.get("user", {})
    user_level = user_session.get("access_level", 0)

    return render_template(
        "user_list.html",
        users=users,
        user_level=user_level,
        user=user_session,
    )


@users_bp.route("/edit/<login>", methods=["GET", "POST"])
@login_required
@require_level(5)
def edit_user(login: str):
    """Allow administrators to edit a user profile."""
    users = load_json(USER_FILE)
    user = next((usr for usr in users if usr["Login"] == login), None)

    if user is None:
        return f"Utilisateur avec le login {login} non trouve.", 404

    if request.method == "POST":
        user["Nom"] = request.form["nom"]
        user["Prenom"] = request.form["prenom"]
        user["Email"] = request.form["email"]
        user["Notification"] = request.form.get("notification") == "on"

        save_json(SAVE_USERS_FILE, users)
        return redirect(url_for("users.list_users"))

    return render_template("user_edit.html", user=user)


@users_bp.route("/add", methods=["GET", "POST"])
@login_required
@require_level(5)
def add_user():
    """Create a new user with a hashed password."""
    if request.method == "POST":
        users = load_json(USER_FILE)

        password = request.form["password"]
        new_user: dict[str, Any] = {
            "Nom": request.form["nom"],
            "Prenom": request.form["prenom"],
            "Login": request.form["login"],
            "Mot de passe": generate_password_hash(password),
            "Niveau acces": int(request.form["niveau_acces"]),
            "Notification": request.form.get("notification") == "on",
            "Email": request.form["email"],
            "Date_connec": None,
            "Contrat": [],
            "id": str(uuid.uuid4()),
        }

        if any(user["Login"] == new_user["Login"] for user in users):
            return "Erreur : le login existe deja.", 400

        users.append(new_user)
        save_json(SAVE_USERS_FILE, users)
        return redirect(url_for("users.list_users"))

    return render_template("user_add.html")


@users_bp.route("/delete/<login>", methods=["POST"])
@login_required
@require_level(5)
def delete_user(login: str):
    """Remove the given user from the JSON store."""
    users = load_json(USER_FILE)
    user = next((usr for usr in users if usr["Login"] == login), None)
    if user is None:
        return f"Utilisateur avec le login {login} non trouve.", 404

    filtered_users = [usr for usr in users if usr["Login"] != login]
    save_json(SAVE_USERS_FILE, filtered_users)
    return redirect(url_for("users.list_users"))


@users_bp.route("/rights")
@login_required
@require_level(1)
def list_rights():
    """Display the rights definitions."""
    rights = load_json(RIGHTS_FILE)
    return render_template("user_rights_list.html", droits=rights)


@users_bp.route("/rights/edit/<int:level>", methods=["GET", "POST"])
@login_required
@require_level(5)
def edit_right(level: int):
    """Edit the definition for a specific access level."""
    rights = load_json(RIGHTS_FILE)
    entry = next((item for item in rights if item["Niveau"] == level), None)

    if entry is None:
        return f"Droit avec le niveau {level} non trouve.", 404

    if request.method == "POST":
        entry["Definition"] = request.form["definition"]
        save_json(RIGHTS_FILE, rights)
        return redirect(url_for("users.list_rights"))

    return render_template("edit_right.html", right=entry)


@users_bp.route("/backup/download", methods=["GET"])
@login_required
@require_level(5)
def download_backup():
    """Build a zip of app/data and send it to the administrator."""
    data_dir = _data_dir()
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if data_dir.exists():
            for path in data_dir.rglob("*"):
                if path.is_file():
                    arcname = Path("data") / path.relative_to(data_dir)
                    archive.write(path, arcname)

    buffer.seek(0)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"karto-data-backup-{timestamp}.zip",
    )


@users_bp.route("/backup/restore", methods=["POST"])
@login_required
@require_level(5)
def restore_backup():
    """Restore app/data from an uploaded zip archive."""
    upload = request.files.get("file")

    if not upload or upload.filename == "":
        flash("Aucun fichier .zip fourni.", "warning")
        return redirect(url_for("users.list_users"))

    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(upload) as archive:
            base = data_dir.resolve()
            for member in archive.infolist():
                # Skip directories; we create them as needed.
                if member.is_dir():
                    continue

                member_path = Path(member.filename)
                parts = list(member_path.parts)
                # Allow archives that include a top-level "data" folder or not.
                if parts and parts[0].lower() == "data":
                    parts = parts[1:]

                if not parts:
                    continue

                target_path = (base / Path(*parts)).resolve()
                try:
                    target_path.relative_to(base)
                except ValueError:
                    raise ValueError("Chemin d'extraction non autorise dans l'archive.")

                target_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member, "r") as source, open(target_path, "wb") as dest:
                    dest.write(source.read())

        flash("Sauvegarde restauree avec succes.", "success")
    except zipfile.BadZipFile:
        flash("Le fichier fourni n'est pas une archive ZIP valide.", "danger")
    except Exception as exc:  # pragma: no cover - defensive logging
        current_app.logger.exception("Echec de la restauration des donnees: %s", exc)
        flash("Echec de la restauration des donnees.", "danger")

    return redirect(url_for("users.list_users"))
