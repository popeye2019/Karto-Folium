import os


class Config:
    """
    Config simple et robuste :
    - Pas de secrets en dur : variables d''environnement
    - DEBUG pilote par FLASK_DEBUG (0/1)
    - SITE_ETATS controle les valeurs possibles du champ ETAT
    """

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-not-safe")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    SITE_ETATS = tuple(
        value.strip()
        for value in os.getenv("SITE_ETATS", "ES,HS").split(",")
        if value.strip()
    ) or ("ES", "HS")
