"""Comprehensive test suite for Phase 16 Advanced Analytics.

Covers:
- Web dashboard view rendering
- Analytics overview KPI calculations and risk distributions
- Multi-criteria filtering (State, District, Hazard model, Date bounds, Risk level)
- Temporal trends, monthly seasonality, and weather correlations
- State, District, and Location risk rankings
- CSV export generation, headers, and security exclusion of private user credentials
- Error handling for invalid inputs and edge cases
"""

from __future__ import annotations

import csv
import io
import json
import pytest

from app import create_app
from config import TestConfig
from extensions import db
from models.alert import AlertEvent
from models.incident import IncidentReport
from models.location import Location
from models.prediction import PredictionHistory
from models.user import ROLE_ADMIN, ROLE_USER, User
from services.analytics_service import (
    export_analytics_csv,
    get_analytics_overview,
    get_available_districts_list,
    get_risk_rankings,
    get_temporal_trends,
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


# ==============================================================================
# 1. ANALYTICS DASHBOARD VIEW TESTS
# ==============================================================================

def test_analytics_page_renders(client):
    res = client.get("/analytics")
    assert res.status_code == 200
    assert b"Advanced Analytics" in res.data
    assert b"State-Wise Disaster Risk" in res.data
    assert b"stateRiskChart" in res.data
    assert b"monthlySeasonalityChart" in res.data


# ==============================================================================
# 2. ANALYTICS OVERVIEW REST API TESTS
# ==============================================================================

def test_api_analytics_overview_default(client):
    res = client.get("/api/analytics/overview")
    assert res.status_code == 200
    data = res.get_json()

    assert data["success"] is True
    assert "kpis" in data
    kpis = data["kpis"]
    assert "total_evaluations" in kpis
    assert kpis["total_evaluations"] > 0
    assert "mean_composite_risk" in kpis
    assert 0.0 <= kpis["mean_composite_risk"] <= 1.0
    assert kpis["composite_risk_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
    assert "mean_flood_probability" in kpis
    assert "mean_landslide_probability" in kpis

    # Distribution check
    assert "distribution" in data
    dist = data["distribution"]
    assert len(dist["labels"]) == 4
    assert len(dist["counts"]) == 4
    assert sum(dist["percentages"]) == pytest.approx(100.0, abs=1.0)

    # State metrics check
    assert "state_metrics" in data
    assert len(data["state_metrics"]) > 0
    for st in data["state_metrics"]:
        assert "state_code" in st
        assert "combined_risk" in st
        assert "dfsi_score" in st


def test_api_analytics_overview_state_and_hazard_filters(client):
    # Filter by state HP and hazard landslide
    res = client.get("/api/analytics/overview?state=HP&hazard=landslide")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["filter_applied"]["state"] == "HP"
    assert data["filter_applied"]["hazard"] == "landslide"

    # Filter by hazard flood
    res_f = client.get("/api/analytics/overview?hazard=flood")
    assert res_f.status_code == 200
    data_f = res_f.get_json()
    assert data_f["success"] is True
    assert data_f["kpis"]["mean_composite_risk"] == pytest.approx(data_f["kpis"]["mean_flood_probability"], abs=1e-3)


def test_api_analytics_overview_date_range_filter(client):
    res = client.get("/api/analytics/overview?start_date=2021-01-01&end_date=2022-12-31")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["kpis"]["total_evaluations"] > 0


# ==============================================================================
# 3. TEMPORAL TRENDS & SEASONALITY TESTS
# ==============================================================================

def test_api_analytics_trends_structure(client):
    res = client.get("/api/analytics/trends")
    assert res.status_code == 200
    data = res.get_json()

    assert data["success"] is True
    assert "seasonality" in data
    season = data["seasonality"]
    assert len(season["labels"]) == 12  # 12 months
    assert len(season["rainfall"]) == 12
    assert len(season["flood_risk"]) == 12
    assert len(season["landslide_risk"]) == 12
    assert len(season["combined_risk"]) == 12

    # Monsoon peak check: July/August rainfall should be higher than January
    jul_idx = season["labels"].index("Jul")
    jan_idx = season["labels"].index("Jan")
    assert season["rainfall"][jul_idx] >= season["rainfall"][jan_idx]

    # Yearly patterns check
    assert "yearly_patterns" in data
    assert len(data["yearly_patterns"]["labels"]) >= 3

    # Weather correlations check
    assert "weather_correlations" in data
    assert len(data["weather_correlations"]) > 0
    pt = data["weather_correlations"][0]
    assert "rainfall" in pt
    assert "air_pressure" in pt
    assert "risk_score" in pt


def test_api_analytics_trends_filtered_state(client):
    res = client.get("/api/analytics/trends?state=UT&hazard=landslide")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert len(data["seasonality"]["labels"]) == 12


# ==============================================================================
# 4. RANKINGS REST API TESTS
# ==============================================================================

def test_api_analytics_rankings(client):
    res = client.get("/api/analytics/rankings?limit=15")
    assert res.status_code == 200
    data = res.get_json()

    assert data["success"] is True
    assert "state_rankings" in data
    assert "district_rankings" in data
    assert "location_rankings" in data

    assert len(data["district_rankings"]) <= 15
    assert len(data["location_rankings"]) <= 15

    # Check sorting: highest risk first
    locs = data["location_rankings"]
    if len(locs) >= 2:
        assert locs[0]["combined_risk"] >= locs[-1]["combined_risk"]

    # Check structure of top location item
    top_loc = locs[0]
    assert "location_name" in top_loc
    assert "state_code" in top_loc
    assert "district" in top_loc
    assert "elevation" in top_loc
    assert "latitude" in top_loc
    assert "longitude" in top_loc
    assert "risk_level" in top_loc


def test_api_analytics_districts_list(client):
    # All districts
    res = client.get("/api/analytics/districts")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert len(data["districts"]) > 0

    # Specific state districts
    res_hp = client.get("/api/analytics/districts?state=HP")
    assert res_hp.status_code == 200
    data_hp = res_hp.get_json()
    assert data_hp["success"] is True
    assert any("Shimla" in d or "Kullu" in d or "Mandi" in d or "Kangra" in d for d in data_hp["districts"])


# ==============================================================================
# 5. CSV EXPORT & PRIVACY SECURITY TESTS
# ==============================================================================

def test_export_analytics_csv_rankings(client):
    res = client.get("/api/analytics/export/csv?type=rankings&hazard=combined")
    assert res.status_code == 200
    assert res.mimetype == "text/csv"
    assert "attachment" in res.headers.get("Content-Disposition", "")
    assert "nidars_analytics_rankings" in res.headers.get("Content-Disposition", "")

    csv_text = res.data.decode("utf-8")
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    assert len(rows) > 1
    header = rows[0]
    assert "Rank" in header
    assert "Location_Name" in header
    assert "Combined_Risk" in header
    assert "Risk_Level" in header

    # CRITICAL SECURITY TEST: Ensure NO sensitive user fields are in CSV export
    lower_header = [h.lower() for h in header]
    assert "password" not in lower_header
    assert "password_hash" not in lower_header
    assert "email" not in lower_header
    assert "token" not in lower_header
    assert "user_id" not in lower_header


def test_export_analytics_csv_districts_and_states(client):
    # Districts CSV
    res_d = client.get("/api/analytics/export/csv?type=districts")
    assert res_d.status_code == 200
    csv_d = res_d.data.decode("utf-8")
    assert "District" in csv_d
    assert "Combined_Risk" in csv_d

    # States CSV
    res_s = client.get("/api/analytics/export/csv?type=states")
    assert res_s.status_code == 200
    csv_s = res_s.data.decode("utf-8")
    assert "State_Code" in csv_s
    assert "DFSI_Score" in csv_s

    # Seasonality CSV
    res_seas = client.get("/api/analytics/export/csv?type=seasonality")
    assert res_seas.status_code == 200
    csv_seas = res_seas.data.decode("utf-8")
    assert "Month" in csv_seas
    assert "Rainfall_mm" in csv_seas


# ==============================================================================
# 6. EDGE CASES & ERROR RESILIENCE TESTS
# ==============================================================================

def test_analytics_invalid_dates_resilience(client):
    # Malformed date strings should not cause 500 error
    res = client.get("/api/analytics/overview?start_date=not-a-date&end_date=invalid-date")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    # Inverted date range
    res_inv = client.get("/api/analytics/overview?start_date=2025-12-31&end_date=2020-01-01")
    assert res_inv.status_code == 200
    assert res_inv.get_json()["success"] is True


def test_analytics_nonexistent_state_resilience(client):
    # Non-existent state query
    res = client.get("/api/analytics/overview?state=NONEXISTENT_STATE")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "kpis" in data


def test_analytics_limit_clamping(client):
    # Limit out of bounds
    res_large = client.get("/api/analytics/rankings?limit=99999")
    assert res_large.status_code == 200
    assert len(res_large.get_json()["location_rankings"]) <= 100

    res_negative = client.get("/api/analytics/rankings?limit=-10")
    assert res_negative.status_code == 200
    assert len(res_negative.get_json()["location_rankings"]) >= 5
