def test_main_page_shows_backup_menu_for_level_five(client):
    with client.session_transaction() as session:
        session["user"] = {"login": "admin", "uuid": "u-admin", "access_level": 5}

    response = client.get("/")

    assert response.status_code == 200
    assert b"Sauvegarde et Restauration" in response.data
    assert b"Gestion des sauvegardes JSON" in response.data


def test_backup_page_requires_level_five(client):
    with client.session_transaction() as session:
        session["user"] = {"login": "low", "uuid": "u-low", "access_level": 4}

    response = client.get("/users/backup")

    assert response.status_code == 200
    assert b"Niveau requis" in response.data


def test_backup_page_denies_level_six(client):
    with client.session_transaction() as session:
        session["user"] = {"login": "super", "uuid": "u-super", "access_level": 6}

    response = client.get("/users/backup")

    assert response.status_code == 200
    assert b"niveau 5 exact" in response.data.lower()
