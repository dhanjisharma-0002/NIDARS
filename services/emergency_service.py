"""Emergency facility discovery and risk-aware emergency response service for NIDARS.

Queries OpenStreetMap / Overpass API for legitimate nearby hospitals, police stations,
and shelters, calculates geodesic distances, caches verified facilities, and evaluates
safety exposure using existing NIDARS GIS and ML hazard predictions.

IMPORTANT:
- Uses ONLY authentic OpenStreetMap data; does NOT fabricate fake hospitals or police stations.
- If Overpass is unavailable, gracefully falls back to cached verified database records.
- Clearly distinguishes nearest-by-distance from risk-aware safest facility.
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
from extensions import db
from gis.processing import get_spatial_risk_engine, load_station_latest_observations
from gis.risk_zones import (
    calculate_combined_risk,
    classify_combined_risk,
    classify_flood_risk,
    classify_landslide_risk,
)
from models.emergency_facility import (
    FACILITY_HOSPITAL,
    FACILITY_POLICE,
    FACILITY_SHELTER,
    VALID_FACILITY_TYPES,
    EmergencyFacility,
)
from models.emergency_request import EmergencyRequest
from services.routing_service import haversine_distance_km


def validate_emergency_coordinates(lat_raw: Any, lon_raw: Any) -> Tuple[Optional[Tuple[float, float]], List[str]]:
    """Validate and clean latitude and longitude coordinates for emergency requests."""
    errors = []
    if lat_raw is None or str(lat_raw).strip() == "":
        errors.append("Latitude coordinate is required.")
    if lon_raw is None or str(lon_raw).strip() == "":
        errors.append("Longitude coordinate is required.")

    if errors:
        return None, errors

    try:
        lat = float(lat_raw)
        lon = float(lon_raw)
    except (ValueError, TypeError):
        return None, ["Latitude and longitude must be valid numeric values."]

    if math.isnan(lat) or math.isinf(lat) or math.isnan(lon) or math.isinf(lon):
        return None, ["Coordinates must be finite numeric values."]

    if lat < -90.0 or lat > 90.0:
        errors.append("Latitude must be between -90.0 and 90.0 degrees.")
    if lon < -180.0 or lon > 180.0:
        errors.append("Longitude must be between -180.0 and 180.0 degrees.")

    if errors:
        return None, errors

    return (round(lat, 6), round(lon, 6)), []


from functools import lru_cache


@lru_cache(maxsize=16)
def _get_scored_stations(flood_weight: float = 0.50, landslide_weight: float = 0.50) -> List[Dict[str, Any]]:
    """Retrieve and cache scored station hazard observations."""
    engine = get_spatial_risk_engine()
    stations_df = load_station_latest_observations()
    return engine.score_station_records(
        stations_df,
        flood_weight=flood_weight,
        landslide_weight=landslide_weight,
    )


def get_current_location_risk(
    latitude: float,
    longitude: float,
    flood_weight: float = 0.50,
    landslide_weight: float = 0.50,
    station_radius_km: float = 50.0,
) -> Dict[str, Any]:
    """Evaluate current disaster risk exposure at user coordinates using nearest NIDARS station."""
    scored = _get_scored_stations(round(flood_weight, 2), round(landslide_weight, 2))


    nearest_st = None
    min_dist = float("inf")

    for st in scored:
        dist = haversine_distance_km(latitude, longitude, st["latitude"], st["longitude"])
        if dist < min_dist:
            min_dist = dist
            nearest_st = st

    is_covered = (min_dist <= station_radius_km) and (nearest_st is not None)

    if is_covered and nearest_st is not None:
        f_prob = float(nearest_st["flood_probability"])
        l_prob = float(nearest_st["landslide_probability"])
        c_risk = calculate_combined_risk(f_prob, l_prob, flood_weight, landslide_weight)
        f_level = classify_flood_risk(f_prob)
        l_level = classify_landslide_risk(l_prob)
        c_level = classify_combined_risk(c_risk)

        return {
            "is_covered": True,
            "station_distance_km": round(min_dist, 2),
            "nearest_station": nearest_st["station_name"],
            "station_district": nearest_st["district"],
            "station_state": nearest_st["state"],
            "station_state_name": nearest_st["state_name"],
            "flood_probability": f_prob,
            "landslide_probability": l_prob,
            "combined_risk": c_risk,
            "flood_risk_level": f_level,
            "landslide_risk_level": l_level,
            "risk_level": c_level,
        }

    return {
        "is_covered": False,
        "station_distance_km": round(min_dist, 2) if nearest_st else None,
        "nearest_station": nearest_st["station_name"] if nearest_st else None,
        "station_district": nearest_st["district"] if nearest_st else None,
        "station_state": nearest_st["state"] if nearest_st else None,
        "station_state_name": nearest_st["state_name"] if nearest_st else None,
        "flood_probability": None,
        "landslide_probability": None,
        "combined_risk": None,
        "flood_risk_level": "UNKNOWN",
        "landslide_risk_level": "UNKNOWN",
        "risk_level": "UNKNOWN",
    }


def build_overpass_query(latitude: float, longitude: float, facility_type: str = "all", radius_m: int = 15000) -> str:
    """Construct an Overpass QL query for verified OpenStreetMap emergency amenities."""
    timeout_sec = 10

    hospital_clause = f"""
      node["amenity"="hospital"](around:{radius_m},{latitude},{longitude});
      way["amenity"="hospital"](around:{radius_m},{latitude},{longitude});
      node["amenity"="clinic"](around:{radius_m},{latitude},{longitude});
      way["amenity"="clinic"](around:{radius_m},{latitude},{longitude});
    """

    police_clause = f"""
      node["amenity"="police"](around:{radius_m},{latitude},{longitude});
      way["amenity"="police"](around:{radius_m},{latitude},{longitude});
    """

    shelter_clause = f"""
      node["amenity"="shelter"](around:{radius_m},{latitude},{longitude});
      way["amenity"="shelter"](around:{radius_m},{latitude},{longitude});
      node["social_facility"="shelter"](around:{radius_m},{latitude},{longitude});
      way["social_facility"="shelter"](around:{radius_m},{latitude},{longitude});
      node["emergency"="shelter"](around:{radius_m},{latitude},{longitude});
      way["emergency"="shelter"](around:{radius_m},{latitude},{longitude});
    """

    if facility_type == FACILITY_HOSPITAL:
        clauses = hospital_clause
    elif facility_type == FACILITY_POLICE:
        clauses = police_clause
    elif facility_type == FACILITY_SHELTER:
        clauses = shelter_clause
    else:
        clauses = hospital_clause + police_clause + shelter_clause

    query = f"""[out:json][timeout:{timeout_sec}];
    (
      {clauses}
    );
    out center tags;"""
    return query


def _extract_address(tags: Dict[str, Any]) -> str:
    parts = []
    street = tags.get("addr:street") or tags.get("addr:housename")
    if street:
        parts.append(str(street))
    suburb = tags.get("addr:suburb") or tags.get("addr:district")
    if suburb:
        parts.append(str(suburb))
    city = tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village")
    if city:
        parts.append(str(city))
    postcode = tags.get("addr:postcode")
    if postcode:
        parts.append(str(postcode))

    if parts:
        return ", ".join(parts)
    full = tags.get("addr:full")
    return str(full) if full else "Not available"


def _determine_facility_type(tags: Dict[str, Any]) -> str:
    amenity = tags.get("amenity", "").lower()
    social = tags.get("social_facility", "").lower()
    emergency = tags.get("emergency", "").lower()

    if amenity in ("hospital", "clinic"):
        return FACILITY_HOSPITAL
    if amenity == "police":
        return FACILITY_POLICE
    if amenity == "shelter" or social == "shelter" or emergency == "shelter":
        return FACILITY_SHELTER
    return FACILITY_HOSPITAL


def fetch_osm_emergency_facilities(
    latitude: float,
    longitude: float,
    facility_type: str = "all",
    radius_km: float = 15.0,
    max_results: int = 25,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Fetch legitimate emergency facilities from OpenStreetMap via Overpass API."""
    overpass_url = (base_url or getattr(Config, "OVERPASS_BASE_URL", "https://overpass-api.de/api/interpreter")).rstrip("/")
    timeout_sec = timeout if timeout is not None else getattr(Config, "OVERPASS_TIMEOUT_SECONDS", 12.0)
    radius_m = int(radius_km * 1000)

    query = build_overpass_query(latitude, longitude, facility_type=facility_type, radius_m=radius_m)
    data_encoded = urllib.parse.urlencode({"data": query}).encode("utf-8")

    req = urllib.request.Request(
        overpass_url,
        data=data_encoded,
        headers={
            "User-Agent": "NIDARS-Emergency-Service/1.0",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    elements = []
    fetch_success = False

    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as res:
            if res.status == 200:
                payload = json.loads(res.read().decode("utf-8"))
                elements = payload.get("elements", [])
                fetch_success = True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as err:
        current_app.logger.warning(f"Overpass API call failed: {str(err)}. Querying local database facility cache.")

    facilities: List[Dict[str, Any]] = []

    if fetch_success and elements:
        for elem in elements:
            tags = elem.get("tags", {})
            f_type = _determine_facility_type(tags)
            if facility_type != "all" and f_type != facility_type:
                continue

            # Extract coordinates from node lat/lon or way center
            if "lat" in elem and "lon" in elem:
                f_lat = float(elem["lat"])
                f_lon = float(elem["lon"])
            elif "center" in elem:
                f_lat = float(elem["center"].get("lat", 0.0))
                f_lon = float(elem["center"].get("lon", 0.0))
            else:
                continue

            dist_km = haversine_distance_km(latitude, longitude, f_lat, f_lon)
            if dist_km > radius_km:
                continue

            name = tags.get("name") or f"Unnamed {f_type.title()}"
            phone = tags.get("phone") or tags.get("contact:phone") or "Not available"
            hours = tags.get("opening_hours") or "Not available"
            address = _extract_address(tags)
            ext_id = f"osm_{elem.get('type')}_{elem.get('id')}"

            fac = {
                "name": name,
                "facility_type": f_type,
                "latitude": round(f_lat, 6),
                "longitude": round(f_lon, 6),
                "distance_km": round(dist_km, 2),
                "address": address,
                "phone": phone,
                "opening_hours": hours,
                "source": "OpenStreetMap",
                "external_id": ext_id,
            }
            facilities.append(fac)

        # Cache in database
        _cache_facilities_to_db(facilities)
    else:
        # Fallback to cached DB records within radius
        facilities = _get_cached_facilities_from_db(latitude, longitude, facility_type, radius_km)

    # Sort nearest first
    facilities.sort(key=lambda x: x["distance_km"])
    if max_results and len(facilities) > max_results:
        facilities = facilities[:max_results]

    return {
        "success": True,
        "total_found": len(facilities),
        "source": "OpenStreetMap (Live)" if fetch_success else "Verified Database Cache",
        "facilities": facilities,
    }


def _cache_facilities_to_db(facilities: List[Dict[str, Any]]):
    """Store or update verified OSM facilities in MySQL without duplicates."""
    try:
        for f in facilities:
            ext_id = f.get("external_id")
            if not ext_id:
                continue
            existing = EmergencyFacility.query.filter_by(external_id=ext_id).first()
            if existing:
                existing.name = f["name"]
                existing.latitude = f["latitude"]
                existing.longitude = f["longitude"]
                existing.address = f["address"] if f["address"] != "Not available" else existing.address
                existing.phone = f["phone"] if f["phone"] != "Not available" else existing.phone
                existing.opening_hours = f["opening_hours"] if f["opening_hours"] != "Not available" else existing.opening_hours
            else:
                new_fac = EmergencyFacility(
                    name=f["name"],
                    facility_type=f["facility_type"],
                    latitude=f["latitude"],
                    longitude=f["longitude"],
                    address=f["address"] if f["address"] != "Not available" else None,
                    phone=f["phone"] if f["phone"] != "Not available" else None,
                    opening_hours=f["opening_hours"] if f["opening_hours"] != "Not available" else None,
                    source=f.get("source", "OpenStreetMap"),
                    external_id=ext_id,
                    is_active=True,
                )
                db.session.add(new_fac)
        db.session.commit()
    except Exception as err:
        db.session.rollback()
        current_app.logger.warning(f"Failed to cache emergency facilities to DB: {str(err)}")


def _get_cached_facilities_from_db(
    latitude: float,
    longitude: float,
    facility_type: str = "all",
    radius_km: float = 15.0,
) -> List[Dict[str, Any]]:
    """Retrieve locally cached verified emergency facilities within radius."""
    try:
        query = EmergencyFacility.query.filter_by(is_active=True)
        if facility_type != "all":
            query = query.filter_by(facility_type=facility_type)

        records = query.all()
        results = []
        for r in records:
            dist = haversine_distance_km(latitude, longitude, float(r.latitude), float(r.longitude))
            if dist <= radius_km:
                d = r.to_dict()
                d["distance_km"] = round(dist, 2)
                results.append(d)
        return results
    except Exception as err:
        current_app.logger.warning(f"Failed to retrieve cached facilities: {str(err)}")
        return []


def rank_facilities_by_safety(
    facilities: List[Dict[str, Any]],
    user_lat: float,
    user_lon: float,
    flood_weight: float = 0.50,
    landslide_weight: float = 0.50,
) -> List[Dict[str, Any]]:
    """Calculate safety scores for facilities combining distance and localized disaster risk."""
    for fac in facilities:
        f_lat = fac["latitude"]
        f_lon = fac["longitude"]
        dist_km = fac["distance_km"]

        # Evaluate risk at facility location
        fac_risk = get_current_location_risk(f_lat, f_lon, flood_weight=flood_weight, landslide_weight=landslide_weight)
        c_risk = fac_risk["combined_risk"] if fac_risk["is_covered"] and fac_risk["combined_risk"] is not None else 0.0

        # Safety cost: distance_km * (1 + 2.0 * combined_risk)
        safety_cost = round(dist_km * (1.0 + 2.0 * c_risk), 3)

        fac["facility_risk"] = fac_risk
        fac["safety_cost"] = safety_cost
        fac["has_risk_assessment"] = fac_risk["is_covered"]

    # Sort by safety cost
    safety_ranked = sorted(facilities, key=lambda x: x["safety_cost"])
    return safety_ranked


def log_emergency_request(
    user_id: Optional[int],
    latitude: float,
    longitude: float,
    request_type: str,
    facility_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    flood_prob: Optional[float] = None,
    landslide_prob: Optional[float] = None,
    summary: Optional[Dict[str, Any]] = None,
):
    """Log an operational emergency search or route request to MySQL."""
    try:
        req_entry = EmergencyRequest(
            user_id=user_id,
            latitude=latitude,
            longitude=longitude,
            request_type=request_type,
            facility_type=facility_type,
            risk_level=risk_level,
            flood_probability=flood_prob,
            landslide_probability=landslide_prob,
            result_summary=summary,
        )
        db.session.add(req_entry)
        db.session.commit()
    except Exception as err:
        db.session.rollback()
        current_app.logger.warning(f"Failed to log emergency request: {str(err)}")


def calculate_safe_zone_score(
    dest_risk: float,
    route_risk: float,
    distance_km: float,
    facility_type: str,
    max_distance_km: float = 50.0,
    w_dest: Optional[float] = None,
    w_route: Optional[float] = None,
    w_dist: Optional[float] = None,
    w_type: Optional[float] = None,
) -> float:
    """Calculate transparent deterministic Safe Zone Score.

    Formula:
        Score = (W_dest * dest_risk) + (W_route * route_risk) + (W_dist * D_norm) + (W_type * P_type)

    Weights:
        W_dest: 0.40 (destination hazard)
        W_route: 0.35 (en-route corridor hazard)
        W_dist: 0.20 (proximity)
        W_type: 0.05 (facility suitability)

    Facility priority offset (P_type):
        - Shelter: 0.00 (primary evacuation destination)
        - Hospital: 0.05 (medical priority)
        - Police: 0.10 (security / coordination point)

    Rule: Lower score = safer/better destination.
    """
    wd = w_dest if w_dest is not None else float(getattr(Config, "EVACUATION_WEIGHT_DEST_RISK", 0.40))
    wr = w_route if w_route is not None else float(getattr(Config, "EVACUATION_WEIGHT_ROUTE_RISK", 0.35))
    w_d = w_dist if w_dist is not None else float(getattr(Config, "EVACUATION_WEIGHT_DISTANCE", 0.20))
    wt = w_type if w_type is not None else float(getattr(Config, "EVACUATION_WEIGHT_TYPE", 0.05))

    p_type_map = {
        FACILITY_SHELTER: 0.00,
        FACILITY_HOSPITAL: 0.05,
        FACILITY_POLICE: 0.10,
    }
    p_type = p_type_map.get(facility_type.lower(), 0.08)

    max_d = max(1.0, max_distance_km)
    d_norm = min(1.0, max(0.0, distance_km / max_d))

    score = (wd * max(0.0, min(1.0, dest_risk))) + \
            (wr * max(0.0, min(1.0, route_risk))) + \
            (w_d * d_norm) + \
            (wt * p_type)

    return round(float(score), 3)


def generate_recommendation_reason(
    facility: Dict[str, Any],
    is_shelter: bool,
    dest_risk_level: str,
    route_risk_level: str,
    dist_km: float,
    eta_min: float,
) -> str:
    """Construct an authentic, deterministic explanation for the safe zone recommendation."""
    if is_shelter and route_risk_level in ("LOW", "MODERATE") and dest_risk_level in ("LOW", "MODERATE"):
        return (
            f"Dedicated relief shelter with low destination risk ({dest_risk_level}) "
            f"and safe road corridor ({route_risk_level}) within {dist_km:.1f} km (~{eta_min:.0f} min)."
        )
    if dest_risk_level == "LOW" and route_risk_level == "LOW":
        return (
            f"Lowest combined destination hazard ({dest_risk_level}) and evacuation route exposure "
            f"({dist_km:.1f} km, ~{eta_min:.0f} min)."
        )
    if route_risk_level in ("LOW", "MODERATE"):
        return (
            f"Safest accessible evacuation corridor ({route_risk_level} route risk) "
            f"to {facility['facility_type'].title()} within {dist_km:.1f} km."
        )
    return (
        f"Optimal available emergency facility with lowest multi-factor risk score "
        f"({dist_km:.1f} km, ~{eta_min:.0f} min)."
    )


def analyze_evacuation_safe_zones(
    user_lat: float,
    user_lon: float,
    max_distance_km: Optional[float] = None,
    facility_types: Optional[List[str]] = None,
    flood_weight: Optional[float] = None,
    landslide_weight: Optional[float] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Perform production-grade risk-aware safe zone and emergency evacuation analysis.

    Reuses existing NIDARS GIS risk model predictions, authentic MySQL/OSM facilities,
    and OSRM route risk evaluation.
    """
    from datetime import datetime, timezone
    from services.route_risk_service import classify_risk_level, get_route_risk_analyzer
    from services.routing_service import fetch_osrm_routes

    search_radius = float(max_distance_km if max_distance_km is not None else getattr(Config, "EVACUATION_MAX_DISTANCE_KM", 25.0))
    fw = float(flood_weight if flood_weight is not None else getattr(Config, "GIS_FLOOD_WEIGHT", 0.50))
    lw = float(landslide_weight if landslide_weight is not None else getattr(Config, "GIS_LANDSLIDE_WEIGHT", 0.50))
    max_candidates = int(getattr(Config, "EVACUATION_MAX_CANDIDATES", 5))

    # 1. Current location disaster risk assessment
    current_risk = get_current_location_risk(user_lat, user_lon, flood_weight=fw, landslide_weight=lw)

    # 2. Query verified facilities (MySQL cache first, stepped Overpass if needed)
    valid_filter_types = set(facility_types) if facility_types else {FACILITY_HOSPITAL, FACILITY_POLICE, FACILITY_SHELTER}
    cached_facilities = _get_cached_facilities_from_db(user_lat, user_lon, facility_type="all", radius_km=search_radius)
    
    # Filter by user-requested facility types
    candidates = [f for f in cached_facilities if f.get("facility_type") in valid_filter_types]

    # If few cached records exist, attempt stepped OSM query to augment cache (skip live network in testing mode)
    is_testing = current_app and current_app.config.get("TESTING", False)
    if len(candidates) < 3 and not is_testing:
        for step_radius in (5.0, 15.0, search_radius):
            try:
                osm_res = fetch_osm_emergency_facilities(
                    latitude=user_lat,
                    longitude=user_lon,
                    facility_type="all",
                    radius_km=step_radius,
                    max_results=30,
                )
                if osm_res.get("facilities"):
                    fresh = [f for f in osm_res["facilities"] if f.get("facility_type") in valid_filter_types]
                    # Merge uniquely by name + lat/lon
                    seen_keys = {(c["name"], round(c["latitude"], 4), round(c["longitude"], 4)) for c in candidates}
                    for f in fresh:
                        key = (f["name"], round(f["latitude"], 4), round(f["longitude"], 4))
                        if key not in seen_keys:
                            seen_keys.add(key)
                            candidates.append(f)
                    if len(candidates) >= 5:
                        break
            except Exception as err:
                current_app.logger.warning(f"OSM stepped facility fetch failed: {str(err)}")
                break

    # If no facilities found in radius
    if not candidates:
        return {
            "success": True,
            "origin": {"latitude": user_lat, "longitude": user_lon},
            "current_risk": current_risk,
            "recommended_destination": None,
            "destinations": [],
            "routes": [],
            "total_found": 0,
            "search_radius_km": search_radius,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": (
                "NIDARS Emergency Evacuation is an academic research prototype. "
                "For real-world emergencies, always follow official orders from local authorities, NDRF, and police."
            ),
            "message": f"No emergency facilities found within {search_radius} km.",
        }

    # 3. Evaluate destination hazard risk for candidates
    for c in candidates:
        f_lat = c["latitude"]
        f_lon = c["longitude"]
        fac_risk = get_current_location_risk(f_lat, f_lon, flood_weight=fw, landslide_weight=lw)
        dest_c_risk = fac_risk["combined_risk"] if fac_risk["is_covered"] and fac_risk["combined_risk"] is not None else 0.15
        c["destination_risk"] = round(dest_c_risk, 4)
        c["destination_risk_level"] = fac_risk.get("risk_level", classify_risk_level(dest_c_risk))
        c["destination_flood_risk"] = fac_risk.get("flood_probability")
        c["destination_landslide_risk"] = fac_risk.get("landslide_probability")
        c["preliminary_cost"] = round(c["distance_km"] * (1.0 + 2.0 * dest_c_risk), 3)

    # Sort and take top N candidates for road routing
    candidates.sort(key=lambda x: x["preliminary_cost"])
    eval_candidates = candidates[:max_candidates]

    # 4. Calculate actual road routes via OSRM & RouteRiskAnalyzer
    analyzer = get_route_risk_analyzer()
    all_evaluated_destinations = []
    all_routes = []

    for idx, cand in enumerate(eval_candidates):
        dest_lat = cand["latitude"]
        dest_lon = cand["longitude"]
        dest_name = cand.get("name", f"Facility {idx + 1}")
        fac_type = cand.get("facility_type", "facility")

        # Fetch road routes
        osrm_res = fetch_osrm_routes(
            start_lat=user_lat,
            start_lon=user_lon,
            end_lat=dest_lat,
            end_lon=dest_lon,
            alternatives=False,
        )

        route_success = osrm_res.get("success", False) and bool(osrm_res.get("routes"))
        if route_success:
            raw_route = osrm_res["routes"][0]
            try:
                eval_res = analyzer.evaluate_routes(
                    raw_routes=[raw_route],
                    sample_interval_km=getattr(Config, "ROUTE_SAMPLE_INTERVAL_KM", 1.0),
                    station_radius_km=getattr(Config, "ROUTE_STATION_RADIUS_KM", 50.0),
                    flood_weight=fw,
                    landslide_weight=lw,
                    penalty_factor=getattr(Config, "ROUTE_RISK_PENALTY_FACTOR", 10.0),
                    min_confidence_coverage=getattr(Config, "ROUTE_MIN_CONFIDENCE_COVERAGE", 30.0),
                )
                evaluated_route = eval_res["routes"][0]
                metrics = evaluated_route["metrics"]

                r_dist_km = metrics["distance_km"]
                r_dur_min = metrics["duration_minutes"]
                r_risk = metrics["average_combined_risk"]
                r_risk_level = metrics["risk_level"]
                r_flood_exposure = metrics["flood_risk_level"]
                r_landslide_exposure = metrics["landslide_risk_level"]
                r_geom = evaluated_route.get("geometry")
                r_points = evaluated_route.get("sampled_points", [])
            except Exception as e:
                current_app.logger.warning(f"Route risk analysis error for {dest_name}: {str(e)}")
                route_success = False

        if not route_success:
            # Fallback to geodesic estimate if OSRM is unreachable
            r_dist_km = cand["distance_km"]
            r_dur_min = round((r_dist_km / 35.0) * 60.0, 1)  # Est. driving at 35 km/h
            r_risk = cand["destination_risk"]
            r_risk_level = cand["destination_risk_level"]
            r_flood_exposure = classify_risk_level(cand.get("destination_flood_risk"))
            r_landslide_exposure = classify_risk_level(cand.get("destination_landslide_risk"))
            r_geom = {
                "type": "LineString",
                "coordinates": [[user_lon, user_lat], [dest_lon, dest_lat]],
            }
            r_points = []

        # 5. Compute Safe Zone Score
        score = calculate_safe_zone_score(
            dest_risk=cand["destination_risk"],
            route_risk=r_risk,
            distance_km=r_dist_km,
            facility_type=fac_type,
            max_distance_km=search_radius,
        )

        cand_data = {
            "id": cand.get("id"),
            "name": dest_name,
            "facility_type": fac_type,
            "latitude": dest_lat,
            "longitude": dest_lon,
            "address": cand.get("address", "Not available"),
            "phone": cand.get("phone", "Not available"),
            "opening_hours": cand.get("opening_hours", "Not available"),
            "source": cand.get("source", "OpenStreetMap"),
            "distance_km": r_dist_km,
            "duration_minutes": r_dur_min,
            "destination_risk": cand["destination_risk"],
            "destination_risk_level": cand["destination_risk_level"],
            "route_risk": round(r_risk, 4),
            "route_risk_level": r_risk_level,
            "flood_exposure": r_flood_exposure,
            "landslide_exposure": r_landslide_exposure,
            "overall_score": score,
            "route_geometry": r_geom,
            "has_road_route": route_success,
        }
        all_evaluated_destinations.append(cand_data)

    # 6. Rank destinations by Safe Zone Score (lower score = safer/better)
    all_evaluated_destinations.sort(key=lambda x: x["overall_score"])

    # 7. Select recommended destination and build reasons
    recommended = all_evaluated_destinations[0]
    for i, dest in enumerate(all_evaluated_destinations):
        is_rec = (i == 0)
        dest["is_recommended"] = is_rec
        dest["rank"] = i + 1
        dest["reason"] = generate_recommendation_reason(
            facility=dest,
            is_shelter=(dest["facility_type"] == FACILITY_SHELTER),
            dest_risk_level=dest["destination_risk_level"],
            route_risk_level=dest["route_risk_level"],
            dist_km=dest["distance_km"],
            eta_min=dest["duration_minutes"],
        )

        # Build route object for map rendering
        all_routes.append({
            "destination_name": dest["name"],
            "facility_type": dest["facility_type"],
            "destination_coords": [dest["latitude"], dest["longitude"]],
            "is_recommended": is_rec,
            "distance_km": dest["distance_km"],
            "duration_minutes": dest["duration_minutes"],
            "route_risk_level": dest["route_risk_level"],
            "overall_score": dest["overall_score"],
            "geometry": dest["route_geometry"],
        })

    # 8. Operational logging to EmergencyRequest
    log_emergency_request(
        user_id=user_id,
        latitude=user_lat,
        longitude=user_lon,
        request_type="evacuation_analysis",
        risk_level=current_risk.get("risk_level"),
        flood_prob=current_risk.get("flood_probability"),
        landslide_prob=current_risk.get("landslide_probability"),
        summary={
            "recommended_destination": recommended["name"],
            "facility_type": recommended["facility_type"],
            "distance_km": recommended["distance_km"],
            "overall_score": recommended["overall_score"],
            "total_candidates": len(all_evaluated_destinations),
        },
    )

    return {
        "success": True,
        "origin": {"latitude": user_lat, "longitude": user_lon},
        "current_risk": current_risk,
        "recommended_destination": recommended,
        "destinations": all_evaluated_destinations,
        "routes": all_routes,
        "total_found": len(all_evaluated_destinations),
        "search_radius_km": search_radius,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": (
            "NIDARS Emergency Evacuation is an academic research prototype. "
            "For real-world emergencies, always follow official orders from local authorities, NDRF, and police."
        ),
    }
