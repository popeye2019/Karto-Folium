import io
import json
import sqlite3

import pytest

from app.catalogue import Catalogue, read_import
from app.utils.site_store import load_json_file
from app.utils.utils_geocarto import load_geo_datasets, load_type_metadata
from scripts.catalogue_sqlite import main, migration_bundle


def bundle():
    return {
        "contrats": [{"REFERENCE": "C1", "NOM": "Contrat exemple"}, {"REFERENCE": "C2", "NOM": "Autre contrat"}],
        "communes": [{"COMMUNE": "Alpha", "CODE_INSEE": "01001", "COLLECTIF": True, "LAT_MAIRIE": "45.1", "LONG_MAIRIE": "1.1"}],
        "types_sites": [{"type": "STEP", "icon": "step.png", "enabled": True, "show": False, "scale": 1}],
        "sites": [{"INDEX": "42", "NOM": "Site A", "COMMUNE": "Alpha", "CODE_INSEE": "01001", "TYPE": "STEP", "CONTRAT": "C1", "LAT": "45.2", "LONG": "1.2", "ETAT": "ES", "TECHNOLOGIE": "Filtration", "DOCUMENTATION": "fiche.pdf", "CHAMP_LIBRE": {"valeur": 3}}],
    }


@pytest.fixture()
def store(tmp_path):
    catalogue = Catalogue(tmp_path / "catalogue.sqlite3")
    catalogue.initialize()
    catalogue.import_bundle(bundle())
    return catalogue


@pytest.fixture()
def sql_app(app, store):
    app.config.update(CATALOGUE_STORAGE="sqlite", CATALOGUE_DATABASE=str(store.path))
    return app


def login(client, level=5):
    with client.session_transaction() as session:
        session["user"] = {"login": "test", "uuid": "u1", "access_level": level}


def test_relational_import_preserves_identifiers_fields_and_types(store):
    site = store.sites()[0]
    assert site["INDEX"] == "42"
    assert site["CODE_INSEE"] == "01001"
    assert site["DOCUMENTATION"] == "fiche.pdf"
    assert site["CHAMP_LIBRE"] == {"valeur": 3}
    assert store.types()[0]["show"] is False
    assert store.check() == {"contrats": 2, "communes": 1, "types_sites": 1, "sites": 1, "contrats_communes": 1}


def test_reimport_is_idempotent_and_partial_update_keeps_other_fields(store):
    store.import_bundle(bundle())
    store.import_bundle({"sites": [{"INDEX": "42", "NOM": "Modifié"}]})
    assert store.check()["sites"] == 1
    site = store.sites()[0]
    assert site["NOM"] == "Modifié"
    assert site["CONTRAT"] == "C1"
    assert site["TECHNOLOGIE"] == "Filtration"
    assert site["DOCUMENTATION"] == "fiche.pdf"


def test_site_has_exactly_one_contract_and_can_be_reassigned(store):
    store.import_bundle({"sites": [{"INDEX": "42", "CONTRAT": "C2"}]})
    assert store.sites()[0]["CONTRAT"] == "C2"
    with store.connect() as db:
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE sites SET contrat_id=NULL WHERE id=42")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE sites SET contrat_id=999 WHERE id=42")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM communes")


@pytest.mark.parametrize("change", [{"CONTRAT": "inconnu"}, {"CONTRAT": ["C1", "C2"]}, {"TYPE": "inconnu"}, {"LAT": "NaN"}, {"LONG": "181"}, {"CODE_INSEE": "99999"}])
def test_bad_batch_rolls_back_all_tables_and_audit(store, change):
    original = store.sites()
    with store.connect() as db:
        imports = db.execute("SELECT COUNT(*) FROM imports").fetchone()[0]
    bad = {"contrats": [{"REFERENCE": "NEW"}], "sites": [{"INDEX": "42", "NOM": "Doit être annulé"}, {**bundle()["sites"][0], "INDEX": "43", **change}]}
    with pytest.raises(ValueError):
        store.import_bundle(bad)
    assert store.sites() == original
    assert len(store.contracts()) == 2
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM imports").fetchone()[0] == imports


