"""Dashboard blueprint displaying the main application home page."""

from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from app.utils.auth import login_required, require_level
from app.utils.import_fichier import save_upload, UploadError

main_bp = Blueprint("main", __name__, template_folder="templates")


@main_bp.route("/")
@login_required
@require_level(1)
def home():
    """Render the authenticated home page."""
    user = session.get("user")
    current_app.logger.debug("Rendering main home page for user %s", user.get("login") if user else "anonymous")

    return render_template(
        "main.html",
        current_app=current_app,
        user=user,
    )


@main_bp.route("/upload-test-icon", methods=["POST"])
@login_required
@require_level(1)
def upload_test_icon():
    file = request.files.get("icon_file")
    if not file or not file.filename:
        flash("Aucun fichier sélectionné.", "danger")
        return redirect(url_for("main.home"))

    try:
        destination = save_upload(file, category="image", target_dir="app/data/icones")
    except UploadError as exc:
        current_app.logger.warning("Upload icon refused: %s", exc)
        flash(str(exc), "danger")
        return redirect(url_for("main.home"))

    flash(f"Icône enregistrée: {destination.name}", "success")
    return redirect(url_for("main.home"))
