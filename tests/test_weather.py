"""Automated test suite for NIDARS Phase 9 Real-Time Weather Monitoring."""

import json
import pytest
from unittest.mock import patch, MagicMock
from urllib.error import URLError

from app import create_app
from config import TestConfig
from extensions import db
from services.weather_service import (
    degrees_to_cardinal,
    evaluate_weather_risks,
    fetch_live_weather,
    find_station_by_name,
    get_available_stations,
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


# --- Unit Tests on Weather Logic & Conversions ---

def test_degrees_to_cardinal():
    assert degrees_to_cardinal(0) == "N"
    assert degrees_to_cardinal(90) == "E"
    assert degrees_to_cardinal(180) == "S"
    assert degrees_to_cardinal(270) == "W"
    assert degrees_to_cardinal(45) == "NE"
    assert degrees_to_cardinal(135) == "SE"
    assert degrees_to_cardinal(360) == "N"


def test_get_available_stations():
    stations = get_available_stations()
    assert len(stations) == 64
    state_codes = {s["state_code"] for s in stations}
    assert {"JK", "HP", "UP", "BR"}.issubset(state_codes)


def test_get_available_stations_filtered_by_state():
    hp_stations = get_available_stations(state_code="HP")
    assert len(hp_stations) == 11
    assert all(s["state_code"] == "HP" for s in hp_stations)

    up_stations = get_available_stations(state_code="UP")
    assert len(up_stations) == 31


def test_find_station_by_name():
    shimla = find_station_by_name("Shimla")
    assert shimla is not None
    assert shimla["state_code"] == "HP"
    assert pytest.approx(shimla["latitude"], 0.01) == 31.1048

    patna = find_station_by_name("patna")
    assert patna is not None
    assert patna["state_code"] == "BR"

    non_existent = find_station_by_name("NonExistentCity")
    assert non_existent is None


def test_evaluate_weather_risks_normal():
    risk = evaluate_weather_risks(rainfall_mm=2.0, wind_speed_ms=3.0, pressure_hpa=1012.0, temperature_c=25.0)
    assert risk["overall_status"] == "LOW"
    assert risk["rainfall_alert"] == "LOW"
    assert risk["wind_alert"] == "LOW"
    assert risk["pressure_alert"] == "LOW"


def test_evaluate_weather_risks_heavy_rainfall():
    risk = evaluate_weather_risks(rainfall_mm=75.0, wind_speed_ms=4.0, pressure_hpa=1010.0, temperature_c=22.0)
    assert risk["overall_status"] == "CRITICAL"
    assert risk["rainfall_alert"] == "CRITICAL"
    assert "flood risk" in risk["advisory"].lower()


def test_evaluate_weather_risks_gale_wind():
    risk = evaluate_weather_risks(rainfall_mm=0.0, wind_speed_ms=19.0, pressure_hpa=1008.0, temperature_c=20.0)
    assert risk["overall_status"] == "CRITICAL"
    assert risk["wind_alert"] == "CRITICAL"


def test_evaluate_weather_risks_barometric_depression():
    risk = evaluate_weather_risks(rainfall_mm=5.0, wind_speed_ms=8.0, pressure_hpa=985.0, temperature_c=18.0)
    assert risk["overall_status"] == "CRITICAL"
    assert risk["pressure_alert"] == "CRITICAL"


# --- Endpoint Integration Tests ---

def test_weather_page_renders(client):
    response = client.get("/weather")
    assert response.status_code == 200
    assert b"Weather Monitoring" in response.data
    assert b"Rainfall Monitoring" in response.data
    assert b"weather-station-select" in response.data


def test_weather_stations_api(client):
    response = client.get("/api/weather/stations")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] == 64
    assert len(data["stations"]) == 64


def test_weather_stations_api_state_filter(client):
    response = client.get("/api/weather/stations?state=UP")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] == 31
    assert all(s["state_code"] == "UP" for s in data["stations"])


def test_weather_api_invalid_station_name(client):
    response = client.get("/api/weather?station=AtlantisCityXYZ")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert "not found" in data["error"].lower()


def test_weather_api_invalid_coordinates_non_numeric(client):
    response = client.get("/api/weather?lat=abc&lon=77.2")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "valid numeric" in data["error"].lower()


def test_weather_api_coordinates_out_of_bounds(client):
    response = client.get("/api/weather?lat=95.0&lon=77.2")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "out of bounds" in data["error"].lower()


def test_weather_api_upstream_error_resilience(client):
    with patch("urllib.request.urlopen", side_effect=URLError("Simulated connection timeout")):
        response = client.get("/api/weather?station=Shimla")
        assert response.status_code == 503
        data = response.get_json()
        assert data["success"] is False
        assert "network error" in data["error"].lower()


def test_weather_api_mock_success(client):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_payload = {
        "latitude": 31.1048,
        "longitude": 77.1734,
        "elevation": 2276.0,
        "current": {
            "time": "2026-09-08T02:00",
            "temperature_2m": 19.5,
            "apparent_temperature": 18.8,
            "relative_humidity_2m": 62,
            "precipitation": 1.2,
            "weather_code": 61,
            "surface_pressure": 988.4,
            "wind_speed_10m": 14.4,
            "wind_direction_10m": 135,
        },
        "hourly": {
            "time": ["2026-09-08T02:00", "2026-09-08T03:00"],
            "temperature_2m": [19.5, 19.1],
            "precipitation": [1.2, 0.8],
            "wind_speed_10m": [14.4, 12.0],
        }
    }
    mock_response.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        response = client.get("/api/weather?station=Shimla")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["location"]["station_name"] == "Shimla"
        assert data["current"]["temperature_c"] == 19.5
        assert data["current"]["relative_humidity_pct"] == 62
        assert data["current"]["condition"] == "Slight rain"
        assert "risk_indicators" in data
        assert "hourly_trends" in data
