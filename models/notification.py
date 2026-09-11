"""Database model for User Notifications and Risk Advisories in NIDARS."""

from datetime import datetime, timezone
from extensions import db


def utc_now():
    return datetime.now(timezone.utc)


TYPE_FLOOD_RISK_INCREASE = "flood_risk_increase"
TYPE_LANDSLIDE_RISK_INCREASE = "landslide_risk_increase"
TYPE_COMBINED_RISK_INCREASE = "combined_risk_increase"
TYPE_ROUTE_RISK_WARNING = "route_risk_warning"
TYPE_EMERGENCY_ADVISORY = "emergency_advisory"

VALID_NOTIFICATION_TYPES = (
    TYPE_FLOOD_RISK_INCREASE,
    TYPE_LANDSLIDE_RISK_INCREASE,
    TYPE_COMBINED_RISK_INCREASE,
    TYPE_ROUTE_RISK_WARNING,
    TYPE_EMERGENCY_ADVISORY,
)

VALID_RISK_LEVELS = ("LOW", "MODERATE", "HIGH", "CRITICAL")


class UserNotification(db.Model):
    """User-targeted risk alert, threshold advisory, or route safety notification."""

    __tablename__ = "user_notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    notification_type = db.Column(db.String(64), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    risk_level = db.Column(db.String(32), nullable=False, default="MODERATE", index=True)
    location_name = db.Column(db.String(255), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    hazard_probability = db.Column(db.Float, nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)

    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic", cascade="all, delete-orphan"))

    def mark_as_read(self):
        """Mark this notification as read with timestamp."""
        if not self.is_read:
            self.is_read = True
            self.read_at = utc_now()

    def to_dict(self):
        """Serialize notification object to JSON-compatible dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "notification_type": self.notification_type,
            "title": self.title,
            "message": self.message,
            "risk_level": self.risk_level,
            "location_name": self.location_name or "Monitored Zone",
            "latitude": self.latitude,
            "longitude": self.longitude,
            "hazard_probability": self.hazard_probability,
            "hazard_probability_pct": f"{self.hazard_probability * 100:.1f}%" if self.hazard_probability is not None else None,
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "metadata": self.metadata_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_at_human": self.created_at.strftime("%b %d, %H:%M UTC") if self.created_at else None,
        }

    def __repr__(self):
        return f"<UserNotification {self.id} {self.notification_type} [{self.risk_level}] read={self.is_read}>"