def test_dry_run_does_not_change_data_or_audit(store):
    summary = store.import_bundle({"sites": [{"INDEX": "42", "NOM": "Essai"}]}, dry_run=True)
    assert summary == {"sites": 1}
    assert store.sites()[0]["NOM"] == "Site A"
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM imports").fetchone()[0] == 1


def test_duplicate_source_indices_cancel_the_batch(store):
    with pytest.raises(ValueError, match="dupliqué"):
        store.import_bundle({"sites": [{"INDEX": "42", "NOM": "A"}, {"INDEX": "042", "NOM": "B"}]})
    assert store.sites()[0]["NOM"] == "Site A"


def test_homonymous_communes_require_insee(store):
    store.import_bundle({"communes": [{"COMMUNE": "Alpha", "CODE_INSEE": "02002"}]})
    row = {**bundle()["sites"][0], "INDEX": "43", "CODE_INSEE": ""}
    with pytest.raises(ValueError, match="ambiguë"):
        store.import_bundle({"sites": [row]})
    store.import_bundle({"sites": [{**row, "CODE_INSEE": "02002"}]})
    assert store.sites()[1]["CODE_INSEE"] == "02002"


def test_csv_and_json_imports_share_the_same_pipeline(store):
    raw = '\ufeffINDEX;NOM;COMMUNE;CODE_INSEE;TYPE;CONTRAT;LAT;LONG\r\n43;"Site; B";Alpha;01001;STEP;C1;"45,3";"1,3"\r\n'.encode("utf-8")
    store.import_bundle(read_import(raw, "sites.csv"))
    assert store.sites()[1]["NOM"] == "Site; B"
    assert float(store.sites()[1]["LAT"]) == 45.3
    with pytest.raises(ValueError):
        read_import(b"INDEX,INDEX\n1,2", "bad.csv")
    with pytest.raises(ValueError):
        read_import(b"INDEX,NOM\n1,Site,Extra", "bad.csv")


def test_migration_requires_contract_and_keeps_original_files(tmp_path):
    folder = tmp_path / "source"
    folder.mkdir()
    row = {k:v for k,v in bundle()["sites"][0].items() if k != "CONTRAT"}
    source = folder / "recap.json"
    source.write_text(json.dumps([row]), encoding="utf-8")
    original = source.read_bytes()
    with pytest.raises(ValueError, match="--contrat"):
        migration_bundle(folder, None)
    target = tmp_path / "new.sqlite3"
    assert main(["--database", str(target), "init"]) == 0
    args = ["--database", str(target), "migrate", "--data-dir", str(folder), "--contrat", "C1"]
    assert main([*args, "--dry-run"]) == 0
    assert Catalogue(target).sites() == []
    assert main(args) == 0
    assert Catalogue(target).sites()[0]["CONTRAT"] == "C1"
    assert source.read_bytes() == original


def test_backup_restore_is_consistent_and_never_overwrites(store, tmp_path):
    backup = tmp_path / "backup.sqlite3"
    store.backup(backup)
    assert Catalogue(backup).check() == store.check()
    with pytest.raises(ValueError):
        store.backup(backup)
    restore = tmp_path / "restored.sqlite3"
    assert main(["--database", str(restore), "restore", str(backup)]) == 0
    assert Catalogue(restore).sites() == store.sites()
    assert main(["--database", str(restore), "restore", str(backup)]) == 1


def test_sqlite_readers_do_not_need_site_json_files(sql_app, store, tmp_path):
    assert load_json_file("./app/data/sites/recap.json") == store.sites()
    assert load_json_file("./app/data/sites/communes.json")[0]["COMMUNE"] == "Alpha"
    assert load_json_file("./app/data/sites/commune_asst_collectif.json")[0]["LAT_MAIRIE"] == "45.1"
    folder = tmp_path / "map"
    (folder / "data" / "sites").mkdir(parents=True)
    (folder / "data" / "sites" / "co.geojson").write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    assert load_geo_datasets(folder)[1] == store.sites()
    assert load_type_metadata(folder)["step"].icon == "step.png"


