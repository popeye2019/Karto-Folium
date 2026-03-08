"""Blueprint responsible for user administration tasks."""

from __future__ import annotations

import uuid
import io
import json
import tempfile
import zipfile
from datetime import datetime, timezone
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

DEFAULT_USER_FILE = "./app/data/users/users.json"
DEFAULT_RIGHTS_FILE = "./app/data/users/droits.json"
DEFAULT_LOGIN_JOURNAL_FILE = "./app/data/users/login_journal.json"

USER_FILE = DEFAULT_USER_FILE
SAVE_USERS_FILE = DEFAULT_USER_FILE
RIGHTS_FILE = DEFAULT_RIGHTS_FILE
LOGIN_JOURNAL_FILE = DEFAULT_LOGIN_JOURNAL_FILE
USERS_VIEW_LEVEL = 1
USERS_ADMIN_LEVEL = 5

users_bp = Blueprint("users", __name__, template_folder="templates")


def _data_dir() -> Path:
    """Absolute path to the data directory."""
    return Path(current_app.root_path) / "data"


def _is_exact_level_five() -> bool:
    user_session = session.get("user", {})
    return user_session.get("access_level") == 5


def _users_file_path(write: bool = False) -> str:
    configured = current_app.config.get("USERS_FILE")
    if configured and str(configured) != DEFAULT_USER_FILE:
        return str(configured)
    return SAVE_USERS_FILE if write else USER_FILE


def _rights_file_path() -> str:
    configured = current_app.config.get("RIGHTS_FILE")
    if configured and str(configured) != DEFAULT_RIGHTS_FILE:
        return str(configured)
    return RIGHTS_FILE


def _login_journal_file_path() -> str:
    configured = current_app.config.get("LOGIN_JOURNAL_FILE")
    if configured and str(configured) != DEFAULT_LOGIN_JOURNAL_FILE:
        return str(configured)
    return LOGIN_JOURNAL_FILE


def _load_access_options() -> list[tuple[int, str]]:
    """Return sorted access level options from droits.json."""
    rights = load_json(_rights_file_path())
    options: list[tuple[int, str]] = []
    if isinstance(rights, list):
        for entry in rights:
            if not isinstance(entry, dict):
                continue
            try:
                level = int(entry.get("Niveau"))
            except (TypeError, ValueError):
                continue
            definition = str(entry.get("Definition", "")).strip()
            label = f"Niveau {level}"
            if definition:
                label = f"{label} - {definition}"
            options.append((level, label))

    if not options:
        options = [(level, f"Niveau {level}") for level in range(1, 6)]

    dedup: dict[int, str] = {}
    for level, label in options:
        dedup[level] = label
    return sorted(dedup.items(), key=lambda item: item[0])


def _iter_json_files(data_dir: Path) -> list[Path]:
    """Return all JSON files under data_dir."""
    if not data_dir.exists():
        return []
    return [path for path in data_dir.rglob("*.json") if path.is_file()]


def _load_login_journal() -> list[dict[str, Any]]:
    try:
        data = load_json(_login_journal_file_path())
    except FileNotFoundError:
        return []
    if isinstance(data, list):
        return [entry for entry in data if isinstance(entry, dict)]
    return []


def _build_json_backup_archive(data_dir: Path, destination: io.BytesIO | Path) -> None:
    """Build a ZIP archive that contains only JSON files from app/data."""
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in _iter_json_files(data_dir):
            arcname = Path("data") / path.relative_to(data_dir)
            # Force POSIX separators inside ZIP for cross-platform restore.
            archive.write(path, arcname.as_posix())


def _save_prerestore_snapshot(data_dir: Path) -> Path:
    """Persist a JSON-only backup before restore for manual rollback."""
    backup_dir = data_dir / "maintenance" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup_path = backup_dir / f"karto-prerestore-json-{timestamp}.zip"
    _build_json_backup_archive(data_dir, backup_path)
    return backup_path


