"""Tests for spatial hazard exposure association, route scoring, and safe routing APIs."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from config import TestConfig
from extensions import db
from services.route_risk_service import RouteRiskAnalyzer, get_route_risk_analyzer
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


def test_route_risk_analyzer_point_association():
    analyzer = get_route_risk_analyzer()

    # Point near Shimla station (31.1048, 77.1734) - should be covered
    pts_near = [{"latitude": 31.1050, "longitude": 77.1730, "cumulative_distance_km": 0.0}]
    analyzed_near = analyzer.analyze_sampled_points(pts_near, station_radius_km=50.0)

    assert len(analyzed_near) == 1
    assert analyzed_near[0]["is_covered"] is True
    assert analyzed_near[0]["nearest_station"] is not None
    assert analyzed_near[0]["distance_to_station_km"] <= 50.0
    assert analyzed_near[0]["flood_probability"] is not None
    assert analyzed_near[0]["landslide_probability"] is not None
    assert analyzed_near[0]["combined_risk"] is not None


def test_route_risk_analyzer_uncovered_point():
    analyzer = get_route_risk_analyzer()

    # Point far out in Arabian Sea (15.0, 65.0) - far beyond 50 km of North India stations
    pts_far = [{"latitude": 15.0, "longitude": 65.0, "cumulative_distance_km": 0.0}]
    analyzed_far = analyzer.analyze_sampled_points(pts_far, station_radius_km=50.0)

    assert len(analyzed_far) == 1
    assert analyzed_far[0]["is_covered"] is False
    assert analyzed_far[0]["flood_probability"] is None
    assert analyzed_far[0]["landslide_probability"] is None
    assert analyzed_far[0]["combined_risk"] is None


def test_route_metrics_calculation_and_cost_formula():
    analyzer = get_route_risk_analyzer()

    raw_route = {"distance": 100000.0, "duration": 7200.0}  # 100 km, 2 hours
    analyzed_pts = [
        {"latitude": 31.0, "longitude": 77.0, "is_covered": True, "flood_probability": 0.20, "landslide_probability": 0.10, "combined_risk": 0.15},
        {"latitude": 31.5, "longitude": 77.2, "is_covered": True, "flood_probability": 0.40, "landslide_probability": 0.20, "combined_risk": 0.30},
        {"latitude": 32.0, "longitude": 77.5, "is_covered": False, "flood_probability": None, "landslide_probability": None, "combined_risk": None},
        {"latitude": 32.5, "longitude": 77.8, "is_covered": True, "flood_probability": 0.30, "landslide_probability": 0.00, "combined_risk": 0.15},
    ]

    metrics = analyzer.calculate_route_metrics(raw_route, analyzed_pts, penalty_factor=10.0)

    assert metrics["distance_km"] == 100.0
    assert metrics["duration_minutes"] == 120.0
    assert metrics["total_points"] == 4
    assert metrics["covered_points"] == 3
    assert metrics["uncovered_points"] == 1
    assert metrics["risk_coverage_percent"] == 75.0

    # Avg combined risk: (0.15 + 0.30 + 0.15) / 3 = 0.20
    assert metrics["average_combined_risk"] == pytest.approx(0.20, abs=1e-4)
    # Risk penalty: 100 * 10 * 0.20 = 200.0
    assert metrics["risk_penalty"] == pytest.approx(200.0, abs=1e-2)
    # Route cost: 100 + 200 = 300.0
    assert metrics["route_cost"] == pytest.approx(300.0, abs=1e-2)


def test_evaluate_candidate_routes_comparison():
    analyzer = get_route_risk_analyzer()

    # Route 1: Shorter (100 km) but passes through high risk
    # Route 2: Longer (120 km) but low risk
    raw_routes = [
        {
            "distance": 100000.0,
            "duration": 7200.0,
            "summary": "High Risk Short",
            "geometry": {"coordinates": [[77.1734, 31.1048], [77.2000, 31.2000]]},
        },
        {
            "distance": 120000.0,
            "duration": 8000.0,
            "summary": "Low Risk Alternative",
            "geometry": {"coordinates": [[77.1734, 31.1048], [77.3000, 31.4000]]},
        },
    ]

    evaluation = analyzer.evaluate_routes(raw_routes, penalty_factor=10.0)
    assert len(evaluation["routes"]) == 2
    assert evaluation["shortest_route_index"] == 0  # 100 km < 120 km
    assert "recommendation_confidence" in evaluation


def test_classify_risk_level():
    from services.route_risk_service import classify_risk_level

    assert classify_risk_level(None) == "UNKNOWN"
    assert classify_risk_level(0.10) == "LOW"
    assert classify_risk_level(0.35) == "MODERATE"
    assert classify_risk_level(0.60) == "HIGH"
    assert classify_risk_level(0.85) == "CRITICAL"


def test_route_metrics_safety_score_and_levels():
    analyzer = get_route_risk_analyzer()

    raw_route = {"distance": 50000.0, "duration": 3600.0}
    pts = [
        {"latitude": 31.0, "longitude": 77.0, "is_covered": True, "flood_probability": 0.10, "landslide_probability": 0.10, "combined_risk": 0.10},
        {"latitude": 31.2, "longitude": 77.2, "is_covered": True, "flood_probability": 0.20, "landslide_probability": 0.20, "combined_risk": 0.20},
    ]

    metrics = analyzer.calculate_route_metrics(raw_route, pts, penalty_factor=10.0)

    # Average combined risk = 0.15 -> Safety score = (1.0 - 0.15) * 100 = 85.0
    assert metrics["safety_score"] == 85.0
    assert metrics["risk_level"] == "LOW"
    assert metrics["flood_risk_level"] == "LOW"
    assert metrics["landslide_risk_level"] == "LOW"
    assert metrics["balanced_cost"] < metrics["route_cost"]


def test_multi_route_comparison_modes():
    analyzer = get_route_risk_analyzer()

    # Create 3 synthetic routes with distinct coordinates & distances
    # Route 0: Shortest (80 km), but high risk (passes through critical stations)
    # Route 1: Safest (130 km), but very low risk
    # Route 2: Balanced (95 km), with low/moderate risk
    raw_routes = [
        {
            "distance": 80000.0,
            "duration": 5000.0,
            "summary": "NH 1 Short",
            "geometry": {"coordinates": [[77.1734, 31.1048], [77.2000, 31.2000]]},
        },
        {
            "distance": 130000.0,
            "duration": 8500.0,
            "summary": "NH 2 Long Safe",
            "geometry": {"coordinates": [[77.1734, 31.1048], [77.3000, 31.4000]]},
        },
        {
            "distance": 95000.0,
            "duration": 6000.0,
            "summary": "NH 3 Balanced",
            "geometry": {"coordinates": [[77.1734, 31.1048], [77.2500, 31.3000]]},
        },
    ]

    # Evaluate with mode='safest'
    eval_safest = analyzer.evaluate_routes(raw_routes, penalty_factor=10.0, mode="safest")
    assert len(eval_safest["routes"]) == 3
    assert eval_safest["shortest_route_index"] == 0
    assert eval_safest["safest_route_index"] in {0, 1, 2}
    assert eval_safest["recommended_route_index"] == eval_safest["safest_route_index"]
    assert eval_safest["active_mode"] == "safest"

    # Evaluate with mode='shortest'
    eval_shortest = analyzer.evaluate_routes(raw_routes, penalty_factor=10.0, mode="shortest")
    assert eval_shortest["recommended_route_index"] == eval_shortest["shortest_route_index"]
    assert eval_shortest["recommended_route_index"] == 0
    assert eval_shortest["active_mode"] == "shortest"

    # Evaluate with mode='balanced'
    eval_balanced = analyzer.evaluate_routes(raw_routes, penalty_factor=10.0, mode="balanced")
    assert eval_balanced["recommended_route_index"] == eval_balanced["balanced_route_index"]
    assert eval_balanced["active_mode"] == "balanced"


def test_evaluate_routes_empty_raises_error():
    analyzer = get_route_risk_analyzer()
    with pytest.raises(ValueError, match="No valid routes to evaluate"):
        analyzer.evaluate_routes([])


# --- API Endpoint Tests ---


def test_routing_api_requires_login(client):
    res = client.get("/api/routing/route?start_lat=28.6139&start_lon=77.2090&end_lat=31.1048&end_lon=77.1734")
    assert res.status_code == 401
    assert res.get_json()["success"] is False


def test_routing_view_requires_login(client):
    res = client.get("/route-optimizer")
    assert res.status_code == 302 or res.status_code == 401


def test_routing_view_authenticated(auth_client):
    res = auth_client.get("/route-optimizer")
    assert res.status_code == 200
    assert "Disaster-Aware Safe Route Optimizer" in res.get_data(as_text=True)


@patch("routes.routing.fetch_osrm_routes")
def test_routing_api_success_with_modes(mock_fetch, auth_client):
    mock_fetch.return_value = {
        "success": True,
        "routes": [
            {
                "distance": 345000.0,
                "duration": 21600.0,
                "summary": "NH 44",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[77.2090, 28.6139], [77.1734, 31.1048]],
                },
            },
            {
                "distance": 360000.0,
                "duration": 22500.0,
                "summary": "State Highway 1",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[77.2090, 28.6139], [77.2500, 30.0000], [77.1734, 31.1048]],
                },
            },
        ],
        "waypoints": [],
    }

    # Test mode=safest
    res = auth_client.get(
        "/api/routing/route?start_lat=28.6139&start_lon=77.2090&end_lat=31.1048&end_lon=77.1734&mode=safest"
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert len(data["routes"]) == 2
    assert data["mode"] == "safest"
    assert "safety_score" in data["routes"][0]["metrics"]
    assert "risk_level" in data["routes"][0]["metrics"]

    # Test mode=shortest
    res_short = auth_client.get(
        "/api/routing/route?start_lat=28.6139&start_lon=77.2090&end_lat=31.1048&end_lon=77.1734&mode=shortest"
    )
    assert res_short.status_code == 200
    data_short = res_short.get_json()
    assert data_short["mode"] == "shortest"
    assert data_short["recommended_route_index"] == data_short["shortest_route_index"]

    # Test mode=balanced
    res_bal = auth_client.get(
        "/api/routing/route?start_lat=28.6139&start_lon=77.2090&end_lat=31.1048&end_lon=77.1734&mode=balanced"
    )
    assert res_bal.status_code == 200
    data_bal = res_bal.get_json()
    assert data_bal["mode"] == "balanced"


def test_routing_api_invalid_mode(auth_client):
    res = auth_client.get(
        "/api/routing/route?start_lat=28.6139&start_lon=77.2090&end_lat=31.1048&end_lon=77.1734&mode=invalid_mode"
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert any("mode" in e for e in data["errors"])


def test_routing_api_invalid_coordinates(auth_client):
    res = auth_client.get("/api/routing/route?start_lat=invalid&start_lon=77.2090&end_lat=31.1048&end_lon=77.1734")
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert any("start_lat" in e for e in data["errors"])


def test_routing_api_invalid_weights(auth_client):
    res = auth_client.get(
        "/api/routing/route?start_lat=28.6139&start_lon=77.2090&end_lat=31.1048&end_lon=77.1734&flood_weight=-0.5"
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False


@patch("routes.routing.fetch_osrm_routes")
def test_routing_api_upstream_osrm_failure(mock_fetch, auth_client):
    mock_fetch.return_value = {
        "success": False,
        "error_type": "OSRM_UNAVAILABLE",
        "message": "OSRM connection timeout.",
        "http_status": 502,
    }

    res = auth_client.get(
        "/api/routing/route?start_lat=28.6139&start_lon=77.2090&end_lat=31.1048&end_lon=77.1734"
    )
    assert res.status_code == 502
    data = res.get_json()
    assert data["success"] is False

