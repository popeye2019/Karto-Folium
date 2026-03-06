import json

from werkzeug.security import check_password_hash, generate_password_hash

from app.blueprints.gestion_user import users as users_bp_module


def _setup_user_file(tmp_path, monkeypatch):
    user_file = tmp_path / "users.json"
    original_hash = generate_password_hash("oldpass")
    payload = [
        {
            "Nom": "Doe",
            "Prenom": "Alice",
            "Login": "alice",
            "Mot de passe": original_hash,
            "Niveau acces": 2,
            "Notification": False,
            "Email": "alice@example.org",
            "Date_connec": None,
            "Contrat": [],
            "id": "u-alice",
        }
    ]
    user_file.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(users_bp_module, "USER_FILE", str(user_file))
    monkeypatch.setattr(users_bp_module, "SAVE_USERS_FILE", str(user_file))
    return user_file, original_hash


def _setup_rights_file(tmp_path, monkeypatch):
    rights_file = tmp_path / "droits.json"
    rights_file.write_text(
        json.dumps(
            [
                {"Niveau": 1, "Definition": "Utilisateur"},
                {"Niveau": 2, "Definition": "Exploitation"},
                {"Niveau": 3, "Definition": "Maintenance"},
                {"Niveau": 4, "Definition": "Gestion"},
                {"Niveau": 5, "Definition": "Admin"},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(users_bp_module, "RIGHTS_FILE", str(rights_file))


def test_edit_user_allows_password_reset_for_level_five(client, tmp_path, monkeypatch):
    user_file, old_hash = _setup_user_file(tmp_path, monkeypatch)
    _setup_rights_file(tmp_path, monkeypatch)
    with client.session_transaction() as session:
        session["user"] = {"login": "admin", "uuid": "u-admin", "access_level": 5}

    response = client.post(
        "/users/edit/alice",
        data={
            "nom": "Doe",
            "prenom": "Alice",
            "email": "alice@example.org",
            "niveau_acces": "2",
            "notification": "on",
            "new_password": "newpass123",
            "confirm_password": "newpass123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    payload = json.loads(user_file.read_text(encoding="utf-8"))
    assert payload[0]["Mot de passe"] != old_hash
    assert check_password_hash(payload[0]["Mot de passe"], "newpass123")


def test_edit_user_rejects_password_reset_when_confirmation_differs(client, tmp_path, monkeypatch):
    user_file, old_hash = _setup_user_file(tmp_path, monkeypatch)
    _setup_rights_file(tmp_path, monkeypatch)
    with client.session_transaction() as session:
        session["user"] = {"login": "admin", "uuid": "u-admin", "access_level": 5}

    response = client.post(
        "/users/edit/alice",
        data={
            "nom": "Doe",
            "prenom": "Alice",
            "email": "alice@example.org",
            "niveau_acces": "2",
            "new_password": "newpass123",
            "confirm_password": "different-pass",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Les nouveaux mots de passe ne correspondent pas." in response.data
    payload = json.loads(user_file.read_text(encoding="utf-8"))
    assert payload[0]["Mot de passe"] == old_hash


def test_edit_user_updates_access_level(client, tmp_path, monkeypatch):
    user_file, _ = _setup_user_file(tmp_path, monkeypatch)
    _setup_rights_file(tmp_path, monkeypatch)
    with client.session_transaction() as session:
        session["user"] = {"login": "admin", "uuid": "u-admin", "access_level": 5}

    response = client.post(
        "/users/edit/alice",
        data={
            "nom": "Doe",
            "prenom": "Alice",
            "email": "alice@example.org",
            "niveau_acces": "4",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    payload = json.loads(user_file.read_text(encoding="utf-8"))
    assert payload[0]["Niveau acces"] == 4


def test_edit_user_rejects_invalid_access_level(client, tmp_path, monkeypatch):
    user_file, _ = _setup_user_file(tmp_path, monkeypatch)
    _setup_rights_file(tmp_path, monkeypatch)
    with client.session_transaction() as session:
        session["user"] = {"login": "admin", "uuid": "u-admin", "access_level": 5}

    response = client.post(
        "/users/edit/alice",
        data={
            "nom": "Doe",
            "prenom": "Alice",
            "email": "alice@example.org",
            "niveau_acces": "42",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'name="niveau_acces"' in response.data
    payload = json.loads(user_file.read_text(encoding="utf-8"))
    assert payload[0]["Niveau acces"] == 2
