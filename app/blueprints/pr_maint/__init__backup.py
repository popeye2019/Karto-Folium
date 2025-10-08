"""Maintenance module for managing interventions on recap.json sites."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, render_template

from app.utils.auth import login_required, require_level
from app.utils.utils_json import load_json_file as load_data

pr_maint_bp = Blueprint("pr_maint", __name__, template_folder="templates")

RECUP_FILE = "./app/data/sites/recap.json"
MAINTENANCE_ACCESS_LEVEL = 2


@pr_maint_bp.route("/")
@login_required
@require_level(MAINTENANCE_ACCESS_LEVEL)
def maintenance_home():
    """Display the maintenance dashboard for recap.json sites."""
    data = load_data(RECUP_FILE)
    if isinstance(data, list):
        site_count = len(data)
    else:
        site_count = 0
    return render_template(
        "pr_maint_home.html",
        site_count=site_count,
    )
