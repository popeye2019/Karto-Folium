from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from app.blueprints.gestion_user import users as users_bp_module


def _set_admin_session(client) -> None:
    with client.session_transaction() as session:
        session["user"] = {"login": "admin", "uuid": "u-admin", "access_level": 5}


def _patch_data_dir(monkeypatch, data_dir: Path) -> None:
    monkeypatch.setattr(users_bp_module, "_data_dir", lambda: data_dir)


def _build_zip(entries: dict[str, str]) -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for arcname, content in entries.items():
            archive.writestr(arcname, content)
    buffer.seek(0)
    return buffer


def test_download_backup_returns_only_json_files(client, tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    (data_dir / "sites").mkdir(parents=True, exist_ok=True)
    (data_dir / "sites" / "recap.json").write_text("[]", encoding="utf-8")
    (data_dir / "icones").mkdir(parents=True, exist_ok=True)
    (data_dir / "icones" / "icon.png").write_bytes(b"not-json")
    _patch_data_dir(monkeypatch, data_dir)
    _set_admin_session(client)

    response = client.get("/users/backup/download")

    assert response.status_code == 200
    assert "karto-data-json-backup-" in response.headers.get("Content-Disposition", "")
    archive = zipfile.ZipFile(io.BytesIO(response.data))
    members = set(archive.namelist())
    assert "data/sites/recap.json" in members
    assert "data/icones/icon.png" not in members


def test_restore_backup_rejects_non_json_archive(client, tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    _patch_data_dir(monkeypatch, data_dir)
    _set_admin_session(client)
    bad_zip = _build_zip({"data/sites/readme.txt": "not-json"})

    response = client.post(
        "/users/backup/restore",
        data={"file": (bad_zip, "bad.zip")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"JSON" in response.data


def test_restore_backup_replaces_json_and_creates_snapshot(client, tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    (data_dir / "sites").mkdir(parents=True, exist_ok=True)
    (data_dir / "sites" / "old.json").write_text(json.dumps({"old": True}), encoding="utf-8")
    _patch_data_dir(monkeypatch, data_dir)
    _set_admin_session(client)
    restore_zip = _build_zip({"data/sites/new.json": json.dumps({"new": True})})

    response = client.post(
        "/users/backup/restore",
        data={"file": (restore_zip, "restore.zip")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Sauvegarde restauree avec succes" in response.data
    assert not (data_dir / "sites" / "old.json").exists()
    assert json.loads((data_dir / "sites" / "new.json").read_text(encoding="utf-8")) == {"new": True}

    snapshots = list((data_dir / "maintenance" / "backups").glob("karto-prerestore-json-*.zip"))
    assert snapshots, "Expected at least one pre-restore snapshot."


def test_restore_backup_accepts_windows_style_zip_paths(client, tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    _patch_data_dir(monkeypatch, data_dir)
    _set_admin_session(client)
    restore_zip = _build_zip({"data\\sites\\from_windows.json": json.dumps({"ok": True})})

    response = client.post(
        "/users/backup/restore",
        data={"file": (restore_zip, "restore_windows.zip")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Sauvegarde restauree avec succes" in response.data
    assert (data_dir / "sites" / "from_windows.json").exists()
