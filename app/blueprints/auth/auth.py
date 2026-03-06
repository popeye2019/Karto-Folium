"""Authentication blueprint: login, logout, and access control helpers."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import generate_password_hash

from app.utils.auth import USER_FILE as AUTH_USER_FILE
from app.utils.auth import login_required, require_level, verify_user
from app.utils.utils_json import load_json_file, save_json_file

auth_bp = Blueprint("auth", __name__, template_folder="templates")
DEFAULT_USER_FILE_PATH = AUTH_USER_FILE
DEFAULT_LOGIN_JOURNAL_FILE = "./app/data/users/login_journal.json"
DEFAULT_LOGIN_BAN_FILE = "./app/data/users/login_bans.json"

USER_FILE_PATH = DEFAULT_USER_FILE_PATH
LOGIN_JOURNAL_FILE = DEFAULT_LOGIN_JOURNAL_FILE
LOGIN_BAN_FILE = DEFAULT_LOGIN_BAN_FILE


def _users_file_path() -> str:
    configured = current_app.config.get("USERS_FILE")
    if configured and str(configured) != DEFAULT_USER_FILE_PATH:
        return str(configured)
    return USER_FILE_PATH


def _login_journal_file_path() -> str:
    configured = current_app.config.get("LOGIN_JOURNAL_FILE")
    if configured and str(configured) != DEFAULT_LOGIN_JOURNAL_FILE:
        return str(configured)
    return LOGIN_JOURNAL_FILE


def _login_ban_file_path() -> str:
    configured = current_app.config.get("LOGIN_BAN_FILE")
    if configured and str(configured) != DEFAULT_LOGIN_BAN_FILE:
        return str(configured)
    return LOGIN_BAN_FILE


def _login_journal_max_entries() -> int:
    raw = current_app.config.get("LOGIN_JOURNAL_MAX_ENTRIES", 2000)
    try:
        return max(100, int(raw))
    except (TypeError, ValueError):
        return 2000


def _append_login_journal(
    *,
    connected_at: str,
    login: str,
    client_ip: str,
    status: str,
    nom: str = "",
    prenom: str = "",
) -> None:
    """Store login attempts (success/failure) for audit and abuse detection."""
    try:
        journal = load_json_file(_login_journal_file_path())
    except FileNotFoundError:
        journal = []
    except Exception as exc:  # pragma: no cover - defensive logging
        current_app.logger.exception("Unable to load login journal: %s", exc)
        return

    if not isinstance(journal, list):
        journal = []

    journal.insert(
        0,
        {
            "Horodatage": connected_at,
            "Nom": nom,
            "Prenom": prenom,
            "Login": login,
            "IP": client_ip,
            "Statut": status,
        },
    )
    journal = journal[: _login_journal_max_entries()]

    try:
        save_json_file(_login_journal_file_path(), journal)
    except Exception as exc:  # pragma: no cover - defensive logging
        current_app.logger.exception("Unable to save login journal: %s", exc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _is_local_test_ip(client_ip: str) -> bool:
    ip = (client_ip or "").strip()
    return ip in {"127.0.0.1", "::1"} or ip.startswith("192.168.0.")


def _is_ban_enforced_for_ip(client_ip: str) -> bool:
    if not bool(current_app.config.get("LOGIN_BAN_ENABLED", True)):
        return False
    include_local = bool(current_app.config.get("LOGIN_BAN_INCLUDE_LOCAL", False))
    if include_local:
        return True
    return not _is_local_test_ip(client_ip)


def _load_ban_state() -> dict:
    try:
        data = load_json_file(_login_ban_file_path())
    except FileNotFoundError:
        return {"ips": {}}
    except Exception as exc:  # pragma: no cover - defensive logging
        current_app.logger.exception("Unable to load login ban state: %s", exc)
        return {"ips": {}}
    if not isinstance(data, dict):
        return {"ips": {}}
    ips = data.get("ips")
    if not isinstance(ips, dict):
        ips = {}
    return {"ips": ips}


def _save_ban_state(state: dict) -> None:
    try:
        save_json_file(_login_ban_file_path(), state)
    except Exception as exc:  # pragma: no cover - defensive logging
        current_app.logger.exception("Unable to save login ban state: %s", exc)


def _normalize_failures(failures: list, now: datetime, window_seconds: int) -> list[str]:
    keep_after = now - timedelta(seconds=window_seconds)
    kept: list[str] = []
    for value in failures:
        if not isinstance(value, str):
            continue
        parsed = _parse_datetime(value)
        if parsed and parsed >= keep_after:
            kept.append(parsed.isoformat())
    return kept


def _get_ban_remaining_seconds(client_ip: str, now: datetime) -> int:
    if not _is_ban_enforced_for_ip(client_ip):
        return 0

    state = _load_ban_state()
    entry = state.get("ips", {}).get(client_ip)
    if not isinstance(entry, dict):
        return 0

    banned_until_raw = entry.get("banned_until")
    if not isinstance(banned_until_raw, str):
        return 0
    banned_until = _parse_datetime(banned_until_raw)
    if not banned_until:
        return 0

    remaining = int((banned_until - now).total_seconds())
    if remaining > 0:
        return remaining

    entry.pop("banned_until", None)
    state.get("ips", {}).pop(client_ip, None)
    _save_ban_state(state)
    return 0


def _register_failed_attempt_and_maybe_ban(client_ip: str, now: datetime) -> int:
    if not _is_ban_enforced_for_ip(client_ip):
        return 0

    max_failures = int(current_app.config.get("LOGIN_BAN_MAX_FAILURES", 5))
    window_seconds = int(current_app.config.get("LOGIN_BAN_WINDOW_SECONDS", 600))
    ban_duration_seconds = int(current_app.config.get("LOGIN_BAN_DURATION_SECONDS", 600))
    if max_failures <= 0:
        return 0

    state = _load_ban_state()
    ips = state.setdefault("ips", {})
    entry = ips.setdefault(client_ip, {})
    failures = entry.get("failures", [])
    if not isinstance(failures, list):
        failures = []

    failures = _normalize_failures(failures, now, window_seconds)
    failures.append(now.isoformat())
    entry["failures"] = failures

    remaining = 0
    if len(failures) >= max_failures:
        banned_until = now + timedelta(seconds=ban_duration_seconds)
        entry["banned_until"] = banned_until.isoformat()
        remaining = int((banned_until - now).total_seconds())

    ips[client_ip] = entry
    _save_ban_state(state)
    return remaining


def _clear_failed_attempts(client_ip: str) -> None:
    if not _is_ban_enforced_for_ip(client_ip):
        return
    state = _load_ban_state()
    ips = state.get("ips", {})
    if isinstance(ips, dict) and client_ip in ips:
        ips.pop(client_ip, None)
        state["ips"] = ips
        _save_ban_state(state)


def _ban_error_message(remaining_seconds: int) -> str:
    minutes = max(1, math.ceil(remaining_seconds / 60))
    return f"Trop de tentatives de connexion. Reessayez dans {minutes} minute(s)."


def _is_sensitive_config_key(name: str) -> bool:
    upper = name.upper()
    return "SECRET" in upper or "PASSWORD" in upper or "TOKEN" in upper


def _jsonable_config_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_jsonable_config_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable_config_value(item) for key, item in value.items()}
    return str(value)


@auth_bp.route("/", methods=["GET", "POST"])
def login():
    """Handle user authentication and session creation."""
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    if "," in client_ip:
        client_ip = client_ip.split(",", 1)[0].strip()

    if request.method == "POST":
        attempt_time = datetime.now().isoformat(timespec="seconds")
        now_utc = _now_utc()
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()

        remaining = _get_ban_remaining_seconds(client_ip, now_utc)
        if remaining > 0:
            _append_login_journal(
                connected_at=attempt_time,
                login=login_value,
                client_ip=client_ip,
                status="bloque_ban",
            )
            return render_template(
                "login.html",
                error=_ban_error_message(remaining),
                client_ip=client_ip,
            )

        if not login_value or not password:
            _append_login_journal(
                connected_at=attempt_time,
                login=login_value,
                client_ip=client_ip,
                status="champs_manquants",
            )
            _register_failed_attempt_and_maybe_ban(client_ip, now_utc)
            current_app.logger.info("Login rejected: missing credentials")
            return render_template(
                "login.html",
                error="Veuillez remplir tous les champs.",
                client_ip=client_ip,
            )

        user = verify_user(login_value, password)
        if user:
            connected_at = datetime.now().isoformat(timespec="seconds")
            session["user"] = {
                "login": user["Login"],
                "access_level": user.get("Niveau acces", 0),
                "nom": user.get("Nom", ""),
                "prenom": user.get("Prenom", ""),
                "connecte_le": connected_at,
                "uuid": user.get("id", ""),
                "autorise_notif": user.get("Notification", False),
            }
            _append_login_journal(
                connected_at=connected_at,
                login=user.get("Login", login_value),
                client_ip=client_ip,
                status="succes",
                nom=user.get("Nom", ""),
                prenom=user.get("Prenom", ""),
            )
            _clear_failed_attempts(client_ip)
            flash("Connexion reussie !", "success")
            current_app.logger.info("User %s logged in", login_value)
            return redirect(url_for("main.home"))

        _append_login_journal(
            connected_at=attempt_time,
            login=login_value,
            client_ip=client_ip,
            status="echec",
        )
        remaining = _register_failed_attempt_and_maybe_ban(client_ip, now_utc)
        if remaining > 0:
            return render_template(
                "login.html",
                error=_ban_error_message(remaining),
                client_ip=client_ip,
            )
        current_app.logger.info("Login rejected: invalid credentials for %s", login_value)
        return render_template("login.html", error="Identifiants invalides.", client_ip=client_ip)

    return render_template("login.html", error=None, client_ip=client_ip)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Clear the session and redirect to the login page."""
    session.pop("user", None)
    flash("Vous avez ete deconnecte.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/about-config", methods=["GET"])
