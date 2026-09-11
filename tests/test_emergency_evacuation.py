"""Unit and integration tests for Phase 14 Emergency Evacuation & Safe Zone Analysis."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from app import create_app
from config import TestConfig
from extensions import db
from models.emergency_facility import (
    FACILITY_HOSPITAL,
    FACILITY_POLICE,
    FACILITY_SHELTER,
    EmergencyFacility,
)
from models.emergency_request import EmergencyRequest
from services.emergency_service import (
    analyze_evacuation_safe_zones,
    calculate_safe_zone_score,
    generate_recommendation_reason,
)
from tests.conftest import login, make_user


@pytest.fixture
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        # Seed test emergency facilities in Shimla area (~31.10, 77.17)
        fac1 = EmergencyFacility(
            name="Shimla Municipal Evacuation Shelter",
            facility_type=FACILITY_SHELTER,
            latitude=31.1080,
            longitude=77.1750,
            address="Town Hall, Shimla",
            phone="1077",
            source="OpenStreetMap",
            external_id="osm_node_1001",
            is_active=True,
        )
        fac2 = EmergencyFacility(
            name="IGMC Hospital Shimla",
            facility_type=FACILITY_HOSPITAL,
            latitude=31.1048,
            longitude=77.1834,
            address="Ridge, Shimla",
            phone="+91-177-2804251",
            source="OpenStreetMap",
            external_id="osm_node_1002",
            is_active=True,
        )
        fac3 = EmergencyFacility(
            name="Sadar Police Station Shimla",
            facility_type=FACILITY_POLICE,
            latitude=31.1030,
            longitude=77.1680,
            address="Mall Road, Shimla",
            phone="112",
            source="OpenStreetMap",
            external_id="osm_node_1003",
            is_active=True,
        )
        db.session.add_all([fac1, fac2, fac3])
        db.session.commit()

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


# --- 1. Unit Tests for Safe Zone Scoring ---

def test_calculate_safe_zone_score_deterministic():
    """Verify Safe Zone Score formula calculation."""
    # Shelter with low risk and short distance
    score_shelter = calculate_safe_zone_score(
        dest_risk=0.10,
        route_risk=0.10,
        distance_km=2.5,
        facility_type="shelter",
        max_distance_km=50.0,
    )
    # Hospital with same risk and distance
    score_hospital = calculate_safe_zone_score(
        dest_risk=0.10,
        route_risk=0.10,
        distance_km=2.5,
        facility_type="hospital",
        max_distance_km=50.0,
    )
    # Police station with same risk and distance
    score_police = calculate_safe_zone_score(
        dest_risk=0.10,
        route_risk=0.10,
        distance_km=2.5,
        facility_type="police",
        max_distance_km=50.0,
    )

    # Shelter offset is 0.00, Hospital is 0.05, Police is 0.10
    assert score_shelter < score_hospital < score_police
    assert 0.0 <= score_shelter <= 1.0


def test_calculate_safe_zone_score_higher_risk_increases_score():
    """Higher hazard exposure strictly increases safe zone score (worse rank)."""
    score_low = calculate_safe_zone_score(
        dest_risk=0.10,
        route_risk=0.10,
        distance_km=5.0,
        facility_type="shelter",
    )
    score_high = calculate_safe_zone_score(
        dest_risk=0.80,
        route_risk=0.80,
        distance_km=5.0,
        facility_type="shelter",
    )
    assert score_low < score_high


def test_generate_recommendation_reason():
    """Test authentic reason generation strings."""
    reason = generate_recommendation_reason(
        facility={"facility_type": "shelter", "name": "Safe Shelter A"},
        is_shelter=True,
        dest_risk_level="LOW",
        route_risk_level="LOW",
        dist_km=3.2,
        eta_min=9.0,
    )
    assert "shelter" in reason.lower()
    assert "3.2 km" in reason


# --- 2. Authentication & Authorization Tests ---

def test_evacuation_api_requires_auth(client):
    """Unauthenticated call to /api/emergency/evacuation must return 401."""
    res = client.post(
        "/api/emergency/evacuation",
        json={"latitude": 31.1048, "longitude": 77.1734},
    )
    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False


def test_emergency_page_unauthenticated_redirects(client):
    """Unauthenticated access to /emergency must redirect to login."""
    res = client.get("/emergency")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_emergency_page_authenticated_renders(auth_client):
    """Authenticated user can load /emergency."""
    res = auth_client.get("/emergency")
    assert res.status_code == 200
    assert b"Emergency" in res.data


# --- 3. Coordinate & Input Validation Tests ---

def test_evacuation_api_valid_coordinates(auth_client):
    """Valid coordinates return 200 with complete response schema."""
    res = auth_client.post(
        "/api/emergency/evacuation",
        json={"latitude": 31.1048, "longitude": 77.1734, "max_distance_km": 15.0},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "origin" in data
    assert "current_risk" in data
    assert "recommended_destination" in data
    assert "destinations" in data
    assert "routes" in data
    assert "generated_at" in data
    assert "disclaimer" in data


def test_evacuation_api_invalid_latitude(auth_client):
    """Out-of-bounds latitude returns 400 Bad Request."""
    res = auth_client.post(
        "/api/emergency/evacuation",
        json={"latitude": 95.0, "longitude": 77.1734},
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert any("Latitude" in e for e in data["errors"])


def test_evacuation_api_invalid_longitude(auth_client):
    """Out-of-bounds longitude returns 400 Bad Request."""
    res = auth_client.post(
        "/api/emergency/evacuation",
        json={"latitude": 31.1048, "longitude": 195.0},
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert any("Longitude" in e for e in data["errors"])


def test_evacuation_api_missing_coordinates(auth_client):
    """Missing coordinates returns 400 Bad Request."""
    res = auth_client.post(
        "/api/emergency/evacuation",
        json={"latitude": 31.1048},
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert any("Longitude" in e for e in data["errors"])


def test_evacuation_api_non_numeric_coordinates(auth_client):
    """Non-numeric string coordinates return 400."""
    res = auth_client.post(
        "/api/emergency/evacuation",
        json={"latitude": "invalid", "longitude": 77.1734},
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert any("numeric" in e for e in data["errors"])


def test_evacuation_api_nan_infinity(auth_client):
    """NaN or Infinity coordinate values return 400."""
    res = auth_client.post(
        "/api/emergency/evacuation",
        json={"latitude": float("nan"), "longitude": 77.1734},
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False


def test_evacuation_api_invalid_radius(auth_client):
    """Negative or excessive radius returns 400."""
    res = auth_client.post(
        "/api/emergency/evacuation",
        json={"latitude": 31.1048, "longitude": 77.1734, "max_distance_km": -5.0},
    )
    assert res.status_code == 400
    data = res.get_json()
    assert any("max_distance_km" in e for e in data["errors"])


def test_evacuation_api_invalid_facility_types(auth_client):
    """Invalid facility type returns 400."""
    res = auth_client.post(
        "/api/emergency/evacuation",
        json={"latitude": 31.1048, "longitude": 77.1734, "facility_types": ["airport", "supermarket"]},
    )
    assert res.status_code == 400
    data = res.get_json()
    assert any("facility types" in e.lower() for e in data["errors"])


# --- 4. Core Evacuation & Safe Zone Logic Tests ---

def test_evacuation_ranks_destinations_ascending_score(auth_client):
    """Destinations are strictly sorted in ascending order of Safe Zone Score."""
    res = auth_client.post(
        "/api/emergency/evacuation",
        json={"latitude": 31.1048, "longitude": 77.1734, "max_distance_km": 20.0},
    )
    assert res.status_code == 200
    data = res.get_json()
    destinations = data.get("destinations", [])
    assert len(destinations) >= 1

    # Verify scores are sorted non-decreasingly
    scores = [d["overall_score"] for d in destinations]
    assert scores == sorted(scores)

    # First destination is marked recommended
    assert destinations[0]["is_recommended"] is True
    assert data["recommended_destination"]["id"] == destinations[0]["id"]
    assert "reason" in data["recommended_destination"]


def test_evacuation_no_facilities_found_pacific(auth_client):
    """Query in remote location (e.g. ocean) handles zero facilities cleanly."""
    res = auth_client.post(
        "/api/emergency/evacuation",
        json={"latitude": 0.0, "longitude": 0.0, "max_distance_km": 5.0},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["total_found"] == 0
    assert data["recommended_destination"] is None
    assert "No emergency facilities found" in data["message"]


def test_evacuation_osrm_failure_graceful_fallback(app):
    """When OSRM is down, evacuation analysis falls back to straight-line metrics."""
    with app.app_context():
        with patch("services.routing_service.fetch_osrm_routes") as mock_osrm:
            mock_osrm.return_value = {"success": False, "message": "OSRM server timeout", "routes": []}
            result = analyze_evacuation_safe_zones(
                user_lat=31.1048,
                user_lon=77.1734,
                max_distance_km=15.0,
            )
            assert result["success"] is True
            assert result["total_found"] >= 1
            rec = result["recommended_destination"]
            assert rec is not None
            # Has distance and calculated score despite OSRM downtime
            assert rec["distance_km"] > 0
            assert rec["overall_score"] is not None
            assert rec["has_road_route"] is False


def test_evacuation_operational_logging(app, auth_client):
    """Evacuation analysis logs non-sensitive event to EmergencyRequest."""
    with app.app_context():
        init_count = EmergencyRequest.query.count()

    res = auth_client.post(
        "/api/emergency/evacuation",
        json={"latitude": 31.1048, "longitude": 77.1734},
    )
    assert res.status_code == 200

    with app.app_context():
        new_count = EmergencyRequest.query.count()
        assert new_count == init_count + 1
        latest = EmergencyRequest.query.order_by(EmergencyRequest.id.desc()).first()
        assert latest.request_type == "evacuation_analysis"
        assert latest.result_summary is not None
        assert "recommended_destination" in latest.result_summary


def test_evacuation_csrf_exempt_when_csrf_enabled(app, auth_client):
    """Regression test: when WTF_CSRF_ENABLED is True, POST /api/emergency/evacuation must succeed without 400."""
    app.config["WTF_CSRF_ENABLED"] = True
    res = auth_client.post(
        "/api/emergency/evacuation",
        json={"latitude": 31.1048, "longitude": 77.1734, "max_distance_km": 15.0},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["origin"]["latitude"] == 31.1048
    app.config["WTF_CSRF_ENABLED"] = False


def test_evacuation_structured_error_code_on_invalid_coords(auth_client):
    """Verify structured error response on invalid coordinates."""
    res = auth_client.post(
        "/api/emergency/evacuation",
        json={"latitude": 200.0, "longitude": 77.1734},
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert data["error"] == "INVALID_COORDINATES"
    assert "Latitude must be between" in data["message"]


def test_evacuation_manual_coordinates_dehradun(auth_client):
    """Verify manual coordinates flow (Dehradun 30.3165, 78.0322)."""
    res = auth_client.post(
        "/api/emergency/evacuation",
        json={"latitude": 30.3165, "longitude": 78.0322, "max_distance_km": 25.0},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["origin"]["latitude"] == 30.3165
    assert data["origin"]["longitude"] == 78.0322
    assert "current_risk" in data

