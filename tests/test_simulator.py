"""Unit and integration tests for Phase 13 What-If Disaster Risk Simulator."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app import create_app
from config import TestConfig
from extensions import db
from services.simulator_service import (
    SIMULATION_DISCLAIMER,
    get_simulation_presets,
    get_station_baselines,
    simulate_risk_scenario,
)
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
def sample_baseline():
    return {
        "rainfall_24h": 20.0,
        "rainfall_72h": 40.0,
        "rainfall_7d": 60.0,
        "temperature": 25.0,
        "wind_speed": 10.0,
        "air_pressure": 1012.0,
        "elevation": 350.0,
        "latitude": 30.5,
        "longitude": 78.0,
    }


@pytest.fixture
def sample_scenario():
    return {
        "rainfall_24h": 120.0,
        "rainfall_72h": 220.0,
        "rainfall_7d": 350.0,
        "temperature": 22.0,
        "wind_speed": 35.0,
        "air_pressure": 995.0,
        "elevation": 350.0,
        "latitude": 30.5,
        "longitude": 78.0,
    }


def test_simulation_presets_structure():
    presets = get_simulation_presets()
    assert isinstance(presets, list)
    assert len(presets) >= 4
    for p in presets:
        assert "id" in p
        assert "name" in p
        assert "deltas" in p
        assert isinstance(p["deltas"], dict)


def test_station_baselines_loading(app):
    with app.app_context():
        stations = get_station_baselines(limit=5)
        assert isinstance(stations, list)
        if len(stations) > 0:
            assert "station_name" in stations[0]
            assert "features" in stations[0]
            assert "rainfall_24h" in stations[0]["features"]


def test_simulate_risk_scenario_valid_combined(app, sample_baseline, sample_scenario):
    with app.app_context():
        res = simulate_risk_scenario(
            current_payload=sample_baseline,
            scenario_payload=sample_scenario,
            hazard_type="combined",
        )

        assert res["success"] is True
        assert res["http_status"] == 200
        assert res["disclaimer"] == SIMULATION_DISCLAIMER
        assert "flood" in res
        assert "landslide" in res
        assert "combined" in res
        assert "feature_deltas" in res

        # In elevated scenario, simulated risk should be higher than baseline
        assert res["combined"]["simulated_risk"] >= res["combined"]["current_risk"]
        assert res["combined"]["delta_pct_points"] >= 0
        assert res["impact_direction"] == "INCREASED"
        assert "percentage points" in res["impact_summary"]


def test_simulate_risk_scenario_flood_focus(app, sample_baseline, sample_scenario):
    with app.app_context():
        res = simulate_risk_scenario(
            current_payload=sample_baseline,
            scenario_payload=sample_scenario,
            hazard_type="flood",
        )
        assert res["success"] is True
        assert res["hazard_type"] == "flood"
        assert "Flood Risk" in res["impact_summary"]


def test_simulate_risk_scenario_landslide_focus(app, sample_baseline, sample_scenario):
    with app.app_context():
        res = simulate_risk_scenario(
            current_payload=sample_baseline,
            scenario_payload=sample_scenario,
            hazard_type="landslide",
        )
        assert res["success"] is True
        assert res["hazard_type"] == "landslide"
        assert "Landslide Risk" in res["impact_summary"]


def test_simulate_risk_scenario_decreased_risk(app, sample_baseline):
    with app.app_context():
        # High base, dry scenario
        high_base = {
            "rainfall_24h": 200.0,
            "rainfall_72h": 350.0,
            "rainfall_7d": 500.0,
            "temperature": 20.0,
            "wind_speed": 40.0,
            "air_pressure": 980.0,
            "elevation": 500.0,
            "latitude": 30.5,
            "longitude": 78.0,
        }
        dry_scenario = {
            "rainfall_24h": 0.0,
            "rainfall_72h": 5.0,
            "rainfall_7d": 10.0,
            "temperature": 28.0,
            "wind_speed": 5.0,
            "air_pressure": 1018.0,
            "elevation": 500.0,
            "latitude": 30.5,
            "longitude": 78.0,
        }

        res = simulate_risk_scenario(
            current_payload=high_base,
            scenario_payload=dry_scenario,
            hazard_type="combined",
        )
        assert res["success"] is True
        assert res["impact_direction"] == "DECREASED"
        assert res["combined"]["delta_pct_points"] <= 0


def test_simulate_risk_scenario_missing_field(app, sample_baseline, sample_scenario):
    with app.app_context():
        bad_base = sample_baseline.copy()
        del bad_base["rainfall_24h"]

        res = simulate_risk_scenario(
            current_payload=bad_base,
            scenario_payload=sample_scenario,
        )
        assert res["success"] is False
        assert res["http_status"] == 400
        assert any("rainfall_24h" in e for e in res["errors"])


def test_simulate_risk_scenario_out_of_bounds(app, sample_baseline, sample_scenario):
    with app.app_context():
        bad_scenario = sample_scenario.copy()
        bad_scenario["temperature"] = 150.0  # Max is 60

        res = simulate_risk_scenario(
            current_payload=sample_baseline,
            scenario_payload=bad_scenario,
        )
        assert res["success"] is False
        assert res["http_status"] == 400
        assert any("temperature" in e for e in res["errors"])


@patch("services.simulator_service.flood_model_status")
def test_simulate_risk_scenario_model_not_trained(mock_flood_status, app, sample_baseline, sample_scenario):
    mock_flood_status.return_value = "not_trained"
    with app.app_context():
        res = simulate_risk_scenario(
            current_payload=sample_baseline,
            scenario_payload=sample_scenario,
        )
        assert res["success"] is False
        assert res["http_status"] == 503
        assert any("Flood model is not trained" in e for e in res["errors"])


# --- Web Views & API Endpoint Tests ---


def test_simulator_view_requires_login(client):
    res = client.get("/simulator")
    assert res.status_code in {302, 401}


def test_simulator_view_authenticated(auth_client):
    res = auth_client.get("/simulator")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "What-If Disaster Risk Simulator" in html
    assert "Simulation Notice:" in html


def test_simulator_api_requires_login(client):
    res = client.post("/api/simulator/simulate", json={})
    assert res.status_code == 401


def test_simulator_api_simulate_success(auth_client, sample_baseline, sample_scenario):
    payload = {
        "current": sample_baseline,
        "scenario": sample_scenario,
        "hazard_type": "combined",
        "flood_weight": 0.6,
        "landslide_weight": 0.4,
    }
    res = auth_client.post("/api/simulator/simulate", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "impact_summary" in data
    assert "flood" in data
    assert "landslide" in data
    assert "combined" in data
    assert data["combined"]["weights"]["flood"] == 0.6
    assert data["disclaimer"] == SIMULATION_DISCLAIMER


def test_simulator_api_invalid_json(auth_client):
    res = auth_client.post(
        "/api/simulator/simulate",
        data="not json",
        content_type="text/plain",
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False


def test_simulator_api_missing_scenario_object(auth_client, sample_baseline):
    payload = {"current": sample_baseline}
    res = auth_client.post("/api/simulator/simulate", json=payload)
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert any("scenario" in e for e in data["errors"])


def test_simulator_api_invalid_weights(auth_client, sample_baseline, sample_scenario):
    payload = {
        "current": sample_baseline,
        "scenario": sample_scenario,
        "flood_weight": 1.5,
    }
    res = auth_client.post("/api/simulator/simulate", json=payload)
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False


def test_simulator_api_presets(auth_client):
    res = auth_client.get("/api/simulator/presets")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "presets" in data
    assert len(data["presets"]) >= 4
