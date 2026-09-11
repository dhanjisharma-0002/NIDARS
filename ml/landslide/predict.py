"""Load the persisted landslide model and score a validated feature row."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ml.landslide.feature_schema import FEATURE_COLUMNS, risk_level_from_probability


def model_files_exist(model_path, preprocessor_path):
    return Path(model_path).is_file() and Path(preprocessor_path).is_file()


def load_artifacts(model_path, preprocessor_path):
    if not model_files_exist(model_path, preprocessor_path):
        return None, None
    import joblib

    model = joblib.load(model_path)
    preprocessor = joblib.load(preprocessor_path)
    return model, preprocessor


def predict_landslide_probability(cleaned_features, model, preprocessor):
    frame = pd.DataFrame([cleaned_features], columns=FEATURE_COLUMNS)
    transformed = preprocessor.transform(frame)
    if hasattr(model, "predict_proba"):
        probability = float(model.predict_proba(transformed)[0][1])
    else:
        probability = float(model.predict(transformed)[0])
    probability = min(1.0, max(0.0, probability))
    return probability


def format_prediction(probability, low_max, moderate_max, high_max):
    return {
        "landslide_probability": round(probability, 4),
        "risk_level": risk_level_from_probability(
            probability, low_max=low_max, moderate_max=moderate_max, high_max=high_max
        ),
    }
