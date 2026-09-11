"""Incident Report database model for citizen disaster observations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from extensions import db


def utc_now():
    return datetime.now(timezone.utc)


VALID_INCIDENT_TYPES = (
    "Flooded Road",
    "Waterlogging",
    "Landslide",
    "Road Blockage",
    "Bridge Issue",
    "Other",
)
INCIDENT_TYPES = VALID_INCIDENT_TYPES

VALID_SEVERITIES = (
    "Low",
    "Moderate",
    "High",
    "Critical",
)
SEVERITY_LEVELS = VALID_SEVERITIES

STATUS_REPORTED = "Reported"
STATUS_UNDER_REVIEW = "Under Review"
STATUS_VERIFIED = "Verified"
STATUS_RESOLVED = "Resolved"

VALID_STATUSES = (
    STATUS_REPORTED,
    STATUS_UNDER_REVIEW,
    STATUS_VERIFIED,
    STATUS_RESOLVED,
)


class IncidentReport(db.Model):
    """Citizen disaster incident report entity."""

    __tablename__ = "incident_reports"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    location_name = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    incident_type = db.Column(db.String(64), nullable=False, index=True)
    severity = db.Column(db.String(32), nullable=False, default="Moderate")
    description = db.Column(db.Text, nullable=False)
    photo_filename = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(32), nullable=False, default=STATUS_REPORTED, index=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False, index=True)
    admin_notes = db.Column(db.Text, nullable=True)
    incident_date = db.Column(db.DateTime, nullable=False, default=utc_now)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", backref=db.backref("incident_reports", lazy=True))

    def to_dict(self, include_admin_details: bool = False) -> Dict[str, Any]:
        """Convert incident report to safe dictionary."""
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user.name if self.user else "Citizen Observer",
            "location_name": self.location_name,
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "incident_type": self.incident_type,
            "severity": self.severity,
            "description": self.description,
            "photo_filename": self.photo_filename,
            "photo_url": f"/static/uploads/incidents/{self.photo_filename}" if self.photo_filename else None,
            "status": self.status,
            "is_verified": self.is_verified,
            "incident_date": self.incident_date.isoformat() if self.incident_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_admin_details:
            data["admin_notes"] = self.admin_notes
            data["user_email"] = self.user.email if self.user else None

        return data

    def to_geojson_feature(self) -> Dict[str, Any]:
        """Convert to GeoJSON feature for map visualization."""
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(self.longitude, 6), round(self.latitude, 6)],
            },
            "properties": {
                "id": self.id,
                "location_name": self.location_name,
                "incident_type": self.incident_type,
                "severity": self.severity,
                "description": self.description,
                "photo_url": f"/static/uploads/incidents/{self.photo_filename}" if self.photo_filename else None,
                "status": self.status,
                "is_verified": self.is_verified,
                "verification_badge": "VERIFIED CITIZEN REPORT" if self.is_verified else "USER REPORTED (UNVERIFIED)",
                "incident_date": self.incident_date.isoformat() if self.incident_date else None,
                "disclaimer": "User-reported incidents represent community observations and should not be interpreted as official government disaster advisories.",
            },
        }

    def __repr__(self) -> str:
        return f"<IncidentReport {self.id}: {self.incident_type} at {self.location_name} ({self.status})>"
