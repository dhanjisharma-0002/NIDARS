"""Emergency Mode endpoints for facility discovery, hazard risk checks, and emergency safe routes."""

from __future__ import annotations

from flask import current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from config import Config
from extensions import csrf
from routes.main import api_bp, main_bp
from services.emergency_service import (
    analyze_evacuation_safe_zones,
    fetch_osm_emergency_facilities,
    get_current_location_risk,
    log_emergency_request,
    rank_facilities_by_safety,
    validate_emergency_coordinates,
)
from services.route_risk_service import get_route_risk_analyzer
from services.routing_service import fetch_osrm_routes, validate_coordinates

VALID_FACILITY_QUERY_TYPES = {"hospital", "police", "shelter", "all"}


@main_bp.route("/emergency")
@login_required
def emergency_view():
    """Render the interactive Emergency Mode page."""
    return render_template("emergency.html")


@api_bp.route("/emergency/risk", methods=["GET"])
@login_required
def get_emergency_risk():
    """Retrieve localized disaster risk exposure for user coordinates."""
    coords, errors = validate_emergency_coordinates(
        lat_raw=request.args.get("lat"),
        lon_raw=request.args.get("lon"),
    )
    if errors:
        return jsonify({"success": False, "errors": errors, "data": None}), 400

    lat, lon = coords
    fw = float(request.args.get("flood_weight", getattr(Config, "GIS_FLOOD_WEIGHT", 0.50)))
    lw = float(request.args.get("landslide_weight", getattr(Config, "GIS_LANDSLIDE_WEIGHT", 0.50)))

    risk_info = get_current_location_risk(latitude=lat, longitude=lon, flood_weight=fw, landslide_weight=lw)

    # Operational logging
    user_id = current_user.id if current_user.is_authenticated else None
    log_emergency_request(
        user_id=user_id,
        latitude=lat,
        longitude=lon,
        request_type="risk_check",
        risk_level=risk_info.get("risk_level"),
        flood_prob=risk_info.get("flood_probability"),
        landslide_prob=risk_info.get("landslide_probability"),
        summary={"nearest_station": risk_info.get("nearest_station"), "distance_km": risk_info.get("station_distance_km")},
    )

    return jsonify({
        "success": True,
        "coordinates": {"latitude": lat, "longitude": lon},
        "risk_status": risk_info,
        "disclaimer": (
            "NIDARS is an MCA research prototype. Risk scores are model-based estimates and must not be treated as official emergency warnings. "
            "In a real emergency, follow government alerts, police, and disaster-management agencies."
        ),
    }), 200


@api_bp.route("/emergency/facilities", methods=["GET"])
@login_required
def get_emergency_facilities():
    """Discover authentic nearby hospitals, police stations, and shelters within radius."""
    coords, errors = validate_emergency_coordinates(
        lat_raw=request.args.get("lat"),
        lon_raw=request.args.get("lon"),
    )
    if errors:
        return jsonify({"success": False, "errors": errors, "facilities": []}), 400

    lat, lon = coords
    f_type = request.args.get("type", "all").strip().lower()
    if f_type not in VALID_FACILITY_QUERY_TYPES:
        return jsonify({
            "success": False,
            "errors": [f"Invalid facility type '{f_type}'. Must be one of: {', '.join(sorted(VALID_FACILITY_QUERY_TYPES))}."],
            "facilities": [],
        }), 400

    radius_raw = request.args.get("radius_km", getattr(Config, "EMERGENCY_SEARCH_RADIUS_KM", 15.0))
    try:
        radius_km = float(radius_raw)
        if radius_km <= 0.0 or radius_km > 100.0:
            raise ValueError()
    except ValueError:
        return jsonify({
            "success": False,
            "errors": ["Parameter 'radius_km' must be a positive number up to 100.0 km."],
            "facilities": [],
        }), 400

    max_results = int(getattr(Config, "EMERGENCY_MAX_RESULTS", 25))
    max_raw = request.args.get("max_results")
    if max_raw:
        try:
            max_results = int(max_raw)
            if max_results <= 0 or max_results > 100:
                raise ValueError()
        except ValueError:
            return jsonify({
                "success": False,
                "errors": ["Parameter 'max_results' must be an integer between 1 and 100."],
                "facilities": [],
            }), 400

    try:
        res = fetch_osm_emergency_facilities(
            latitude=lat,
            longitude=lon,
            facility_type=f_type,
            radius_km=radius_km,
            max_results=max_results,
        )
    except Exception as err:
        current_app.logger.exception("Failed to query emergency facilities.")
        return jsonify({
            "success": False,
            "errors": [f"Emergency facility discovery service temporarily unavailable: {str(err)}"],
            "facilities": [],
        }), 502

    # Operational logging
    user_id = current_user.id if current_user.is_authenticated else None
    log_emergency_request(
        user_id=user_id,
        latitude=lat,
        longitude=lon,
        request_type="facility_search",
        facility_type=f_type,
        summary={"total_found": res["total_found"], "radius_km": radius_km, "source": res["source"]},
    )

    return jsonify({
        "success": True,
        "origin": {"latitude": lat, "longitude": lon},
        "search_parameters": {
            "facility_type": f_type,
            "radius_km": radius_km,
            "max_results": max_results,
        },
        "total_found": res["total_found"],
        "source": res["source"],
        "facilities": res["facilities"],
        "disclaimer": (
            "Facility locations are sourced from verified OpenStreetMap data. "
            "For active emergency assistance, call official emergency numbers."
        ),
    }), 200


