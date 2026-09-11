"""Safe Route Optimization web routes and REST API endpoints for NIDARS."""

from __future__ import annotations

from flask import current_app, jsonify, render_template, request
from flask_login import login_required

from config import Config
from routes.main import api_bp, main_bp
from services.route_risk_service import get_route_risk_analyzer
from services.routing_service import fetch_osrm_routes, validate_coordinates


@main_bp.route("/route-optimizer")
@login_required
def route_optimizer_view():
    """Render the interactive Safe Route Optimization page."""
    return render_template("route_optimizer.html")


@api_bp.route("/routing/route", methods=["GET"])
@login_required
def get_optimized_route():
    """Find road routes between origin and destination, evaluate disaster risk exposure, and recommend safe routes.

    Query parameters:
    - start_lat: float
    - start_lon: float
    - end_lat: float
    - end_lon: float
    - flood_weight: optional float (default 0.50)
    - landslide_weight: optional float (default 0.50)
    - station_radius_km: optional float (default 50.0)
    - sample_interval_km: optional float (default 1.0)
    """
    coords, coord_errors = validate_coordinates(
        start_lat=request.args.get("start_lat"),
        start_lon=request.args.get("start_lon"),
        end_lat=request.args.get("end_lat"),
        end_lon=request.args.get("end_lon"),
    )
    if coord_errors:
        return jsonify({
            "success": False,
            "errors": coord_errors,
            "routes": [],
            "data": None,
        }), 400

    s_lat, s_lon, e_lat, e_lon = coords

    # Optional weights validation
    fw_raw = request.args.get("flood_weight")
    lw_raw = request.args.get("landslide_weight")
    flood_weight = getattr(Config, "GIS_FLOOD_WEIGHT", 0.50)
    landslide_weight = getattr(Config, "GIS_LANDSLIDE_WEIGHT", 0.50)

    if fw_raw is not None:
        try:
            val = float(fw_raw)
            if val < 0.0 or val > 1.0:
                raise ValueError()
            flood_weight = val
        except ValueError:
            return jsonify({
                "success": False,
                "errors": ["Parameter 'flood_weight' must be a numeric value between 0.0 and 1.0."],
                "routes": [],
            }), 400

    if lw_raw is not None:
        try:
            val = float(lw_raw)
            if val < 0.0 or val > 1.0:
                raise ValueError()
            landslide_weight = val
        except ValueError:
            return jsonify({
                "success": False,
                "errors": ["Parameter 'landslide_weight' must be a numeric value between 0.0 and 1.0."],
                "routes": [],
            }), 400

    if flood_weight + landslide_weight <= 0.0:
        return jsonify({
            "success": False,
            "errors": ["Sum of 'flood_weight' and 'landslide_weight' must be greater than 0."],
            "routes": [],
        }), 400

    # Optional radius and sampling parameters
    radius_km = getattr(Config, "ROUTE_STATION_RADIUS_KM", 50.0)
    rad_raw = request.args.get("station_radius_km")
    if rad_raw is not None:
        try:
            val = float(rad_raw)
            if val <= 0.0 or val > 500.0:
                raise ValueError()
            radius_km = val
        except ValueError:
            return jsonify({
                "success": False,
                "errors": ["Parameter 'station_radius_km' must be a positive number up to 500."],
                "routes": [],
            }), 400

    sample_km = getattr(Config, "ROUTE_SAMPLE_INTERVAL_KM", 1.0)
    samp_raw = request.args.get("sample_interval_km")
    if samp_raw is not None:
        try:
            val = float(samp_raw)
            if val < 0.1 or val > 50.0:
                raise ValueError()
            sample_km = val
        except ValueError:
            return jsonify({
                "success": False,
                "errors": ["Parameter 'sample_interval_km' must be between 0.1 and 50.0 km."],
                "routes": [],
            }), 400

    penalty_factor = getattr(Config, "ROUTE_RISK_PENALTY_FACTOR", 10.0)
    min_confidence = getattr(Config, "ROUTE_MIN_CONFIDENCE_COVERAGE", 30.0)

    # Optimization mode parameter: 'safest', 'shortest', 'balanced' (default 'safest')
    mode_raw = request.args.get("mode", "safest")
    mode = (mode_raw or "safest").lower().strip()
    if mode not in {"safest", "shortest", "balanced"}:
        return jsonify({
            "success": False,
            "errors": ["Parameter 'mode' must be one of: 'safest', 'shortest', 'balanced'."],
            "routes": [],
        }), 400

    # Fetch OSRM route(s)
    osrm_result = fetch_osrm_routes(
        start_lat=s_lat,
        start_lon=s_lon,
        end_lat=e_lat,
        end_lon=e_lon,
        alternatives=True,
    )

    if not osrm_result["success"]:
        return jsonify({
            "success": False,
            "error_type": osrm_result.get("error_type", "ROUTING_ERROR"),
            "errors": [osrm_result.get("message", "Routing failed.")],
            "routes": [],
        }), osrm_result.get("http_status", 502)

    raw_routes = osrm_result.get("routes", [])

    try:
        analyzer = get_route_risk_analyzer()
        evaluation = analyzer.evaluate_routes(
            raw_routes=raw_routes,
            sample_interval_km=sample_km,
            station_radius_km=radius_km,
            flood_weight=flood_weight,
            landslide_weight=landslide_weight,
            penalty_factor=penalty_factor,
            min_confidence_coverage=min_confidence,
            mode=mode,
        )
    except Exception as err:
        current_app.logger.exception("Failed to analyze route disaster risk.")
        return jsonify({
            "success": False,
            "errors": [f"Route risk evaluation failed: {str(err)}"],
            "routes": [],
        }), 500

    response_payload = {
        "success": True,
        "origin": {"latitude": s_lat, "longitude": s_lon},
        "destination": {"latitude": e_lat, "longitude": e_lon},
        "routes": evaluation["routes"],
        "mode": evaluation.get("active_mode", mode),
        "shortest_route_index": evaluation["shortest_route_index"],
        "safest_route_index": evaluation["safest_route_index"],
        "balanced_route_index": evaluation.get("balanced_route_index", evaluation["safest_route_index"]),
        "recommended_route_index": evaluation["recommended_route_index"],
        "recommendation_note": evaluation["recommendation_note"],
        "recommendation_confidence": evaluation["recommendation_confidence"],
        "metadata": {
            "mode": evaluation.get("active_mode", mode),
            "station_radius_km": radius_km,
            "sample_interval_km": sample_km,
            "risk_penalty_factor": penalty_factor,
            "risk_method": "nearest_station_within_radius",
            "risk_weights": {
                "flood": flood_weight,
                "landslide": landslide_weight,
            },
            "disclaimer": (
                "This route recommendation is a research prototype based on available station-based hazard predictions "
                "and OpenStreetMap/OSRM routing. It is not an official emergency warning or guaranteed safe route. "
                "Follow current government and local authority advisories."
            ),
        },
    }

    return jsonify(response_payload), 200
