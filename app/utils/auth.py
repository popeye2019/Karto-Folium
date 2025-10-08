"""Authentication utilities: password checks and access control decorators."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import current_app, flash, redirect, render_template, session, url_for
from werkzeug.security import check_password_hash

from app.utils.utils_json import load_json_file as load_users

USER_FILE = "./app/data/users/users.json"


def verify_user(login_value: str, password: str) -> dict[str, Any] | None:
    """Return the matching user when credentials are valid, otherwise None."""
    users = load_users(USER_FILE)
    user = next((usr for usr in users if usr["Login"] == login_value), None)

    if user is None:
        current_app.logger.info("User %s not found", login_value)
        return None

    current_app.logger.info("Verifying password for user %s", login_value)
    if check_password_hash(user["Mot de passe"], password):
        current_app.logger.info("User %s authenticated", login_value)
        return user

    current_app.logger.info("User %s provided an invalid password", login_value)
    return None


def login_required(func: Callable) -> Callable:
    """Ensure the route is accessible only to authenticated users."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        user = session.get("user")
        if not user:
            flash("Veuillez vous connecter pour acceder a cette page.", "warning")
            return redirect(url_for("auth.login"))
        return func(*args, **kwargs)

    return wrapper


def require_level(required_level: int) -> Callable:
    """Allow access only when the session user has the expected level."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            if not user:
                return render_template(
                    "not_authorized.html",
                    message="Utilisateur non authentifie",
                    required_level=required_level,
                    user_level=None,
                )

            user_level = user.get("access_level", 0)
            if user_level < required_level:
                return render_template(
                    "not_authorized.html",
                    message="Vous n'avez pas les droits suffisants pour acceder a cette page.",
                    required_level=required_level,
                    user_level=user_level,
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def route_with_level(blueprint, route: str, level: int) -> Callable:
    """Attach a route to the blueprint and guard it with an access level."""

    def decorator(func: Callable) -> Callable:
        @blueprint.route(route)
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            if not user:
                return render_template(
                    "not_authorized.html",
                    message="Utilisateur non authentifie",
                    required_level=level,
                    user_level=None,
                )

            user_level = user.get("access_level", 0)
            if user_level < level:
                return render_template(
                    "not_authorized.html",
                    message="Vous n'avez pas les droits suffisants pour acceder a cette page.",
                    required_level=level,
                    user_level=user_level,
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_same_user_or_level(required_level: int) -> Callable:
    """Allow access to the same user or anyone meeting the required level."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            if not user:
                return render_template(
                    "not_authorized.html",
                    message="Utilisateur non authentifie",
                    required_level=required_level,
                    user_level=None,
                )

            user_level = user.get("access_level", 0)
            login_param = kwargs.get("login")

            if user["login"] == login_param or user_level >= required_level:
                return func(*args, **kwargs)

            return render_template(
                "not_authorized.html",
                message=(
                    "Acces refuse : vous ne pouvez modifier que votre propre compte ou devez avoir un niveau suffisant."
                ),
                required_level=required_level,
                user_level=user_level,
            )

        return wrapper

    return decorator