def _load_restore_payload(upload_stream, data_dir: Path) -> dict[Path, str]:
    """Validate the uploaded archive and return JSON payload mapped by relative path."""
    payload: dict[Path, str] = {}
    with zipfile.ZipFile(upload_stream) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue

            # Accept both "/" and "\" as separators from external ZIP creators.
            normalized_name = member.filename.replace("\\", "/")
            member_path = Path(normalized_name)
            parts = list(member_path.parts)
            if parts and parts[0].lower() == "data":
                parts = parts[1:]
            if not parts:
                continue

            relative_path = Path(*parts)
            if relative_path.suffix.lower() != ".json":
                raise ValueError("L'archive ne doit contenir que des fichiers JSON.")

            target_path = (data_dir / relative_path).resolve()
            base_path = data_dir.resolve()
            try:
                target_path.relative_to(base_path)
            except ValueError:
                raise ValueError("Chemin d'extraction non autorise dans l'archive.") from None

            raw_bytes = archive.read(member)
            try:
                raw_text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Encodage invalide pour {member.filename}. UTF-8 requis.") from exc

            try:
                json.loads(raw_text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON invalide dans {member.filename}: {exc.msg}") from exc

            payload[relative_path] = raw_text

    if not payload:
        raise ValueError("Archive vide: aucun fichier JSON detecte.")

    return payload


def _apply_restore_payload(data_dir: Path, payload: dict[Path, str]) -> None:
    """Apply JSON restore in two phases: stage files then replace targets."""
    data_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="krto-restore-", dir=str(data_dir.parent)) as temp_dir:
        staging_root = Path(temp_dir) / "data"
        staging_root.mkdir(parents=True, exist_ok=True)

        for relative_path, raw_text in payload.items():
            staged_file = staging_root / relative_path
            staged_file.parent.mkdir(parents=True, exist_ok=True)
            staged_file.write_text(raw_text, encoding="utf-8")

        existing_rel = {
            path.relative_to(data_dir)
            for path in _iter_json_files(data_dir)
            if (data_dir / path.relative_to(data_dir)).is_file()
        }
        incoming_rel = set(payload.keys())

        for relative_path in incoming_rel:
            target = data_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            staged_file = staging_root / relative_path
            target.write_text(staged_file.read_text(encoding="utf-8"), encoding="utf-8")

        for relative_path in sorted(existing_rel - incoming_rel):
            obsolete = data_dir / relative_path
            if obsolete.exists():
                obsolete.unlink()


def _contracts_to_text(raw_contracts: Any) -> str:
    if not isinstance(raw_contracts, list):
        return ""
    cleaned = [str(item).strip() for item in raw_contracts if str(item).strip()]
    return "\n".join(cleaned)


def _parse_contracts_text(raw_text: str) -> list[str]:
    tokens: list[str] = []
    for line in raw_text.splitlines():
        for part in line.split(","):
            value = part.strip()
            if value:
                tokens.append(value)
    return tokens


def _build_edit_user_view_model(user_record: dict[str, Any]) -> dict[str, Any]:
    view_model = dict(user_record)
    view_model.setdefault("Nom", "")
    view_model.setdefault("Prenom", "")
    view_model.setdefault("Login", "")
    view_model.setdefault("Email", "")
    view_model.setdefault("Niveau acces", 1)
    view_model.setdefault("Notification", False)
    view_model.setdefault("First_Login", False)
    view_model.setdefault("Date_connec", None)
    view_model.setdefault("id", "")
    view_model["contracts_text"] = _contracts_to_text(view_model.get("Contrat", []))
    return view_model


@users_bp.route("/")
@login_required
@require_level(USERS_ADMIN_LEVEL)
def list_users():
    """Display the list of registered users."""
    users = load_json(_users_file_path())
    current_app.logger.info("Listing users")

    user_session = session.get("user", {})
    user_level = user_session.get("access_level", 0)

    return render_template(
        "user_list.html",
        users=users,
        user_level=user_level,
        user=user_session,
    )


@users_bp.route("/backup", methods=["GET"])
@login_required
@require_level(USERS_ADMIN_LEVEL)
def backup_restore():
    """Render the dedicated backup/restore page for administrators."""
    if not _is_exact_level_five():
        user_level = session.get("user", {}).get("access_level")
        return render_template(
            "not_authorized.html",
            message="Cette fonctionnalite est reservee au niveau 5 exact.",
            required_level=5,
            user_level=user_level,
        )
    user_session = session.get("user", {})
    return render_template("backup_restore.html", user=user_session)