@api_bp.route("/emergency/nearest", methods=["GET"])
@login_required
def get_nearest_emergency_facility():
    """Find the nearest facility and provide a disaster-risk-aware ranking."""
    coords, errors = validate_emergency_coordinates(
        lat_raw=request.args.get("lat"),
        lon_raw=request.args.get("lon"),
    )
    if errors:
        return jsonify({"success": False, "errors": errors, "nearest": None}), 400

    lat, lon = coords
    f_type = request.args.get("type", "all").strip().lower()
    if f_type not in VALID_FACILITY_QUERY_TYPES:
        return jsonify({
            "success": False,
            "errors": [f"Invalid facility type '{f_type}'."],
            "nearest": None,
        }), 400

    radius_km = float(request.args.get("radius_km", getattr(Config, "EMERGENCY_SEARCH_RADIUS_KM", 15.0)))
    fw = float(request.args.get("flood_weight", getattr(Config, "GIS_FLOOD_WEIGHT", 0.50)))
    lw = float(request.args.get("landslide_weight", getattr(Config, "GIS_LANDSLIDE_WEIGHT", 0.50)))

    try:
        res = fetch_osm_emergency_facilities(
            latitude=lat,
            longitude=lon,
            facility_type=f_type,
            radius_km=radius_km,
            max_results=30,
        )
    except Exception as err:
        return jsonify({
            "success": False,
            "errors": [f"Emergency facility service unavailable: {str(err)}"],
            "nearest": None,
        }), 502

    facilities = res.get("facilities", [])
    if not facilities:
        return jsonify({
            "success": True,
            "origin": {"latitude": lat, "longitude": lon},
            "nearest_by_distance": None,
            "recommended_safest": None,
            "total_found": 0,
            "message": f"No verified {f_type} facilities found within {radius_km} km radius.",
        }), 200

    nearest_by_dist = facilities[0]

    # Evaluate safety ranking
    ranked_by_safety = rank_facilities_by_safety(
        facilities=facilities,
        user_lat=lat,
        user_lon=lon,
        flood_weight=fw,
        landslide_weight=lw,
    )
    safest_facility = ranked_by_safety[0]

    # Operational logging
    user_id = current_user.id if current_user.is_authenticated else None
    log_emergency_request(
        user_id=user_id,
        latitude=lat,
        longitude=lon,
        request_type="nearest_facility",
        facility_type=f_type,
        summary={"nearest_name": nearest_by_dist["name"], "distance_km": nearest_by_dist["distance_km"]},
    )

    return jsonify({
        "success": True,
        "origin": {"latitude": lat, "longitude": lon},
        "facility_type": f_type,
        "total_found": len(facilities),
        "nearest_by_distance": nearest_by_dist,
        "recommended_safest": safest_facility,
        "ranked_facilities": ranked_by_safety,
        "ranking_method": (
            "Nearest is sorted strictly by Euclidean/Haversine distance. "
            "Safest incorporates station disaster risk score (Cost = Distance * (1 + 2 * Hazard Risk))."
        ),
    }), 200


