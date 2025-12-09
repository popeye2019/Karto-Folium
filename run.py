from pathlib import Path

from dotenv import load_dotenv

# Load local dev environment variables on Windows (no effect in prod where run.py n'est pas utilisé).
BASE_DIR = Path(__file__).resolve().parent
DOTENV_DEV = BASE_DIR / ".env.dev"
if DOTENV_DEV.exists():
    load_dotenv(DOTENV_DEV)

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Simple HTTP server for ngrok tunneling
    app.run(debug=True, host="0.0.0.0", port=5000)
