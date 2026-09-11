"""Phase 14 — AI Prediction Explainability Tests.

Verifies model-compatible explainability, local marginal feature attribution,
top contributing factors sorting, horizontal chart data structuring,
error handling (model unavailable, invalid input, missing features),
and standard academic disclaimer validation.
"""

from __future__ import annotations

import json
from unittest.mock import patch
import pytest

from app import create_app
from config import TestConfig
from extensions import db
from ml.explainability import (
    EXPLAINABILITY_DISCLAIMER,
    FEATURE_METADATA,
    explain_prediction,
)
from ml.flood.feature_schema import FEATURE_COLUMNS as FLOOD_COLS
from ml.flood.predict import load_artifacts as load_flood_artifacts
from ml.landslide.feature_schema import FEATURE_COLUMNS as LANDSLIDE_COLS
from ml.landslide.predict import load_artifacts as load_landslide_artifacts
from models.prediction import PredictionHistory
from tests.conftest import login, make_user


@pytest.fixture
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(app, client):
    make_user(app)
    login(client)
    return client



@pytest.fixture
def valid_flood_payload():
    return {
        "rainfall_24h": 145.0,
        "rainfall_72h": 280.5,
        "rainfall_7d": 460.0,
        "temperature": 27.5,
        "wind_speed": 18.2,
        "air_pressure": 998.0,
        "elevation": 85.0,
        "latitude": 25.5941,
        "longitude": 85.1376,
    }


@pytest.fixture
def valid_landslide_payload():
    return {
        "rainfall_24h": 110.0,
        "rainfall_72h": 240.0,
        "rainfall_7d": 410.0,
        "temperature": 16.0,
        "wind_speed": 14.5,
        "air_pressure": 982.0,
        "elevation": 2276.0,
        "latitude": 31.1048,
        "longitude": 77.1734,
    }


# =========================================================================
# 1. CORE EXPLAINABILITY UNIT TESTS
# =========================================================================

def test_explain_prediction_flood_core(app, valid_flood_payload):
    """Test unit execution of explain_prediction on trained Flood model."""
    with app.app_context():
        model, preprocessor = load_flood_artifacts(
            app.config["FLOOD_MODEL_PATH"],
            app.config["FLOOD_PREPROCESSOR_PATH"],
        )
        assert model is not None
        assert preprocessor is not None

        result = explain_prediction(
            features_dict=valid_flood_payload,
            model=model,
            preprocessor=preprocessor,
            feature_columns=FLOOD_COLS,
            hazard_type="flood",
        )

        assert "top_contributing_factors" in result
        assert "chart_data" in result
        assert "disclaimer" in result
        assert result["disclaimer"] == EXPLAINABILITY_DISCLAIMER

        factors = result["top_contributing_factors"]
        assert len(factors) == len(FLOOD_COLS)

        # Verify factors structure
        for f in factors:
            assert "feature" in f
            assert "label" in f
            assert "impact" in f
            assert f["impact"] in ("HIGH", "MODERATE", "LOW")
            assert "direction" in f
            assert f["direction"] in ("POSITIVE", "NEGATIVE", "NEUTRAL")
            assert "contribution_score" in f
            assert "raw_delta" in f
            assert "current_value" in f
            assert "baseline_value" in f

        # Verify sorting by influence
        scores = [abs(f["contribution_score"]) for f in factors]
        assert scores == sorted(scores, reverse=True)

        # Verify chart data structure
        chart = result["chart_data"]
        assert len(chart["labels"]) == len(FLOOD_COLS)
        assert len(chart["contributions"]) == len(FLOOD_COLS)
        assert len(chart["colors"]) == len(FLOOD_COLS)


def test_explain_prediction_landslide_core(app, valid_landslide_payload):
    """Test unit execution of explain_prediction on trained Landslide model."""
    with app.app_context():
        model, preprocessor = load_landslide_artifacts(
            app.config["LANDSLIDE_MODEL_PATH"],
            app.config["LANDSLIDE_PREPROCESSOR_PATH"],
        )
        assert model is not None
        assert preprocessor is not None

        result = explain_prediction(
            features_dict=valid_landslide_payload,
            model=model,
            preprocessor=preprocessor,
            feature_columns=LANDSLIDE_COLS,
            hazard_type="landslide",
        )

        assert result["disclaimer"] == EXPLAINABILITY_DISCLAIMER
        factors = result["top_contributing_factors"]
        assert len(factors) == len(LANDSLIDE_COLS)

        impacts = {f["impact"] for f in factors}
        assert impacts.issubset({"HIGH", "MODERATE", "LOW"})


def test_explain_prediction_null_artifacts_error():
    """Verify ValueError is raised if model or preprocessor is missing."""
    with pytest.raises(ValueError, match="Model and preprocessor must be loaded"):
        explain_prediction({}, None, None, FLOOD_COLS)


# =========================================================================
# 2. INTEGRATION TESTS VIA PREDICTION APIS
# =========================================================================

