"""What-If Disaster Risk Simulator web routes and REST API endpoints for NIDARS."""

from __future__ import annotations

from flask import current_app, jsonify, render_template, request
from flask_login import login_required

from extensions import csrf
from routes.main import api_bp, main_bp
from services.simulator_service import (
    get_simulation_presets,
    get_station_baselines,
    simulate_risk_scenario,
)


@main_bp.route("/simulator")
def simulator_view():
    """Render the interactive What-If Disaster Risk Simulator."""
    presets = get_simulation_presets()
    station_baselines = get_station_baselines(limit=20)
    return render_template(
        "simulator.html",
        presets=presets,
        station_baselines=station_baselines,
    )


@api_bp.route("/simulator/presets", methods=["GET"])
def get_presets():
    """Retrieve available simulation presets and genuine station baselines."""
    return jsonify({
        "success": True,
        "presets": get_simulation_presets(),
        "station_baselines": get_station_baselines(limit=20),
    }), 200


@api_bp.route("/simulator/simulate", methods=["POST"])
@csrf.exempt
def simulate_scenario():
    """Run what-if disaster risk simulation comparing current baseline and scenario conditions.

    JSON Payload:
    {
        "current": { ...canonical features... },
        "scenario": { ...canonical features... },
        "hazard_type": "combined" | "flood" | "landslide",
        "flood_weight": optional float,
        "landslide_weight": optional float
    }
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({
            "success": False,
            "errors": ["Request body must be a valid JSON object."],
        }), 400

    current_data = payload.get("current")
    scenario_data = payload.get("scenario")

    if not isinstance(current_data, dict):
        return jsonify({
            "success": False,
            "errors": ["Missing or invalid 'current' baseline conditions object."],
        }), 400

    if not isinstance(scenario_data, dict):
        return jsonify({
            "success": False,
            "errors": ["Missing or invalid 'scenario' conditions object."],
        }), 400

    hazard_type = payload.get("hazard_type", "combined")
    flood_weight = payload.get("flood_weight")
    landslide_weight = payload.get("landslide_weight")

    # Optional weights validation if provided
    if flood_weight is not None:
        try:
            flood_weight = float(flood_weight)
            if flood_weight < 0.0 or flood_weight > 1.0:
                raise ValueError()
        except ValueError:
            return jsonify({
                "success": False,
                "errors": ["'flood_weight' must be a numeric value between 0.0 and 1.0."],
            }), 400

    if landslide_weight is not None:
        try:
            landslide_weight = float(landslide_weight)
            if landslide_weight < 0.0 or landslide_weight > 1.0:
                raise ValueError()
        except ValueError:
            return jsonify({
                "success": False,
                "errors": ["'landslide_weight' must be a numeric value between 0.0 and 1.0."],
            }), 400

    try:
        result = simulate_risk_scenario(
            current_payload=current_data,
            scenario_payload=scenario_data,
            hazard_type=hazard_type,
            flood_weight=flood_weight,
            landslide_weight=landslide_weight,
        )
    except Exception as err:
        current_app.logger.exception("What-If simulation failed unexpectedly")
        return jsonify({
            "success": False,
            "errors": [f"Simulation execution failed: {str(err)}"],
        }), 500

    http_status = result.pop("http_status", 200 if result["success"] else 400)
    return jsonify(result), http_status
