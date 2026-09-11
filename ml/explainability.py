"""Core explainability engine for NIDARS ML models.

Computes mathematically valid, model-compatible feature explanations
using local marginal baseline attributions and model feature importances
without retraining existing ML models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

EXPLAINABILITY_DISCLAIMER = (
    "Model explanations indicate feature influence and should not be interpreted as causal proof."
)

FEATURE_METADATA: Dict[str, Dict[str, str]] = {
    "rainfall_24h": {
        "label": "Rainfall 24h",
        "unit": "mm",
        "description": "Short-term precipitation accumulation over 24 hours",
    },
    "rainfall_72h": {
        "label": "Rainfall 72h",
        "unit": "mm",
        "description": "Intermediate precipitation accumulation over 72 hours",
    },
    "rainfall_7d": {
        "label": "Rainfall 7d",
        "unit": "mm",
        "description": "Cumulative precipitation over the preceding 7 days",
    },
    "temperature": {
        "label": "Temperature",
        "unit": "°C",
        "description": "Ambient surface air temperature",
    },
    "wind_speed": {
        "label": "Wind Speed",
        "unit": "m/s",
        "description": "Near-surface wind speed",
    },
    "air_pressure": {
        "label": "Air Pressure",
        "unit": "hPa",
        "description": "Atmospheric surface barometric pressure",
    },
    "elevation": {
        "label": "Elevation",
        "unit": "m",
        "description": "Topographical elevation above sea level",
    },
    "latitude": {
        "label": "Latitude",
        "unit": "°N",
        "description": "Geographical coordinate (North latitude)",
    },
    "longitude": {
        "label": "Longitude",
        "unit": "°E",
        "description": "Geographical coordinate (East longitude)",
    },
}


def explain_prediction(
    features_dict: Dict[str, Any],
    model: Any,
    preprocessor: Any,
    feature_columns: List[str],
    hazard_type: str = "flood",
) -> Dict[str, Any]:
    """Compute local feature attributions and explainability metrics for a prediction.

    Args:
        features_dict: Cleaned numeric feature map.
        model: Trained scikit-learn classifier (RandomForest or GradientBoosting).
        preprocessor: Fitted preprocessor containing training medians in fill_values_.
        feature_columns: Ordered list of feature column names.
        hazard_type: "flood" or "landslide".

    Returns:
        Structured dictionary containing top contributing factors, horizontal bar chart
        data, global importance rankings, and standard academic disclaimer.
    """
    if model is None or preprocessor is None:
        raise ValueError("Model and preprocessor must be loaded to generate explanations.")

    # Base prediction probability
    frame = pd.DataFrame([features_dict], columns=feature_columns)
    transformed = preprocessor.transform(frame)
    if hasattr(model, "predict_proba"):
        base_probability = float(model.predict_proba(transformed)[0][1])
    else:
        base_probability = float(model.predict(transformed)[0])
    base_probability = min(1.0, max(0.0, base_probability))

    # Baseline reference values from preprocessor training medians
    baselines: Dict[str, float] = getattr(preprocessor, "fill_values_", {})

    # Model global feature importances
    raw_importances = getattr(model, "feature_importances_", None)
    if raw_importances is not None and len(raw_importances) == len(feature_columns):
        importances_map = {
            col: float(raw_importances[i]) for i, col in enumerate(feature_columns)
        }
    else:
        importances_map = {col: 1.0 / len(feature_columns) for col in feature_columns}

    # Compute marginal local attributions by replacing each feature with baseline
    factor_list = []
    for col in feature_columns:
        baseline_val = float(baselines.get(col, 0.0))
        current_val = float(features_dict.get(col, baseline_val))

        # Evaluate model with this single feature perturbed to baseline
        perturbed_dict = dict(features_dict)
        perturbed_dict[col] = baseline_val
        p_frame = pd.DataFrame([perturbed_dict], columns=feature_columns)
        p_trans = preprocessor.transform(p_frame)
        if hasattr(model, "predict_proba"):
            p_prob = float(model.predict_proba(p_trans)[0][1])
        else:
            p_prob = float(model.predict(p_trans)[0])
        p_prob = min(1.0, max(0.0, p_prob))

        delta = base_probability - p_prob
        meta = FEATURE_METADATA.get(col, {"label": col.replace("_", " ").title(), "unit": ""})

        factor_list.append(
            {
                "feature": col,
                "label": meta["label"],
                "unit": meta["unit"],
                "current_value": current_val,
                "baseline_value": baseline_val,
                "global_importance": round(importances_map.get(col, 0.0), 4),
                "raw_delta": round(delta, 4),
            }
        )

    sum_abs_delta = sum(abs(f["raw_delta"]) for f in factor_list)

    for f in factor_list:
        if sum_abs_delta > 0.0001:
            rel_contrib = f["raw_delta"] / sum_abs_delta
        else:
            # Fallback to global feature importance when inputs equal baseline
            rel_contrib = f["global_importance"]

        f["contribution_score"] = round(rel_contrib, 4)

        # Categorize impact level
        abs_contrib = abs(f["contribution_score"])
        abs_raw_delta = abs(f["raw_delta"])
        if abs_contrib >= 0.20 or abs_raw_delta >= 0.08:
            f["impact"] = "HIGH"
        elif abs_contrib >= 0.08 or abs_raw_delta >= 0.02:
            f["impact"] = "MODERATE"
        else:
            f["impact"] = "LOW"

        # Directional impact
        if f["raw_delta"] > 0.0001:
            f["direction"] = "POSITIVE"
            f["direction_label"] = "Increases Risk"
        elif f["raw_delta"] < -0.0001:
            f["direction"] = "NEGATIVE"
            f["direction_label"] = "Decreases Risk"
        else:
            f["direction"] = "NEUTRAL"
            f["direction_label"] = "Neutral Baseline"

    # Sort factors by magnitude of contribution score (highest influence first)
    factor_list.sort(
        key=lambda x: (abs(x["contribution_score"]), x["global_importance"]),
        reverse=True,
    )

    # Prepare data specifically for horizontal bar chart
    # Chart will show top factors sorted so highest is at the top
    chart_labels = [f["label"] for f in factor_list]
    chart_contributions = [round(f["contribution_score"] * 100, 1) for f in factor_list]
    chart_colors = [
        "#ef4444" if f["direction"] == "POSITIVE" else ("#10b981" if f["direction"] == "NEGATIVE" else "#94a3b8")
        for f in factor_list
    ]

    return {
        "method": "Local Baseline Attribution & Tree Feature Importances",
        "hazard_type": hazard_type,
        "base_probability": round(base_probability, 4),
        "top_contributing_factors": factor_list,
        "chart_data": {
            "labels": chart_labels,
            "contributions": chart_contributions,
            "colors": chart_colors,
            "unit": "% Contribution",
        },
        "disclaimer": EXPLAINABILITY_DISCLAIMER,
    }
