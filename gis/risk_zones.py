"""Spatial risk representation, scoring formulas, risk classification, and GeoJSON serialization.

IMPORTANT DISCLAIMER:
NIDARS is an academic/research prototype. Risk classifications and combined hazard
indices are research indicators and application UI thresholds, NOT official
government disaster warnings. Official warnings from IMD / NDMA / CWC / GSI remain authoritative.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def calculate_combined_risk(
    flood_prob: float,
    landslide_prob: float,
    flood_weight: float = 0.50,
    landslide_weight: float = 0.50,
) -> float:
    """Calculate a weighted combination of flood and landslide probabilities.

    Preserves original probabilities while providing a normalized joint risk score:
        combined_risk = (flood_weight * flood_prob) + (landslide_weight * landslide_prob)

    Normalized if weights sum to 1.0.
    """
    f_prob = max(0.0, min(1.0, float(flood_prob)))
    l_prob = max(0.0, min(1.0, float(landslide_prob)))
    total_weight = flood_weight + landslide_weight
    if total_weight <= 0:
        raise ValueError("Sum of hazard weights must be greater than 0.")

    # Normalize weights so output remains bounded in [0, 1]
    norm_f = flood_weight / total_weight
    norm_l = landslide_weight / total_weight

    score = (norm_f * f_prob) + (norm_l * l_prob)
    return round(float(score), 4)


def classify_flood_risk(
    prob: float,
    low_max: float = 0.25,
    moderate_max: float = 0.50,
    high_max: float = 0.75,
) -> str:
    """Classify flood probability into UI risk bands."""
    p = max(0.0, min(1.0, float(prob)))
    if p < low_max:
        return "LOW"
    if p < moderate_max:
        return "MODERATE"
    if p < high_max:
        return "HIGH"
    return "CRITICAL"


def classify_landslide_risk(
    prob: float,
    low_max: float = 0.02,
    moderate_max: float = 0.10,
    high_max: float = 0.25,
) -> str:
    """Classify landslide probability preserving validated Phase 4.1 thresholds.

    - < 0.02: LOW (below advisory threshold)
    - 0.02 to < 0.10: MODERATE (advisory threshold reached)
    - 0.10 to < 0.25: HIGH (warning/action threshold reached)
    - >= 0.25: CRITICAL (severe landslide risk band)
    """
    p = max(0.0, min(1.0, float(prob)))
    if p < low_max:
        return "LOW"
    if p < moderate_max:
        return "MODERATE"
    if p < high_max:
        return "HIGH"
    return "CRITICAL"


def classify_combined_risk(
    score: float,
    low_max: float = 0.25,
    moderate_max: float = 0.50,
    high_max: float = 0.75,
) -> str:
    """Classify combined hazard score into project-defined UI risk bands."""
    s = max(0.0, min(1.0, float(score)))
    if s < low_max:
        return "LOW"
    if s < moderate_max:
        return "MODERATE"
    if s < high_max:
        return "HIGH"
    return "CRITICAL"


def to_geojson_feature(
    latitude: float,
    longitude: float,
    properties: Dict[str, Any],
    feature_id: Optional[Any] = None,
) -> Dict[str, Any]:
    """Create a GeoJSON Feature adhering to RFC 7946.

    Coordinates follow standard [longitude, latitude] ordering.
    """
    feature: Dict[str, Any] = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [round(float(longitude), 6), round(float(latitude), 6)],
        },
        "properties": properties,
    }
    if feature_id is not None:
        feature["id"] = feature_id
    return feature


def to_feature_collection(
    features: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Wrap a list of features into a GeoJSON FeatureCollection."""
    collection: Dict[str, Any] = {
        "type": "FeatureCollection",
        "features": features,
    }
    if metadata:
        collection["metadata"] = metadata
    return collection


def validate_geojson(geojson_obj: Any) -> Tuple[bool, List[str]]:
    """Validate a GeoJSON object against RFC 7946 structure."""
    errors = []
    if not isinstance(geojson_obj, dict):
        return False, ["GeoJSON must be a dictionary/object."]

    obj_type = geojson_obj.get("type")
    if obj_type != "FeatureCollection":
        errors.append(f"Expected type 'FeatureCollection', got '{obj_type}'")

    features = geojson_obj.get("features")
    if not isinstance(features, list):
        errors.append("GeoJSON FeatureCollection must have a 'features' array.")
        return False, errors

    for idx, f in enumerate(features):
        if not isinstance(f, dict):
            errors.append(f"Feature at index {idx} is not an object.")
            continue
        if f.get("type") != "Feature":
            errors.append(f"Feature at index {idx} type must be 'Feature'.")
        geom = f.get("geometry")
        if not isinstance(geom, dict):
            errors.append(f"Feature at index {idx} missing geometry object.")
        else:
            coords = geom.get("coordinates")
            if not isinstance(coords, (list, tuple)) or len(coords) < 2:
                errors.append(f"Feature at index {idx} invalid coordinates.")
            else:
                lon, lat = coords[0], coords[1]
                if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                    errors.append(f"Feature at index {idx} coordinates out of range: [{lon}, {lat}]")
        if not isinstance(f.get("properties"), dict):
            errors.append(f"Feature at index {idx} missing properties object.")

    return len(errors) == 0, errors
