import json

from app.blueprints.carto_modif import type_sites


def _setup_type_files(tmp_path, monkeypatch):
    type_file = tmp_path / "types.json"
    data_file = tmp_path / "data.json"
    type_file.write_text(json.dumps([]), encoding="utf-8")
    data_file.write_text(json.dumps([]), encoding="utf-8")
    monkeypatch.setattr(type_sites, "TYPE_FILE", str(type_file))
    monkeypatch.setattr(type_sites, "DATA_FILE", str(data_file))


def test_type_sites_list_requires_level_four(client, monkeypatch, tmp_path):
    _setup_type_files(tmp_path, monkeypatch)
    with client.session_transaction() as session:
        session["user"] = {"login": "low", "uuid": "u-low", "access_level": 3}

    response = client.get("/type-sites/")

    assert response.status_code == 200
    assert b"Niveau requis" in response.data


def test_type_sites_list_allows_level_four(client, monkeypatch, tmp_path):
    _setup_type_files(tmp_path, monkeypatch)
    with client.session_transaction() as session:
        session["user"] = {
            "login": "high",
            "uuid": "u-high",
            "access_level": 4,
            "prenom": "Hi",
            "nom": "Level",
        }

    response = client.get("/type-sites/")

    assert response.status_code == 200
    assert b"Niveau requis" not in response.data


def test_main_page_hides_type_editor_for_low_level(client):
    with client.session_transaction() as session:
        session["user"] = {
            "login": "low",
            "uuid": "u-low",
            "access_level": 2,
            "prenom": "Low",
            "nom": "User",
        }

    response = client.get("/")

    assert response.status_code == 200
    assert b"Editeur de type ouvrages" not in response.data
    assert b"Liste les types de sites" not in response.data


def test_main_page_shows_type_editor_for_level_four(client):
    with client.session_transaction() as session:
        session["user"] = {
            "login": "high",
            "uuid": "u-high",
            "access_level": 4,
            "prenom": "High",
            "nom": "User",
        }

    response = client.get("/")

    assert response.status_code == 200
    assert b"Editeur de type ouvrages" in response.data
    assert b"Liste les types de sites" in response.data
