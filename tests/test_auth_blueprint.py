import json
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash


def test_login_success_sets_session_and_redirects(client, monkeypatch):
    def fake_verify_user(login_value, password):
        return {
            "Login": login_value,
            "Niveau acces": 2,
            "Nom": "Test",
            "Prenom": "User",
            "id": "uuid",
            "Notification": True,
        }

    monkeypatch.setattr("app.blueprints.auth.auth.verify_user", fake_verify_user)

    response = client.post(
        "/auth/",
        data={"login": "alice", "password": "secret"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    with client.session_transaction() as session:
        assert session["user"]["login"] == "alice"
        assert session["user"]["access_level"] == 2
        # ISO format timestamp set
        assert datetime.fromisoformat(session["user"]["connecte_le"])  # will raise if invalid


def test_login_invalid_credentials_returns_error(client, monkeypatch):
    monkeypatch.setattr("app.blueprints.auth.auth.verify_user", lambda *_: None)

    response = client.post(
        "/auth/",
        data={"login": "alice", "password": "wrong"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert b"Identifiants invalides." in response.data


def test_login_missing_fields_shows_error(client):
    response = client.post(
        "/auth/",
        data={"login": "", "password": ""},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert b"Veuillez remplir tous les champs." in response.data


def test_logout_clears_session(client):
    with client.session_transaction() as session:
        session["user"] = {"login": "alice"}

    response = client.get("/auth/logout", follow_redirects=False)

    assert response.status_code == 302
    assert "/auth/" in response.headers["Location"]
    with client.session_transaction() as session:
        assert "user" not in session


def test_change_password_requires_login(client):
    response = client.get("/auth/change-password")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/")


def test_change_password_mismatch_shows_error(client):
    with client.session_transaction() as session:
        session["user"] = {
            "login": "alice",
            "prenom": "Alice",
            "nom": "Durand",
            "access_level": 2,
        }

    response = client.post(
        "/auth/change-password",
        data={
            "current_password": "old",
            "new_password": "secret1",
            "confirm_password": "secret2",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Les nouveaux mots de passe ne correspondent pas." in response.data


def test_change_password_updates_file(client, monkeypatch, tmp_path):
    hashed_password = generate_password_hash("oldpass")
    users = [
        {
            "Nom": "Doe",
            "Prenom": "Jane",
            "Login": "jane",
            "Mot de passe": hashed_password,
            "Niveau acces": 2,
            "Notification": True,
            "id": "abc-123",
        }
    ]

    user_file = tmp_path / "users.json"
    user_file.write_text(json.dumps(users), encoding="utf-8")

    monkeypatch.setattr("app.utils.auth.USER_FILE", str(user_file))
    monkeypatch.setattr("app.blueprints.auth.auth.USER_FILE_PATH", str(user_file))

    with client.session_transaction() as session_tx:
        session_tx["user"] = {
            "login": "jane",
            "prenom": "Jane",
            "nom": "Doe",
            "access_level": 2,
        }

    response = client.post(
        "/auth/change-password",
        data={
            "current_password": "oldpass",
            "new_password": "newpass",
            "confirm_password": "newpass",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    updated_users = json.loads(user_file.read_text(encoding="utf-8"))
    assert check_password_hash(updated_users[0]["Mot de passe"], "newpass")


def test_change_password_rejects_bad_current_password(client, monkeypatch, tmp_path):
    hashed_password = generate_password_hash("oldpass")
    users = [
        {
            "Nom": "Doe",
            "Prenom": "Jane",
            "Login": "jane",
            "Mot de passe": hashed_password,
            "Niveau acces": 2,
            "Notification": True,
            "id": "abc-123",
        }
    ]

    user_file = tmp_path / "users.json"
    user_file.write_text(json.dumps(users), encoding="utf-8")

    monkeypatch.setattr("app.utils.auth.USER_FILE", str(user_file))
    monkeypatch.setattr("app.blueprints.auth.auth.USER_FILE_PATH", str(user_file))

    with client.session_transaction() as session_tx:
        session_tx["user"] = {
            "login": "jane",
            "prenom": "Jane",
            "nom": "Doe",
            "access_level": 2,
        }

    response = client.post(
        "/auth/change-password",
        data={
            "current_password": "wrong",
            "new_password": "newpass",
            "confirm_password": "newpass",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Mot de passe actuel incorrect." in response.data

    updated_users = json.loads(user_file.read_text(encoding="utf-8"))
    assert updated_users[0]["Mot de passe"] == hashed_password
