"""OSRM routing integration and route geometry sampling service for NIDARS.

Connects to OpenStreetMap / OSRM routing engine, decodes route geometries,
and samples continuous path coordinates for downstream spatial hazard analysis.
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app

from config import Config


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in kilometers."""
    r = 6371.0  # Earth's radius in kilometers
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return r * c


def validate_coordinates(
    start_lat: Any, start_lon: Any, end_lat: Any, end_lon: Any
) -> Tuple[Optional[Tuple[float, float, float, float]], List[str]]:
    """Validate and clean start and destination latitude/longitude pairs."""
    errors = []
    cleaned = []

    names_and_vals = [
        ("start_lat", start_lat, -90.0, 90.0),
        ("start_lon", start_lon, -180.0, 180.0),
        ("end_lat", end_lat, -90.0, 90.0),
        ("end_lon", end_lon, -180.0, 180.0),
    ]

    for name, val, min_val, max_val in names_and_vals:
        if val is None or str(val).strip() == "":
            errors.append(f"Missing required coordinate parameter '{name}'.")
            continue
        try:
            num = float(val)
        except (ValueError, TypeError):
            errors.append(f"Coordinate '{name}' must be a valid numeric value.")
            continue

        if math.isnan(num) or math.isinf(num):
            errors.append(f"Coordinate '{name}' must be a finite number.")
            continue

        if num < min_val or num > max_val:
            errors.append(f"Coordinate '{name}' must be between {min_val} and {max_val}.")
            continue

        cleaned.append(num)

    if errors:
        return None, errors

    s_lat, s_lon, e_lat, e_lon = cleaned
    if abs(s_lat - e_lat) < 1e-6 and abs(s_lon - e_lon) < 1e-6:
        errors.append("Start location and destination must be distinct points.")
        return None, errors

    return (s_lat, s_lon, e_lat, e_lon), []


