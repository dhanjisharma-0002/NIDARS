"""
NIDARS — Phase 18: Notification and Alert Service Engine.
Handles notification creation, anti-spam deduplication, cooldown policies,
state transitions (read/unread), and resilient email dispatch.
"""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Tuple

from extensions import db
from models.notification import (
    TYPE_COMBINED_RISK_INCREASE,
    TYPE_EMERGENCY_ADVISORY,
    TYPE_FLOOD_RISK_INCREASE,
    TYPE_LANDSLIDE_RISK_INCREASE,
    TYPE_ROUTE_RISK_WARNING,
    VALID_NOTIFICATION_TYPES,
    VALID_RISK_LEVELS,
    UserNotification,
)
from models.user import User

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


def create_notification(
    user_id: Optional[int],
    notification_type: str,
    title: str,
    message: str,
    risk_level: str = "MODERATE",
    location_name: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    hazard_probability: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
    cooldown_minutes: int = 30,
    send_email: bool = False,
) -> Tuple[UserNotification, bool]:
    """
    Create a user notification with cooldown-based anti-spam deduplication.

    Returns:
        Tuple of (UserNotification, was_created: bool).
        If deduplicated within cooldown window, returns (existing_notification, False).
    """
    if notification_type not in VALID_NOTIFICATION_TYPES:
        notification_type = TYPE_COMBINED_RISK_INCREASE

    if risk_level not in VALID_RISK_LEVELS:
        risk_level = "MODERATE"

    # Anti-Spam / Deduplication Check
    if cooldown_minutes > 0:
        cutoff = utc_now() - timedelta(minutes=cooldown_minutes)
        query = UserNotification.query.filter(
            UserNotification.user_id == user_id,
            UserNotification.notification_type == notification_type,
            UserNotification.risk_level == risk_level,
            UserNotification.is_read.is_(False),
            UserNotification.created_at >= cutoff,
        )

        if location_name:
            query = query.filter(UserNotification.location_name == location_name)

        existing = query.order_by(UserNotification.created_at.desc()).first()
        if existing:
            logger.info(
                "Deduplicating notification '%s' for user %s at '%s' (within %dm cooldown window)",
                notification_type,
                user_id,
                location_name,
                cooldown_minutes,
            )
            return existing, False

    # Create new notification
    notification = UserNotification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        risk_level=risk_level,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        hazard_probability=hazard_probability,
        metadata_json=metadata or {},
        is_read=False,
    )
    db.session.add(notification)
    db.session.commit()

    # Optional Email Dispatch
    if send_email and user_id:
        user = db.session.get(User, user_id)
        if user and user.email:
            send_email_notification(
                recipient_email=user.email,
                subject=f"[NIDARS Advisory] {title}",
                body_text=f"{title}\n\nLocation: {location_name or 'N/A'}\nRisk Level: {risk_level}\n\n{message}\n\nDisclaimer: NIDARS notifications are AI advisory signals for research decision support and do not replace official government warnings.",
            )

    return notification, True


