import pytest

from app import create_app
from config import TestConfig
from extensions import db
from models import PredictionHistory
from tests.conftest import VALID_FLOOD_PAYLOAD, login, make_user


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


def test_predict_requires_login(client):
    response = client.post("/api/predict/flood", json=VALID_FLOOD_PAYLOAD)
    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_missing_json_body(auth_client):
    response = auth_client.post("/api/predict/flood", data="not-json")
    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False


def test_missing_fields_on_endpoint(auth_client):
    payload = dict(VALID_FLOOD_PAYLOAD)
    del payload["rainfall_24h"]
    response = auth_client.post("/api/predict/flood", json=payload)
    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["prediction"] is None
    assert any("rainfall_24h" in err for err in body["errors"])


def test_invalid_payload_on_endpoint(auth_client):
    payload = dict(VALID_FLOOD_PAYLOAD)
    payload["temperature"] = "hot"
    response = auth_client.post("/api/predict/flood", json=payload)
    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["prediction"] is None


def test_model_not_trained_behavior(app, auth_client, tmp_path):
    app.config["FLOOD_MODEL_PATH"] = tmp_path / "flood_model.pkl"
    app.config["FLOOD_PREPROCESSOR_PATH"] = tmp_path / "flood_preprocessor.pkl"
    response = auth_client.post("/api/predict/flood", json=VALID_FLOOD_PAYLOAD)
    assert response.status_code == 503
    body = response.get_json()
    assert body["success"] is False
    assert body["model_status"] == "not_trained"
    assert body["prediction"] is None
    assert "not trained" in body["errors"][0].lower()


def test_untrained_request_does_not_store_history(app, auth_client, tmp_path):
    app.config["FLOOD_MODEL_PATH"] = tmp_path / "flood_model.pkl"
    app.config["FLOOD_PREPROCESSOR_PATH"] = tmp_path / "flood_preprocessor.pkl"
    auth_client.post("/api/predict/flood", json=VALID_FLOOD_PAYLOAD)
    with app.app_context():
        assert PredictionHistory.query.count() == 0


@pytest.mark.skipif(
    not TestConfig.FLOOD_MODEL_PATH.is_file() or not TestConfig.FLOOD_PREPROCESSOR_PATH.is_file(),
    reason="Model-dependent: train with a legitimate dataset before enabling this test.",
)
def test_trained_prediction_persists_history(app, auth_client):
    response = auth_client.post("/api/predict/flood", json=VALID_FLOOD_PAYLOAD)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["model_status"] == "trained"
    assert "risk_level" in body["prediction"]
    with app.app_context():
        row = PredictionHistory.query.filter_by(prediction_type="flood").one()
        assert row.result_json["risk_level"] == body["prediction"]["risk_level"]
