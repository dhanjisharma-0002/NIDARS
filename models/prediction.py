from datetime import datetime, timezone

from extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class PredictionHistory(db.Model):
    """
    History of ML and routing results.

    Phase 3 stores flood scores in result_json when a trained model produces them.
    Untrained requests are not written as fake predictions.
    """

    __tablename__ = "prediction_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=True, index=True)
    prediction_type = db.Column(db.String(32), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default="queued")
    result_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    user = db.relationship("User", back_populates="predictions")
    location = db.relationship("Location", back_populates="predictions")

    def __repr__(self):
        return f"<PredictionHistory {self.id} {self.prediction_type}>"
