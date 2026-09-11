"""Disaster Report generation web routes and REST API endpoints for NIDARS."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required

from extensions import db
from models.prediction import PredictionHistory
from routes.main import api_bp
from services.report_service import generate_disaster_pdf_report


@api_bp.route("/reports/disaster", methods=["GET", "POST"])
@login_required
def generate_disaster_report():
    """Generate a downloadable PDF disaster intelligence briefing report."""
    if request.method == "POST":
        payload = request.get_json(silent=True) or request.form.to_dict() or {}
    else:
        payload = request.args.to_dict()

    # 1. Check if prediction_id is provided
    if "prediction_id" in payload or "id" in payload:
        raw_id = payload.get("prediction_id") if "prediction_id" in payload else payload.get("id")
        if raw_id is None or str(raw_id).strip() == "":
            return jsonify({
                "success": False,
                "error": "INVALID_PREDICTION_ID",
                "message": "Prediction ID cannot be empty."
            }), 400
        try:
            pred_id_int = int(raw_id)
            pred = db.session.get(PredictionHistory, pred_id_int)
            if not pred:
                return jsonify({
                    "success": False,
                    "error": f"Prediction history record #{pred_id_int} not found.",
                    "message": "Prediction record was not found."
                }), 404

            # Authorization check: regular users can only access their own records or unassigned records
            if pred.user_id is not None and current_user.is_authenticated:
                if not current_user.is_admin() and pred.user_id != current_user.id:
                    return jsonify({
                        "success": False,
                        "error": "UNAUTHORIZED",
                        "message": "You are not authorized to access this prediction report."
                    }), 403

            res_data = pred.result_json or {}
            inputs = res_data.get("inputs") or {}

            # Stored latitude and longitude resolution
            db_lat = inputs.get("latitude")
            db_lon = inputs.get("longitude")
            if db_lat is None and pred.location:
                db_lat = float(pred.location.latitude)
            if db_lon is None and pred.location:
                db_lon = float(pred.location.longitude)
            if db_lat is None:
                db_lat = 30.0
            if db_lon is None:
                db_lon = 78.0

            payload["location_name"] = payload.get("location_name") or inputs.get("location_name") or inputs.get("location") or (pred.location.name if pred.location else "Monitored Location")
            payload["latitude"] = payload.get("latitude") or db_lat
            payload["longitude"] = payload.get("longitude") or db_lon
            payload["elevation"] = payload.get("elevation") or inputs.get("elevation", 450.0)
            payload["rainfall_24h"] = payload.get("rainfall_24h") or inputs.get("rainfall_24h", 0.0)
            payload["rainfall_72h"] = payload.get("rainfall_72h") or inputs.get("rainfall_72h", 0.0)
            payload["rainfall_7d"] = payload.get("rainfall_7d") or inputs.get("rainfall_7d", 0.0)
            payload["temperature"] = payload.get("temperature") or inputs.get("temperature", 22.0)
            payload["wind_speed"] = payload.get("wind_speed") or inputs.get("wind_speed", 4.5)
            payload["air_pressure"] = payload.get("air_pressure") or inputs.get("air_pressure", 1012.0)

            if "flood_probability" in res_data:
                payload["flood_probability"] = res_data["flood_probability"]
            if "landslide_probability" in res_data:
                payload["landslide_probability"] = res_data["landslide_probability"]
            if "risk_level" in res_data:
                payload["risk_level"] = res_data["risk_level"]
            if "explainability" in res_data:
                payload["explainability"] = res_data["explainability"]

        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid prediction_id parameter."}), 400

    # 2. Validate essential geographical parameters
    lat_val = payload.get("latitude")
    lon_val = payload.get("longitude")
    
    if lat_val is None or lon_val is None or str(lat_val).strip() == "" or str(lon_val).strip() == "":
        return jsonify({
            "success": False,
            "error": "Latitude and longitude coordinates are required for report generation.",
        }), 400

    try:
        lat = float(lat_val)
        lon = float(lon_val)
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            return jsonify({
                "success": False,
                "error": "Coordinates out of valid bounds (Latitude: -90 to 90, Longitude: -180 to 180).",
            }), 400
        payload["latitude"] = lat
        payload["longitude"] = lon
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "Invalid numeric coordinates provided.",
        }), 400

    # 3. Generate PDF Document
    try:
        pdf_buffer = generate_disaster_pdf_report(payload)
    except Exception as err:
        return jsonify({
            "success": False,
            "error": f"PDF report compilation failed: {str(err)}",
        }), 500

    # Clean filename
    loc_clean = re.sub(r"[^\w\-]", "_", str(payload.get("location_name", "Location"))).strip("_") or "Location"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"NIDARS_Disaster_Report_{loc_clean}_{timestamp}.pdf"

    return Response(
        pdf_buffer.getvalue(),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )
