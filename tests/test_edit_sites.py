import json

from app.blueprints.carto_modif import edit_sites


def _write_sites(tmp_path, sites):
    path = tmp_path / "sites.json"
    path.write_text(json.dumps(sites), encoding="utf-8")
    return path


def test_add_record_defaults_state_when_missing(app, client, monkeypatch, tmp_path):
    sites = [
        {
            "INDEX": "1",
            "COMMUNE": "Alpha",
            "NOM": "Site A",
            "TYPE": "STEP",
            "LAT": "45.0",
            "LONG": "1.0",
            "ETAT": "ES",
        }
    ]
    data_file = _write_sites(tmp_path, sites)
    monkeypatch.setattr(edit_sites, "DATA_FILE", str(data_file))
    type_file = tmp_path / "types.json"
    type_file.write_text(json.dumps(["STEP"]), encoding="utf-8")
    monkeypatch.setattr(edit_sites, "TYPE_FILE", str(type_file))
    app.config["SITE_ETATS"] = ("ES", "HS")

    response = client.post(
        "/edit-sites/add",
        data={
            "COMMUNE": "Alpha",
            "NOM": "Nouveau",
            "TYPE": "STEP",
            "LAT": "45.2",
            "LONG": "1.2",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    saved = json.loads(data_file.read_text(encoding="utf-8"))
    new_record = next(item for item in saved if item["NOM"] == "Nouveau")
    assert new_record["ETAT"] == "ES"


def test_add_record_rejects_invalid_state(app, client, monkeypatch, tmp_path):
    sites = [
        {
            "INDEX": "1",
            "COMMUNE": "Alpha",
            "NOM": "Site A",
            "TYPE": "STEP",
            "LAT": "45.0",
            "LONG": "1.0",
            "ETAT": "ES",
        }
    ]
    data_file = _write_sites(tmp_path, sites)
    monkeypatch.setattr(edit_sites, "DATA_FILE", str(data_file))
    type_file = tmp_path / "types.json"
    type_file.write_text(json.dumps(["STEP"]), encoding="utf-8")
    monkeypatch.setattr(edit_sites, "TYPE_FILE", str(type_file))
    app.config["SITE_ETATS"] = ("ES", "HS")

    response = client.post(
        "/edit-sites/add",
        data={
            "COMMUNE": "Alpha",
            "NOM": "Invalide",
            "TYPE": "STEP",
            "LAT": "45.2",
            "LONG": "1.2",
            "ETAT": "KO",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    saved = json.loads(data_file.read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["NOM"] == "Site A"


def test_edit_record_normalizes_state(app, client, monkeypatch, tmp_path):
    sites = [
        {
            "INDEX": "1",
            "COMMUNE": "Alpha",
            "NOM": "Site A",
            "TYPE": "STEP",
            "LAT": "45.0",
            "LONG": "1.0",
            "ETAT": "ES",
        }
    ]
    data_file = _write_sites(tmp_path, sites)
    monkeypatch.setattr(edit_sites, "DATA_FILE", str(data_file))
    type_file = tmp_path / "types.json"
    type_file.write_text(json.dumps(["STEP"]), encoding="utf-8")
    monkeypatch.setattr(edit_sites, "TYPE_FILE", str(type_file))
    app.config["SITE_ETATS"] = ("ES", "HS")

    response = client.post(
        "/edit-sites/edit/0",
        data={"ETAT": "hs"},
        follow_redirects=False,
    )

    assert response.status_code == 302

    saved = json.loads(data_file.read_text(encoding="utf-8"))
    assert saved[0]["ETAT"] == "HS"


def test_add_record_requires_level_four(client):
    with client.session_transaction() as session:
        session["user"] = {"login": "low", "uuid": "u2", "access_level": 3}

    response = client.get("/edit-sites/add")

    assert response.status_code == 200
    assert b"Niveau requis" in response.data


def test_edit_record_requires_level_four(client):
    with client.session_transaction() as session:
        session["user"] = {"login": "low", "uuid": "u2", "access_level": 2}

    response = client.get("/edit-sites/edit/0")

    assert response.status_code == 200
    assert b"Niveau requis" in response.data
