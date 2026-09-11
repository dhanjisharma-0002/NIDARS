import pandas as pd
import pytest

from app import create_app
from config import TestConfig
from extensions import db
from ml.flood.feature_schema import (
    FEATURE_COLUMNS,
    FloodSchemaError,
    MISSING_DATASET_MESSAGE,
    risk_level_from_probability,
    validate_feature_payload,
)
from ml.flood.preprocess import load_raw_csv, prepare_training_frame, resolve_dataset_path
from tests.conftest import VALID_FLOOD_PAYLOAD


@pytest.fixture
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def test_required_features_listed():
    assert "rainfall_24h" in FEATURE_COLUMNS
    assert len(FEATURE_COLUMNS) == 9


def test_valid_payload_passes():
    cleaned, errors = validate_feature_payload(VALID_FLOOD_PAYLOAD)
    assert errors == []
    assert cleaned["rainfall_24h"] == 120.0
    assert cleaned["temperature"] == 26.0


def test_missing_fields():
    payload = dict(VALID_FLOOD_PAYLOAD)
    del payload["temperature"]
    cleaned, errors = validate_feature_payload(payload)
    assert cleaned == {}
    assert any("temperature" in err for err in errors)


def test_invalid_numeric():
    payload = dict(VALID_FLOOD_PAYLOAD)
    payload["wind_speed"] = "fast"
    cleaned, errors = validate_feature_payload(payload)
    assert cleaned == {}
    assert any("wind_speed" in err for err in errors)


def test_out_of_range_temperature():
    payload = dict(VALID_FLOOD_PAYLOAD)
    payload["temperature"] = 100.0
    _, errors = validate_feature_payload(payload)
    assert errors


def test_risk_level_bands():
    assert risk_level_from_probability(0.0) == "LOW"
    assert risk_level_from_probability(0.24) == "LOW"
    assert risk_level_from_probability(0.25) == "MODERATE"
    assert risk_level_from_probability(0.49) == "MODERATE"
    assert risk_level_from_probability(0.50) == "HIGH"
    assert risk_level_from_probability(0.74) == "HIGH"
    assert risk_level_from_probability(0.75) == "CRITICAL"
    assert risk_level_from_probability(1.0) == "CRITICAL"


def test_dataset_path_points_to_processed_csv():
    path = resolve_dataset_path()
    assert path.name == "flood_training.csv"
    assert path.parent.name == "processed"


def test_load_raw_csv_missing_file(tmp_path):
    missing = tmp_path / "flood_training.csv"
    with pytest.raises(FileNotFoundError, match="Flood dataset not found"):
        load_raw_csv(missing)


def test_train_missing_dataset_message(tmp_path):
    from ml.flood.train import train

    with pytest.raises(FileNotFoundError) as exc:
        train(tmp_path / "does-not-exist.csv")
    assert "Flood dataset not found" in str(exc.value)


def test_alias_mapping_and_cleaning():
    raw = pd.DataFrame(
        {
            "rain_24h": [10, 80, 10],
            "rainfall_72h": [20, 150, 20],
            "rainfall_7d": [40, 300, 40],
            "temp": [22, 28, 22],
            "wind": [4.0, 12.0, 4.0],
            "pressure": [1012, 1005, 1012],
            "altitude": [400, 200, 400],
            "lat": [28.5, 27.2, 28.5],
            "lon": [77.2, 85.1, 77.2],
            "flood_occurred": [0, 1, 0],
        }
    )
    frame = prepare_training_frame(raw)
    assert set(FEATURE_COLUMNS).issubset(frame.columns)
    assert frame["flood_risk"].nunique() == 2
    assert len(frame) == 2


def test_missing_required_columns_raises():
    raw = pd.DataFrame({"rainfall_24h": [1], "flood_risk": [0]})
    with pytest.raises(FloodSchemaError, match="missing required columns"):
        prepare_training_frame(raw)
