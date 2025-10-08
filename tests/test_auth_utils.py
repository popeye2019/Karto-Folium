import json

import pytest
from werkzeug.security import generate_password_hash

from app.utils import auth


def _write_users(tmp_path, users):
    user_file = tmp_path / "users.json"
    user_file.write_text(json.dumps(users), encoding="utf-8")
    return user_file


def test_verify_user_returns_user(app, monkeypatch, tmp_path):
    hashed_password = generate_password_hash("secret")
    users = [
        {
            "Login": "alice",
            "Mot de passe": hashed_password,
            "Niveau acces": 2,
            "Notification": True,
            "Nom": "Test",
            "Prenom": "User",
            "id": "abc",
        }
    ]
    user_file = _write_users(tmp_path, users)

    monkeypatch.setattr(auth, "USER_FILE", str(user_file))

    result = auth.verify_user("alice", "secret")

    assert result is not None
    assert result["Login"] == "alice"


def test_verify_user_invalid_password(app, monkeypatch, tmp_path):
    hashed_password = generate_password_hash("secret")
    users = [
        {
            "Login": "alice",
            "Mot de passe": hashed_password,
        }
    ]
    user_file = _write_users(tmp_path, users)

    monkeypatch.setattr(auth, "USER_FILE", str(user_file))

    assert auth.verify_user("alice", "wrong") is None


def test_verify_user_unknown_user(app, monkeypatch, tmp_path):
    hashed_password = generate_password_hash("secret")
    users = [
        {
            "Login": "bob",
            "Mot de passe": hashed_password,
        }
    ]
    user_file = _write_users(tmp_path, users)

    monkeypatch.setattr(auth, "USER_FILE", str(user_file))

    assert auth.verify_user("alice", "secret") is None


def test_require_level_respects_user_access(app):
    @auth.require_level(3)
    def protected():
        return "allowed"

    with app.test_request_context("/test"):
        # Without user -> renders template
        response = protected()
        assert "Utilisateur non authentifie" in response

    with app.test_request_context("/test"):
        from flask import session

        session["user"] = {"access_level": 2}
        response = protected()
        assert "droits suffisants" in response

    with app.test_request_context("/test"):
        from flask import session

        session["user"] = {"access_level": 4}
        assert protected() == "allowed"


def test_login_required_redirects_when_no_session(app):
    @auth.login_required
    def protected_view():
        return "visible"

    with app.test_request_context("/needs-login"):
        response = protected_view()

    assert response.status_code == 302
    assert "/auth/" in response.location
