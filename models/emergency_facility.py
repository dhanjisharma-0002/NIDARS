"""Emergency Facility model for hospitals, police stations, and shelters."""

from __future__ import annotations

from datetime import datetime, timezone

from extensions import db


def utc_now():
    return datetime.now(timezone.utc)


FACILITY_HOSPITAL = "hospital"
FACILITY_POLICE = "police"
FACILITY_SHELTER = "shelter"
VALID_FACILITY_TYPES = (FACILITY_HOSPITAL, FACILITY_POLICE, FACILITY_SHELTER)


class EmergencyFacility(db.Model):
    __tablename__ = "emergency_facilities"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    facility_type = db.Column(db.String(32), nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=False, index=True)
    longitude = db.Column(db.Float, nullable=False, index=True)
    address = db.Column(db.String(500), nullable=True)
    phone = db.Column(db.String(100), nullable=True)
    opening_hours = db.Column(db.String(255), nullable=True)
    source = db.Column(db.String(50), nullable=False, default="OpenStreetMap")
    external_id = db.Column(db.String(100), nullable=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.text("1"))
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        db.CheckConstraint("facility_type IN ('hospital', 'police', 'shelter')", name="ck_emergency_facilities_type"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "facility_type": self.facility_type,
            "latitude": round(float(self.latitude), 6),
            "longitude": round(float(self.longitude), 6),
            "address": self.address or "Not available",
            "phone": self.phone or "Not available",
            "opening_hours": self.opening_hours or "Not available",
            "source": self.source,
            "external_id": self.external_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<EmergencyFacility {self.id} {self.facility_type}: {self.name}>"