@login_required
@require_level(5)
def about_config():
    """Return a sanitized view of app configuration for admins."""
    safe_config: dict[str, object] = {}
    for key in sorted(current_app.config.keys()):
        if _is_sensitive_config_key(key):
            continue
        safe_config[key] = _jsonable_config_value(current_app.config.get(key))
    return jsonify({"config": safe_config})


@auth_bp.route("/change-password", methods=["GET", "POST"])@login_required
def change_password():
    """Allow an authenticated user to update their password."""
    user = session.get("user")
    if not user:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        current_password = (request.form.get("current_password") or "").strip()
        new_password = (request.form.get("new_password") or "").strip()
        confirm_password = (request.form.get("confirm_password") or "").strip()

        if not current_password or not new_password or not confirm_password:
            flash("Tous les champs sont obligatoires.", "warning")
        elif new_password != confirm_password:
            flash("Les nouveaux mots de passe ne correspondent pas.", "warning")
        else:
            verified = verify_user(user["login"], current_password)
            if not verified:
                flash("Mot de passe actuel incorrect.", "danger")
            else:
                try:
                    users = load_json_file(_users_file_path())
                except FileNotFoundError:
                    current_app.logger.error("User file missing: %s", _users_file_path())
                    flash("Impossible de mettre a jour le mot de passe. Contactez l'administrateur.", "danger")
                else:
                    updated = False
                    for record in users:
                        if record.get("Login") == verified["Login"]:
                            record["Mot de passe"] = generate_password_hash(new_password)
                            updated = True
                            break

                    if not updated:
                        flash("Utilisateur introuvable.", "danger")
                    else:
                        save_json_file(_users_file_path(), users)
                        flash("Mot de passe mis a jour.", "success")
                        current_app.logger.info("User %s updated password", user["login"])
                        return redirect(url_for("main.home"))

    return render_template("change_password.html", user=user)


def route_with_level(blueprint: Blueprint, route: str, level: int) -> Callable:
    """Restrict access to a route based on the user access level."""

    def decorator(func: Callable) -> Callable:
        @blueprint.route(route)
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            if not user or user.get("access_level", 0) < level:
                return render_template(
                    "not_authorized.html",
                    required_level=level,
                    user_level=user["access_level"] if user else None,
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator
