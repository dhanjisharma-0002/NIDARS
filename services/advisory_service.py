"""AI-Based Early Warning and Advisory Service for NIDARS.

Evaluates real spatial flood, landslide, and combined hazard predictions across
North India meteorological stations and translates them into research advisories
and safety recommendations.

MANDATORY DISCLAIMER:
NIDARS provides an academic/research-based advisory signal and is not an official
emergency warning system. Follow official government, NDRF, SDMA and local authority alerts.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Tuple

from extensions import db
from gis.processing import get_spatial_risk_engine, load_station_latest_observations
from gis.risk_zones import (
    classify_combined_risk,
    classify_flood_risk,
    classify_landslide_risk,
)
from models.alert import AlertEvent

DISCLAIMER_TEXT = (
    "NIDARS provides an academic/research-based advisory signal and is not an official "
    "emergency warning system. Follow official government, NDRF, SDMA and local authority alerts."
)

SEVERITY_ORDER = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MODERATE": 2,
    "LOW": 1,
}

SEVERITY_COLORS = {
    "CRITICAL": "#ef4444",
    "HIGH": "#f97316",
    "MODERATE": "#eab308",
    "LOW": "#22c55e",
}

SEVERITY_BADGES = {
    "CRITICAL": "danger",
    "HIGH": "warning",
    "MODERATE": "warning-subtle",
    "LOW": "success",
}


def classify_hazard_risk(hazard_type: str, probability: float) -> str:
    """Classify probability into risk band according to hazard type."""
    try:
        prob = float(probability)
    except (ValueError, TypeError):
        prob = 0.0

    prob = max(0.0, min(1.0, prob))
    hazard = (hazard_type or "combined").lower()

    if hazard == "landslide":
        return classify_landslide_risk(prob)
    elif hazard == "flood":
        return classify_flood_risk(prob)
    else:
        return classify_combined_risk(prob)


def generate_advisory_text(hazard_type: str, risk_level: str, station_name: str, telemetry: Dict[str, Any]) -> str:
    """Generate professional, context-aware academic advisory description."""
    hazard = (hazard_type or "combined").lower()
    r24 = telemetry.get("rainfall_24h", 0.0)
    wind = telemetry.get("wind_speed", 0.0)

    if hazard == "flood":
        if risk_level == "CRITICAL":
            return (
                f"Severe flood hazard detected for {station_name} region with 24h rainfall of {r24:.1f} mm. "
                "Significant risk of waterlogging in low-lying areas and elevated stream levels."
            )
        elif risk_level == "HIGH":
            return (
                f"Elevated flood risk indicated for {station_name}. Continuous precipitation ({r24:.1f} mm) "
                "may cause localized inundation and drainage congestion."
            )
        elif risk_level == "MODERATE":
            return (
                f"Moderate hydrological alert for {station_name}. River runoff and catchment saturation "
                "require precautionary observation."
            )
        else:
            return f"Low hydrological flood risk across {station_name}. Conditions remain within baseline thresholds."

    elif hazard == "landslide":
        elev = telemetry.get("elevation", 0.0)
        if risk_level == "CRITICAL":
            return (
                f"High slope instability and critical landslide risk identified near {station_name} "
                f"(elevation {elev:.0f} m). Saturated soils pose extreme hazard along mountain roads."
            )
        elif risk_level == "HIGH":
            return (
                f"Elevated landslide susceptibility around {station_name}. Heavy cumulative rainfall increases "
                "potential for debris flow and cut-slope failures."
            )
        elif risk_level == "MODERATE":
            return (
                f"Moderate landslide advisory for {station_name} terrain. Exercise caution along vulnerable hillside passes."
            )
        else:
            return f"Minimal landslide probability detected for {station_name}. Slope stability indicators are nominal."

    else:  # Combined
        if risk_level == "CRITICAL":
            return (
                f"Multi-hazard critical advisory for {station_name}. Concurrent flood and landslide signals "
                "indicate severe disruption potential for transport routes and low-lying settlements."
            )
        elif risk_level == "HIGH":
            return (
                f"Elevated multi-hazard risk across {station_name}. Integrated hydrometeorological modeling indicates "
                "compounded regional vulnerabilities."
            )
        elif risk_level == "MODERATE":
            return (
                f"Moderate multi-hazard advisory for {station_name}. Precautionary route planning is recommended."
            )
        else:
            return f"Nominal baseline risk for {station_name}. No critical multi-hazard anomalies detected."


def get_recommended_precautions(hazard_type: str, risk_level: str) -> List[str]:
    """Provide standard actionable precautions for the given hazard and risk level."""
    hazard = (hazard_type or "combined").lower()

    if risk_level == "CRITICAL":
        if hazard == "landslide":
            return [
                "Avoid travel along vulnerable ghat roads and steep hillside corridors.",
                "Stay clear of active drainage gullies, debris fans, and steep road cuts.",
                "Monitor district administration and State Disaster Management Authority (SDMA) directives.",
                "Identify nearby emergency shelters in higher stable terrain."
            ]
        elif hazard == "flood":
            return [
                "Evacuate vulnerable low-lying basements and riverfront zones to higher ground.",
                "Do not drive or walk through moving floodwater or submerged bridges.",
                "Secure emergency kits, drinking water, first aid, and charged communication devices.",
                "Follow official evacuation and alert instructions from NDRF / SDMA."
            ]
        else:
            return [
                "Restrict non-essential travel across mountain passes and river crossings.",
                "Stay updated on district administration emergency broadcasts.",
                "Utilize NIDARS Disaster-Aware Safe Route Optimizer before any transit.",
                "Keep emergency contact numbers and disaster kit accessible."
            ]

    elif risk_level == "HIGH":
        return [
            "Avoid unnecessary travel through low-lying areas and unpaved slopes.",
            "Verify real-time road conditions and alternate safe transit routes.",
            "Inspect local stormwater drains and culverts for blockages.",
            "Keep emergency contact channels open and monitor official weather forecasts."
        ]

    elif risk_level == "MODERATE":
        return [
            "Maintain situational awareness of local weather changes and rainfall trends.",
            "Plan travel routes in advance using disaster-aware navigation.",
            "Ensure emergency contacts and communication devices are charged.",
            "Report any localized waterlogging or minor soil displacement to local authorities."
        ]

    else:  # LOW
        return [
            "Standard baseline awareness; no immediate disruption anticipated.",
            "Regularly monitor routine meteorological forecasts.",
            "Maintain standard personal safety protocols."
        ]


def _make_alert_code(state: str, station_name: str, hazard: str) -> str:
    """Generate a clean, reproducible alert identifier code."""
    st_clean = re.sub(r"[^A-Za-z0-9]", "", state).upper()[:3]
    stn_clean = re.sub(r"[^A-Za-z0-9]", "", station_name).upper()[:4]
    hz_clean = hazard[:3].upper()
    return f"ALT-{st_clean}-{stn_clean}-{hz_clean}"


import time as _time

_scored_stations_cache: Dict[str, Any] = {"records": None, "timestamp": 0.0}


def get_cached_or_fresh_scored_stations(max_age_seconds: float = 30.0) -> List[Dict[str, Any]]:
    """Retrieve station risk evaluations with a short TTL cache to avoid redundant recalculation."""
    now = _time.time()
    cached = _scored_stations_cache.get("records")
    ts = _scored_stations_cache.get("timestamp", 0.0)
    if cached is not None and (now - ts) < max_age_seconds:
        return cached

    engine = get_spatial_risk_engine()
    stations_df = load_station_latest_observations()
    scored = engine.score_station_records(stations_df)
    _scored_stations_cache["records"] = scored
    _scored_stations_cache["timestamp"] = now
    return scored


def generate_live_station_alerts(
    hazard_type: str = "all",
    state: Optional[str] = None,
    district: Optional[str] = None,
    min_risk_level: Optional[str] = None,
    risk_level: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Generate real-time early warning alerts across all validated meteorological stations."""
    scored_records = get_cached_or_fresh_scored_stations()

    target_hazards = ["flood", "landslide", "combined"] if hazard_type in ("all", None, "") else [hazard_type.lower()]
    min_rank = SEVERITY_ORDER.get(min_risk_level.upper(), 1) if min_risk_level else 1
    req_level = risk_level.upper() if risk_level else None
    state_filter = state.upper() if state else None
    district_filter = district.lower() if district else None

    alerts: List[Dict[str, Any]] = []

    for record in scored_records:
        rec_state = record["state"].upper()
        rec_district = record["district"].lower()

        if state_filter and rec_state != state_filter and state_filter not in record["state_name"].upper():
            continue
        if district_filter and district_filter not in rec_district:
            continue

        telemetry = record["features"]

        for hz in target_hazards:
            if hz == "flood":
                prob = record["flood_probability"]
                lvl = record["flood_risk_level"]
            elif hz == "landslide":
                prob = record["landslide_probability"]
                lvl = record["landslide_risk_level"]
            else:
                prob = record["combined_risk"]
                lvl = record["combined_risk_level"]

            if req_level and lvl != req_level:
                continue
            if SEVERITY_ORDER.get(lvl, 1) < min_rank:
                continue

            alert_code = _make_alert_code(record["state"], record["station_name"], hz)
            advisory = generate_advisory_text(hz, lvl, record["station_name"], telemetry)
            precautions = get_recommended_precautions(hz, lvl)

            alerts.append({
                "id": alert_code,
                "alert_code": alert_code,
                "station_name": record["station_name"],
                "district": record["district"],
                "state_code": record["state"],
                "state_name": record["state_name"],
                "hazard_type": hz,
                "probability": prob,
                "probability_pct": f"{prob * 100:.2f}%",
                "risk_level": lvl,
                "severity_rank": SEVERITY_ORDER.get(lvl, 1),
                "badge_color": SEVERITY_COLORS.get(lvl, "#94a3b8"),
                "badge_class": SEVERITY_BADGES.get(lvl, "secondary"),
                "advisory": advisory,
                "precautions": precautions,
                "telemetry": telemetry,
                "latitude": record["latitude"],
                "longitude": record["longitude"],
                "elevation": record["elevation"],
                "observation_date": record["date_of_observation"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "disclaimer": DISCLAIMER_TEXT,
            })

    # Sort alerts by severity descending (CRITICAL -> HIGH -> MODERATE -> LOW) then probability descending
    alerts.sort(key=lambda x: (x["severity_rank"], x["probability"]), reverse=True)

    if limit and limit > 0:
        alerts = alerts[:limit]

    return alerts


def get_advisory_summary_stats() -> Dict[str, Any]:
    """Calculate summary risk statistics across all 64 stations in a single fast pass."""
    scored_records = get_cached_or_fresh_scored_stations()

    distribution = {"CRITICAL": 0, "HIGH": 0, "MODERATE": 0, "LOW": 0}
    flood_summary = {"critical": 0, "high": 0, "moderate": 0, "low": 0}
    landslide_summary = {"critical": 0, "high": 0, "moderate": 0, "low": 0}
    state_distribution: Dict[str, Dict[str, int]] = {}
    top_candidates = []

    for rec in scored_records:
        comb_lvl = rec["combined_risk_level"]
        distribution[comb_lvl] = distribution.get(comb_lvl, 0) + 1

        f_lvl = rec["flood_risk_level"].lower()
        if f_lvl in flood_summary:
            flood_summary[f_lvl] += 1

        ls_lvl = rec["landslide_risk_level"].lower()
        if ls_lvl in landslide_summary:
            landslide_summary[ls_lvl] += 1

        st = rec["state"]
        if st not in state_distribution:
            state_distribution[st] = {"CRITICAL": 0, "HIGH": 0, "MODERATE": 0, "LOW": 0}
        state_distribution[st][comb_lvl] = state_distribution[st].get(comb_lvl, 0) + 1

        top_candidates.append({
            "station_name": rec["station_name"],
            "district": rec["district"],
            "state_code": rec["state"],
            "probability": rec["combined_risk"],
            "probability_pct": f"{rec['combined_risk'] * 100:.2f}%",
            "risk_level": comb_lvl,
        })

    top_risk_locations = sorted(top_candidates, key=lambda x: x["probability"], reverse=True)[:5]
    total_count = len(scored_records)
    active_count = distribution["CRITICAL"] + distribution["HIGH"] + distribution["MODERATE"]

    return {
        "total_monitored_stations": total_count,
        "active_alerts_count": active_count,
        "critical_count": distribution["CRITICAL"],
        "high_count": distribution["HIGH"],
        "moderate_count": distribution["MODERATE"],
        "low_count": distribution["LOW"],
        "distribution": distribution,
        "state_distribution": state_distribution,
        "top_risk_locations": top_risk_locations,
        "flood_summary": flood_summary,
        "landslide_summary": landslide_summary,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "disclaimer": DISCLAIMER_TEXT,
    }


def get_alert_by_id_or_code(alert_id_or_code: str) -> Optional[Dict[str, Any]]:
    """Look up an alert by its ID/code from live station evaluations or database history."""
    clean_id = str(alert_id_or_code).strip().upper()

    # Search live station alerts
    all_alerts = generate_live_station_alerts(hazard_type="all")
    for a in all_alerts:
        if a["id"].upper() == clean_id or a["alert_code"].upper() == clean_id:
            return a

    # Try station name direct match
    for a in all_alerts:
        if a["station_name"].upper() == clean_id or a["district"].upper() == clean_id:
            return a

    # Fallback to database history if inside Flask app context
    from flask import has_app_context
    if has_app_context():
        try:
            is_digit = clean_id.isdigit()
            filter_clause = (AlertEvent.alert_code == clean_id)
            if is_digit:
                filter_clause = filter_clause | (AlertEvent.id == int(clean_id))

            db_alert = AlertEvent.query.filter(filter_clause).first()
            if db_alert:
                return db_alert.to_dict()
        except Exception:
            pass

    return None


def sync_alerts_to_history(min_level: str = "MODERATE") -> int:
    """Non-destructively snapshot high-severity active alerts into MySQL database history."""
    alerts = generate_live_station_alerts(hazard_type="all", min_risk_level=min_level)
    saved_count = 0

    for a in alerts:
        existing = AlertEvent.query.filter_by(alert_code=a["alert_code"]).first()
        if existing:
            # Update existing record
            existing.probability = a["probability"]
            existing.risk_level = a["risk_level"]
            existing.advisory = a["advisory"]
            existing.precautions = a["precautions"]
            existing.telemetry_json = a["telemetry"]
            existing.created_at = datetime.now(timezone.utc)
        else:
            new_event = AlertEvent(
                alert_code=a["alert_code"],
                station_name=a["station_name"],
                district=a["district"],
                state_code=a["state_code"],
                state_name=a["state_name"],
                hazard_type=a["hazard_type"],
                probability=a["probability"],
                risk_level=a["risk_level"],
                advisory=a["advisory"],
                precautions=a["precautions"],
                telemetry_json=a["telemetry"],
                latitude=a["latitude"],
                longitude=a["longitude"],
                elevation=a["elevation"],
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(new_event)
            saved_count += 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return saved_count
