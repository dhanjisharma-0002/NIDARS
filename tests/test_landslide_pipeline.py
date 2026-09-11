import pandas as pd
import pytest

from ml.landslide.feature_schema import (
    FEATURE_COLUMNS,
    LandslideSchemaError,
    MISSING_DATASET_MESSAGE,
    risk_level_from_probability,
    validate_feature_payload,
)
from ml.landslide.preprocess import (
    load_raw_csv,
    prepare_training_frame,
    resolve_dataset_path,
)

VALID_LANDSLIDE_PAYLOAD = {
    "rainfall_24h": 85.0,
    "rainfall_72h": 190.0,
    "rainfall_7d": 310.0,
    "temperature": 22.5,
    "wind_speed": 5.4,
    "air_pressure": 1005.0,
    "elevation": 1850.0,
    "latitude": 32.2667,
    "longitude": 77.1667,
}


def test_landslide_required_features_listed():
    assert "rainfall_24h" in FEATURE_COLUMNS
    assert "rainfall_72h" in FEATURE_COLUMNS
    assert "rainfall_7d" in FEATURE_COLUMNS
    assert "elevation" in FEATURE_COLUMNS
    assert "latitude" in FEATURE_COLUMNS
    assert "longitude" in FEATURE_COLUMNS
    assert len(FEATURE_COLUMNS) == 9


def test_theoretical_gis_features_not_required():
    theoretical = ["slope", "aspect", "soil_moisture", "distance_to_road", "distance_to_river", "vegetation_index"]
    for feat in theoretical:
        assert feat not in FEATURE_COLUMNS


def test_landslide_valid_payload_passes():
    cleaned, errors = validate_feature_payload(VALID_LANDSLIDE_PAYLOAD)
    assert errors == []
    assert cleaned["rainfall_24h"] == 85.0
    assert cleaned["elevation"] == 1850.0
    assert cleaned["latitude"] == 32.2667


def test_landslide_missing_fields():
    payload = dict(VALID_LANDSLIDE_PAYLOAD)
    del payload["rainfall_72h"]
    cleaned, errors = validate_feature_payload(payload)
    assert cleaned == {}
    assert any("rainfall_72h" in err for err in errors)


def test_landslide_invalid_numeric():
    payload = dict(VALID_LANDSLIDE_PAYLOAD)
    payload["temperature"] = "hot"
    cleaned, errors = validate_feature_payload(payload)
    assert cleaned == {}
    assert any("temperature" in err for err in errors)


def test_landslide_out_of_range_temperature():
    payload = dict(VALID_LANDSLIDE_PAYLOAD)
    payload["temperature"] = 85.0
    _, errors = validate_feature_payload(payload)
    assert errors


def test_landslide_risk_level_bands():
    assert risk_level_from_probability(0.0) == "LOW"
    assert risk_level_from_probability(0.24) == "LOW"
    assert risk_level_from_probability(0.25) == "MODERATE"
    assert risk_level_from_probability(0.49) == "MODERATE"
    assert risk_level_from_probability(0.50) == "HIGH"
    assert risk_level_from_probability(0.74) == "HIGH"
    assert risk_level_from_probability(0.75) == "CRITICAL"
    assert risk_level_from_probability(1.0) == "CRITICAL"


def test_landslide_dataset_path_points_to_processed_csv():
    path = resolve_dataset_path()
    assert path.name == "landslide_training.csv"
    assert path.parent.name == "processed"


def test_landslide_load_raw_csv_missing_file(tmp_path):
    missing = tmp_path / "landslide_training.csv"
    with pytest.raises(FileNotFoundError, match="Landslide dataset not found"):
        load_raw_csv(missing)


def test_landslide_alias_mapping_and_cleaning():
    raw = pd.DataFrame(
        {
            "rain_24h": [10, 80, 10],
            "rainfall_72h": [20, 150, 20],
            "rainfall_7d": [40, 300, 40],
            "temp": [18, 25, 18],
            "wind": [3.2, 8.5, 3.2],
            "pressure": [1010, 998, 1010],
            "altitude": [1200, 2200, 1200],
            "lat": [32.1, 31.8, 32.1],
            "lon": [76.5, 77.2, 76.5],
            "landslide_occurred": [0, 1, 0],
        }
    )
    frame = prepare_training_frame(raw)
    assert set(FEATURE_COLUMNS).issubset(frame.columns)
    assert frame["landslide_risk"].nunique() == 2
    assert len(frame) == 2


def test_prepared_dataset_positives_and_deduplication():
    csv_path = resolve_dataset_path()
    if csv_path.is_file():
        raw = pd.read_csv(csv_path)
        assert raw["landslide_risk"].isin([0, 1]).all()
        positives_before = (raw["landslide_risk"] == 1).sum()
        assert positives_before == 56

        frame = prepare_training_frame(raw)
        positives_after = (frame["landslide_risk"] == 1).sum()
        assert positives_after == 56, "Deduplication must not remove any positive samples"


def test_landslide_missing_required_columns_raises():
    raw = pd.DataFrame({"rainfall_24h": [10], "landslide_risk": [0]})
    with pytest.raises(LandslideSchemaError, match="missing required columns"):
        prepare_training_frame(raw)
