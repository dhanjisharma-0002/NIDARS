"""Weather monitoring routes and API endpoints for NIDARS."""

from __future__ import annotations

from flask import jsonify, render_template, request

from routes.main import api_bp, main_bp
from services.weather_service import (
    fetch_live_weather,
    find_station_by_name,
    get_available_stations,
)


@main_bp.route("/weather")
def weather_view():
    """Render the NIDARS Weather Monitoring Dashboard."""
    return render_template("weather.html")


@api_bp.route("/weather/stations", methods=["GET"])
def list_weather_stations():
    """Return available authentic North India meteorological stations."""
    state_filter = request.args.get("state")
    stations = get_available_stations(state_code=state_filter)
    return jsonify({
        "success": True,
        "count": len(stations),
        "stations": stations,
    })


@api_bp.route("/weather", methods=["GET"])
def get_live_weather():
    """Return live meteorological metrics and risk indicators for given station or coordinates."""
    station_query = request.args.get("station")
    lat_raw = request.args.get("lat")
    lon_raw = request.args.get("lon")

    # If station name provided, lookup station
    if station_query:
        station = find_station_by_name(station_query)
        if not station:
            return jsonify({
                "success": False,
                "error": f"Station '{station_query}' not found in North India meteorological grid.",
                "valid_stations": [s["station_name"] for s in get_available_stations()[:10]],
            }), 404

        data = fetch_live_weather(
            latitude=station["latitude"],
            longitude=station["longitude"],
            station_name=station["station_name"],
            state_name=station["state_name"],
            district=station["district"],
            elevation=station["elevation"],
        )
        status_code = data.pop("status_code", 200 if data["success"] else 502)
        return jsonify(data), status_code

    # If coordinates provided
    if lat_raw is not None and lon_raw is not None:
        try:
            lat = float(lat_raw)
            lon = float(lon_raw)
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "Coordinates 'lat' and 'lon' must be valid numeric values.",
            }), 400

        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return jsonify({
                "success": False,
                "error": "Coordinates out of bounds. Latitude [-90, 90], Longitude [-180, 180].",
            }), 400

        station_name = request.args.get("name")
        data = fetch_live_weather(
            latitude=lat,
            longitude=lon,
            station_name=station_name,
        )
        status_code = data.pop("status_code", 200 if data["success"] else 502)
        return jsonify(data), status_code

    # Default to Shimla station if no parameter passed
    default_station = find_station_by_name("Shimla") or get_available_stations()[0]
    data = fetch_live_weather(
        latitude=default_station["latitude"],
        longitude=default_station["longitude"],
        station_name=default_station["station_name"],
        state_name=default_station["state_name"],
        district=default_station["district"],
        elevation=default_station["elevation"],
    )
    status_code = data.pop("status_code", 200 if data["success"] else 502)
    return jsonify(data), status_code
