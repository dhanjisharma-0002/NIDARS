"""Canonical landslide-risk feature schema, aliases, and input validation."""

from __future__ import annotations

FEATURE_COLUMNS = [
    "rainfall_24h",
    "rainfall_72h",
    "rainfall_7d",
    "temperature",
    "wind_speed",
    "air_pressure",
    "elevation",
    "latitude",
    "longitude",
]

TARGET_COLUMN = "landslide_risk"

COLUMN_ALIASES = {
    "rain_24h": "rainfall_24h",
    "rainfall24h": "rainfall_24h",
    "rainfall_24": "rainfall_24h",
    "rain_72h": "rainfall_72h",
    "rainfall72h": "rainfall_72h",
    "rain_7d": "rainfall_7d",
    "rainfall_7day": "rainfall_7d",
    "rainfall_7days": "rainfall_7d",
    "temp": "temperature",
    "avg_temp": "temperature",
    "wind": "wind_speed",
    "windspeed": "wind_speed",
    "pressure": "air_pressure",
    "airpressure": "air_pressure",
    "altitude": "elevation",
    "elevation_m": "elevation",
    "lat": "latitude",
    "lon": "longitude",
    "long": "longitude",
    "landslide_occurred": "landslide_risk",
    "landslide": "landslide_risk",
    "hazard": "landslide_risk",
    "label": "landslide_risk",
    "target": "landslide_risk",
}

FEATURE_BOUNDS = {
    "rainfall_24h": (0, 2000),
    "rainfall_72h": (0, 4000),
    "rainfall_7d": (0, 8000),
    "temperature": (-40, 60),
    "wind_speed": (0, 200),
    "air_pressure": (500, 1100),
    "elevation": (-100, 9000),
    "latitude": (0, 90),
    "longitude": (0, 180),
}

MISSING_DATASET_MESSAGE = (
    "Landslide dataset not found. Place a legitimate dataset at "
    "data/processed/landslide_training.csv before training."
)

MODEL_NOT_TRAINED_MESSAGE = (
    "Landslide model is not trained yet. Run: python -m ml.landslide.train"
)


class LandslideSchemaError(ValueError):
    """Raised when landslide features or the training CSV schema are invalid."""


def normalize_column_name(name):
    return str(name).strip().lower().replace(" ", "_")


def apply_column_aliases(columns):
    """Return a rename dict from original headers to canonical names."""
    rename = {}
    for original in columns:
        key = normalize_column_name(original)
        canonical = COLUMN_ALIASES.get(key, key)
        rename[original] = canonical
    return rename


def risk_level_from_probability(probability, low_max=0.25, moderate_max=0.50, high_max=0.75):
    """Map a probability to an application UI band."""
    if probability < low_max:
        return "LOW"
    if probability < moderate_max:
        return "MODERATE"
    if probability < high_max:
        return "HIGH"
    return "CRITICAL"


def validate_feature_payload(payload):
    """Validate a landslide prediction dict. Returns (cleaned_dict, errors)."""
    errors = []
    cleaned = {}

    if not isinstance(payload, dict):
        return {}, ["Request body must be a JSON object."]

    missing = [name for name in FEATURE_COLUMNS if name not in payload or payload[name] in (None, "")]
    if missing:
        errors.append("Missing required fields: " + ", ".join(missing))

    extra_checked = [name for name in FEATURE_COLUMNS if name in payload and payload[name] not in (None, "")]
    for name in extra_checked:
        raw = payload[name]
        try:
            value = float(raw)
        except (TypeError, ValueError):
            errors.append(f"{name} must be numeric.")
            continue
        if value != value:  # NaN
            errors.append(f"{name} is not a valid number.")
            continue
        low, high = FEATURE_BOUNDS[name]
        if value < low or value > high:
            errors.append(f"{name} must be between {low} and {high}.")
            continue
        cleaned[name] = value

    if errors:
        return {}, errors
    return cleaned, []
