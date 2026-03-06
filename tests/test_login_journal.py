import json


def test_login_writes_journal_entry(client, monkeypatch, tmp_path):
    journal_file = tmp_path / "login_journal.json"

    def fake_verify_user(login_value, _password):
        return {
            "Login": login_value,
            "Niveau acces": 2,
            "Nom": "Durand",
            "Prenom": "Alice",
            "id": "uuid-1",
            "Notification": True,
        }

    monkeypatch.setattr("app.blueprints.auth.auth.verify_user", fake_verify_user)
    monkeypatch.setattr("app.blueprints.auth.auth.LOGIN_JOURNAL_FILE", str(journal_file))

    response = client.post(
        "/auth/",
        data={"login": "alice", "password": "secret"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    entries = json.loads(journal_file.read_text(encoding="utf-8"))
    assert len(entries) == 1
    assert entries[0]["Login"] == "alice"
    assert entries[0]["Nom"] == "Durand"
    assert entries[0]["Prenom"] == "Alice"
    assert entries[0]["IP"] == "127.0.0.1"
    assert entries[0]["Statut"] == "succes"
    assert "Horodatage" in entries[0]


def test_login_journal_page_and_reset(client, monkeypatch, tmp_path):
    journal_file = tmp_path / "login_journal.json"
    journal_file.write_text(
        json.dumps(
            [
                {
                    "Horodatage": "2026-03-06T09:10:11",
                    "Nom": "Martin",
                    "Prenom": "Paul",
                    "Login": "pmartin",
                    "IP": "10.0.0.8",
                    "Statut": "succes",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.blueprints.gestion_user.users.LOGIN_JOURNAL_FILE", str(journal_file))

    with client.session_transaction() as session:
        session["user"] = {"login": "admin", "uuid": "u-admin", "access_level": 5}

    response = client.get("/users/login-journal")
    assert response.status_code == 200
    assert b"Journal des connexions" in response.data
    assert b"pmartin" in response.data

    response = client.post("/users/login-journal/reset", follow_redirects=True)
    assert response.status_code == 200
    entries = json.loads(journal_file.read_text(encoding="utf-8"))
    assert entries == []


def test_failed_login_is_logged_with_ip(client, monkeypatch, tmp_path):
    journal_file = tmp_path / "login_journal.json"
    monkeypatch.setattr("app.blueprints.auth.auth.verify_user", lambda *_: None)
    monkeypatch.setattr("app.blueprints.auth.auth.LOGIN_JOURNAL_FILE", str(journal_file))

    response = client.post(
        "/auth/",
        data={"login": "intrus", "password": "bad"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    entries = json.loads(journal_file.read_text(encoding="utf-8"))
    assert len(entries) == 1
    assert entries[0]["Login"] == "intrus"
    assert entries[0]["IP"] == "127.0.0.1"
    assert entries[0]["Statut"] == "echec"