@users_bp.route("/edit/<login>", methods=["GET", "POST"])
@login_required
@require_level(USERS_ADMIN_LEVEL)
def edit_user(login: str):
    """Allow administrators to edit a user profile."""
    user_session = session.get("user", {})
    can_reset_password = user_session.get("access_level", 0) > 4
    access_options = _load_access_options()
    allowed_levels = {level for level, _ in access_options}
    users = load_json(_users_file_path())
    user_record = next((usr for usr in users if usr["Login"] == login), None)

    if user_record is None:
        return f"Utilisateur avec le login {login} non trouve.", 404

    def render_edit(form_data: dict[str, Any]) -> str:
        return render_template(
            "user_edit.html",
            user=user_session,
            edit_user=form_data,
            edit_target_login=login,
            can_reset_password=can_reset_password,
            access_options=access_options,
        )

    if request.method == "POST":
        current_login = str(user_record.get("Login", ""))
        updated_user = dict(user_record)

        updated_user["Nom"] = (request.form.get("nom") or "").strip()
        updated_user["Prenom"] = (request.form.get("prenom") or "").strip()
        updated_user["Email"] = (request.form.get("email") or "").strip()
        updated_user["Notification"] = request.form.get("notification") == "on"
        updated_user["First_Login"] = request.form.get("first_login") == "on"
        updated_user["Contrat"] = _parse_contracts_text(request.form.get("contrat") or "")

        updated_login = (request.form.get("login") or current_login).strip()
        if not updated_login:
            flash("Le login est obligatoire.", "warning")
            return render_edit(_build_edit_user_view_model(updated_user))
        if updated_login != current_login and any(usr.get("Login") == updated_login for usr in users):
            flash("Ce login est deja utilise.", "warning")
            return render_edit(_build_edit_user_view_model(updated_user))
        updated_user["Login"] = updated_login

        selected_level_raw = (request.form.get("niveau_acces") or "").strip()
        try:
            selected_level = int(selected_level_raw)
        except ValueError:
            flash("Niveau d'acces invalide.", "warning")
            return render_edit(_build_edit_user_view_model(updated_user))

        if selected_level not in allowed_levels:
            flash("Niveau d'acces non autorise.", "warning")
            return render_edit(_build_edit_user_view_model(updated_user))
        updated_user["Niveau acces"] = selected_level

        if can_reset_password:
            new_password = (request.form.get("new_password") or "").strip()
            confirm_password = (request.form.get("confirm_password") or "").strip()
            if new_password or confirm_password:
                if new_password != confirm_password:
                    flash("Les nouveaux mots de passe ne correspondent pas.", "warning")
                    return render_edit(_build_edit_user_view_model(updated_user))
                updated_user["Mot de passe"] = generate_password_hash(new_password)
                flash("Mot de passe reinitialise.", "success")

        user_record.update(updated_user)
        save_json(_users_file_path(write=True), users)
        if user_session.get("login") == current_login:
            user_session["login"] = str(user_record.get("Login", user_session.get("login", "")))
            user_session["access_level"] = user_record.get("Niveau acces", user_session.get("access_level", 0))
            user_session["nom"] = str(user_record.get("Nom", user_session.get("nom", "")))
            user_session["prenom"] = str(user_record.get("Prenom", user_session.get("prenom", "")))
            user_session["uuid"] = str(user_record.get("id", user_session.get("uuid", "")))
            user_session["autorise_notif"] = bool(
                user_record.get("Notification", user_session.get("autorise_notif", False))
            )
            session["user"] = user_session
        return redirect(url_for("users.list_users"))

    return render_edit(_build_edit_user_view_model(user_record))


@users_bp.route("/login-journal", methods=["GET"])
@login_required
@require_level(USERS_ADMIN_LEVEL)
def login_journal():
    """Display recent login history for administrators."""
    entries = _load_login_journal()
    user_session = session.get("user", {})
    return render_template("login_journal.html", entries=entries, user=user_session)


@users_bp.route("/login-journal/reset", methods=["POST"])
@login_required
@require_level(USERS_ADMIN_LEVEL)
def reset_login_journal():
    """Clear login history entries."""
    save_json(_login_journal_file_path(), [])
    flash("Journal des connexions remis a zero.", "success")
    return redirect(url_for("users.login_journal"))


