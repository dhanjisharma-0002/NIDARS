"""Notification and Risk Alert routes for NIDARS."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from models.notification import (
    TYPE_COMBINED_RISK_INCREASE,
    TYPE_EMERGENCY_ADVISORY,
    TYPE_FLOOD_RISK_INCREASE,
    TYPE_LANDSLIDE_RISK_INCREASE,
    TYPE_ROUTE_RISK_WARNING,
    VALID_NOTIFICATION_TYPES,
    VALID_RISK_LEVELS,
)
from routes.main import api_bp
from services.notification_service import (
    create_notification,
    get_unread_count,
    get_user_notifications,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)


@api_bp.route("/notifications", methods=["GET"])
@login_required
def list_notifications():
    """Retrieve paginated notifications and unread counter for current authenticated user."""
    unread_only = request.args.get("unread_only", "").lower() in ("true", "1", "yes")
    limit = request.args.get("limit", default=20, type=int)
    offset = request.args.get("offset", default=0, type=int)

    data = get_user_notifications(
        user_id=current_user.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )

    return jsonify({
        "success": True,
        "notifications": data["notifications"],
        "unread_count": data["unread_count"],
        "total": data["total"],
        "limit": data["limit"],
        "offset": data["offset"],
    })


@api_bp.route("/notifications/stats", methods=["GET"])
@login_required
def notification_stats():
    """Lightweight polling endpoint for live unread notification count badge."""
    unread = get_unread_count(current_user.id)
    return jsonify({
        "success": True,
        "unread_count": unread,
    })


@api_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_single_read(notification_id: int):
    """Mark a specific notification as read."""
    ok = mark_notification_as_read(notification_id, current_user.id)
    if not ok:
        return jsonify({
            "success": False,
            "error": f"Notification #{notification_id} not found or unauthorized.",
        }), 404

    unread = get_unread_count(current_user.id)
    return jsonify({
        "success": True,
        "message": f"Notification #{notification_id} marked as read.",
        "unread_count": unread,
    })


@api_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_read():
    """Mark all active unread notifications as read for current user."""
    count = mark_all_notifications_as_read(current_user.id)
    return jsonify({
        "success": True,
        "message": f"Marked {count} notifications as read.",
        "updated_count": count,
        "unread_count": 0,
    })


@api_bp.route("/notifications/trigger", methods=["POST"])
@login_required
def trigger_notification():
    """
    Trigger or test an advisory notification for the current user.
    Applies deduplication and cooldown policies.
    """
    payload = request.get_json(silent=True) or {}
    notif_type = payload.get("notification_type") or TYPE_COMBINED_RISK_INCREASE

    if notif_type not in VALID_NOTIFICATION_TYPES:
        return jsonify({
            "success": False,
            "error": f"Invalid notification_type. Must be one of: {list(VALID_NOTIFICATION_TYPES)}",
        }), 400

    title = (payload.get("title") or "").strip()
    message = (payload.get("message") or "").strip()

    if not title or not message:
        return jsonify({
            "success": False,
            "error": "Both 'title' and 'message' fields are required.",
        }), 400

    risk_level = (payload.get("risk_level") or "MODERATE").upper()
    if risk_level not in VALID_RISK_LEVELS:
        risk_level = "MODERATE"

    location_name = payload.get("location_name")
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    hazard_prob = payload.get("hazard_probability")
    cooldown = payload.get("cooldown_minutes", 30)
    send_email = bool(payload.get("send_email", False))

    try:
        lat_f = float(latitude) if latitude is not None else None
        lon_f = float(longitude) if longitude is not None else None
        prob_f = float(hazard_prob) if hazard_prob is not None else None
        cooldown_i = int(cooldown) if cooldown is not None else 30
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "Invalid numeric format in coordinates, probability, or cooldown parameters.",
        }), 400

    notif, was_created = create_notification(
        user_id=current_user.id,
        notification_type=notif_type,
        title=title,
        message=message,
        risk_level=risk_level,
        location_name=location_name,
        latitude=lat_f,
        longitude=lon_f,
        hazard_probability=prob_f,
        metadata=payload.get("metadata"),
        cooldown_minutes=cooldown_i,
        send_email=send_email,
    )

    return jsonify({
        "success": True,
        "notification": notif.to_dict(),
        "created": was_created,
        "cooldown_applied": not was_created,
    })
