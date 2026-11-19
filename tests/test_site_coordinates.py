import json

import pytest
from flask import template_rendered

from app.blueprints.carto_modif import edit_map, edit_sites


@pytest.fixture()
def site_form(app, monkeypatch, tmp_path):
    record = {
        "INDEX": "1", "COMMUNE": "Alpha", "NOM": "Site A", "TYPE": "STEP",
        "LAT": "45.0", "LONG": "1.0", "ETAT": "ES", "TECHNOLOGIE": "Initiale",
    }
    data_file = tmp_path / "sites.json"
    for attribute, filename, payload in (
        ("DATA_FILE", "sites.json", [record]),
        ("TYPE_FILE", "types.json", ["STEP"]),
        ("COMMUNES_FILE", "communes.json", ["Alpha"]),
    ):
        path = tmp_path / filename
        path.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(edit_sites, attribute, str(path))
    contexts = []

    def capture(sender, template, context, **extra):
        contexts.append(context)

    with template_rendered.connected_to(capture, app):
        yield data_file, record, contexts


@pytest.mark.parametrize("route", ["/edit-sites/add", "/edit-sites/edit/0"])
@pytest.mark.parametrize("field,value", [
    ("LAT", ""), ("LAT", "invalide"), ("LAT", "NaN"), ("LAT", "inf"),
    ("LAT", "-inf"), ("LAT", "1e309"), ("LAT", "90.01"), ("LAT", "-90.01"),
    ("LONG", ""), ("LONG", "texte"), ("LONG", "NaN"), ("LONG", "Infinity"),
    ("LONG", "180.01"), ("LONG", "-180.01"),
])
def test_invalid_coordinates_keep_form_and_do_not_write(client, site_form, route, field, value):
    data_file, record, contexts = site_form
    original_bytes = data_file.read_bytes()
    submitted = {**record, "NOM": "Nom conservé", "TECHNOLOGIE": "Saisie conservée", field: value}

    response = client.post(route, data=submitted)

    assert response.status_code == 200
    assert data_file.read_bytes() == original_bytes
    assert f"{field} doit être un nombre compris" in response.get_data(as_text=True)
    context = contexts[-1]
    assert context["record"][field] == value
    assert context["record"]["NOM"] == "Nom conservé"
    assert context["record"]["TECHNOLOGIE"] == "Saisie conservée"
    assert (context["lat0"], context["lon0"]) == (46.5, 2.5)


@pytest.mark.parametrize("route", ["/edit-sites/add", "/edit-sites/edit/0"])
@pytest.mark.parametrize("latitude,longitude", [("0", "0"), ("90", "180"), ("-90", "-180"), ("45.25", "-1.5")])
def test_valid_coordinates_are_saved(client, site_form, route, latitude, longitude):
    data_file, record, _ = site_form
    response = client.post(route, data={**record, "LAT": latitude, "LONG": longitude})

    assert response.status_code == 302
    saved = json.loads(data_file.read_text(encoding="utf-8"))[-1]
    assert float(saved["LAT"]) == float(latitude)
    assert float(saved["LONG"]) == float(longitude)


@pytest.mark.parametrize("latitude,longitude", [("texte", "1"), ("NaN", "1"), ("45", "181"), (None, "")])
def test_legacy_invalid_coordinates_can_be_opened(client, site_form, latitude, longitude):
    data_file, record, contexts = site_form
    record.update(LAT=latitude, LONG=longitude)
    data_file.write_text(json.dumps([record]), encoding="utf-8")
    original_bytes = data_file.read_bytes()

    response = client.get("/edit-sites/edit/0")

    assert response.status_code == 200
    assert (contexts[-1]["lat0"], contexts[-1]["lon0"]) == (46.5, 2.5)
    assert data_file.read_bytes() == original_bytes


def test_other_validation_errors_keep_submitted_fields(client, site_form):
    data_file, record, contexts = site_form
    response = client.post("/edit-sites/add", data={**record, "NOM": "", "TECHNOLOGIE": "À conserver"})

    assert response.status_code == 200
    assert contexts[-1]["record"]["TECHNOLOGIE"] == "À conserver"
    assert (contexts[-1]["lat0"], contexts[-1]["lon0"]) == (45.0, 1.0)
    assert len(json.loads(data_file.read_text(encoding="utf-8"))) == 1


@pytest.mark.parametrize("query,expected", [
    ("lat=NaN&lon=1", [46.5, 2.5]),
    ("lat=45&lon=inf", [46.5, 2.5]),
    ("lat=91&lon=1", [46.5, 2.5]),
    ("lat=45&lon=-181", [46.5, 2.5]),
    ("lat=texte&lon=1", [46.5, 2.5]),
    ("", [46.5, 2.5]),
    ("lat=0&lon=0", [0.0, 0.0]),
    ("lat=-90&lon=180", [-90.0, 180.0]),
])
def test_map_uses_safe_coordinates(app, client, monkeypatch, query, expected):
    with client.session_transaction() as session:
        session["user"] = {"login": "tester", "uuid": "u1", "access_level": 5}
    locations = []
    original_map = edit_map.folium.Map

    def capture_map(*args, **kwargs):
        locations.append(kwargs["location"])
        return original_map(*args, **kwargs)

    monkeypatch.setattr(edit_map.folium, "Map", capture_map)
    response = client.get("/edit-map/map?" + query)

    assert response.status_code == 200
    assert locations == [expected]