def get_user_notifications(
    user_id: int,
    unread_only: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """Retrieve paginated notifications and unread counter for a user."""
    base_query = UserNotification.query.filter(
        (UserNotification.user_id == user_id) | (UserNotification.user_id.is_(None))
    )

    unread_count = base_query.filter(UserNotification.is_read.is_(False)).count()

    if unread_only:
        base_query = base_query.filter(UserNotification.is_read.is_(False))

    total = base_query.count()
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    items = (
        base_query.order_by(UserNotification.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "notifications": [item.to_dict() for item in items],
        "unread_count": unread_count,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_unread_count(user_id: int) -> int:
    """Return total unread notification count for a user."""
    return UserNotification.query.filter(
        ((UserNotification.user_id == user_id) | (UserNotification.user_id.is_(None)))
        & UserNotification.is_read.is_(False)
    ).count()


def mark_notification_as_read(notification_id: int, user_id: int) -> bool:
    """
    Mark a single notification as read, ensuring user ownership isolation.
    """
    notification = db.session.get(UserNotification, notification_id)
    if not notification:
        return False

    # Ownership check: must belong to the requesting user or be broadcast
    if notification.user_id is not None and notification.user_id != user_id:
        return False

    notification.mark_as_read()
    db.session.commit()
    return True


def mark_all_notifications_as_read(user_id: int) -> int:
    """Mark all unread notifications for a user as read."""
    unread_notifications = UserNotification.query.filter(
        ((UserNotification.user_id == user_id) | (UserNotification.user_id.is_(None)))
        & UserNotification.is_read.is_(False)
    ).all()

    count = 0
    now = utc_now()
    for notif in unread_notifications:
        notif.is_read = True
        notif.read_at = now
        count += 1

    if count > 0:
        db.session.commit()

    return count


def evaluate_and_notify_risk_change(
    user_id: Optional[int],
    hazard_type: str,
    current_probability: float,
    previous_probability: Optional[float] = None,
    risk_level: str = "MODERATE",
    location_name: str = "Monitored Location",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[UserNotification]:
    """
    Evaluate whether a prediction or live risk change warrants an automatic advisory notification.
    Triggers if risk level is HIGH or CRITICAL, or if probability increased significantly (+0.15).
    """
    prob_delta = (
        (current_probability - previous_probability)
        if previous_probability is not None
        else 0.0
    )

    should_notify = (
        risk_level in ("HIGH", "CRITICAL")
        or (risk_level == "MODERATE" and prob_delta >= 0.15)
        or (prob_delta >= 0.20)
    )

    if not should_notify:
        return None

    # Determine notification type
    hazard_lower = (hazard_type or "").lower()
    if "flood" in hazard_lower:
        notif_type = TYPE_FLOOD_RISK_INCREASE
        type_title = "Flood Risk Increase Detected"
    elif "landslide" in hazard_lower:
        notif_type = TYPE_LANDSLIDE_RISK_INCREASE
        type_title = "Landslide Risk Increase Detected"
    else:
        notif_type = TYPE_COMBINED_RISK_INCREASE
        type_title = "Combined Multi-Hazard Risk Escalation"

    pct_str = f"{current_probability * 100:.1f}%"
    delta_str = f" (+{prob_delta * 100:.1f}%)" if prob_delta > 0 else ""
    msg = (
        f"Hazard assessment for {location_name} calculated a calibrated risk probability of {pct_str}{delta_str}, "
        f"placing this zone in the {risk_level} risk tier. Exercise heightened awareness."
    )

    notification, _ = create_notification(
        user_id=user_id,
        notification_type=notif_type,
        title=f"{type_title} — {location_name}",
        message=msg,
        risk_level=risk_level,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        hazard_probability=current_probability,
        metadata=metadata,
        cooldown_minutes=30,
    )
    return notification


def send_email_notification(
    recipient_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Dispatch an email notification using environment-configured SMTP settings.
    Gracefully handles failures without throwing exceptions or leaking secrets.
    """
    mail_server = os.environ.get("MAIL_SERVER")
    if not mail_server:
        logger.info("Email notification skipped: MAIL_SERVER environment variable not configured.")
        return False, "MAIL_SERVER not configured"

    mail_port = int(os.environ.get("MAIL_PORT", 587))
    mail_user = os.environ.get("MAIL_USERNAME")
    mail_pass = os.environ.get("MAIL_PASSWORD")
    mail_sender = os.environ.get("MAIL_DEFAULT_SENDER", "nidars-alerts@nidars.gov.in")
    use_tls = os.environ.get("MAIL_USE_TLS", "true").lower() in ("true", "1", "yes")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_sender
    msg["To"] = recipient_email
    msg.set_content(body_text)

    if body_html:
        msg.add_alternative(body_html, subtype="html")

    try:
        with smtplib.SMTP(mail_server, mail_port, timeout=10) as server:
            if use_tls:
                server.starttls()
            if mail_user and mail_pass:
                server.login(mail_user, mail_pass)
            server.send_message(msg)

        logger.info("Successfully dispatched email notification to %s", recipient_email)
        return True, "Dispatched"

    except Exception as err:
        logger.warning(
            "Failed to send email notification to %s: %s (gracefully handled)",
            recipient_email,
            str(err),
        )
        return False, str(err)
