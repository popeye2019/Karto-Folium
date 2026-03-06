from __future__ import annotations


def test_login_ban_blocks_local_ip_when_switch_enabled(client, monkeypatch, tmp_path):
    ban_file = tmp_path / "login_bans.json"
    journal_file = tmp_path / "login_journal.json"

    monkeypatch.setattr("app.blueprints.auth.auth.LOGIN_BAN_FILE", str(ban_file))
    monkeypatch.setattr("app.blueprints.auth.auth.LOGIN_JOURNAL_FILE", str(journal_file))
    monkeypatch.setattr("app.blueprints.auth.auth.verify_user", lambda *_: None)

    client.application.config["LOGIN_BAN_ENABLED"] = True
    client.application.config["LOGIN_BAN_INCLUDE_LOCAL"] = True
    client.application.config["LOGIN_BAN_MAX_FAILURES"] = 2
    client.application.config["LOGIN_BAN_WINDOW_SECONDS"] = 600
    client.application.config["LOGIN_BAN_DURATION_SECONDS"] = 600

    first = client.post("/auth/", data={"login": "alice", "password": "bad"}, follow_redirects=False)
    assert first.status_code == 200
    assert b"Identifiants invalides." in first.data

    second = client.post("/auth/", data={"login": "alice", "password": "bad"}, follow_redirects=False)
    assert second.status_code == 200
    assert b"Trop de tentatives de connexion." in second.data

    # Even with valid credentials, the IP remains blocked during ban duration.
    monkeypatch.setattr(
        "app.blueprints.auth.auth.verify_user",
        lambda login, _pwd: {
            "Login": login,
            "Niveau acces": 2,
            "Nom": "Durand",
            "Prenom": "Alice",
            "id": "u1",
            "Notification": True,
        },
    )
    blocked = client.post("/auth/", data={"login": "alice", "password": "good"}, follow_redirects=False)
    assert blocked.status_code == 200
    assert b"Trop de tentatives de connexion." in blocked.data


def test_login_ban_ignores_local_ip_when_switch_disabled(client, monkeypatch, tmp_path):
    ban_file = tmp_path / "login_bans.json"
    journal_file = tmp_path / "login_journal.json"

    monkeypatch.setattr("app.blueprints.auth.auth.LOGIN_BAN_FILE", str(ban_file))
    monkeypatch.setattr("app.blueprints.auth.auth.LOGIN_JOURNAL_FILE", str(journal_file))
    monkeypatch.setattr("app.blueprints.auth.auth.verify_user", lambda *_: None)

    client.application.config["LOGIN_BAN_ENABLED"] = True
    client.application.config["LOGIN_BAN_INCLUDE_LOCAL"] = False
    client.application.config["LOGIN_BAN_MAX_FAILURES"] = 1
    client.application.config["LOGIN_BAN_WINDOW_SECONDS"] = 600
    client.application.config["LOGIN_BAN_DURATION_SECONDS"] = 600

    failed = client.post("/auth/", data={"login": "alice", "password": "bad"}, follow_redirects=False)
    assert failed.status_code == 200
    assert b"Identifiants invalides." in failed.data

    monkeypatch.setattr(
        "app.blueprints.auth.auth.verify_user",
        lambda login, _pwd: {
            "Login": login,
            "Niveau acces": 2,
            "Nom": "Durand",
            "Prenom": "Alice",
            "id": "u1",
            "Notification": True,
        },
    )
    success = client.post("/auth/", data={"login": "alice", "password": "good"}, follow_redirects=False)
    assert success.status_code == 302
