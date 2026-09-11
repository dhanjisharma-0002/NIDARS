from datetime import datetime, timezone

from extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class Location(db.Model):
    """Named coordinates for later flood, landslide, and routing work. No seed data in Phase 2."""

    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    latitude = db.Column(db.Numeric(9, 6), nullable=False)
    longitude = db.Column(db.Numeric(9, 6), nullable=False)
    state = db.Column(db.String(100), nullable=False, index=True)
    district = db.Column(db.String(100), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    predictions = db.relationship("PredictionHistory", back_populates="location", lazy="dynamic")

    def __repr__(self):
        return f"<Location {self.name}>"
