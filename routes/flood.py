from flask import jsonify, render_template, request

from extensions import csrf
from routes.main import api_bp, main_bp
from services.explainability_service import explain_from_payload
from services.flood_service import predict_from_payload as predict_flood_payload
from services.landslide_service import predict_from_payload as predict_landslide_payload


@main_bp.route("/flood-prediction")
def flood_prediction():
    return render_template("flood_prediction.html")


@main_bp.route("/landslide")
def landslide_prediction():
    return render_template("landslide_prediction.html")


@api_bp.route("/predict/flood", methods=["POST"])
@csrf.exempt
def predict_flood():
    try:
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
    except Exception as exc:
        import traceback
        return jsonify({
            "success": False,
            "errors": [f"Prediction Engine Error: {str(exc)}"],
            "model_status": "error",
            "prediction": None,
            "traceback": traceback.format_exc(),
        }), 500


@api_bp.route("/predict/landslide", methods=["POST"])
@csrf.exempt
def predict_landslide():
    try:
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
    except Exception as exc:
        import traceback
        return jsonify({
            "success": False,
            "errors": [f"Prediction Engine Error: {str(exc)}"],
            "model_status": "error",
            "prediction": None,
            "traceback": traceback.format_exc(),
        }), 500


@api_bp.route("/explain/<hazard_type>", methods=["POST"])
@csrf.exempt
def explain_hazard(hazard_type):
    try:
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
    except Exception as exc:
        import traceback
        return jsonify({
            "success": False,
            "errors": [f"Explainability Error: {str(exc)}"],
            "hazard_type": hazard_type,
            "traceback": traceback.format_exc(),
        }), 500


