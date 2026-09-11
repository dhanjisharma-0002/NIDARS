"""Emergency request tracking model for analytics and operational logging."""

from __future__ import annotations

from datetime import datetime, timezone

from extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class EmergencyRequest(db.Model):
    __tablename__ = "emergency_requests"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    request_type = db.Column(db.String(50), nullable=False, index=True)
    facility_type = db.Column(db.String(32), nullable=True)
    risk_level = db.Column(db.String(20), nullable=True)
    flood_probability = db.Column(db.Float, nullable=True)
    landslide_probability = db.Column(db.Float, nullable=True)
    result_summary = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)

    user = db.relationship("User", backref=db.backref("emergency_requests", lazy="dynamic"))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "latitude": round(float(self.latitude), 6),
            "longitude": round(float(self.longitude), 6),
            "request_type": self.request_type,
            "facility_type": self.facility_type,
            "risk_level": self.risk_level,
            "flood_probability": self.flood_probability,
            "landslide_probability": self.landslide_probability,
            "result_summary": self.result_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<EmergencyRequest {self.id} {self.request_type}>"
