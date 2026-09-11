"""Unit and integration tests for OSRM routing service and geometry sampling."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from services.routing_service import (
    fetch_osrm_routes,
    haversine_distance_km,
    sample_route_geometry,
    validate_coordinates,
)


def test_haversine_distance_known_points():
    # Delhi (28.6139, 77.2090) to Shimla (31.1048, 77.1734) ~ 277 km
    dist = haversine_distance_km(28.6139, 77.2090, 31.1048, 77.1734)
    assert 270.0 <= dist <= 285.0


def test_haversine_distance_zero_distance():
    dist = haversine_distance_km(28.6139, 77.2090, 28.6139, 77.2090)
    assert dist == pytest.approx(0.0, abs=1e-5)


def test_validate_coordinates_valid():
    coords, errors = validate_coordinates(28.6139, 77.2090, 31.1048, 77.1734)
    assert len(errors) == 0
    assert coords == (28.6139, 77.2090, 31.1048, 77.1734)


def test_validate_coordinates_missing():
    coords, errors = validate_coordinates(28.6139, None, 31.1048, 77.1734)
    assert coords is None
    assert any("start_lon" in e for e in errors)


def test_validate_coordinates_non_numeric():
    coords, errors = validate_coordinates("invalid", 77.2090, 31.1048, 77.1734)
    assert coords is None
    assert any("start_lat" in e for e in errors)


def test_validate_coordinates_out_of_bounds():
    coords, errors = validate_coordinates(95.0, 77.2090, 31.1048, 77.1734)
    assert coords is None
    assert any("start_lat" in e for e in errors)


def test_validate_coordinates_same_point():
    coords, errors = validate_coordinates(28.6139, 77.2090, 28.6139, 77.2090)
    assert coords is None
    assert any("distinct" in e for e in errors)


def test_sample_route_geometry_preserves_endpoints():
    # Coords: [[lon1, lat1], [lon2, lat2], [lon3, lat3]]
    coords = [
        [77.2090, 28.6139],
        [77.2000, 28.7000],
        [77.1734, 31.1048],
    ]
    sampled = sample_route_geometry(coords, sample_interval_km=5.0)
    assert len(sampled) >= 2
    assert sampled[0]["latitude"] == pytest.approx(28.6139, abs=1e-4)
    assert sampled[0]["longitude"] == pytest.approx(77.2090, abs=1e-4)
    assert sampled[-1]["latitude"] == pytest.approx(31.1048, abs=1e-4)
    assert sampled[-1]["longitude"] == pytest.approx(77.1734, abs=1e-4)


def test_sample_route_geometry_empty():
    assert sample_route_geometry([]) == []
    assert sample_route_geometry([[77.0, 28.0]]) == []


@patch("urllib.request.urlopen")
def test_fetch_osrm_routes_success(mock_urlopen):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_payload = {
        "code": "Ok",
        "routes": [
            {
                "distance": 345000.0,
                "duration": 21600.0,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[77.2090, 28.6139], [77.1734, 31.1048]],
                },
                "summary": "NH 44",
            }
        ],
        "waypoints": [],
    }
    mock_response.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = fetch_osrm_routes(28.6139, 77.2090, 31.1048, 77.1734)
    assert result["success"] is True
    assert len(result["routes"]) == 1
    assert result["routes"][0]["distance"] == 345000.0


@patch("urllib.request.urlopen")
def test_fetch_osrm_routes_no_route(mock_urlopen):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_payload = {
        "code": "NoRoute",
        "message": "No route found",
        "routes": [],
    }
    mock_response.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = fetch_osrm_routes(28.6139, 77.2090, 31.1048, 77.1734)
    assert result["success"] is False
    assert result["error_type"] == "NO_ROUTE_FOUND"
    assert result["http_status"] == 404


@patch("urllib.request.urlopen")
def test_fetch_osrm_routes_network_timeout(mock_urlopen):
    mock_urlopen.side_effect = TimeoutError("Connection timed out")

    result = fetch_osrm_routes(28.6139, 77.2090, 31.1048, 77.1734)
    assert result["success"] is False
    assert result["error_type"] == "OSRM_UNAVAILABLE"
    assert result["http_status"] == 502


@patch("urllib.request.urlopen")
def test_fetch_osrm_routes_http_error(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.HTTPError(
        url="http://osrm", code=500, msg="Server Error", hdrs={}, fp=None
    )

    result = fetch_osrm_routes(28.6139, 77.2090, 31.1048, 77.1734)
    assert result["success"] is False
    assert result["http_status"] == 502
