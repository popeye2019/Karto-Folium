import sys
import os

# Chemin ABSOLU vers ton projet
PROJECT_DIR = '/var/www/krto'

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Variables d'environnement éventuelles
os.environ.setdefault('FLASK_ENV', 'production')
# os.environ.setdefault('FLASK_DEBUG', '0')  # au cas où

from app import create_app

application = create_app()
