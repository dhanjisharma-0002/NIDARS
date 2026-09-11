"""Explainability application service for NIDARS.

Provides explainability computation for real-time predictions and historical records.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from flask import current_app

from ml.explainability import (
    EXPLAINABILITY_DISCLAIMER,
    FEATURE_METADATA,
    explain_prediction,
)
from ml.flood.feature_schema import (
    FEATURE_COLUMNS as FLOOD_FEATURE_COLUMNS,
    validate_feature_payload as validate_flood_payload,
)
from ml.flood.predict import (
    load_artifacts as load_flood_artifacts,
    model_files_exist as flood_files_exist,
)
from ml.landslide.feature_schema import (
    FEATURE_COLUMNS as LANDSLIDE_FEATURE_COLUMNS,
    validate_feature_payload as validate_landslide_payload,
)
from ml.landslide.predict import (
    load_artifacts as load_landslide_artifacts,
    model_files_exist as landslide_files_exist,
)


def get_flood_explainability(cleaned_features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Compute explainability for a valid flood feature dictionary."""
    model_path = current_app.config["FLOOD_MODEL_PATH"]
    preprocessor_path = current_app.config["FLOOD_PREPROCESSOR_PATH"]
    if not flood_files_exist(model_path, preprocessor_path):
        return None

    model, preprocessor = load_flood_artifacts(model_path, preprocessor_path)
    if model is None or preprocessor is None:
        return None

    return explain_prediction(
        features_dict=cleaned_features,
        model=model,
        preprocessor=preprocessor,
        feature_columns=FLOOD_FEATURE_COLUMNS,
        hazard_type="flood",
    )


def get_landslide_explainability(cleaned_features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Compute explainability for a valid landslide feature dictionary."""
    model_path = current_app.config["LANDSLIDE_MODEL_PATH"]
    preprocessor_path = current_app.config["LANDSLIDE_PREPROCESSOR_PATH"]
    if not landslide_files_exist(model_path, preprocessor_path):
        return None

    model, preprocessor = load_landslide_artifacts(model_path, preprocessor_path)
    if model is None or preprocessor is None:
        return None

    return explain_prediction(
        features_dict=cleaned_features,
        model=model,
        preprocessor=preprocessor,
        feature_columns=LANDSLIDE_FEATURE_COLUMNS,
        hazard_type="landslide",
    )


def explain_from_payload(hazard_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate payload and compute explainability for a given hazard type."""
    hazard = (hazard_type or "").lower().strip()
    if hazard not in ("flood", "landslide"):
        return {
            "success": False,
            "errors": [f"Invalid hazard type '{hazard_type}'. Must be 'flood' or 'landslide'."],
            "http_status": 400,
        }

    if hazard == "flood":
        cleaned, errors = validate_flood_payload(payload)
        if errors:
            return {
                "success": False,
                "errors": errors,
                "hazard_type": hazard,
                "http_status": 400,
            }

        model_path = current_app.config["FLOOD_MODEL_PATH"]
        preprocessor_path = current_app.config["FLOOD_PREPROCESSOR_PATH"]
        if not flood_files_exist(model_path, preprocessor_path):
            return {
                "success": False,
                "errors": ["Flood ML model is not available or trained."],
                "hazard_type": hazard,
                "http_status": 503,
            }

        model, preprocessor = load_flood_artifacts(model_path, preprocessor_path)
        explanation = explain_prediction(
            features_dict=cleaned,
            model=model,
            preprocessor=preprocessor,
            feature_columns=FLOOD_FEATURE_COLUMNS,
            hazard_type="flood",
        )
        return {
            "success": True,
            "hazard_type": "flood",
            "input_summary": cleaned,
            "explainability": explanation,
            "http_status": 200,
        }

    else:  # landslide
        cleaned, errors = validate_landslide_payload(payload)
        if errors:
            return {
                "success": False,
                "errors": errors,
                "hazard_type": hazard,
                "http_status": 400,
            }

        model_path = current_app.config["LANDSLIDE_MODEL_PATH"]
        preprocessor_path = current_app.config["LANDSLIDE_PREPROCESSOR_PATH"]
        if not landslide_files_exist(model_path, preprocessor_path):
            return {
                "success": False,
                "errors": ["Landslide ML model is not available or trained."],
                "hazard_type": hazard,
                "http_status": 503,
            }

        model, preprocessor = load_landslide_artifacts(model_path, preprocessor_path)
        explanation = explain_prediction(
            features_dict=cleaned,
            model=model,
            preprocessor=preprocessor,
            feature_columns=LANDSLIDE_FEATURE_COLUMNS,
            hazard_type="landslide",
        )
        return {
            "success": True,
            "hazard_type": "landslide",
            "input_summary": cleaned,
            "explainability": explanation,
            "http_status": 200,
        }