def test_sites_use_stable_ids_and_save_to_sqlite(sql_app, client, store):
    login(client)
    response = client.get("/edit-sites/")
    assert b'/edit-sites/edit/42' in response.data
    assert client.get("/edit-sites/edit/42").status_code == 200
    assert client.post("/edit-sites/edit/42", data={"NOM": "Nouveau nom", "CONTRAT": "C2"}).status_code == 302
    assert store.sites()[0]["NOM"] == "Nouveau nom"
    assert store.sites()[0]["CONTRAT"] == "C2"
    new = {**bundle()["sites"][0], "NOM": "Site ajouté", "TECHNOLOGIE": "Membrane"}
    assert client.post("/edit-sites/add", data=new).status_code == 302
    assert store.sites()[1]["INDEX"] == "43"
    assert store.sites()[1]["TECHNOLOGIE"] == "Membrane"


def test_sqlite_add_requires_a_contract(sql_app, client, store):
    login(client)
    data = {**bundle()["sites"][0], "CONTRAT": ""}
    response = client.post("/edit-sites/add", data=data)
    assert response.status_code == 200
    assert "CONTRAT inconnu" in response.get_data(as_text=True)
    assert store.check()["sites"] == 1


def test_sqlite_search_and_maintenance_read_catalogue(sql_app, client):
    login(client)
    payload = client.get("/site-search?q=Site").get_json()
    assert payload["results"][0]["index"] == "42"
    assert client.get("/maintenance/").status_code == 200
    response = client.get("/maintenance/recherche?latitude=45.2&longitude=1.2")
    assert response.status_code == 200
    assert b'Site A' in response.data


def test_catalogue_page_import_and_preview_are_protected(sql_app, client, store):
    assert client.get("/catalogue/").status_code == 302
    login(client, 4)
    assert b'Niveau requis' in client.get("/catalogue/").data
    login(client)
    assert b'Contrats et donn' in client.get("/catalogue/").data
    for action in ("preview", "import"):
        response = client.post("/catalogue/", data={"action": action, "entity": "sites", "file": (io.BytesIO(b'INDEX,NOM\n42,Modification'), "sites.csv")}, follow_redirects=True)
        assert response.status_code == 200
        assert "Opération annulée" not in response.get_data(as_text=True)
        assert store.sites()[0]["NOM"] == ("Site A" if action == "preview" else "Modification")


def test_admin_export_round_trips_and_backup_is_sqlite(sql_app, client, store, tmp_path):
    login(client)
    exported = client.get("/catalogue/export")
    target = Catalogue(tmp_path / "copy.sqlite3")
    target.initialize()
    target.import_bundle(exported.get_json())
    assert target.sites() == store.sites()
    assert target.communes(collective=True) == store.communes(collective=True)
    response = client.get("/catalogue/backup")
    assert response.status_code == 200
    assert response.data.startswith(b"SQLite format 3")


def test_catalogue_admin_routes_redirect_anonymous(sql_app, client):
    for path in ("/catalogue/", "/catalogue/export", "/catalogue/backup"):
        response = client.get(path)
        assert response.status_code == 302
        assert "/auth/" in response.location


def test_used_type_cannot_be_removed(store):
    with pytest.raises(sqlite3.IntegrityError):
        store.replace_types([])
    assert store.types()[0]["type"] == "STEP"


@pytest.mark.parametrize("entity,row", [
    ("sites", {"INDEX": "999999999999999999999999999999999"}),
    ("types_sites", {"type": "NEW", "scale": None}),
    ("types_sites", {"type": "NEW", "enabled": 2}),
    ("communes", {"COMMUNE": "Beta", "COLLECTIF": "peut-être"}),
])
def test_malformed_values_are_reported_without_writes(store, entity, row):
    before = store.check()
    with pytest.raises(ValueError):
        store.import_bundle({entity: [row]})
    assert store.check() == before


def test_sqlite_contract_page_creates_persistent_contracts(sql_app, client, store):
    login(client, 3)
    response = client.post("/contrats/liste", data={"REFERENCE": "C3", "NOM": "Nouveau contrat"}, follow_redirects=True)
    assert response.status_code == 200
    assert "Nouveau contrat" in response.get_data(as_text=True)
    assert len(store.contracts()) == 3
    assert store.contracts()[0]["site_count"] == 1


def test_export_preserves_extra_contract_metadata(store):
    store.import_bundle({"contrats": [{"REFERENCE": "C1", "DATE_DEBUT": "2026-01-01"}]})
    assert store.export_bundle()["contrats"][0]["DATE_DEBUT"] == "2026-01-01"
