"""Global data loaded from JSON configuration files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path("./app/data/users")


def _load_json(filename: str) -> Any:
    """Helper returning JSON content for the given filename."""
    with (DATA_DIR / filename).open("r", encoding="utf-8") as file:
        return json.load(file)


DROITS = _load_json("droits.json")
USER_FILE = str(DATA_DIR / "users.json")
SAVE_USERS_FILE = USER_FILE
