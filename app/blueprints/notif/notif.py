"""Blueprint implementing notification management and delivery."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.utils.auth import login_required, require_level
from app.utils.utils_json import load_json_file as load_json
from app.utils.utils_json import save_json_file as save_json

USER_FILE = "./app/data/users/users.json"
NOTIFICATION_FILE = "./app/blueprints/notif/notifications.json"

notif_bp = Blueprint("notif", __name__, template_folder="templates")


@notif_bp.route("/")
@login_required
@require_level(3)
def show_index():
    """Legacy entry point redirecting to the notification list."""
    user = session.get("user", {})
    user_uuid = user.get("uuid")
    current_app.logger.debug("Redirecting notification index for user %s", user_uuid)
    return redirect(url_for("notif.view_notifications"))


@notif_bp.route("/notifications/<user_id>")
@login_required
@require_level(3)
def get_notifications(user_id: str):
    """Return unread notifications for the given user id."""
    notifications = load_json(NOTIFICATION_FILE)
    pending = [
        notification
        for notification in notifications
        if notification["recipient_id"] == user_id and not notification["is_read"]
    ]
    return jsonify(pending)


@notif_bp.route("/notify", methods=["POST"])
@login_required
@require_level(3)
def create_notification():
    """Persist a notification provided as JSON payload."""
    payload = request.get_json(force=True)
    notification = _build_notification(payload)

    notifications = load_json(NOTIFICATION_FILE)
    notifications.append(notification)
    save_json(NOTIFICATION_FILE, notifications)
    return jsonify({"status": "ok", "notif": notification})


@notif_bp.route("/read/<notif_id>", methods=["POST"])
@login_required
@require_level(3)
def mark_as_read(notif_id: str):
    """Mark a notification as read."""
    notifications = load_json(NOTIFICATION_FILE)
    for notification in notifications:
        if str(notification["id"]) == notif_id:
            notification["is_read"] = True
    save_json(NOTIFICATION_FILE, notifications)
    return jsonify({"status": "updated"})


@notif_bp.route("/send-multi", methods=["GET", "POST"])
@login_required
@require_level(3)
def send_multi_notification():
    """Send a notification to multiple recipients."""
    current_user = session.get("user", {})
    current_id = current_user.get("id")
    users = load_json(USER_FILE)

    eligible_users = [
        user
        for user in users
        if user.get("Notification") and user.get("id") != current_id
    ]

    if request.method == "POST":
        message = request.form.get("message", "")
        url = request.form.get("url", "")
        recipient_ids = request.form.getlist("recipients")

        notifications = load_json(NOTIFICATION_FILE)
        for recipient_id in recipient_ids:
            notifications.append(
                _build_notification(
                    {
                        "recipient_id": recipient_id,
                        "sender_id": current_id,
                        "message": message,
                        "url": url,
                    }
                )
            )

        save_json(NOTIFICATION_FILE, notifications)
        return redirect(url_for("notif.view_notifications"))

    return render_template("multi_notify.html", users=eligible_users)


@notif_bp.route("/create", methods=["GET", "POST"])
@login_required
@require_level(3)
def create_from_form():
    """Create a notification from a form submission."""
    current_user = session.get("user", {})
    current_id = current_user.get("uuid")

    users = load_json(USER_FILE)
    eligible_users = [
        {
            "id": str(user.get("id")),
            "login": user.get("Login", ""),
            "nom": user.get("Nom", ""),
            "prenom": user.get("Prenom", ""),
        }
        for user in users
        if user.get("Notification") and str(user.get("id")) != str(current_id)
    ]

    form_data = {
        "recipient_id": (request.form.get("recipient_id") or "").strip(),
        "message": (request.form.get("message") or "").strip(),
        "url": (request.form.get("url") or "").strip(),
    }

    if request.method == "POST":
        valid_ids = {user["id"] for user in eligible_users if user["id"]}
        if not form_data["recipient_id"]:
            flash("Veuillez choisir un destinataire.", "warning")
        elif not form_data["message"]:
            flash("Le message est obligatoire.", "warning")
        elif form_data["recipient_id"] not in valid_ids:
            flash("Destinataire invalide.", "danger")
        else:
            notification = _build_notification(
                {
                    "recipient_id": form_data["recipient_id"],
                    "sender_id": current_id,
                    "message": form_data["message"],
                    "url": form_data["url"],
                }
            )

            notifications = load_json(NOTIFICATION_FILE)
            notifications.append(notification)
            save_json(NOTIFICATION_FILE, notifications)
            flash("Notification envoyee.", "success")
            return redirect(url_for("notif.view_notifications"))

    return render_template(
        "create_form.html",
        users=eligible_users,
        form=form_data,
    )


@notif_bp.route("/view")
@login_required
@require_level(3)
def view_notifications():
    """Display all notifications for the current user."""
    user = session.get("user")
    if not user or not user.get("uuid"):
        return redirect(url_for("main.home"))

    notifications = load_json(NOTIFICATION_FILE)
    user_id = user["uuid"]
    filtered = sorted(
        (notif for notif in notifications if notif["recipient_id"] == user_id),
        key=lambda notif: notif["created_at"],
        reverse=True,
    )

    return render_template("notification_view.html", notifications=list(filtered))


def _build_notification(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized notification dictionary."""
    timestamp = datetime.utcnow().timestamp()
    return {
        "id": str(int(timestamp)),
        "recipient_id": payload["recipient_id"],
        "sender_id": payload.get("sender_id"),
        "message": payload["message"],
        "url": payload.get("url"),
        "is_read": False,
        "created_at": datetime.utcnow().isoformat(),
    }
