import hashlib
import json

import pytest

from app.catalogue import Catalogue
from scripts.catalogue_sqlite import main, migration_bundle, prepare_migration


def write_sources(directory, sites, communes=None):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "recap.json").write_text(json.dumps(sites), encoding="utf-8")
    if communes is not None:
        (directory / "communes.json").write_text(json.dumps(communes), encoding="utf-8")


def site(index=1, code="01001", contract="C1"):
    return {"INDEX": str(index), "NOM": f"Site {index}", "COMMUNE": "Alpha", "CODE_INSEE": code,
            "TYPE": "STEP", "CONTRAT": contract, "LAT": "45.2", "LONG": "1.2"}


def test_prepare_creates_six_tables_and_reports_absent_sources(tmp_path):
    database = tmp_path / "catalogue.sqlite3"
    report_path = tmp_path / "rapport.json"
    result = main(["--database", str(database), "prepare", "--data-dir", str(tmp_path / "absent"), "--report", str(report_path)])
    assert result == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["tables_pretes"] is True
    assert report["schema_version"] == 1
    assert set(report["tables"]) == {"contrats", "communes", "types_sites", "contrats_communes", "sites", "imports"}
    assert report["migration_verifiee"] is False
    assert report["donnees_importees"] is False
    assert report["erreurs"]
    store = Catalogue(database)
    with store.connect() as connection:
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert tables == {"contrats", "communes", "types_sites", "contrats_communes", "sites", "imports"}
        fields = {r["name"]: r for r in connection.execute("PRAGMA table_info(sites)")}
        assert fields["contrat_id"]["notnull"] == 1
        assert connection.execute("PRAGMA foreign_key_list(sites)").fetchall()
    assert all(count == 0 for count in store.check().values())


def test_prepare_simulates_on_snapshot_and_keeps_source_and_target_unchanged(tmp_path):
    source = tmp_path / "sources"
    write_sources(source, [site()])
    store = Catalogue(tmp_path / "catalogue.sqlite3")
    store.initialize()
    before_database = store.path.read_bytes()
    before_source = (source / "recap.json").read_bytes()
    report = prepare_migration(store, source)
    assert report["migration_verifiee"] is True
    assert report["comptes_actuels"]["sites"] == 0
    assert report["comptes_apres_simulation"]["sites"] == 1
    assert report["donnees_importees"] is False
    assert store.path.read_bytes() == before_database
    assert (source / "recap.json").read_bytes() == before_source
    assert report["sources"][0]["sha256"] == hashlib.sha256(before_source).hexdigest()


def test_prepare_reports_invalid_batch_without_applying_it(tmp_path):
    source = tmp_path / "sources"
    write_sources(source, [site(), {**site(2), "LAT": "invalide"}])
    store = Catalogue(tmp_path / "catalogue.sqlite3")
    report = prepare_migration(store, source)
    assert report["migration_verifiee"] is False
    assert "ligne 2" in report["erreurs"][0]
    assert all(count == 0 for count in store.check().values())


def test_migration_recovers_distinct_homonymous_communes_from_sites(tmp_path):
    source = tmp_path / "sources"
    write_sources(source, [site(1, "01001"), site(2, "02002")])
    store = Catalogue(tmp_path / "catalogue.sqlite3")
    store.initialize()
    store.import_bundle(migration_bundle(source, None))
    assert store.check()["communes"] == 2
    assert [r["CODE_INSEE"] for r in store.sites()] == ["01001", "02002"]


def test_migration_refuses_conflicting_names_for_the_same_code(tmp_path):
    source = tmp_path / "sources"
    write_sources(source, [site()], communes=[{"COMMUNE": "Alpha", "CODE_INSEE": "01001"}, {"COMMUNE": "Beta", "CODE_INSEE": "01001"}])
    with pytest.raises(ValueError, match="plusieurs noms"):
        migration_bundle(source, None)


def test_migration_keeps_existing_contract_name(tmp_path):
    source = tmp_path / "sources"
    write_sources(source, [site()])
    store = Catalogue(tmp_path / "catalogue.sqlite3")
    store.initialize()
    store.import_bundle({"contrats": [{"REFERENCE": "C1", "NOM": "Libellé métier"}]})
    store.import_bundle(migration_bundle(source, None))
    assert store.contracts()[0]["nom"] == "Libellé métier"


def test_migration_never_invents_multiple_contract_reference(tmp_path):
    source = tmp_path / "sources"
    write_sources(source, [site(contract=["C1", "C2"])])
    with pytest.raises(ValueError, match="valeur simple"):
        migration_bundle(source, None)


@pytest.mark.parametrize("destination", ["database", "recap.json", "communes.json"])
def test_report_cannot_overwrite_database_or_sources(tmp_path, destination):
    source = tmp_path / "sources"
    write_sources(source, [site()])
    database = tmp_path / "catalogue.sqlite3"
    target = database if destination == "database" else source / destination
    before = target.read_bytes() if target.exists() else None
    assert main(["--database", str(database), "prepare", "--data-dir", str(source), "--report", str(target)]) == 1
    assert (target.read_bytes() if target.exists() else None) == before