def fetch_osrm_routes(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    base_url: Optional[str] = None,
    profile: Optional[str] = None,
    timeout: Optional[float] = None,
    alternatives: bool = True,
) -> Dict[str, Any]:
    """Query OSRM HTTP API for driving route geometries between origin and destination.

    OSRM coordinate format: {longitude},{latitude}
    """
    osrm_url = (base_url or getattr(Config, "OSRM_BASE_URL", "https://router.project-osrm.org")).rstrip("/")
    osrm_profile = profile or getattr(Config, "ROUTE_PROFILE", "driving")
    timeout_sec = timeout if timeout is not None else getattr(Config, "OSRM_TIMEOUT_SECONDS", 10.0)

    # OSRM expects coordinates in lon,lat order
    coords_param = f"{start_lon:.6f},{start_lat:.6f};{end_lon:.6f},{end_lat:.6f}"
    alt_param = "true" if alternatives else "false"
    query_url = f"{osrm_url}/route/v1/{osrm_profile}/{coords_param}?overview=full&geometries=geojson&alternatives={alt_param}&steps=false"

    req = urllib.request.Request(
        query_url,
        headers={"User-Agent": "NIDARS-Disaster-Aware-Router/1.0", "Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as response:
            status_code = response.status
            if status_code != 200:
                return {
                    "success": False,
                    "error_type": "OSRM_HTTP_ERROR",
                    "message": f"OSRM upstream service returned HTTP status {status_code}.",
                    "http_status": 502,
                }
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        try:
            err_body = json.loads(err.read().decode("utf-8"))
            err_msg = err_body.get("message", f"OSRM HTTP {err.code}")
        except Exception:
            err_msg = f"OSRM upstream service HTTP error: {err.code}"
        return {
            "success": False,
            "error_type": "OSRM_HTTP_ERROR",
            "message": err_msg,
            "http_status": 502 if err.code >= 500 else 400,
        }
    except (urllib.error.URLError, TimeoutError) as err:
        return {
            "success": False,
            "error_type": "OSRM_UNAVAILABLE",
            "message": f"Unable to reach OSRM routing service: {str(err)}",
            "http_status": 502,
        }
    except json.JSONDecodeError:
        return {
            "success": False,
            "error_type": "OSRM_INVALID_JSON",
            "message": "OSRM upstream service returned non-JSON response.",
            "http_status": 502,
        }
    except Exception as err:
        return {
            "success": False,
            "error_type": "ROUTING_UNEXPECTED_ERROR",
            "message": f"Unexpected routing failure: {str(err)}",
            "http_status": 500,
        }

    code = payload.get("code")
    if code != "Ok":
        msg = payload.get("message", f"OSRM returned code '{code}'")
        return {
            "success": False,
            "error_type": "NO_ROUTE_FOUND" if code == "NoRoute" else "OSRM_ERROR",
            "message": msg,
            "http_status": 404 if code == "NoRoute" else 400,
        }

    routes = payload.get("routes", [])
    if not routes:
        return {
            "success": False,
            "error_type": "NO_ROUTE_FOUND",
            "message": "No navigable road route found between the specified coordinates.",
            "http_status": 404,
        }

    return {
        "success": True,
        "routes": routes,
        "waypoints": payload.get("waypoints", []),
    }


def sample_route_geometry(
    coordinates_lon_lat: List[List[float]],
    sample_interval_km: float = 1.0,
) -> List[Dict[str, Any]]:
    """Sample coordinates along a route at regular distance intervals.

    Input coordinates format: [[lon, lat], [lon, lat], ...]
    Returns list of dicts with latitude, longitude, and cumulative_distance_km.
    Guarantees start and destination points are included.
    """
    if not coordinates_lon_lat or len(coordinates_lon_lat) < 2:
        return []

    sampled: List[Dict[str, Any]] = []

    # Add origin point
    start_lon, start_lat = coordinates_lon_lat[0][0], coordinates_lon_lat[0][1]
    sampled.append({
        "latitude": round(float(start_lat), 6),
        "longitude": round(float(start_lon), 6),
        "cumulative_distance_km": 0.0,
    })

    total_dist = 0.0
    last_sampled_dist = 0.0

    for i in range(1, len(coordinates_lon_lat)):
        prev_lon, prev_lat = coordinates_lon_lat[i - 1][0], coordinates_lon_lat[i - 1][1]
        curr_lon, curr_lat = coordinates_lon_lat[i][0], coordinates_lon_lat[i][1]

        seg_dist = haversine_distance_km(prev_lat, prev_lon, curr_lat, curr_lon)
        if seg_dist <= 0:
            continue

        target_sample_dist = last_sampled_dist + sample_interval_km

        # Check if one or more sample points fall on this segment
        while (total_dist + seg_dist) >= target_sample_dist:
            fraction = (target_sample_dist - total_dist) / seg_dist
            fraction = max(0.0, min(1.0, fraction))
            interp_lat = prev_lat + fraction * (curr_lat - prev_lat)
            interp_lon = prev_lon + fraction * (curr_lon - prev_lon)

            sampled.append({
                "latitude": round(float(interp_lat), 6),
                "longitude": round(float(interp_lon), 6),
                "cumulative_distance_km": round(float(target_sample_dist), 3),
            })
            last_sampled_dist = target_sample_dist
            target_sample_dist = last_sampled_dist + sample_interval_km

        total_dist += seg_dist

    # Ensure final destination is explicitly included
    end_lon, end_lat = coordinates_lon_lat[-1][0], coordinates_lon_lat[-1][1]
    dist_to_last = haversine_distance_km(sampled[-1]["latitude"], sampled[-1]["longitude"], end_lat, end_lon)

    if dist_to_last > 0.05 or len(sampled) == 1:
        sampled.append({
            "latitude": round(float(end_lat), 6),
            "longitude": round(float(end_lon), 6),
            "cumulative_distance_km": round(float(total_dist), 3),
        })

    return sampled
