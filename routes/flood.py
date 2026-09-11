from flask import jsonify, render_template, request
from flask_login import login_required

from routes.main import api_bp, main_bp
from services.explainability_service import explain_from_payload
from services.flood_service import predict_from_payload as predict_flood_payload
from services.landslide_service import predict_from_payload as predict_landslide_payload


@main_bp.route("/flood-prediction")
@login_required
def flood_prediction():
    return render_template("flood_prediction.html")


@main_bp.route("/landslide")
@login_required
def landslide_prediction():
    return render_template("landslide_prediction.html")


@api_bp.route("/predict/flood", methods=["POST"])
@login_required
def predict_flood():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify(
            {
                "success": False,
                "errors": ["Request body must be JSON."],
                "model_status": "unknown",
                "prediction": None,
            }
        ), 400

    result = predict_flood_payload(payload)
    status = result.pop("http_status", 200 if result["success"] else 400)
    return jsonify(result), status


@api_bp.route("/predict/landslide", methods=["POST"])
@login_required
def predict_landslide():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify(
            {
                "success": False,
                "errors": ["Request body must be JSON."],
                "model_status": "unknown",
                "prediction": None,
            }
        ), 400

    result = predict_landslide_payload(payload)
    status = result.pop("http_status", 200 if result["success"] else 400)
    return jsonify(result), status


@api_bp.route("/explain/<hazard_type>", methods=["POST"])
@login_required
def explain_hazard(hazard_type):
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify(
            {
                "success": False,
                "errors": ["Request body must be JSON."],
                "hazard_type": hazard_type,
            }
        ), 400

    result = explain_from_payload(hazard_type, payload)
    status = result.pop("http_status", 200 if result["success"] else 400)
    return jsonify(result), status


