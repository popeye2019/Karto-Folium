import json
import app as app_pkg

from app.blueprints.gestion_user import users as users_bp_module
from app.blueprints.rights import niveau_user as rights_bp_module


def _setup_user_file(tmp_path, monkeypatch):
    user_file = tmp_path / "users.json"
    user_file.write_text(json.dumps([]), encoding="utf-8")
    monkeypatch.setattr(users_bp_module, "USER_FILE", str(user_file))
    monkeypatch.setattr(users_bp_module, "SAVE_USERS_FILE", str(user_file))


def _setup_rights_file(tmp_path, monkeypatch):
    rights_file = tmp_path / "droits.json"
    rights_file.write_text(json.dumps([]), encoding="utf-8")
    monkeypatch.setattr(rights_bp_module, "DATA_FILE", str(rights_file))


def test_users_list_requires_level_five(client, tmp_path, monkeypatch):
    _setup_user_file(tmp_path, monkeypatch)
    with client.session_transaction() as session:
        session["user"] = {"login": "low", "uuid": "u-low", "access_level": 4}

    response = client.get("/users/")

    assert response.status_code == 200
    assert b"Niveau requis" in response.data


def test_users_list_allows_level_five(client, tmp_path, monkeypatch):
    _setup_user_file(tmp_path, monkeypatch)
    with client.session_transaction() as session:
        session["user"] = {"login": "admin", "uuid": "u-admin", "access_level": 5}

    response = client.get("/users/")

    assert response.status_code == 200
    assert b"Niveau requis" not in response.data


def test_main_page_hides_user_editor_for_low_level(client):
    with client.session_transaction() as session:
        session["user"] = {"login": "low", "uuid": "u-low", "access_level": 2}

    response = client.get("/")

    assert response.status_code == 200
    assert b"Editeur utilisateurs" not in response.data
    assert b"Liste des utilisateurs" not in response.data


def test_main_page_shows_user_editor_for_level_five(client):
    with client.session_transaction() as session:
        session["user"] = {"login": "admin", "uuid": "u-admin", "access_level": 5}

    response = client.get("/")

    assert response.status_code == 200
    assert b"Editeur utilisateurs" in response.data
    assert b"Liste des utilisateurs" in response.data


def test_rights_list_requires_level_five(client, tmp_path, monkeypatch):
    _setup_rights_file(tmp_path, monkeypatch)
    with client.session_transaction() as session:
        session["user"] = {"login": "low", "uuid": "u-low", "access_level": 4}

    response = client.get("/rights/")

    assert response.status_code == 200
    assert b"Niveau requis" in response.data


def test_rights_list_allows_level_five(client, tmp_path, monkeypatch):
    _setup_rights_file(tmp_path, monkeypatch)
    with client.session_transaction() as session:
        session["user"] = {"login": "admin", "uuid": "u-admin", "access_level": 5}

    response = client.get("/rights/")

    assert response.status_code == 200
    assert b"Niveau requis" not in response.data


def test_main_page_hides_rights_editor_for_low_level(client):
    with client.session_transaction() as session:
        session["user"] = {"login": "low", "uuid": "u-low", "access_level": 2}

    response = client.get("/")

    assert response.status_code == 200
    assert b"Editeur des droits" not in response.data
    assert b"Liste des droits des utilisateurs" not in response.data


def test_main_page_shows_rights_editor_for_level_five(client):
    with client.session_transaction() as session:
        session["user"] = {"login": "admin", "uuid": "u-admin", "access_level": 5}

    response = client.get("/")

    assert response.status_code == 200
    assert b"Editeur des droits" in response.data
    assert b"Liste des droits des utilisateurs" in response.data


def test_main_page_shows_rights_definition(monkeypatch, client):
    def fake_load_json_file(path):
        if "droits.json" in str(path):
            return [
                {"Niveau": 3, "Definition": "Maintenance"},
            ]
        return []

    monkeypatch.setattr(app_pkg, "load_json_file", fake_load_json_file, raising=False)

    with client.session_transaction() as session:
        session["user"] = {
            "login": "maint",
            "uuid": "u-maint",
            "access_level": 3,
            "prenom": "Tech",
            "nom": "User",
        }

    response = client.get("/")

    assert response.status_code == 200
    assert b"Maintenance" in response.data
