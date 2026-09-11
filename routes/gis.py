"""GIS API endpoints for spatial disaster risk representation, layers, and GeoJSON output."""

from __future__ import annotations

from flask import jsonify, request
from flask_login import login_required

from routes.main import api_bp
from services.gis_service import (
    get_district_boundaries_geojson,
    get_emergency_facilities_geojson,
    get_gis_summary_statistics,
    get_north_india_rivers_geojson,
    get_spatial_risk_data,
)

VALID_HAZARDS = {"flood", "landslide", "combined"}
VALID_FACILITY_TYPES = {"hospital", "police", "shelter", "all"}
VALID_STATES = {"JK", "HP", "UP", "BR", "ALL"}


@api_bp.route("/gis/risk", methods=["GET"])
@login_required
def get_gis_risk():
    """Expose spatial disaster risk GeoJSON FeatureCollection.

    Query parameters:
    - hazard: 'combined' (default), 'flood', 'landslide'
    - state: filter by state (e.g. 'UP', 'HP', 'JK', 'BR')
    - district: filter by district name
    - station: filter by station name substring
    - risk_level: filter by risk level ('LOW', 'MODERATE', 'HIGH', 'CRITICAL')
    - limit: maximum number of stations to return (positive integer)
    - flood_weight, landslide_weight: optional float weights
    """
    hazard = request.args.get("hazard", "combined").strip().lower()
    if hazard not in VALID_HAZARDS:
        return jsonify(
            {
                "success": False,
                "errors": [f"Invalid hazard '{hazard}'. Must be one of: {', '.join(sorted(VALID_HAZARDS))}."],
                "data": None,
            }
        ), 400

    state = request.args.get("state")
    district = request.args.get("district")
    station = request.args.get("station")
    risk_level = request.args.get("risk_level")
    limit_raw = request.args.get("limit")

    limit = None
    if limit_raw:
        try:
            limit = int(limit_raw)
            if limit <= 0:
                raise ValueError()
        except ValueError:
            return jsonify(
                {
                    "success": False,
                    "errors": ["Parameter 'limit' must be a positive integer."],
                    "data": None,
                }
            ), 400

    flood_weight_raw = request.args.get("flood_weight")
    landslide_weight_raw = request.args.get("landslide_weight")
    flood_weight = None
    landslide_weight = None

    if flood_weight_raw is not None:
        try:
            flood_weight = float(flood_weight_raw)
            if flood_weight < 0:
                raise ValueError()
        except ValueError:
            return jsonify({"success": False, "errors": ["flood_weight must be a non-negative number."]}), 400

    if landslide_weight_raw is not None:
        try:
            landslide_weight = float(landslide_weight_raw)
            if landslide_weight < 0:
                raise ValueError()
        except ValueError:
            return jsonify({"success": False, "errors": ["landslide_weight must be a non-negative number."]}), 400

    try:
        geojson_data = get_spatial_risk_data(
            state=state,
            district=district,
            station=station,
            risk_level=risk_level,
            hazard=hazard,
            limit=limit,
            flood_weight=flood_weight,
            landslide_weight=landslide_weight,
        )
        return jsonify(geojson_data), 200
    except Exception as err:
        return jsonify(
            {
                "success": False,
                "errors": [f"Failed to generate GIS spatial risk data: {str(err)}"],
                "data": None,
            }
        ), 500


@api_bp.route("/gis/stats", methods=["GET"])
@login_required
def get_gis_stats():
    """Retrieve live computed spatial risk statistics across stations."""
    hazard = request.args.get("hazard", "combined").strip().lower()
    if hazard not in VALID_HAZARDS:
        hazard = "combined"

    flood_weight_raw = request.args.get("flood_weight")
    landslide_weight_raw = request.args.get("landslide_weight")
    flood_weight = float(flood_weight_raw) if flood_weight_raw is not None else None
    landslide_weight = float(landslide_weight_raw) if landslide_weight_raw is not None else None

    try:
        stats = get_gis_summary_statistics(
            hazard=hazard,
            flood_weight=flood_weight,
            landslide_weight=landslide_weight,
        )
        return jsonify(stats), 200
    except Exception as err:
        return jsonify({"success": False, "errors": [f"Failed to compute GIS stats: {str(err)}"]}), 500


@api_bp.route("/gis/facilities", methods=["GET"])
@login_required
def get_gis_facilities():
    """Retrieve authentic emergency facilities (hospitals, police, shelters) as GeoJSON."""
    f_type = request.args.get("type", "all").strip().lower()
    if f_type not in VALID_FACILITY_TYPES:
        return jsonify({
            "success": False,
            "errors": [f"Invalid facility type '{f_type}'. Must be one of: {', '.join(sorted(VALID_FACILITY_TYPES))}."],
        }), 400

    state = request.args.get("state")
    try:
        data = get_emergency_facilities_geojson(facility_type=f_type, state=state)
        return jsonify(data), 200
    except Exception as err:
        return jsonify({"success": False, "errors": [f"Failed to load facilities layer: {str(err)}"]}), 500


@api_bp.route("/gis/rivers", methods=["GET"])
@login_required
def get_gis_rivers():
    """Retrieve authentic hydrography river line vectors as GeoJSON."""
    try:
        data = get_north_india_rivers_geojson()
        return jsonify(data), 200
    except Exception as err:
        return jsonify({"success": False, "errors": [f"Failed to load river hydrography layer: {str(err)}"]}), 500


@api_bp.route("/gis/boundaries", methods=["GET"])
@login_required
def get_gis_boundaries():
    """Retrieve authentic district and state administrative boundaries as GeoJSON."""
    try:
        data = get_district_boundaries_geojson()
        return jsonify(data), 200
    except Exception as err:
        return jsonify({"success": False, "errors": [f"Failed to load administrative boundaries: {str(err)}"]}), 500
