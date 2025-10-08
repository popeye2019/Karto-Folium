"""Authentication blueprint: login, logout, and access control helpers."""

from __future__ import annotations

from datetime import datetime
from functools import wraps
from typing import Callable

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import generate_password_hash

from app.utils.auth import USER_FILE as AUTH_USER_FILE
from app.utils.auth import login_required, verify_user
from app.utils.utils_json import load_json_file, save_json_file

auth_bp = Blueprint("auth", __name__, template_folder="templates")
USER_FILE_PATH = AUTH_USER_FILE


@auth_bp.route("/", methods=["GET", "POST"])
def login():
    """Handle user authentication and session creation."""
    if request.method == "POST":
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()

        if not login_value or not password:
            current_app.logger.info("Login rejected: missing credentials")
            return render_template("login.html", error="Veuillez remplir tous les champs.")

        user = verify_user(login_value, password)
        if user:
            session["user"] = {
                "login": user["Login"],
                "access_level": user.get("Niveau acces", 0),
                "nom": user.get("Nom", ""),
                "prenom": user.get("Prenom", ""),
                "connecte_le": datetime.now().isoformat(),
                "uuid": user.get("id", ""),
                "autorise_notif": user.get("Notification", False),
            }
            flash("Connexion reussie !", "success")
            current_app.logger.info("User %s logged in", login_value)
            return redirect(url_for("main.home"))

        current_app.logger.info("Login rejected: invalid credentials for %s", login_value)
        return render_template("login.html", error="Identifiants invalides.")

    return render_template("login.html", error=None)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Clear the session and redirect to the login page."""
    session.pop("user", None)
    flash("Vous avez ete deconnecte.", "info")
    return redirect(url_for("auth.login"))


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
                    users = load_json_file(USER_FILE_PATH)
                except FileNotFoundError:
                    current_app.logger.error("User file missing: %s", USER_FILE_PATH)
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
                        save_json_file(USER_FILE_PATH, users)
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
