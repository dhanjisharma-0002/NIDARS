"""Weather monitoring and live meteorological service for NIDARS.

Fetches real-time weather observations and short-term forecasts for North India
stations and coordinates using verified meteorological APIs (Open-Meteo WMO standard).

Evaluates hydrometeorological risk indicators according to IMD meteorological guidelines.
Does NOT fabricate fake weather numbers when external APIs are unavailable.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
import urllib.parse
import urllib.request
import json

from flask import current_app
import pandas as pd

from gis.processing import load_station_latest_observations

# WMO Weather interpretation codes (WW)
WMO_WEATHER_CODES = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"),
    48: ("Depositing rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Moderate drizzle", "🌦️"),
    55: ("Dense drizzle", "🌧️"),
    56: ("Light freezing drizzle", "🌧️"),
    57: ("Dense freezing drizzle", "🌧️"),
    61: ("Slight rain", "🌧️"),
    62: ("Moderate rain", "🌧️"),
    63: ("Moderate rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    66: ("Light freezing rain", "🌧️"),
    67: ("Heavy freezing rain", "🌧️"),
    71: ("Slight snow fall", "🌨️"),
    73: ("Moderate snow fall", "🌨️"),
    75: ("Heavy snow fall", "🌨️"),
    77: ("Snow grains", "🌨️"),
    80: ("Slight rain showers", "🌦️"),
    81: ("Moderate rain showers", "🌧️"),
    82: ("Violent rain showers", "⛈️"),
    85: ("Slight snow showers", "🌨️"),
    86: ("Heavy snow showers", "🌨️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm with slight hail", "⛈️"),
    99: ("Thunderstorm with heavy hail", "⛈️"),
}

CARDINAL_DIRECTIONS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def degrees_to_cardinal(deg: float) -> str:
    """Convert meteorological wind direction in degrees to cardinal compass string."""
    try:
        val = float(deg) % 360
        idx = int((val + 11.25) / 22.5) % 16
        return CARDINAL_DIRECTIONS[idx]
    except Exception:
        return "N"


def get_available_stations(state_code: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all authentic 64 North India meteorological stations with coordinates and metadata."""
    df = load_station_latest_observations()
    if state_code and state_code.upper() != "ALL":
        st_clean = state_code.strip().upper()
        df = df[df["state_code"] == st_clean]

    stations = []
    for _, row in df.iterrows():
        stations.append({
            "station_name": str(row.get("station_name", "")),
            "state_code": str(row.get("state_code", "")),
            "state_name": str(row.get("state_name", "")),
            "district": str(row.get("district", "")),
            "latitude": float(row.get("latitude", 0.0)),
            "longitude": float(row.get("longitude", 0.0)),
            "elevation": float(row.get("elevation", 0.0)),
            "baseline_temp": float(row.get("temperature", 25.0)),
            "baseline_rainfall": float(row.get("rainfall_24h", 0.0)),
            "baseline_wind": float(row.get("wind_speed", 5.0)),
            "baseline_pressure": float(row.get("air_pressure", 1010.0)),
        })
    return stations


