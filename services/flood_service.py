"""Flood prediction application service. Does not invent scores when untrained."""

from __future__ import annotations

from flask import current_app
from flask_login import current_user

from extensions import db
from ml.explainability import explain_prediction
from ml.flood.feature_schema import FEATURE_COLUMNS, MODEL_NOT_TRAINED_MESSAGE, validate_feature_payload
from ml.flood.predict import (
    format_prediction,
    load_artifacts,
    model_files_exist,
    predict_flood_probability,
)
from models import PredictionHistory


def model_status():
    model_path = current_app.config["FLOOD_MODEL_PATH"]
    preprocessor_path = current_app.config["FLOOD_PREPROCESSOR_PATH"]
    if model_files_exist(model_path, preprocessor_path):
        return "trained"
    return "not_trained"


def predict_from_payload(payload, persist=True):
    cleaned, errors = validate_feature_payload(payload)
    if errors:
        return {
            "success": False,
            "errors": errors,
            "model_status": model_status(),
            "prediction": None,
            "http_status": 400,
        }

    status = model_status()
    if status != "trained":
        return {
            "success": False,
            "errors": [MODEL_NOT_TRAINED_MESSAGE],
            "model_status": status,
            "prediction": None,
            "input_summary": cleaned,
            "http_status": 503,
        }

    model, preprocessor = load_artifacts(
        current_app.config["FLOOD_MODEL_PATH"],
        current_app.config["FLOOD_PREPROCESSOR_PATH"],
    )
    probability = predict_flood_probability(cleaned, model, preprocessor)
    prediction = format_prediction(
        probability,
        low_max=current_app.config["FLOOD_RISK_LOW_MAX"],
        moderate_max=current_app.config["FLOOD_RISK_MODERATE_MAX"],
        high_max=current_app.config["FLOOD_RISK_HIGH_MAX"],
    )

    # Compute AI Prediction Explainability
    explainability = None
    try:
        explainability = explain_prediction(
            features_dict=cleaned,
            model=model,
            preprocessor=preprocessor,
            feature_columns=FEATURE_COLUMNS,
            hazard_type="flood",
        )
    except Exception:
        current_app.logger.exception("Failed to generate flood prediction explainability")

    pred_id = None
    if persist:
        pred_id = _store_history(cleaned, prediction, explainability)

    return {
        "success": True,
        "prediction_id": pred_id,
        "id": pred_id,
        "prediction": prediction,
        "probability": prediction.get("flood_probability"),
        "risk_level": prediction.get("risk_level"),
        "explainability": explainability,
        "model_status": status,
        "input_summary": cleaned,
        "threshold_note": (
            "Risk bands are application UI thresholds for this prototype, "
            "not official government warning levels."
        ),
        "http_status": 200,
    }


def _store_history(cleaned, prediction, explainability=None):
    user_id = getattr(current_user, "id", None) if getattr(current_user, "is_authenticated", False) else None
    prob_val = prediction.get("flood_probability") or prediction.get("probability", 0.0)
    risk_lvl = prediction.get("risk_level", "LOW")
    result_data = {
        "inputs": cleaned,
        "flood_probability": prob_val,
        "risk_level": risk_lvl,
    }
    if explainability is not None:
        result_data["explainability"] = explainability

    record = PredictionHistory(
        user_id=user_id,
        location_id=None,
        prediction_type="flood",
        status="completed",
        result_json=result_data,
    )
    try:
        db.session.add(record)
        db.session.commit()
        return record.id
    except Exception:
        db.session.rollback()
        try:
            db.create_all()
            db.session.add(record)
            db.session.commit()
            return record.id
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to store flood prediction history")
            return None
