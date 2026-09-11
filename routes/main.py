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


def _database_info():
    try:
        from models import User
        driver_name = db.engine.url.drivername
        host = db.engine.url.host or "local"
        database = db.engine.url.database or ""
        dialect = db.engine.dialect.name
        sanitized_uri = db.engine.url.render_as_string(hide_password=True)
        users_count = db.session.query(User).count()
        return {
            "status": "connected",
            "driver": driver_name,
            "dialect": dialect,
            "host": host,
            "database": database,
            "sanitized_uri": sanitized_uri,
            "users_count": users_count,
        }
    except Exception as exc:
        db.session.rollback()
        return {
            "status": "unavailable",
            "error": str(exc),
        }


def _database_status():
    info = _database_info()
    return info.get("status", "unavailable")


@api_bp.route("/health")
def health():
    db_info = _database_info()
    return jsonify(
        {
            "status": "running",
            "application": "NIDARS",
            "message": "Application is running",
            "phase": 3,
            "secret_key_configured": bool(os.environ.get("SECRET_KEY", "").strip()),
            "secret_key_loaded": True,
            "database": db_info.get("status", "unknown"),
            "database_driver": db_info.get("driver", "unknown"),
            "database_dialect": db_info.get("dialect", "unknown"),
            "database_host": db_info.get("host", "unknown"),
            "database_name": db_info.get("database", "unknown"),
            "database_uri_sanitized": db_info.get("sanitized_uri", "unknown"),
            "users_in_db": db_info.get("users_count", 0),
            "environment": "vercel_serverless" if (os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV")) else "local",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@api_bp.route("/predictions/recent", methods=["GET"])
def recent_predictions():
    """Retrieve recent predictions for the dashboard table with explainability data."""
    limit = min(50, max(1, request.args.get("limit", 10, type=int)))
    records = []
    try:
        records = (
            PredictionHistory.query.order_by(PredictionHistory.created_at.desc())
            .limit(limit)
            .all()
        )
    except Exception:
        db.session.rollback()
        records = []

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
                "hazard_type": hazard,
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
    record = None
    try:
        record = db.session.get(PredictionHistory, prediction_id)
    except Exception:
        db.session.rollback()

    if not record:
        return jsonify({
            "success": False,
            "error": f"Prediction history record #{prediction_id} not found.",
            "message": "Prediction record was not found.",
        }), 404

    res = record.result_json if isinstance(record.result_json, dict) else {}
    expl = res.get("explainability")
    inputs = res.get("inputs")
    hazard_type = record.prediction_type
    risk_level = res.get("risk_level", "LOW")
    probability = res.get(f"{hazard_type}_probability") or res.get("probability", 0.0)

    if expl is None and inputs and isinstance(inputs, dict):
        if hazard_type == "flood":
            expl = get_flood_explainability(inputs)
        elif hazard_type == "landslide":
            expl = get_landslide_explainability(inputs)

    if expl is None:
        return jsonify({
            "success": False,
            "error": "Explainability could not be generated for this record.",
            "message": "Explainability calculation failed.",
        }), 500

    return jsonify({
        "success": True,
        "prediction_id": record.id,
        "prediction": {
            "id": record.id,
            "hazard_type": hazard_type,
            "prediction_type": hazard_type,
            "risk_level": risk_level,
            "probability": probability,
            "inputs": inputs,
        },
        "prediction_type": hazard_type,
        "hazard_type": hazard_type,
        "risk_level": risk_level,
        "probability": probability,
        "inputs": inputs,
        "explainability": expl,
    })

