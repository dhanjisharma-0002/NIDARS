"""Automated test suite for NIDARS Phase 10 AI-Based Early Warning & Advisory System."""

import pytest

from app import create_app
from config import TestConfig
from extensions import db
from models.alert import AlertEvent
from services.advisory_service import (
    DISCLAIMER_TEXT,
    classify_hazard_risk,
    generate_advisory_text,
    generate_live_station_alerts,
    get_advisory_summary_stats,
    get_alert_by_id_or_code,
    get_recommended_precautions,
    sync_alerts_to_history,
)


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


# --- Unit Tests: Risk Classification Rules ---

def test_classify_hazard_risk_flood():
    assert classify_hazard_risk("flood", 0.10) == "LOW"
    assert classify_hazard_risk("flood", 0.249) == "LOW"
    assert classify_hazard_risk("flood", 0.25) == "MODERATE"
    assert classify_hazard_risk("flood", 0.499) == "MODERATE"
    assert classify_hazard_risk("flood", 0.50) == "HIGH"
    assert classify_hazard_risk("flood", 0.749) == "HIGH"
    assert classify_hazard_risk("flood", 0.75) == "CRITICAL"
    assert classify_hazard_risk("flood", 0.95) == "CRITICAL"


def test_classify_hazard_risk_landslide():
    assert classify_hazard_risk("landslide", 0.01) == "LOW"
    assert classify_hazard_risk("landslide", 0.019) == "LOW"
    assert classify_hazard_risk("landslide", 0.02) == "MODERATE"
    assert classify_hazard_risk("landslide", 0.099) == "MODERATE"
    assert classify_hazard_risk("landslide", 0.10) == "HIGH"
    assert classify_hazard_risk("landslide", 0.249) == "HIGH"
    assert classify_hazard_risk("landslide", 0.25) == "CRITICAL"
    assert classify_hazard_risk("landslide", 0.85) == "CRITICAL"


def test_classify_hazard_risk_combined():
    assert classify_hazard_risk("combined", 0.15) == "LOW"
    assert classify_hazard_risk("combined", 0.35) == "MODERATE"
    assert classify_hazard_risk("combined", 0.65) == "HIGH"
    assert classify_hazard_risk("combined", 0.80) == "CRITICAL"


def test_classify_hazard_risk_edge_cases():
    # Out of range clamped to [0, 1]
    assert classify_hazard_risk("flood", -0.5) == "LOW"
    assert classify_hazard_risk("flood", 1.5) == "CRITICAL"
    # Invalid string clamped to 0.0
    assert classify_hazard_risk("flood", "invalid") == "LOW"


# --- Unit Tests: Advisory Text & Precautions ---

def test_generate_advisory_text():
    telemetry = {"rainfall_24h": 65.0, "wind_speed": 12.0, "elevation": 1800.0}
    text = generate_advisory_text("flood", "CRITICAL", "Shimla", telemetry)
    assert "Shimla" in text
    assert "flood hazard" in text.lower()
    assert "65.0 mm" in text

    ls_text = generate_advisory_text("landslide", "HIGH", "Manali", telemetry)
    assert "Manali" in ls_text
    assert "landslide" in ls_text.lower()


def test_get_recommended_precautions():
    precautions_crit = get_recommended_precautions("flood", "CRITICAL")
    assert len(precautions_crit) >= 3
    assert any("evacuate" in p.lower() or "higher ground" in p.lower() for p in precautions_crit)

    precautions_low = get_recommended_precautions("landslide", "LOW")
    assert len(precautions_low) >= 2


# --- Unit Tests: Station Alert Generation & Aggregations ---

def test_generate_live_station_alerts_all():
    alerts = generate_live_station_alerts(hazard_type="combined")
    assert len(alerts) == 64
    first = alerts[0]
    assert "alert_code" in first
    assert "station_name" in first
    assert "probability" in first
    assert "risk_level" in first
    assert "disclaimer" in first
    assert first["disclaimer"] == DISCLAIMER_TEXT


def test_generate_live_station_alerts_filtered():
    hp_alerts = generate_live_station_alerts(hazard_type="combined", state="HP")
    assert len(hp_alerts) == 11
    assert all(a["state_code"] == "HP" for a in hp_alerts)

    limited = generate_live_station_alerts(hazard_type="combined", limit=5)
    assert len(limited) == 5


def test_get_advisory_summary_stats():
    summary = get_advisory_summary_stats()
    assert summary["total_monitored_stations"] == 64
    dist = summary["distribution"]
    total_dist = dist["CRITICAL"] + dist["HIGH"] + dist["MODERATE"] + dist["LOW"]
    assert total_dist == 64
    assert len(summary["top_risk_locations"]) <= 5
    assert "HP" in summary["state_distribution"]


def test_get_alert_by_id_or_code(app):
    with app.app_context():
        alerts = generate_live_station_alerts(hazard_type="combined")
        sample_code = alerts[0]["alert_code"]
        found = get_alert_by_id_or_code(sample_code)
        assert found is not None
        assert found["alert_code"] == sample_code

        not_found = get_alert_by_id_or_code("NONEXISTENT-ALERT-999")
        assert not_found is None


def test_sync_alerts_to_history(app):
    with app.app_context():
        saved = sync_alerts_to_history(min_level="LOW")
        assert saved > 0
        events = AlertEvent.query.all()
        assert len(events) == saved


# --- Integration Tests: Endpoints & Views ---

def test_alerts_page_view(client):
    response = client.get("/alerts")
    assert response.status_code == 200
    assert b"Early Warning" in response.data
    assert b"Academic" in response.data
    assert b"disclaimer" in response.data.lower()


def test_api_get_alerts_success(client):
    response = client.get("/api/alerts")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] > 0
    assert "alerts" in data
    assert "disclaimer" in data


def test_api_get_alerts_filter_state(client):
    response = client.get("/api/alerts?state=HP&hazard=flood")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] == 11
    assert all(a["state_code"] == "HP" for a in data["alerts"])


def test_api_get_alerts_invalid_limit(client):
    response = client.get("/api/alerts?limit=notanumber")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "positive integer" in data["error"].lower()


def test_api_get_alerts_summary(client):
    response = client.get("/api/alerts/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["summary"]["total_monitored_stations"] == 64
    assert "distribution" in data["summary"]


def test_api_get_alert_detail_success_and_404(client):
    # Fetch first alert code
    res_list = client.get("/api/alerts?limit=1")
    code = res_list.get_json()["alerts"][0]["alert_code"]

    res_detail = client.get(f"/api/alerts/{code}")
    assert res_detail.status_code == 200
    data = res_detail.get_json()
    assert data["success"] is True
    assert data["alert"]["alert_code"] == code

    res_404 = client.get("/api/alerts/INVALID-CODE-000")
    assert res_404.status_code == 404
    data_404 = res_404.get_json()
    assert data_404["success"] is False


def test_api_sync_alerts(client):
    response = client.post("/api/alerts/sync")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "saved_count" in data