@api_bp.route("/emergency/route", methods=["GET"])
@login_required
def get_emergency_route():
    """Calculate an emergency safe route from user location to chosen facility reusing Phase 6 routing engine."""
    coords, coord_errors = validate_coordinates(
        start_lat=request.args.get("start_lat"),
        start_lon=request.args.get("start_lon"),
        end_lat=request.args.get("facility_lat"),
        end_lon=request.args.get("facility_lon"),
    )
    if coord_errors:
        return jsonify({"success": False, "errors": coord_errors, "routes": []}), 400

    s_lat, s_lon, f_lat, f_lon = coords
    fw = float(request.args.get("flood_weight", getattr(Config, "GIS_FLOOD_WEIGHT", 0.50)))
    lw = float(request.args.get("landslide_weight", getattr(Config, "GIS_LANDSLIDE_WEIGHT", 0.50)))
    fac_name = request.args.get("facility_name", "Emergency Facility")
    fac_type = request.args.get("facility_type", "facility")

    # Reuse Phase 6 routing engine
    osrm_result = fetch_osrm_routes(
        start_lat=s_lat,
        start_lon=s_lon,
        end_lat=f_lat,
        end_lon=f_lon,
        alternatives=True,
    )

    if not osrm_result["success"]:
        return jsonify({
            "success": False,
            "errors": [osrm_result.get("message", "Emergency routing failed.")],
            "routes": [],
        }), osrm_result.get("http_status", 502)

    raw_routes = osrm_result.get("routes", [])

    try:
        analyzer = get_route_risk_analyzer()
        evaluation = analyzer.evaluate_routes(
            raw_routes=raw_routes,
            sample_interval_km=getattr(Config, "ROUTE_SAMPLE_INTERVAL_KM", 1.0),
            station_radius_km=getattr(Config, "ROUTE_STATION_RADIUS_KM", 50.0),
            flood_weight=fw,
            landslide_weight=lw,
            penalty_factor=getattr(Config, "ROUTE_RISK_PENALTY_FACTOR", 10.0),
            min_confidence_coverage=getattr(Config, "ROUTE_MIN_CONFIDENCE_COVERAGE", 30.0),
        )
    except Exception as err:
        current_app.logger.exception("Failed to evaluate emergency route safety.")
        return jsonify({
            "success": False,
            "errors": [f"Emergency route risk analysis failed: {str(err)}"],
            "routes": [],
        }), 500

    # Operational logging
    user_id = current_user.id if current_user.is_authenticated else None
    log_emergency_request(
        user_id=user_id,
        latitude=s_lat,
        longitude=s_lon,
        request_type="route_request",
        facility_type=fac_type,
        summary={"target_facility": fac_name, "routes_evaluated": len(evaluation["routes"])},
    )

    return jsonify({
        "success": True,
        "emergency_target": {
            "name": fac_name,
            "facility_type": fac_type,
            "latitude": f_lat,
            "longitude": f_lon,
        },
        "origin": {"latitude": s_lat, "longitude": s_lon},
        "routes": evaluation["routes"],
        "recommended_route_index": evaluation["recommended_route_index"],
        "shortest_route_index": evaluation["shortest_route_index"],
        "recommendation_note": evaluation["recommendation_note"],
        "recommendation_confidence": evaluation["recommendation_confidence"],
        "disclaimer": (
            "NIDARS Emergency Route is a research prototype. Follow official emergency agency directions."
        ),
    }), 200