def test_flood_prediction_api_returns_explainability(auth_client, valid_flood_payload):
    """Test that /api/predict/flood includes explainability in response payload."""
    res = auth_client.post(
        "/api/predict/flood",
        json=valid_flood_payload,
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "prediction" in data
    assert "explainability" in data
    assert data["explainability"] is not None

    expl = data["explainability"]
    assert expl["disclaimer"] == EXPLAINABILITY_DISCLAIMER
    assert len(expl["top_contributing_factors"]) == 9
    assert len(expl["chart_data"]["labels"]) == 9


def test_landslide_prediction_api_returns_explainability(auth_client, valid_landslide_payload):
    """Test that /api/predict/landslide includes explainability in response payload."""
    res = auth_client.post(
        "/api/predict/landslide",
        json=valid_landslide_payload,
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "prediction" in data
    assert "explainability" in data
    assert data["explainability"] is not None

    expl = data["explainability"]
    assert expl["disclaimer"] == EXPLAINABILITY_DISCLAIMER
    assert len(expl["top_contributing_factors"]) == 9


# =========================================================================
# 3. STANDALONE EXPLAIN API TESTS (/api/explain/<hazard>)
# =========================================================================

def test_explain_api_flood_endpoint(auth_client, valid_flood_payload):
    """Test standalone POST /api/explain/flood endpoint."""
    res = auth_client.post(
        "/api/explain/flood",
        json=valid_flood_payload,
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["hazard_type"] == "flood"
    assert "explainability" in data
    assert data["explainability"]["disclaimer"] == EXPLAINABILITY_DISCLAIMER


def test_explain_api_landslide_endpoint(auth_client, valid_landslide_payload):
    """Test standalone POST /api/explain/landslide endpoint."""
    res = auth_client.post(
        "/api/explain/landslide",
        json=valid_landslide_payload,
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["hazard_type"] == "landslide"
    assert "explainability" in data


def test_explain_api_invalid_hazard_type(auth_client, valid_flood_payload):
    """Test /api/explain/invalid returns 400 error."""
    res = auth_client.post(
        "/api/explain/earthquake",
        json=valid_flood_payload,
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert any("Invalid hazard type" in e for e in data["errors"])


def test_explain_api_non_json_body(auth_client):
    """Test /api/explain/flood with non-JSON payload returns 400 error."""
    res = auth_client.post(
        "/api/explain/flood",
        data="not-a-json",
        content_type="text/plain",
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False


# =========================================================================
# 4. ERROR & EDGE CASES (Invalid Input, Missing Feature, Model Unavailable)
# =========================================================================

def test_explain_invalid_input_numeric_types(auth_client, valid_flood_payload):
    """Test explainability request with non-numeric / invalid inputs returns 400."""
    bad_payload = dict(valid_flood_payload)
    bad_payload["rainfall_24h"] = "INVALID_NOT_A_NUMBER"

    res = auth_client.post(
        "/api/explain/flood",
        json=bad_payload,
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert any("rainfall_24h" in e for e in data["errors"])


def test_explain_missing_feature(auth_client, valid_flood_payload):
    """Test explainability request missing a required feature returns 400."""
    bad_payload = dict(valid_flood_payload)
    del bad_payload["rainfall_72h"]

    res = auth_client.post(
        "/api/explain/flood",
        json=bad_payload,
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert any("rainfall_72h" in e for e in data["errors"])


def test_explain_model_unavailable_returns_503(auth_client, valid_flood_payload):
    """Test that if model files are missing/unavailable, 503 is returned."""
    with patch("services.explainability_service.flood_files_exist", return_value=False):
        res = auth_client.post(
            "/api/explain/flood",
            json=valid_flood_payload,
        )
        assert res.status_code == 503
        data = res.get_json()
        assert data["success"] is False
        assert any("not available" in e for e in data["errors"])


# =========================================================================
# 5. DASHBOARD PREDICTION DETAILS & HISTORY EXPLAINABILITY
# =========================================================================

def test_recent_predictions_endpoint(auth_client, valid_flood_payload):
    """Test GET /api/predictions/recent returns predictions list with explainability."""
    # First make a prediction to ensure at least one record exists
    auth_client.post("/api/predict/flood", json=valid_flood_payload)

    res = auth_client.get("/api/predictions/recent?limit=5")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "predictions" in data
    assert isinstance(data["predictions"], list)
    assert len(data["predictions"]) > 0

    latest = data["predictions"][0]
    assert "id" in latest
    assert "prediction_type" in latest
    assert "risk_level" in latest
    assert "has_explainability" in latest


def test_explain_saved_prediction_endpoint(auth_client, valid_flood_payload, app):
    """Test GET /api/prediction/<id>/explain returns explainability for existing record."""
    # Make a prediction to store history
    pred_res = auth_client.post("/api/predict/flood", json=valid_flood_payload)
    assert pred_res.status_code == 200

    with app.app_context():
        rec = PredictionHistory.query.order_by(PredictionHistory.id.desc()).first()
        assert rec is not None
        rec_id = rec.id

    res = auth_client.get(f"/api/prediction/{rec_id}/explain")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["prediction_id"] == rec_id
    assert "explainability" in data
    assert data["explainability"]["disclaimer"] == EXPLAINABILITY_DISCLAIMER


def test_explain_saved_prediction_not_found(auth_client):
    """Test GET /api/prediction/999999/explain returns 404."""
    res = auth_client.get("/api/prediction/999999/explain")
    assert res.status_code == 404
    data = res.get_json()
    assert data["success"] is False
