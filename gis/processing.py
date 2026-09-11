"""GIS data processing and spatial risk scoring engine for North India.

Aggregates real meteorological observation stations across North India, evaluates
trained Flood and Landslide ML models, and produces GeoJSON FeatureCollections.

IMPORTANT:
- Reuses existing trained Flood and Landslide model artifacts without retraining.
- Uses only legitimate spatial coordinates and observations from data/processed/.
- Does NOT fabricate raster layers, slope/NDVI fields, or fake road closures.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from flask import current_app

from config import Config
from gis.risk_zones import (
    calculate_combined_risk,
    classify_combined_risk,
    classify_flood_risk,
    classify_landslide_risk,
    to_feature_collection,
    to_geojson_feature,
)
from ml.flood.predict import (
    load_artifacts as load_flood_artifacts,
    model_files_exist as flood_files_exist,
    predict_flood_probability,
)
from ml.landslide.predict import (
    load_artifacts as load_landslide_artifacts,
    model_files_exist as landslide_files_exist,
    predict_landslide_probability,
)

STATE_FULL_NAMES = {
    "JK": "Jammu & Kashmir",
    "HP": "Himachal Pradesh",
    "UP": "Uttar Pradesh",
    "BR": "Bihar",
    "UTTAR PRADESH": "Uttar Pradesh",
    "BIHAR": "Bihar",
    "HIMACHAL PRADESH": "Himachal Pradesh",
    "JAMMU & KASHMIR": "Jammu & Kashmir",
}

DEFAULT_WEATHER_FILE = Path(__file__).resolve().parent.parent / "data" / "processed" / "flood_labeled_weather.csv"
FALLBACK_STATIONS_JSON = Path(__file__).resolve().parent / "geojson" / "stations_latest.json"


def load_station_latest_observations(csv_path: Optional[Path | str] = None) -> pd.DataFrame:
    """Load and aggregate weather observations to the latest representative record per station.

    Computes 24h, 72h, and 7d rainfall totals for all 64 stations across North India.
    """
    file_path = Path(csv_path) if csv_path else DEFAULT_WEATHER_FILE
    if not file_path.is_file():
        # Fallback to north_india_weather.csv if labeled CSV not found
        file_path = file_path.parent / "north_india_weather.csv"

    if not file_path.is_file():
        # Fallback to bundled stations_latest.json for serverless/git deployments
        if FALLBACK_STATIONS_JSON.is_file():
            return pd.read_json(FALLBACK_STATIONS_JSON)
        raise FileNotFoundError(f"Weather dataset not found at {file_path}")

    df = pd.read_csv(file_path)
    df["date"] = pd.to_datetime(df.get("date", df.get("date_of_record")), errors="coerce")
    df["rainfall"] = pd.to_numeric(df["rainfall"], errors="coerce").fillna(0.0)

    # Sort chronologically per station
    df = df.sort_values(["station_name", "date"]).reset_index(drop=True)
    df["rainfall_24h"] = df["rainfall"]

    # Rolling rainfall totals
    r72 = df.set_index("date").groupby("station_name")["rainfall"].rolling("3D", min_periods=1).sum().reset_index()
    r7d = df.set_index("date").groupby("station_name")["rainfall"].rolling("7D", min_periods=1).sum().reset_index()
    df["rainfall_72h"] = r72["rainfall"].values
    df["rainfall_7d"] = r7d["rainfall"].values

    df["temperature"] = pd.to_numeric(df["avg_temp"], errors="coerce").fillna(25.0)
    df["wind_speed"] = pd.to_numeric(df["wind_speed"], errors="coerce").fillna(5.0)
    df["air_pressure"] = pd.to_numeric(df["air_pressure"], errors="coerce").fillna(1010.0)
    df["elevation"] = pd.to_numeric(df["elevation"], errors="coerce").fillna(300.0)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    # Take the latest observation per station
    latest = df.groupby("station_name", as_index=False).last()

    # Format state names cleanly
    latest["state_code"] = latest["state"].astype(str).str.strip().str.upper()
    latest["state_name"] = latest["state_code"].map(STATE_FULL_NAMES).fillna(latest["state_code"])

    return latest


class SpatialRiskEngine:
    """Evaluates spatial hazard risks using trained Flood and Landslide models."""

    def __init__(
        self,
        flood_model_path: Optional[Path | str] = None,
        flood_preprocessor_path: Optional[Path | str] = None,
        landslide_model_path: Optional[Path | str] = None,
        landslide_preprocessor_path: Optional[Path | str] = None,
    ):
        self.flood_model_path = Path(flood_model_path or Config.FLOOD_MODEL_PATH)
        self.flood_preprocessor_path = Path(flood_preprocessor_path or Config.FLOOD_PREPROCESSOR_PATH)
        self.landslide_model_path = Path(landslide_model_path or Config.LANDSLIDE_MODEL_PATH)
        self.landslide_preprocessor_path = Path(landslide_preprocessor_path or Config.LANDSLIDE_PREPROCESSOR_PATH)

        self._flood_model = None
        self._flood_preprocessor = None
        self._landslide_model = None
        self._landslide_preprocessor = None
        self._cached_station_features: Optional[List[Dict[str, Any]]] = None

    def _ensure_models_loaded(self):
        if self._flood_model is None and flood_files_exist(self.flood_model_path, self.flood_preprocessor_path):
            self._flood_model, self._flood_preprocessor = load_flood_artifacts(
                self.flood_model_path, self.flood_preprocessor_path
            )
        if self._landslide_model is None and landslide_files_exist(
            self.landslide_model_path, self.landslide_preprocessor_path
        ):
            self._landslide_model, self._landslide_preprocessor = load_landslide_artifacts(
                self.landslide_model_path, self.landslide_preprocessor_path
            )

    def score_station_records(
        self,
        stations_df: pd.DataFrame,
        flood_weight: float = 0.50,
        landslide_weight: float = 0.50,
        flood_low_max: float = 0.25,
        flood_mod_max: float = 0.50,
        flood_high_max: float = 0.75,
        landslide_low_max: float = 0.02,
        landslide_mod_max: float = 0.10,
        landslide_high_max: float = 0.25,
        combined_low_max: float = 0.25,
        combined_mod_max: float = 0.50,
        combined_high_max: float = 0.75,
    ) -> List[Dict[str, Any]]:
        """Compute Flood, Landslide, and Combined risk scores for all stations."""
        self._ensure_models_loaded()
        scored_records = []

        for _, row in stations_df.iterrows():
            features = {
                "rainfall_24h": float(row["rainfall_24h"]),
                "rainfall_72h": float(row["rainfall_72h"]),
                "rainfall_7d": float(row["rainfall_7d"]),
                "temperature": float(row["temperature"]),
                "wind_speed": float(row["wind_speed"]),
                "air_pressure": float(row["air_pressure"]),
                "elevation": float(row["elevation"]),
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
            }

            # Predict flood probability
            if self._flood_model is not None and self._flood_preprocessor is not None:
                flood_prob = predict_flood_probability(features, self._flood_model, self._flood_preprocessor)
            else:
                flood_prob = 0.0

            # Predict landslide probability
            if self._landslide_model is not None and self._landslide_preprocessor is not None:
                landslide_prob = predict_landslide_probability(
                    features, self._landslide_model, self._landslide_preprocessor
                )
            else:
                landslide_prob = 0.0

            combined_risk = calculate_combined_risk(
                flood_prob=flood_prob,
                landslide_prob=landslide_prob,
                flood_weight=flood_weight,
                landslide_weight=landslide_weight,
            )

            flood_risk_level = classify_flood_risk(
                flood_prob, low_max=flood_low_max, moderate_max=flood_mod_max, high_max=flood_high_max
            )
            landslide_risk_level = classify_landslide_risk(
                landslide_prob, low_max=landslide_low_max, moderate_max=landslide_mod_max, high_max=landslide_high_max
            )
            combined_risk_level = classify_combined_risk(
                combined_risk, low_max=combined_low_max, moderate_max=combined_mod_max, high_max=combined_high_max
            )

            record = {
                "station_name": str(row["station_name"]),
                "district": str(row["district"]),
                "state": str(row["state_code"]),
                "state_name": str(row["state_name"]),
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "elevation": float(row["elevation"]),
                "date_of_observation": str(row["date"].strftime("%Y-%m-%d") if pd.notna(row["date"]) else ""),
                "features": features,
                "flood_probability": round(flood_prob, 4),
                "landslide_probability": round(landslide_prob, 4),
                "combined_risk": round(combined_risk, 4),
                "flood_risk_level": flood_risk_level,
                "landslide_risk_level": landslide_risk_level,
                "combined_risk_level": combined_risk_level,
            }
            scored_records.append(record)

        return scored_records

    def get_spatial_risk_features(
        self,
        stations_df: Optional[pd.DataFrame] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        station: Optional[str] = None,
        risk_level: Optional[str] = None,
        hazard: str = "combined",
        limit: Optional[int] = None,
        flood_weight: Optional[float] = None,
        landslide_weight: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Produce a filtered GeoJSON FeatureCollection."""
        hazard_norm = str(hazard).strip().lower()
        if hazard_norm not in ("flood", "landslide", "combined"):
            raise ValueError(f"Invalid hazard type '{hazard}'. Must be 'flood', 'landslide', or 'combined'.")

        fw = flood_weight if flood_weight is not None else getattr(Config, "GIS_FLOOD_WEIGHT", 0.50)
        lw = landslide_weight if landslide_weight is not None else getattr(Config, "GIS_LANDSLIDE_WEIGHT", 0.50)

        df = stations_df if stations_df is not None else load_station_latest_observations()
        scored = self.score_station_records(
            df,
            flood_weight=fw,
            landslide_weight=lw,
            flood_low_max=getattr(Config, "FLOOD_RISK_LOW_MAX", 0.25),
            flood_mod_max=getattr(Config, "FLOOD_RISK_MODERATE_MAX", 0.50),
            flood_high_max=getattr(Config, "FLOOD_RISK_HIGH_MAX", 0.75),
            landslide_low_max=getattr(Config, "LANDSLIDE_RISK_LOW_MAX", 0.02),
            landslide_mod_max=getattr(Config, "LANDSLIDE_RISK_MODERATE_MAX", 0.10),
            landslide_high_max=getattr(Config, "LANDSLIDE_RISK_HIGH_MAX", 0.25),
            combined_low_max=getattr(Config, "GIS_COMBINED_RISK_LOW_MAX", 0.25),
            combined_mod_max=getattr(Config, "GIS_COMBINED_RISK_MODERATE_MAX", 0.50),
            combined_high_max=getattr(Config, "GIS_COMBINED_RISK_HIGH_MAX", 0.75),
        )

        # Apply filtering
        filtered = []
        state_filter = state.strip().upper() if state else None
        district_filter = district.strip().upper() if district else None
        station_filter = station.strip().lower() if station else None
        risk_level_filter = risk_level.strip().upper() if risk_level else None

        for item in scored:
            if state_filter and item["state"] != state_filter and item["state_name"].upper() != state_filter:
                continue
            if district_filter and item["district"].upper() != district_filter:
                continue
            if station_filter and (station_filter not in item["station_name"].lower() and station_filter not in item["district"].lower()):
                continue

            if hazard_norm == "flood":
                active_level = item["flood_risk_level"]
            elif hazard_norm == "landslide":
                active_level = item["landslide_risk_level"]
            else:
                active_level = item["combined_risk_level"]

            if risk_level_filter and risk_level_filter != "ALL" and active_level != risk_level_filter:
                continue

            filtered.append(item)

        if limit is not None and limit > 0:
            filtered = filtered[:limit]

        # Build GeoJSON features
        features = []
        for idx, item in enumerate(filtered):
            if hazard_norm == "flood":
                active_score = item["flood_probability"]
                active_level = item["flood_risk_level"]
            elif hazard_norm == "landslide":
                active_score = item["landslide_probability"]
                active_level = item["landslide_risk_level"]
            else:
                active_score = item["combined_risk"]
                active_level = item["combined_risk_level"]

            props = {
                "station": item["station_name"],
                "district": item["district"],
                "state": item["state"],
                "state_name": item["state_name"],
                "elevation_m": item["elevation"],
                "observation_date": item["date_of_observation"],
                "flood_probability": item["flood_probability"],
                "landslide_probability": item["landslide_probability"],
                "combined_risk": item["combined_risk"],
                "risk_level": active_level,
                "risk_score": active_score,
                "hazard": hazard_norm,
                "rainfall_24h": item["features"]["rainfall_24h"],
                "rainfall_72h": item["features"]["rainfall_72h"],
                "rainfall_7d": item["features"]["rainfall_7d"],
                "temperature": item["features"]["temperature"],
                "wind_speed": item["features"]["wind_speed"],
                "air_pressure": item["features"]["air_pressure"],
            }
            feat = to_geojson_feature(
                latitude=item["latitude"],
                longitude=item["longitude"],
                properties=props,
                feature_id=idx + 1,
            )
            features.append(feat)

        metadata = {
            "total_stations": len(features),
            "hazard_mode": hazard_norm,
            "weights": {
                "flood_weight": fw,
                "landslide_weight": lw,
            },
            "thresholds": {
                "flood": {
                    "low_max": getattr(Config, "FLOOD_RISK_LOW_MAX", 0.25),
                    "moderate_max": getattr(Config, "FLOOD_RISK_MODERATE_MAX", 0.50),
                    "high_max": getattr(Config, "FLOOD_RISK_HIGH_MAX", 0.75),
                },
                "landslide": {
                    "low_max": getattr(Config, "LANDSLIDE_RISK_LOW_MAX", 0.02),
                    "moderate_max": getattr(Config, "LANDSLIDE_RISK_MODERATE_MAX", 0.10),
                    "high_max": getattr(Config, "LANDSLIDE_RISK_HIGH_MAX", 0.25),
                },
                "combined": {
                    "low_max": getattr(Config, "GIS_COMBINED_RISK_LOW_MAX", 0.25),
                    "moderate_max": getattr(Config, "GIS_COMBINED_RISK_MODERATE_MAX", 0.50),
                    "high_max": getattr(Config, "GIS_COMBINED_RISK_HIGH_MAX", 0.75),
                },
            },
            "disclaimer": (
                "NIDARS is a research prototype decision support system. "
                "Official government disaster alerts remain authoritative."
            ),
        }

        return to_feature_collection(features, metadata=metadata)

    def get_spatial_summary_statistics(
        self,
        stations_df: Optional[pd.DataFrame] = None,
        hazard: str = "combined",
        flood_weight: Optional[float] = None,
        landslide_weight: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Compute live aggregated spatial risk counts and statistics across stations."""
        hazard_norm = str(hazard).strip().lower()
        if hazard_norm not in ("flood", "landslide", "combined"):
            hazard_norm = "combined"

        fw = flood_weight if flood_weight is not None else getattr(Config, "GIS_FLOOD_WEIGHT", 0.50)
        lw = landslide_weight if landslide_weight is not None else getattr(Config, "GIS_LANDSLIDE_WEIGHT", 0.50)

        df = stations_df if stations_df is not None else load_station_latest_observations()
        scored = self.score_station_records(df, flood_weight=fw, landslide_weight=lw)

        counts = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "CRITICAL": 0}
        state_breakdown: Dict[str, Dict[str, int]] = {}
        total_flood_prob = 0.0
        total_landslide_prob = 0.0
        total_combined_risk = 0.0
        highest_risk_station = None
        max_score = -1.0

        for item in scored:
            state_code = item["state"]
            if state_code not in state_breakdown:
                state_breakdown[state_code] = {"total": 0, "LOW": 0, "MODERATE": 0, "HIGH": 0, "CRITICAL": 0}

            if hazard_norm == "flood":
                lvl = item["flood_risk_level"]
                score = item["flood_probability"]
            elif hazard_norm == "landslide":
                lvl = item["landslide_risk_level"]
                score = item["landslide_probability"]
            else:
                lvl = item["combined_risk_level"]
                score = item["combined_risk"]

            counts[lvl] = counts.get(lvl, 0) + 1
            state_breakdown[state_code]["total"] += 1
            state_breakdown[state_code][lvl] = state_breakdown[state_code].get(lvl, 0) + 1

            total_flood_prob += item["flood_probability"]
            total_landslide_prob += item["landslide_probability"]
            total_combined_risk += item["combined_risk"]

            if score > max_score:
                max_score = score
                highest_risk_station = {
                    "station_name": item["station_name"],
                    "district": item["district"],
                    "state": item["state"],
                    "risk_level": lvl,
                    "score": score,
                }

        n = len(scored) if scored else 1
        return {
            "success": True,
            "monitored_stations": len(scored),
            "hazard_mode": hazard_norm,
            "risk_counts": {
                "low": counts["LOW"],
                "moderate": counts["MODERATE"],
                "high": counts["HIGH"],
                "critical": counts["CRITICAL"],
            },
            "state_breakdown": state_breakdown,
            "averages": {
                "avg_flood_probability": round(total_flood_prob / n, 4),
                "avg_landslide_probability": round(total_landslide_prob / n, 4),
                "avg_combined_risk": round(total_combined_risk / n, 4),
            },
            "highest_risk_station": highest_risk_station,
        }


# Module-level singleton
_engine_instance: Optional[SpatialRiskEngine] = None


def get_spatial_risk_engine() -> SpatialRiskEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SpatialRiskEngine()
    return _engine_instance