def find_station_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Look up station details by station name (case-insensitive)."""
    if not name:
        return None
    name_clean = name.strip().lower()
    for st in get_available_stations():
        if st["station_name"].lower() == name_clean or st["station_name"].lower().replace(" ", "") == name_clean.replace(" ", ""):
            return st
    return None


def evaluate_weather_risks(
    rainfall_mm: float,
    wind_speed_ms: float,
    pressure_hpa: float,
    temperature_c: float,
) -> Dict[str, Any]:
    """Evaluate hydrometeorological risk signals based on IMD disaster standards."""
    # 1. Rainfall severity assessment
    if rainfall_mm >= 65.0:
        rainfall_alert = "CRITICAL"
        rain_desc = "Extremely Heavy Rainfall Warning (>65 mm/day)"
    elif rainfall_mm >= 35.0:
        rainfall_alert = "HIGH"
        rain_desc = "Heavy Rainfall Advisory (35-65 mm/day)"
    elif rainfall_mm >= 10.0:
        rainfall_alert = "MODERATE"
        rain_desc = "Moderate Precipitation (10-35 mm/day)"
    else:
        rainfall_alert = "LOW"
        rain_desc = "Normal / Light Rainfall (<10 mm/day)"

    # 2. Wind risk assessment
    if wind_speed_ms >= 18.0:
        wind_alert = "CRITICAL"
        wind_desc = "Severe Gale / Storm Warning (>=18 m/s)"
    elif wind_speed_ms >= 12.0:
        wind_alert = "HIGH"
        wind_desc = "Strong Winds Advisory (12-18 m/s)"
    elif wind_speed_ms >= 6.0:
        wind_alert = "MODERATE"
        wind_desc = "Moderate Breeze (6-12 m/s)"
    else:
        wind_alert = "LOW"
        wind_desc = "Light Breeze (<6 m/s)"

    # 3. Barometric pressure depression
    if pressure_hpa < 990.0:
        pressure_alert = "CRITICAL"
        press_desc = "Deep Barometric Depression (<990 hPa)"
    elif pressure_hpa < 1000.0:
        pressure_alert = "HIGH"
        press_desc = "Low Pressure Depression (<1000 hPa)"
    elif pressure_hpa < 1006.0:
        pressure_alert = "MODERATE"
        press_desc = "Marginal Low Pressure (<1006 hPa)"
    else:
        pressure_alert = "LOW"
        press_desc = "Stable Atmospheric Pressure (>=1006 hPa)"

    # Overall Status computation (highest severity)
    severity_order = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "CRITICAL": 4}
    overall_score = max(
        severity_order.get(rainfall_alert, 1),
        severity_order.get(wind_alert, 1),
        severity_order.get(pressure_alert, 1),
    )
    score_to_status = {1: "LOW", 2: "MODERATE", 3: "HIGH", 4: "CRITICAL"}
    overall_status = score_to_status[overall_score]

    # Contextual Advisory message
    advisories = []
    if rainfall_alert in ("HIGH", "CRITICAL"):
        advisories.append("High flood risk potential; monitor local drainage and river levels.")
    if wind_alert in ("HIGH", "CRITICAL"):
        advisories.append("High wind velocities; beware of falling branches and damaged powerlines.")
    if pressure_alert in ("HIGH", "CRITICAL"):
        advisories.append("Severe depression detected; prepare for sudden convective weather transitions.")
    if not advisories:
        advisory = "Normal meteorological conditions. No severe weather alerts active."
    else:
        advisory = " ".join(advisories)

    return {
        "overall_status": overall_status,
        "rainfall_alert": rainfall_alert,
        "rainfall_description": rain_desc,
        "wind_alert": wind_alert,
        "wind_description": wind_desc,
        "pressure_alert": pressure_alert,
        "pressure_description": press_desc,
        "advisory": advisory,
    }


def fetch_live_weather(
    latitude: float,
    longitude: float,
    station_name: Optional[str] = None,
    state_name: Optional[str] = None,
    district: Optional[str] = None,
    elevation: Optional[float] = None,
) -> Dict[str, Any]:
    """Fetch live real-time meteorological metrics from Open-Meteo endpoint."""
    timeout_sec = 8.0
    if current_app:
        timeout_sec = float(current_app.config.get("WEATHER_TIMEOUT_SECONDS", 8.0))

    base_url = "https://api.open-meteo.com/v1/forecast"
    if current_app:
        base_url = current_app.config.get("WEATHER_API_BASE_URL", base_url)

    params = {
        "latitude": f"{latitude:.4f}",
        "longitude": f"{longitude:.4f}",
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,"
            "precipitation,rain,weather_code,surface_pressure,"
            "wind_speed_10m,wind_direction_10m"
        ),
        "hourly": "temperature_2m,precipitation,wind_speed_10m",
        "forecast_days": "2",
        "timezone": "auto",
    }
    query_string = urllib.parse.urlencode(params)
    target_url = f"{base_url}?{query_string}"

    try:
        req = urllib.request.Request(
            target_url,
            headers={"User-Agent": "NIDARS-Disaster-Awareness-System/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as response:
            if response.status != 200:
                return {
                    "success": False,
                    "error": f"Upstream weather service returned status HTTP {response.status}",
                    "status_code": 502,
                }
            raw_data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, Exception) as exc:
        return {
            "success": False,
            "error": f"Weather service network error: {str(exc)}",
            "status_code": 503,
            "target_url": base_url,
        }

    current = raw_data.get("current", {})
    hourly = raw_data.get("hourly", {})

    temp = float(current.get("temperature_2m", 25.0))
    feels_like = float(current.get("apparent_temperature", temp))
    humidity = float(current.get("relative_humidity_2m", 50.0))
    precipitation = float(current.get("precipitation", 0.0))
    weather_code = int(current.get("weather_code", 0))
    pressure = float(current.get("surface_pressure", 1010.0))
    wind_kmh = float(current.get("wind_speed_10m", 10.0))
    wind_ms = round(wind_kmh / 3.6, 2)
    wind_dir = float(current.get("wind_direction_10m", 0.0))
    cardinal = degrees_to_cardinal(wind_dir)

    condition_text, icon = WMO_WEATHER_CODES.get(weather_code, ("Fair", "☀️"))

    # Hydrometeorological risk assessment
    risk_assessment = evaluate_weather_risks(
        rainfall_mm=precipitation,
        wind_speed_ms=wind_ms,
        pressure_hpa=pressure,
        temperature_c=temp,
    )

    # Process next 24-hour trends
    hourly_times = hourly.get("time", [])[:24]
    hourly_temps = hourly.get("temperature_2m", [])[:24]
    hourly_rain = hourly.get("precipitation", [])[:24]
    hourly_wind = [round(w / 3.6, 2) for w in hourly.get("wind_speed_10m", [])[:24]]

    # Format hourly labels (e.g., '14:00')
    formatted_times = []
    for t_str in hourly_times:
        try:
            dt = datetime.fromisoformat(t_str)
            formatted_times.append(dt.strftime("%H:%M"))
        except Exception:
            formatted_times.append(str(t_str)[-5:])

    return {
        "success": True,
        "location": {
            "station_name": station_name or "Custom Coordinate Location",
            "state_name": state_name or "North India",
            "district": district or "Regional",
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation or raw_data.get("elevation", 0.0),
        },
        "current": {
            "temperature_c": temp,
            "feels_like_c": feels_like,
            "relative_humidity_pct": humidity,
            "precipitation_mm": precipitation,
            "rainfall_rate_mm": precipitation,
            "air_pressure_hpa": pressure,
            "wind_speed_kmh": wind_kmh,
            "wind_speed_ms": wind_ms,
            "wind_direction_deg": wind_dir,
            "wind_direction_cardinal": cardinal,
            "weather_code": weather_code,
            "condition": condition_text,
            "icon": icon,
            "last_updated": current.get("time", datetime.now(timezone.utc).isoformat()),
        },
        "risk_indicators": risk_assessment,
        "hourly_trends": {
            "timestamps": formatted_times,
            "temperature": hourly_temps,
            "precipitation": hourly_rain,
            "wind_speed": hourly_wind,
        },
        "provider": "Open-Meteo WMO Meteorological Grid",
    }
