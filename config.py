import os


class Config:
    """
    Config simple et robuste :
    - Pas de secrets en dur : variables d''environnement
    - DEBUG pilote par FLASK_DEBUG (0/1)
    """

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-not-safe")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
