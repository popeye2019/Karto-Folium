"""Public landing blueprint providing the minimal index page."""

from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("public_main", __name__)


@bp.get("/")
def index() -> str:
    """Serve the base index template."""
    return render_template("index.html")
