"""Unit and integration tests for Phase 7 Emergency Mode and Facility Discovery."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from config import TestConfig
from extensions import db
from models.emergency_facility import EmergencyFacility
from models.emergency_request import EmergencyRequest
from models.user import User
from services.emergency_service import (
    fetch_osm_emergency_facilities,
    get_current_location_risk,
    rank_facilities_by_safety,
    validate_emergency_coordinates,
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


# --- Coordinate Validation Unit Tests ---

def test_validate_emergency_coordinates_valid():
    coords, errors = validate_emergency_coordinates(28.6139, 77.2090)
    assert len(errors) == 0
    assert coords == (28.6139, 77.2090)


def test_validate_emergency_coordinates_missing():
    coords, errors = validate_emergency_coordinates(28.6139, None)
    assert coords is None
    assert any("Longitude" in e for e in errors)


def test_validate_emergency_coordinates_out_of_bounds():
    coords, errors = validate_emergency_coordinates(95.0, 77.2090)
    assert coords is None
    assert any("Latitude" in e for e in errors)

    coords, errors = validate_emergency_coordinates(28.6139, 195.0)
    assert coords is None
    assert any("Longitude" in e for e in errors)


def test_validate_emergency_coordinates_non_numeric():
    coords, errors = validate_emergency_coordinates("invalid_lat", 77.2090)
    assert coords is None
    assert any("numeric" in e for e in errors)


# --- Emergency Service Unit Tests ---

def test_get_current_location_risk_covered_station(app):
    with app.app_context():
        # Shimla station coordinates (~31.1048, 77.1734) in HP
        risk_data = get_current_location_risk(31.1048, 77.1734)
        assert risk_data is not None
        assert "is_covered" in risk_data
        assert "flood_probability" in risk_data
        assert "landslide_probability" in risk_data
        assert "combined_risk" in risk_data
        assert "risk_level" in risk_data
        if risk_data["is_covered"]:
            assert 0.0 <= risk_data["flood_probability"] <= 1.0
            assert 0.0 <= risk_data["landslide_probability"] <= 1.0
            assert 0.0 <= risk_data["combined_risk"] <= 1.0


def test_get_current_location_risk_uncovered_coordinates(app):
    with app.app_context():
        # Far outside North India (e.g. equatorial ocean)
        risk_data = get_current_location_risk(0.0, 0.0)
        assert risk_data is not None
        assert risk_data["is_covered"] is False
        assert risk_data["flood_probability"] is None
        assert risk_data["risk_level"] == "UNKNOWN"


def test_rank_facilities_by_safety(app):
    with app.app_context():
        sample_facilities = [
            {
                "name": "Close Facility",
                "latitude": 31.10,
                "longitude": 77.17,
                "distance_km": 2.0,
                "facility_type": "hospital",
            },
            {
                "name": "Farther Facility",
                "latitude": 31.15,
                "longitude": 77.20,
                "distance_km": 5.0,
                "facility_type": "hospital",
            },
        ]
        ranked = rank_facilities_by_safety(sample_facilities, user_lat=31.1048, user_lon=77.1734)
        assert len(ranked) == 2
        assert "safety_cost" in ranked[0]
        assert "facility_risk" in ranked[0]
        assert ranked[0]["safety_cost"] <= ranked[1]["safety_cost"]


# --- Authentication & Access Control Tests ---

def test_emergency_page_requires_auth(client):
    res = client.get("/emergency")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_emergency_page_authenticated(auth_client):
    res = auth_client.get("/emergency")
    assert res.status_code == 200
    assert b"Emergency Mode" in res.data
    assert b"RESEARCH &amp; PROTOTYPE ADVISORY" in res.data


def test_emergency_risk_api_requires_auth(client):
    res = client.get("/api/emergency/risk?lat=28.6139&lon=77.2090")
    assert res.status_code == 401
    assert res.get_json()["success"] is False


def test_emergency_facilities_api_requires_auth(client):
    res = client.get("/api/emergency/facilities?lat=28.6139&lon=77.2090")
    assert res.status_code == 401


def test_emergency_nearest_api_requires_auth(client):
    res = client.get("/api/emergency/nearest?lat=28.6139&lon=77.2090")
    assert res.status_code == 401


def test_emergency_route_api_requires_auth(client):
    res = client.get("/api/emergency/route?start_lat=28.61&start_lon=77.20&facility_lat=28.65&facility_lon=77.22")
    assert res.status_code == 401


# --- API Validation & Response Tests ---

def test_emergency_risk_api_success(auth_client):
    res = auth_client.get("/api/emergency/risk?lat=31.1048&lon=77.1734")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "risk_status" in data
    assert "coordinates" in data


def test_emergency_risk_api_invalid_coords(auth_client):
    res = auth_client.get("/api/emergency/risk?lat=120.0&lon=77.2090")
    assert res.status_code == 400
    assert res.get_json()["success"] is False


def test_emergency_facilities_invalid_type(auth_client):
    res = auth_client.get("/api/emergency/facilities?lat=28.61&lon=77.20&type=supermarket")
    assert res.status_code == 400
    assert "Invalid facility type" in res.get_json()["errors"][0]


def test_emergency_facilities_invalid_radius(auth_client):
    res = auth_client.get("/api/emergency/facilities?lat=28.61&lon=77.20&radius_km=-5")
    assert res.status_code == 400


MOCK_OVERPASS_RESPONSE = {
    "elements": [
        {
            "type": "node",
            "id": 1001,
            "lat": 28.6200,
            "lon": 77.2100,
            "tags": {
                "amenity": "hospital",
                "name": "AIIMS New Delhi",
                "addr:street": "Sri Aurobindo Marg",
                "addr:city": "New Delhi",
                "phone": "+91-11-26588500",
                "opening_hours": "24/7",
            }
        },
        {
            "type": "node",
            "id": 1002,
            "lat": 28.6150,
            "lon": 77.2050,
            "tags": {
                "amenity": "police",
                "name": "Parliament Street Police Station",
                "phone": "+91-11-23361100",
            }
        },
        {
            "type": "way",
            "id": 1003,
            "center": {"lat": 28.6300, "lon": 77.2200},
            "tags": {
                "amenity": "shelter",
                "name": "Community Relief Shelter",
            }
        }
    ]
}


@patch("urllib.request.urlopen")
def test_emergency_facilities_mock_overpass(mock_urlopen, auth_client):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(MOCK_OVERPASS_RESPONSE).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    res = auth_client.get("/api/emergency/facilities?lat=28.6139&lon=77.2090&radius_km=10&type=all")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["success"] is True

    facilities = payload["facilities"]
    assert len(facilities) == 3

    # Sorted by nearest distance first
    assert facilities[0]["distance_km"] <= facilities[1]["distance_km"] <= facilities[2]["distance_km"]

    # Check fields
    first = facilities[0]
    assert first["name"] in ["Parliament Street Police Station", "AIIMS New Delhi", "Community Relief Shelter"]
    assert first["source"] == "OpenStreetMap"
    assert "distance_km" in first
    assert "latitude" in first
    assert "longitude" in first


@patch("urllib.request.urlopen")
def test_emergency_nearest_mock_overpass(mock_urlopen, auth_client):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(MOCK_OVERPASS_RESPONSE).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    res = auth_client.get("/api/emergency/nearest?lat=28.6139&lon=77.2090&type=hospital")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["success"] is True
    assert payload["nearest_by_distance"]["facility_type"] == "hospital"
    assert payload["nearest_by_distance"]["name"] == "AIIMS New Delhi"


@patch("urllib.request.urlopen")
def test_emergency_external_service_failure(mock_urlopen, auth_client):
    # Simulate network failure to Overpass API
    mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

    res = auth_client.get("/api/emergency/facilities?lat=28.6139&lon=77.2090")
    # Controlled fallback response
    assert res.status_code in [200, 502]
    payload = res.get_json()
    if res.status_code == 502:
        assert payload["success"] is False
    else:
        # Graceful fallback to cached facilities
        assert payload["success"] is True


MOCK_OSRM_ROUTE_RESPONSE = {
    "code": "Ok",
    "routes": [
        {
            "distance": 3500.0,
            "duration": 420.0,
            "weight_name": "routability",
            "weight": 450.0,
            "geometry": {
                "coordinates": [
                    [77.2090, 28.6139],
                    [77.2100, 28.6200],
                ],
                "type": "LineString",
            },
            "legs": [],
        }
    ],
    "waypoints": [],
}


@patch("urllib.request.urlopen")
def test_emergency_route_integration(mock_urlopen, auth_client):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(MOCK_OSRM_ROUTE_RESPONSE).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    res = auth_client.get(
        "/api/emergency/route?start_lat=28.6139&start_lon=77.2090&facility_lat=28.6200&facility_lon=77.2100"
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["success"] is True
    assert "routes" in payload
    routes = payload["routes"]
    assert len(routes) >= 1
    metrics = routes[0]["metrics"]
    assert metrics["distance_km"] == pytest.approx(3.5, abs=0.1)
    assert "average_combined_risk" in metrics
    assert "route_cost" in metrics


def test_emergency_request_logged_in_db(app, auth_client):
    with app.app_context():
        initial_count = EmergencyRequest.query.count()

    auth_client.get("/api/emergency/risk?lat=31.1048&lon=77.1734")

    with app.app_context():
        new_count = EmergencyRequest.query.count()
        assert new_count == initial_count + 1
        last_req = EmergencyRequest.query.order_by(EmergencyRequest.id.desc()).first()
        assert last_req.request_type == "risk_check"
        assert last_req.latitude == pytest.approx(31.1048, abs=1e-4)
