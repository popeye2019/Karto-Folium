import json

from app.blueprints.notif import notif as notif_bp
import app.blueprints.pr_maint as pr_maint_bp
from app.blueprints.Contrat import contrats as contrats_bp


def _setup_notifications(tmp_path, monkeypatch):
    notif_file = tmp_path / "notifications.json"
    notif_file.write_text("[]", encoding="utf-8")
    users_file = tmp_path / "users.json"
    users_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(notif_bp, "NOTIFICATION_FILE", str(notif_file))
    monkeypatch.setattr(notif_bp, "USER_FILE", str(users_file))
    return notif_file


def _setup_maintenance(tmp_path, monkeypatch):
    recap_file = tmp_path / "recap.json"
    recap_file.write_text("[]", encoding="utf-8")
    comment_file = tmp_path / "commentaire.json"
    comment_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(pr_maint_bp, "RECUP_FILE", recap_file)
    monkeypatch.setattr(pr_maint_bp, "COMMENT_FILE", comment_file)


def test_notifications_require_level_three(client, tmp_path, monkeypatch):
    _setup_notifications(tmp_path, monkeypatch)
    with client.session_transaction() as session:
        session["user"] = {"login": "u2", "uuid": "u2", "access_level": 2}

    response = client.get("/notif/view")

    assert response.status_code == 200
    assert b"Niveau requis" in response.data


def test_notifications_allow_level_three(client, tmp_path, monkeypatch):
    notif_file = _setup_notifications(tmp_path, monkeypatch)
    notif_file.write_text(
        json.dumps(
            [
                {
                    "id": "1",
                    "recipient_id": "u3",
                    "sender_id": "u1",
                    "message": "Bonjour",
                    "url": "",
                    "is_read": False,
                    "created_at": "2024-01-01T00:00:00",
                }
            ]
        ),
        encoding="utf-8",
    )

    with client.session_transaction() as session:
        session["user"] = {"login": "u3", "uuid": "u3", "access_level": 3}

    response = client.get("/notif/view")

    assert response.status_code == 200
    assert b"Vos notifications" in response.data


def test_maintenance_requires_level_three(client, tmp_path, monkeypatch):
    _setup_maintenance(tmp_path, monkeypatch)
    with client.session_transaction() as session:
        session["user"] = {"login": "u2", "uuid": "u2", "access_level": 2}

    response = client.get("/maintenance/")

    assert response.status_code == 200
    assert b"Niveau requis" in response.data


def test_maintenance_allows_level_three(client, tmp_path, monkeypatch):
    _setup_maintenance(tmp_path, monkeypatch)
    with client.session_transaction() as session:
        session["user"] = {"login": "u3", "uuid": "u3", "access_level": 3}

    response = client.get("/maintenance/")

    assert response.status_code == 200
    assert b"Espace maintenance" in response.data


def test_contrats_require_level_three(client, monkeypatch):
    def fake_load_json_file(_):
        return {"features": [{"properties": {"libgeo": "X", "reg": 1}}]}

    monkeypatch.setattr(contrats_bp, "load_json_file", fake_load_json_file)

    with client.session_transaction() as session:
        session["user"] = {"login": "low", "uuid": "u-low", "access_level": 1}

    response = client.get("/contrats/liste")

    assert response.status_code == 200
    assert b"Niveau requis" in response.data


def test_contrats_allow_level_three(client, monkeypatch):
    def fake_load_json_file(_):
        return {"features": [{"properties": {"libgeo": "X", "reg": 1}}]}

    monkeypatch.setattr(contrats_bp, "load_json_file", fake_load_json_file)

    with client.session_transaction() as session:
        session["user"] = {"login": "maint", "uuid": "u3", "access_level": 3}

    response = client.get("/contrats/liste")

    assert response.status_code == 200
    assert b"regions" in response.data.lower()
