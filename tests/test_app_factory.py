import json
from pathlib import Path

from flask import session


def test_main_blueprint_registered(app):
    assert "main.home" in app.view_functions
    assert "auth.login" in app.view_functions


def test_template_context_counts_user_notifications(app):
    notif_store = Path(app.config["NOTIFICATION_STORE"])
    notifications = [
        {"recipient_id": "123", "is_read": False},
        {"recipient_id": "456", "is_read": False},
        {"recipient_id": "123", "is_read": True},
    ]
    notif_store.write_text(json.dumps(notifications), encoding="utf-8")

    with app.test_request_context("/"):
        session["user"] = {"uuid": "123", "login": "alice"}
        context: dict[str, object] = {}
        app.update_template_context(context)

    assert context["notif_count"] == 1
    assert context["user"]["login"] == "alice"
    assert context["app_version"] == app.config.get("APP_VERSION")
