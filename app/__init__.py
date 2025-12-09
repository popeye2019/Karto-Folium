"""Core application factory and shared setup utilities."""

from __future__ import annotations

import os
from datetime import datetime

from flask import Flask, session

NOTIFICATION_STORE = "./app/data/notif/notifications.json"
DEFAULT_SITE_ETATS = ("ES", "HS")
DEFAULT_URL_OUVRAGE = "/static/ouvrages/"
SUFFIXE_APP_VERSION = "V1.0.0"

def create_app(config_object: str | object = "config.Config") -> Flask:
    """Create, configure, and return the Flask application instance."""
    app = Flask(__name__)
    app.config.from_object(config_object)

    app.config.setdefault(
        "APP_VERSION",
        f"{os.getenv('APP_VERSION', 'Karto-Folium-dev')} {SUFFIXE_APP_VERSION}",
    )
    app.config.setdefault("NOTIFICATION_STORE", NOTIFICATION_STORE)
    app.config["SITE_ETATS"] = _load_site_states()
    app.config.setdefault("URL_OUVRAGE", os.getenv("URL_OUVRAGE", DEFAULT_URL_OUVRAGE))

    _register_blueprints(app)
    _register_context_processors(app)
    _register_filters(app)

    return app


def _load_site_states() -> tuple[str, ...]:
    """Read SITE_ETATS from env (comma-separated) with a safe fallback."""
    raw = os.getenv("SITE_ETATS")
    if not raw:
        return DEFAULT_SITE_ETATS

    states = tuple(value.strip() for value in raw.split(",") if value.strip())
    return states or DEFAULT_SITE_ETATS


def _register_blueprints(app: Flask) -> None:
    """Import and register the application's blueprints."""
    from .blueprints.auth.auth import auth_bp
    from .blueprints.carto.main import main_bp as carto_main_bp
    from .blueprints.carto_modif.edit_map import edit_map_bp
    from .blueprints.carto_modif.edit_sites import edit_sites_bp
    from .blueprints.carto_modif.type_sites import type_sites_bp
    from .blueprints.pr_maint import pr_maint_bp
    from .blueprints.champs.champs import champs_bp
    from .blueprints.Contrat.contrats import contrats_bp
    from .blueprints.Contrat.regions import region_bp
    from .blueprints.gestion_user.users import users_bp
    from .blueprints.notif.notif import notif_bp
    from .blueprints.rights.niveau_user import rights_bp

    app.register_blueprint(carto_main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(edit_sites_bp, url_prefix="/edit-sites")
    app.register_blueprint(type_sites_bp, url_prefix="/type-sites")
    app.register_blueprint(edit_map_bp, url_prefix="/edit-map")
    app.register_blueprint(pr_maint_bp, url_prefix="/maintenance")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(rights_bp, url_prefix="/rights")
    app.register_blueprint(champs_bp, url_prefix="/champs")
    app.register_blueprint(notif_bp, url_prefix="/notif")
    app.register_blueprint(contrats_bp, url_prefix="/contrats")
    app.register_blueprint(region_bp, url_prefix="/regions")


def _register_context_processors(app: Flask) -> None:
    """Expose global template variables."""
    from .utils.utils_json import load_json_file

    @app.context_processor
    def inject_template_globals() -> dict[str, object]:
        """Make session user, notification count, and app version available."""
        user = session.get("user")
        notif_count = 0
        access_definition: str | None = None

        if user:
            user_uuid = user.get("uuid")
            if user_uuid:
                store_path = app.config.get("NOTIFICATION_STORE", NOTIFICATION_STORE)
                try:
                    notifications = load_json_file(store_path) or []
                except FileNotFoundError:
                    app.logger.debug("Notification store missing: %s", store_path)
                    notifications = []
                except Exception as exc:  # pragma: no cover - defensive logging
                    app.logger.warning("Unable to read notifications: %s", exc)
                    notifications = []

                notif_count = sum(
                    1
                    for notif in notifications
                    if str(notif.get("recipient_id")) == str(user_uuid)
                    and not notif.get("is_read")
                )
            # Resolve the textual definition for the user's access level, if available.
            try:
                rights = load_json_file("./app/data/users/droits.json")
            except FileNotFoundError:
                rights = []
            except Exception:  # pragma: no cover - defensive
                rights = []
            user_level = user.get("access_level")
            if isinstance(rights, list) and user_level is not None:
                try:
                    level_int = int(user_level)
                except (TypeError, ValueError):
                    level_int = None
                if level_int is not None:
                    for item in rights:
                        if (
                            isinstance(item, dict)
                            and int(item.get("Niveau", -1)) == level_int
                        ):
                            access_definition = item.get("Definition")
                            break

        return {
            "user": user,
            "notif_count": notif_count,
            "app_version": app.config.get("APP_VERSION"),
            "user_access_definition": access_definition,
        }


def _register_filters(app: Flask) -> None:
    """Register custom Jinja filters used across the application."""
    from babel.dates import format_datetime

    def format_notification_date(value: object) -> str:
        if not value:
            return ""

        dt: datetime | None
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value)
        elif isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", ""))
            except ValueError:
                dt = None
        else:
            dt = None

        if not dt:
            return str(value)

        return format_datetime(dt, "d MMMM yyyy", locale="fr_FR")

    app.jinja_env.filters["format_notification_date"] = format_notification_date

