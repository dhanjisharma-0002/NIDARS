"""Database model for Early Warning and Advisory alerts."""

from datetime import datetime, timezone

from extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class AlertEvent(db.Model):
    """Stores early warning and risk advisory snapshots generated from ML predictions."""

    __tablename__ = "alert_events"

    id = db.Column(db.Integer, primary_key=True)
    alert_code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    station_name = db.Column(db.String(128), nullable=False, index=True)
    district = db.Column(db.String(128), nullable=False, index=True)
    state_code = db.Column(db.String(16), nullable=False, index=True)
    state_name = db.Column(db.String(128), nullable=False)
    hazard_type = db.Column(db.String(32), nullable=False, index=True)  # 'flood', 'landslide', 'combined'
    probability = db.Column(db.Float, nullable=False)
    risk_level = db.Column(db.String(32), nullable=False, index=True)  # 'LOW', 'MODERATE', 'HIGH', 'CRITICAL'
    advisory = db.Column(db.Text, nullable=False)
    precautions = db.Column(db.JSON, nullable=True)
    telemetry_json = db.Column(db.JSON, nullable=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    elevation = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "alert_code": self.alert_code,
            "station_name": self.station_name,
            "district": self.district,
            "state_code": self.state_code,
            "state_name": self.state_name,
            "hazard_type": self.hazard_type,
            "probability": self.probability,
            "probability_pct": f"{self.probability * 100:.1f}%",
            "risk_level": self.risk_level,
            "advisory": self.advisory,
            "precautions": self.precautions or [],
            "telemetry": self.telemetry_json or {},
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation": self.elevation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<AlertEvent {self.alert_code} {self.hazard_type} {self.risk_level}>"
