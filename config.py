import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _env_tuple(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    return values or default


class Config:
    """
    Config simple et robuste :
    - Pas de secrets en dur : variables d'environnement
    - DEBUG pilote par FLASK_DEBUG (0/1)
    """

    APP_NAME = "Karto-Folium"
    APP_VERSION = "V0.4.0"

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-not-safe")
    DEBUG = _env_bool("FLASK_DEBUG", False)
    APP_MODE = os.getenv("APP_MODE", "INCONNU")
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)

    URL_OUVRAGE = os.getenv("URL_OUVRAGE", "/static/ouvrages/")
    SITE_ETATS = _env_tuple("SITE_ETATS", ("ES", "HS"))

    NOTIFICATION_STORE = os.getenv("NOTIFICATION_STORE", "./app/data/notif/notifications.json")
    USERS_FILE = os.getenv("USERS_FILE", "./app/data/users/users.json")
    RIGHTS_FILE = os.getenv("RIGHTS_FILE", "./app/data/users/droits.json")
    LOGIN_JOURNAL_FILE = os.getenv("LOGIN_JOURNAL_FILE", "./app/data/users/login_journal.json")
    LOGIN_BAN_FILE = os.getenv("LOGIN_BAN_FILE", "./app/data/users/login_bans.json")
    LOGIN_JOURNAL_MAX_ENTRIES = _env_int("LOGIN_JOURNAL_MAX_ENTRIES", 2000)

    LOGIN_BAN_ENABLED = _env_bool("LOGIN_BAN_ENABLED", True)
    LOGIN_BAN_INCLUDE_LOCAL = _env_bool("LOGIN_BAN_INCLUDE_LOCAL", False)
    LOGIN_BAN_MAX_FAILURES = _env_int("LOGIN_BAN_MAX_FAILURES", 5)
    LOGIN_BAN_WINDOW_SECONDS = _env_int("LOGIN_BAN_WINDOW_SECONDS", 600)
    LOGIN_BAN_DURATION_SECONDS = _env_int("LOGIN_BAN_DURATION_SECONDS", 600)
