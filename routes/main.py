from datetime import datetime, timezone
import os

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from extensions import db
from models.prediction import PredictionHistory
from services.explainability_service import (
    get_flood_explainability,
    get_landslide_explainability,
)

main_bp = Blueprint("main", __name__)
api_bp = Blueprint("api", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@main_bp.route("/map")
def map_view():
    return render_template("map.html")


def _database_status():
    try:
        db.session.execute(text("SELECT 1"))
        return "connected"
    except OperationalError:
        db.session.rollback()
        return "unavailable"


@api_bp.route("/health")
def health():
    return jsonify(
        {
            "status": "running",
            "application": "NIDARS",
            "message": "Application is running",
            "phase": 3,
            "database": _database_status(),
            "database_name": os.environ.get("DB_NAME", "nidars_db"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@api_bp.route("/predictions/recent", methods=["GET"])
def recent_predictions():
    """Retrieve recent predictions for the dashboard table with explainability data."""
    limit = min(50, max(1, request.args.get("limit", 10, type=int)))
    records = (
        PredictionHistory.query.order_by(PredictionHistory.created_at.desc())
        .limit(limit)
        .all()
    )

    items = []
    for r in records:
        res = r.result_json if isinstance(r.result_json, dict) else {}
        inputs = res.get("inputs") or {}
        hazard = r.prediction_type
        prob = res.get(f"{hazard}_probability") or res.get("probability")
        risk_lvl = res.get("risk_level", "LOW")
        expl = res.get("explainability")

        items.append(
            {
                "id": r.id,
                "prediction_type": hazard,
                "status": r.status,
                "risk_level": risk_lvl,
                "probability": prob,
                "inputs": inputs,
                "has_explainability": expl is not None or bool(inputs),
                "explainability": expl,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )

    return jsonify({"success": True, "predictions": items})


@api_bp.route("/prediction/<int:prediction_id>/explain", methods=["GET"])
def explain_saved_prediction(prediction_id):
    """Retrieve or compute explainability for a specific historical prediction."""
    record = db.session.get(PredictionHistory, prediction_id)
    if not record:
        return jsonify({"success": False, "errors": ["Prediction record not found."]}), 404

    res = record.result_json if isinstance(record.result_json, dict) else {}
    expl = res.get("explainability")
    inputs = res.get("inputs")

    if expl is None and inputs and isinstance(inputs, dict):
        if record.prediction_type == "flood":
            expl = get_flood_explainability(inputs)
        elif record.prediction_type == "landslide":
            expl = get_landslide_explainability(inputs)

    if expl is None:
        return jsonify(
            {
                "success": False,
                "errors": ["Explainability could not be generated for this record."],
            }
        ), 404

    return jsonify(
        {
            "success": True,
            "prediction_id": record.id,
            "prediction_type": record.prediction_type,
            "risk_level": res.get("risk_level"),
            "probability": res.get(f"{record.prediction_type}_probability"),
            "inputs": inputs,
            "explainability": expl,
        }
    )

