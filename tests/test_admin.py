"""Unit and integration tests for Phase 7 Admin Dashboard, Role Protection, and Analytics."""

from __future__ import annotations

import json
import pytest

from app import create_app
from config import TestConfig
from extensions import db
from models.emergency_facility import EmergencyFacility
from models.emergency_request import EmergencyRequest
from models.location import Location
from models.prediction import PredictionHistory
from models.user import ROLE_ADMIN, ROLE_USER, User
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


def make_admin(app, email="admin@example.com", password="password12"):
    with app.app_context():
        admin = User(name="Admin User", email=email, role=ROLE_ADMIN)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        return admin.id


@pytest.fixture
def user_client(app, client):
    make_user(app, email="user@example.com", password="password12")
    login(client, email="user@example.com", password="password12")
    return client


@pytest.fixture
def admin_client(app, client):
    make_admin(app, email="admin@example.com", password="password12")
    login(client, email="admin@example.com", password="password12")
    return client


# --- Authentication & Authorization Tests ---

def test_admin_page_unauthenticated(client):
    res = client.get("/admin")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_admin_api_unauthenticated(client):
    res = client.get("/api/admin/stats")
    assert res.status_code == 401
    assert res.get_json()["success"] is False


def test_admin_page_forbidden_for_regular_user(user_client):
    res = user_client.get("/admin")
    assert res.status_code == 403
    assert b"Access Denied" in res.data or b"403" in res.data


def test_admin_api_forbidden_for_regular_user(user_client):
    endpoints = [
        "/api/admin/stats",
        "/api/admin/predictions",
        "/api/admin/emergency",
        "/api/admin/facilities",
    ]
    for ep in endpoints:
        res = user_client.get(ep)
        assert res.status_code == 403
        data = res.get_json()
        assert data["success"] is False
        assert any("privileges required" in e.lower() for e in data["errors"])


def test_admin_page_accessible_for_admin(admin_client):
    res = admin_client.get("/admin")
    assert res.status_code == 200
    assert b"Admin Control Center" in res.data or b"Analytics" in res.data


# --- Admin API Data & Analytics Tests ---

def test_admin_stats_api(app, admin_client):
    with app.app_context():
        # Seed test data
        loc = Location(name="Shimla Station", state="Himachal Pradesh", district="Shimla", latitude=31.10, longitude=77.17)
        db.session.add(loc)
        db.session.commit()

        pred = PredictionHistory(
            user_id=1,
            location_id=loc.id,
            prediction_type="flood",
            status="completed",
            result_json={"probability": 0.78, "risk_level": "HIGH"},
        )
        db.session.add(pred)

        fac = EmergencyFacility(
            name="IGMC Shimla",
            facility_type="hospital",
            latitude=31.1048,
            longitude=77.1734,
            address="Circular Road",
            phone="+91-177-2804251",
            source="OpenStreetMap",
        )
        db.session.add(fac)

        req = EmergencyRequest(
            user_id=1,
            latitude=31.1048,
            longitude=77.1734,
            request_type="nearest_facility",
            facility_type="hospital",
            risk_level="HIGH",
        )
        db.session.add(req)
        db.session.commit()

    res = admin_client.get("/api/admin/stats")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["success"] is True
    metrics = payload["metrics"]

    assert metrics["total_users"] >= 1
    assert metrics["total_predictions"] >= 1
    assert metrics["flood_predictions"] >= 1
    assert metrics["total_facilities"] >= 1
    assert metrics["total_emergency_requests"] >= 1
    assert "risk_distribution" in metrics
    assert "facilities_by_type" in metrics
    assert metrics["facilities_by_type"]["hospitals"] >= 1


def test_admin_predictions_api(app, admin_client):
    with app.app_context():
        loc = Location(name="Patna Station", state="Bihar", district="Patna", latitude=25.59, longitude=85.13)
        db.session.add(loc)
        db.session.commit()

        pred = PredictionHistory(
            user_id=1,
            location_id=loc.id,
            prediction_type="landslide",
            status="completed",
            result_json={"probability": 0.45, "risk_level": "MODERATE"},
        )
        db.session.add(pred)
        db.session.commit()

    res = admin_client.get("/api/admin/predictions?limit=10")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["success"] is True
    assert len(payload["predictions"]) >= 1

    first = payload["predictions"][0]
    assert first["prediction_type"] == "landslide"
    assert first["status"] == "completed"
    assert "created_at" in first


def test_admin_emergency_logs_api(app, admin_client):
    with app.app_context():
        req = EmergencyRequest(
            user_id=1,
            latitude=28.6139,
            longitude=77.2090,
            request_type="risk_check",
            risk_level="CRITICAL",
            flood_probability=0.88,
            landslide_probability=0.72,
        )
        db.session.add(req)
        db.session.commit()

    res = admin_client.get("/api/admin/emergency?limit=10")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["success"] is True
    assert len(payload["emergency_logs"]) >= 1

    first = payload["emergency_logs"][0]
    assert first["request_type"] == "risk_check"
    assert first["risk_level"] == "CRITICAL"
    assert first["flood_probability"] == pytest.approx(0.88, abs=1e-3)


def test_admin_facilities_api(app, admin_client):
    with app.app_context():
        fac = EmergencyFacility(
            name="Dehradun Police Station",
            facility_type="police",
            latitude=30.3165,
            longitude=78.0322,
            address="Clock Tower, Dehradun",
            phone="+91-135-2716200",
            source="OpenStreetMap",
        )
        db.session.add(fac)
        db.session.commit()

    res = admin_client.get("/api/admin/facilities?limit=10")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["success"] is True
    assert len(payload["facilities"]) >= 1
    assert payload["facilities"][0]["name"] == "Dehradun Police Station"


def test_no_sensitive_credentials_leakage(admin_client):
    """Ensure no password hashes or credentials are exposed in admin endpoints."""
    endpoints = [
        "/api/admin/stats",
        "/api/admin/predictions",
        "/api/admin/emergency",
        "/api/admin/facilities",
    ]
    for ep in endpoints:
        res = admin_client.get(ep)
        body = res.get_data(as_text=True)
        assert "password_hash" not in body.lower()
        assert "pbkdf2" not in body.lower()
        assert "scrypt" not in body.lower()