@users_bp.route("/add", methods=["GET", "POST"])
@login_required
@require_level(USERS_ADMIN_LEVEL)
def add_user():
    """Create a new user with a hashed password."""
    if request.method == "POST":
        users = load_json(_users_file_path())

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
        save_json(_users_file_path(write=True), users)
        return redirect(url_for("users.list_users"))

    return render_template("user_add.html")


@users_bp.route("/delete/<login>", methods=["POST"])
@login_required
@require_level(USERS_ADMIN_LEVEL)
def delete_user(login: str):
    """Remove the given user from the JSON store."""
    users = load_json(_users_file_path())
    user = next((usr for usr in users if usr["Login"] == login), None)
    if user is None:
        return f"Utilisateur avec le login {login} non trouve.", 404

    filtered_users = [usr for usr in users if usr["Login"] != login]
    save_json(_users_file_path(write=True), filtered_users)
    return redirect(url_for("users.list_users"))


@users_bp.route("/rights")
@login_required
@require_level(USERS_VIEW_LEVEL)
def list_rights():
    """Display the rights definitions."""
    rights = load_json(_rights_file_path())
    return render_template("user_rights_list.html", droits=rights)


@users_bp.route("/rights/edit/<int:level>", methods=["GET", "POST"])
@login_required
@require_level(USERS_ADMIN_LEVEL)
def edit_right(level: int):
    """Edit the definition for a specific access level."""
    rights = load_json(_rights_file_path())
    entry = next((item for item in rights if item["Niveau"] == level), None)

    if entry is None:
        return f"Droit avec le niveau {level} non trouve.", 404

    if request.method == "POST":
        entry["Definition"] = request.form["definition"]
        save_json(_rights_file_path(), rights)
        return redirect(url_for("users.list_rights"))

    return render_template("edit_right.html", right=entry)


@users_bp.route("/backup/download", methods=["GET"])
@login_required
@require_level(USERS_ADMIN_LEVEL)
def download_backup():
    """Build a JSON-only zip of app/data and send it to the administrator."""
    if not _is_exact_level_five():
        user_level = session.get("user", {}).get("access_level")
        return render_template(
            "not_authorized.html",
            message="Cette fonctionnalite est reservee au niveau 5 exact.",
            required_level=5,
            user_level=user_level,
        )
    data_dir = _data_dir()
    buffer = io.BytesIO()
    _build_json_backup_archive(data_dir, buffer)

    buffer.seek(0)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"karto-data-json-backup-{timestamp}.zip",
    )


@users_bp.route("/backup/restore", methods=["POST"])
@login_required
@require_level(USERS_ADMIN_LEVEL)
def restore_backup():
    """Restore app/data JSON files from an uploaded zip archive."""
    if not _is_exact_level_five():
        user_level = session.get("user", {}).get("access_level")
        return render_template(
            "not_authorized.html",
            message="Cette fonctionnalite est reservee au niveau 5 exact.",
            required_level=5,
            user_level=user_level,
        )
    upload = request.files.get("file")

    if not upload or upload.filename == "":
        flash("Aucun fichier .zip fourni.", "warning")
        return redirect(url_for("users.backup_restore"))
    if not str(upload.filename).lower().endswith(".zip"):
        flash("Le fichier doit etre une archive .zip.", "warning")
        return redirect(url_for("users.backup_restore"))

    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    try:
        upload.stream.seek(0)
        restore_payload = _load_restore_payload(upload.stream, data_dir)
        snapshot = _save_prerestore_snapshot(data_dir)
        _apply_restore_payload(data_dir, restore_payload)
        flash(f"Sauvegarde restauree avec succes. Snapshot: {snapshot.name}", "success")
    except zipfile.BadZipFile:
        flash("Le fichier fourni n'est pas une archive ZIP valide.", "danger")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:  # pragma: no cover - defensive logging
        current_app.logger.exception("Echec de la restauration des donnees: %s", exc)
        flash(
            "Echec de la restauration des donnees. "
            f"Detail technique: {type(exc).__name__}: {exc}",
            "danger",
        )

    return redirect(url_for("users.backup_restore"))

