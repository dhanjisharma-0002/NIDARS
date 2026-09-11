"""What-If Disaster Risk Simulation Service for NIDARS.

Allows users to simulate how changing environmental variables affect flood,
landslide, and combined multi-hazard risk predictions using real trained ML pipelines.

IMPORTANT:
- Reuses existing trained Flood and Landslide ML services (services.flood_service and services.landslide_service).
- Does not create synthetic or fake prediction models.
- Results are explicitly flagged as academic simulations, not official government forecasts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import current_app

from config import Config
from gis.processing import load_station_latest_observations
from gis.risk_zones import calculate_combined_risk, classify_combined_risk
from ml.flood.feature_schema import (
    FEATURE_COLUMNS,
    validate_feature_payload as validate_flood_payload,
)
from ml.landslide.feature_schema import (
    validate_feature_payload as validate_landslide_payload,
)
from services.flood_service import (
    model_status as flood_model_status,
    predict_from_payload as predict_flood_payload,
)
from services.landslide_service import (
    model_status as landslide_model_status,
    predict_from_payload as predict_landslide_payload,
)

SIMULATION_DISCLAIMER = (
    "This simulation demonstrates model response to user-defined scenarios. "
    "It is not a real-time official forecast."
)

FEATURE_UNITS = {
    "rainfall_24h": "mm",
    "rainfall_72h": "mm",
    "rainfall_7d": "mm",
    "temperature": "°C",
    "wind_speed": "km/h",
    "air_pressure": "hPa",
    "elevation": "m",
    "latitude": "°N",
    "longitude": "°E",
}

PRESET_SCENARIOS = [
    {
        "id": "heavy_rainfall",
        "name": "Heavy Rainfall Surge",
        "icon": "🌧️",
        "description": "Simulates intensive monsoon precipitation (+50mm 24h, +100mm 72h, +150mm 7d).",
        "deltas": {
            "rainfall_24h": 50.0,
            "rainfall_72h": 100.0,
            "rainfall_7d": 150.0,
        },
    },
    {
        "id": "extreme_rainfall",
        "name": "Extreme Cloudburst / Deluge",
        "icon": "⛈️",
        "description": "Simulates torrential cloudburst conditions (+150mm 24h, +250mm 72h, +400mm 7d).",
        "deltas": {
            "rainfall_24h": 150.0,
            "rainfall_72h": 250.0,
            "rainfall_7d": 400.0,
        },
    },
    {
        "id": "high_wind",
        "name": "Severe Gale & Storm Winds",
        "icon": "💨",
        "description": "Simulates high gale-force winds (+45 km/h) and moderate pressure dip (-15 hPa).",
        "deltas": {
            "wind_speed": 45.0,
            "air_pressure": -15.0,
            "rainfall_24h": 25.0,
        },
    },
    {
        "id": "low_pressure",
        "name": "Deep Cyclonic Depression",
        "icon": "🌪️",
        "description": "Simulates barometric depression (-30 hPa) with sustained rainfall (+40mm 24h, +80mm 72h).",
        "deltas": {
            "air_pressure": -30.0,
            "rainfall_24h": 40.0,
            "rainfall_72h": 80.0,
        },
    },
]


def get_simulation_presets() -> List[Dict[str, Any]]:
    """Return available environmental preset scenarios."""
    return PRESET_SCENARIOS


def get_station_baselines(limit: int = 20) -> List[Dict[str, Any]]:
    """Return genuine station observations from North India to serve as baseline presets."""
    try:
        df = load_station_latest_observations()
        if df.empty:
            return []

        records = []
        for _, row in df.head(limit).iterrows():
            st_data = {
                "station_name": str(row.get("station_name", "Unknown Station")),
                "district": str(row.get("district", "Unknown")),
                "state": str(row.get("state", "Unknown")),
                "features": {
                    "rainfall_24h": float(row.get("rainfall_24h", 0.0)),
                    "rainfall_72h": float(row.get("rainfall_72h", 0.0)),
                    "rainfall_7d": float(row.get("rainfall_7d", 0.0)),
                    "temperature": float(row.get("temperature", 25.0)),
                    "wind_speed": float(row.get("wind_speed", 10.0)),
                    "air_pressure": float(row.get("air_pressure", 1010.0)),
                    "elevation": float(row.get("elevation", 300.0)),
                    "latitude": float(row.get("latitude", 28.0)),
                    "longitude": float(row.get("longitude", 77.0)),
                },
            }
            records.append(st_data)
        return records
    except Exception:
        current_app.logger.exception("Failed to load station baselines for simulator")
        return []


def simulate_risk_scenario(
    current_payload: Dict[str, Any],
    scenario_payload: Dict[str, Any],
    hazard_type: str = "combined",
    flood_weight: Optional[float] = None,
    landslide_weight: Optional[float] = None,
) -> Dict[str, Any]:
    """Simulate risk changes between baseline and scenario environmental conditions.

    Parameters:
    - current_payload: Dict with canonical feature keys for current baseline
    - scenario_payload: Dict with canonical feature keys for simulated scenario
    - hazard_type: 'combined', 'flood', or 'landslide'
    - flood_weight: Weight for flood in combined calculation (default 0.50)
    - landslide_weight: Weight for landslide in combined calculation (default 0.50)
    """
    current_app.logger.info("Simulation request received for hazard_type: %s", hazard_type)

    # 1. Validate baseline payload using canonical schema validation
    cleaned_current, current_errors = validate_flood_payload(current_payload)
    if current_errors:
        current_app.logger.warning("Simulation validation error (current features): %s", current_errors)
        return {
            "success": False,
            "errors": [f"Current conditions: {e}" for e in current_errors],
            "http_status": 400,
        }

    # 2. Validate scenario payload using canonical schema validation
    cleaned_scenario, scenario_errors = validate_flood_payload(scenario_payload)
    if scenario_errors:
        current_app.logger.warning("Simulation validation error (scenario features): %s", scenario_errors)
        return {
            "success": False,
            "errors": [f"Scenario conditions: {e}" for e in scenario_errors],
            "http_status": 400,
        }

    # 3. Check ML model readiness via existing services
    f_status = flood_model_status()
    l_status = landslide_model_status()
    if f_status != "trained" or l_status != "trained":
        errs = []
        if f_status != "trained":
            errs.append("Flood model is not trained yet.")
        if l_status != "trained":
            errs.append("Landslide model is not trained yet.")
        current_app.logger.warning("Simulation models unavailable: %s", errs)
        return {
            "success": False,
            "errors": errs,
            "http_status": 503,
        }

    # 4. Resolve weights
    fw = flood_weight if flood_weight is not None else getattr(Config, "GIS_FLOOD_WEIGHT", 0.50)
    lw = landslide_weight if landslide_weight is not None else getattr(Config, "GIS_LANDSLIDE_WEIGHT", 0.50)

    # 5. Execute ML Inferences via existing Flood and Landslide services
    current_app.logger.info("Calling existing Flood ML service for current & scenario...")
    curr_flood_res = predict_flood_payload(cleaned_current, persist=False)
    if not curr_flood_res["success"]:
        return {
            "success": False,
            "errors": [f"Current flood prediction error: {e}" for e in curr_flood_res.get("errors", [])],
            "http_status": curr_flood_res.get("http_status", 400),
        }

    scen_flood_res = predict_flood_payload(cleaned_scenario, persist=False)
    if not scen_flood_res["success"]:
        return {
            "success": False,
            "errors": [f"Scenario flood prediction error: {e}" for e in scen_flood_res.get("errors", [])],
            "http_status": scen_flood_res.get("http_status", 400),
        }

    current_app.logger.info("Calling existing Landslide ML service for current & scenario...")
    curr_ls_res = predict_landslide_payload(cleaned_current, persist=False)
    if not curr_ls_res["success"]:
        return {
            "success": False,
            "errors": [f"Current landslide prediction error: {e}" for e in curr_ls_res.get("errors", [])],
            "http_status": curr_ls_res.get("http_status", 400),
        }

    scen_ls_res = predict_landslide_payload(cleaned_scenario, persist=False)
    if not scen_ls_res["success"]:
        return {
            "success": False,
            "errors": [f"Scenario landslide prediction error: {e}" for e in scen_ls_res.get("errors", [])],
            "http_status": scen_ls_res.get("http_status", 400),
        }

    curr_flood_prob = float(curr_flood_res["prediction"]["flood_probability"])
    scen_flood_prob = float(scen_flood_res["prediction"]["flood_probability"])
    curr_flood_lvl = str(curr_flood_res["prediction"]["risk_level"])
    scen_flood_lvl = str(scen_flood_res["prediction"]["risk_level"])

    curr_ls_prob = float(curr_ls_res["prediction"]["landslide_probability"])
    scen_ls_prob = float(scen_ls_res["prediction"]["landslide_probability"])
    curr_ls_lvl = str(curr_ls_res["prediction"]["risk_level"])
    scen_ls_lvl = str(scen_ls_res["prediction"]["risk_level"])

    # 6. Combined Multi-Hazard Risk calculation
    curr_combined_risk = calculate_combined_risk(
        flood_prob=curr_flood_prob,
        landslide_prob=curr_ls_prob,
        flood_weight=fw,
        landslide_weight=lw,
    )
    scen_combined_risk = calculate_combined_risk(
        flood_prob=scen_flood_prob,
        landslide_prob=scen_ls_prob,
        flood_weight=fw,
        landslide_weight=lw,
    )

    curr_comb_lvl = classify_combined_risk(curr_combined_risk)
    scen_comb_lvl = classify_combined_risk(scen_combined_risk)

    # 7. Compute Deltas & Metrics
    flood_delta_pts = round((scen_flood_prob - curr_flood_prob) * 100.0, 2)
    ls_delta_pts = round((scen_ls_prob - curr_ls_prob) * 100.0, 2)
    comb_delta_pts = round((scen_combined_risk - curr_combined_risk) * 100.0, 2)

    comb_rel_change = (
        round(((scen_combined_risk - curr_combined_risk) / curr_combined_risk) * 100.0, 1)
        if curr_combined_risk > 0
        else (0.0 if scen_combined_risk == 0 else 100.0)
    )

    # Determine dominant hazard focus for impact statement
    hazard_norm = (hazard_type or "combined").lower().strip()
    if hazard_norm == "flood":
        active_delta = flood_delta_pts
        active_curr_lvl = curr_flood_lvl
        active_scen_lvl = scen_flood_lvl
        active_hazard_name = "Flood Risk"
    elif hazard_norm == "landslide":
        active_delta = ls_delta_pts
        active_curr_lvl = curr_ls_lvl
        active_scen_lvl = scen_ls_lvl
        active_hazard_name = "Landslide Risk"
    else:
        active_delta = comb_delta_pts
        active_curr_lvl = curr_comb_lvl
        active_scen_lvl = scen_comb_lvl
        active_hazard_name = "Combined Disaster Risk"
        hazard_norm = "combined"

    # Human-readable impact summary
    if active_delta > 0:
        impact_summary = (
            f"{active_hazard_name} increased by +{active_delta} percentage points "
            f"({active_curr_lvl} → {active_scen_lvl})."
        )
        impact_direction = "INCREASED"
    elif active_delta < 0:
        impact_summary = (
            f"{active_hazard_name} decreased by {active_delta} percentage points "
            f"({active_curr_lvl} → {active_scen_lvl})."
        )
        impact_direction = "DECREASED"
    else:
        impact_summary = f"{active_hazard_name} remained unchanged at {active_curr_lvl}."
        impact_direction = "UNCHANGED"

    # Feature Delta Breakdown Table
    feature_deltas = []
    for col in FEATURE_COLUMNS:
        c_val = cleaned_current[col]
        s_val = cleaned_scenario[col]
        d_val = round(s_val - c_val, 2)
        feature_deltas.append({
            "feature": col,
            "label": col.replace("_", " ").title(),
            "unit": FEATURE_UNITS.get(col, ""),
            "current_value": c_val,
            "scenario_value": s_val,
            "delta": d_val,
            "has_changed": abs(d_val) > 1e-4,
        })

    return {
        "success": True,
        "hazard_type": hazard_norm,
        "current": {
            "flood_probability": round(curr_flood_prob, 4),
            "landslide_probability": round(curr_ls_prob, 4),
            "combined_risk": round(curr_combined_risk, 4),
            "risk_level": curr_comb_lvl,
            "flood_risk_level": curr_flood_lvl,
            "landslide_risk_level": curr_ls_lvl,
        },
        "scenario": {
            "flood_probability": round(scen_flood_prob, 4),
            "landslide_probability": round(scen_ls_prob, 4),
            "combined_risk": round(scen_combined_risk, 4),
            "risk_level": scen_comb_lvl,
            "flood_risk_level": scen_flood_lvl,
            "landslide_risk_level": scen_ls_lvl,
        },
        "change": {
            "flood_probability_points": flood_delta_pts,
            "landslide_probability_points": ls_delta_pts,
            "combined_risk_points": comb_delta_pts,
            "relative_change_pct": comb_rel_change,
            "risk_level_shift": f"{curr_comb_lvl} → {scen_comb_lvl}",
            "impact_direction": impact_direction,
        },
        "impact_summary": impact_summary,
        "impact_direction": impact_direction,
        "primary_delta_pct_points": active_delta,
        "flood": {
            "current_probability": round(curr_flood_prob, 4),
            "simulated_probability": round(scen_flood_prob, 4),
            "delta_pct_points": flood_delta_pts,
            "current_risk_level": curr_flood_lvl,
            "simulated_risk_level": scen_flood_lvl,
            "level_changed": curr_flood_lvl != scen_flood_lvl,
        },
        "landslide": {
            "current_probability": round(curr_ls_prob, 4),
            "simulated_probability": round(scen_ls_prob, 4),
            "delta_pct_points": ls_delta_pts,
            "current_risk_level": curr_ls_lvl,
            "simulated_risk_level": scen_ls_lvl,
            "level_changed": curr_ls_lvl != scen_ls_lvl,
        },
        "combined": {
            "current_risk": round(curr_combined_risk, 4),
            "simulated_risk": round(scen_combined_risk, 4),
            "delta_pct_points": comb_delta_pts,
            "relative_change_pct": comb_rel_change,
            "current_risk_level": curr_comb_lvl,
            "simulated_risk_level": scen_comb_lvl,
            "level_changed": curr_comb_lvl != scen_comb_lvl,
            "weights": {
                "flood": fw,
                "landslide": lw,
            },
        },
        "feature_deltas": feature_deltas,
        "current_inputs": cleaned_current,
        "scenario_inputs": cleaned_scenario,
        "disclaimer": SIMULATION_DISCLAIMER,
        "http_status": 200,
    }