@api_bp.route("/emergency/evacuation", methods=["GET", "POST"])
@csrf.exempt
@login_required
def post_emergency_evacuation():
    """Phase 14: Production-style Emergency Evacuation & Safe Zone Analysis API.

    Accepts POST JSON payload (or GET query parameters):
    - latitude: float (required, -90 to +90)
    - longitude: float (required, -180 to +180)
    - max_distance_km: optional float (1.0 to 100.0)
    - facility_types: optional list of strings ['shelter', 'hospital', 'police']
    """
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        lat_raw = payload.get("latitude", payload.get("lat"))
        lon_raw = payload.get("longitude", payload.get("lon"))
        max_dist_raw = payload.get("max_distance_km", payload.get("radius_km"))
        f_types = payload.get("facility_types")
        fw_raw = payload.get("flood_weight")
        lw_raw = payload.get("landslide_weight")
    else:
        lat_raw = request.args.get("latitude", request.args.get("lat"))
        lon_raw = request.args.get("longitude", request.args.get("lon"))
        max_dist_raw = request.args.get("max_distance_km", request.args.get("radius_km"))
        f_types_raw = request.args.get("facility_types")
        f_types = [t.strip().lower() for t in f_types_raw.split(",") if t.strip()] if f_types_raw else None
        fw_raw = request.args.get("flood_weight")
        lw_raw = request.args.get("landslide_weight")

    current_app.logger.info(
        f"[EVAC DEBUG] method={request.method} content_type={request.content_type} "
        f"lat={lat_raw} lon={lon_raw} max_dist={max_dist_raw} f_types={f_types}"
    )

    # Validate coordinates
    coords, errors = validate_emergency_coordinates(lat_raw=lat_raw, lon_raw=lon_raw)
    if errors:
        current_app.logger.warning(f"[EVAC DEBUG] Validation failed: {errors}")
        return jsonify({
            "success": False,
            "error": "INVALID_COORDINATES",
            "message": errors[0],
            "errors": errors,
            "origin": None,
            "current_risk": None,
            "recommended_destination": None,
            "destinations": [],
            "routes": [],
        }), 400

    lat, lon = coords

    # Validate max_distance_km
    max_dist_km = getattr(Config, "EVACUATION_MAX_DISTANCE_KM", 25.0)
    if max_dist_raw is not None:
        try:
            max_dist_km = float(max_dist_raw)
            if max_dist_km <= 0.0 or max_dist_km > 100.0:
                raise ValueError()
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "INVALID_RADIUS",
                "message": "Parameter 'max_distance_km' must be a positive number up to 100.0 km.",
                "errors": ["Parameter 'max_distance_km' must be a positive number up to 100.0 km."],
                "origin": {"latitude": lat, "longitude": lon},
                "recommended_destination": None,
                "destinations": [],
            }), 400

    # Validate facility_types
    validated_types = None
    if f_types:
        if isinstance(f_types, str):
            f_types = [f_types]
        if not isinstance(f_types, list):
            return jsonify({
                "success": False,
                "error": "INVALID_FACILITY_TYPES",
                "message": "Parameter 'facility_types' must be an array of facility types.",
                "errors": ["Parameter 'facility_types' must be an array of facility types."],
            }), 400
        valid_set = {"hospital", "police", "shelter", "all"}
        invalid_types = [str(t) for t in f_types if str(t).strip().lower() not in valid_set]
        if invalid_types:
            return jsonify({
                "success": False,
                "error": "INVALID_FACILITY_TYPES",
                "message": f"Invalid facility types: {', '.join(invalid_types)}. Allowed: hospital, police, shelter, all.",
                "errors": [f"Invalid facility types: {', '.join(invalid_types)}. Allowed: hospital, police, shelter, all."],
            }), 400
        if "all" in [str(t).lower() for t in f_types]:
            validated_types = ["hospital", "police", "shelter"]
        else:
            validated_types = [str(t).strip().lower() for t in f_types]

    # Validate weights if provided
    flood_weight = None
    if fw_raw is not None:
        try:
            fw = float(fw_raw)
            if fw < 0.0 or fw > 1.0:
                raise ValueError()
            flood_weight = fw
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "INVALID_WEIGHTS",
                "message": "Parameter 'flood_weight' must be between 0.0 and 1.0.",
                "errors": ["Parameter 'flood_weight' must be between 0.0 and 1.0."],
            }), 400

    landslide_weight = None
    if lw_raw is not None:
        try:
            lw = float(lw_raw)
            if lw < 0.0 or lw > 1.0:
                raise ValueError()
            landslide_weight = lw
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "INVALID_WEIGHTS",
                "message": "Parameter 'landslide_weight' must be between 0.0 and 1.0.",
                "errors": ["Parameter 'landslide_weight' must be between 0.0 and 1.0."],
            }), 400

    try:
        user_id = current_user.id if current_user.is_authenticated else None
        result = analyze_evacuation_safe_zones(
            user_lat=lat,
            user_lon=lon,
            max_distance_km=max_dist_km,
            facility_types=validated_types,
            flood_weight=flood_weight,
            landslide_weight=landslide_weight,
            user_id=user_id,
        )
        return jsonify(result), 200
    except Exception as err:
        current_app.logger.exception("Emergency evacuation analysis failed.")
        return jsonify({
            "success": False,
            "errors": [f"Emergency evacuation analysis failed: {str(err)}"],
            "origin": {"latitude": lat, "longitude": lon},
            "current_risk": None,
            "recommended_destination": None,
            "destinations": [],
            "routes": [],
        }), 500
