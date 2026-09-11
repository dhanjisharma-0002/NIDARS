"""Comprehensive test suite for Phase 15 User Incident Reporting.

Covers:
- Incident submission (JSON & multipart form data with photo uploads)
- Form validation (coordinates, types, severities, descriptions)
- Authentication enforcement (anonymous access restricted)
- Photo upload security (extensions, magic bytes, size limits)
- Admin authorization & triage workflows (status change, verification, delete, filters)
- GIS incident mapping endpoint (GeoJSON format, coordinate order, disclaimer, sensitive data filtering)
"""

from __future__ import annotations

import io
import json
import pytest

from app import create_app
from config import TestConfig
from extensions import db
from models.incident import (
    INCIDENT_TYPES,
    SEVERITY_LEVELS,
    STATUS_REPORTED,
    STATUS_RESOLVED,
    STATUS_UNDER_REVIEW,
    STATUS_VERIFIED,
    IncidentReport,
)
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
def user_client(app):
    c = app.test_client()
    make_user(app, email="citizen@example.com", password="password12")
    login(c, email="citizen@example.com", password="password12")
    return c


@pytest.fixture
def admin_client(app):
    c = app.test_client()
    make_admin(app, email="admin@example.com", password="password12")
    login(c, email="admin@example.com", password="password12")
    return c


# 1x1 valid transparent PNG bytes for testing image uploads
VALID_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ==============================================================================
# 1. AUTHENTICATION & ACCESS CONTROL TESTS
# ==============================================================================

def test_report_incident_page_unauthenticated(client):
    res = client.get("/report-incident")
    assert res.status_code == 302
    assert "/login" in res.location


def test_my_reports_page_unauthenticated(client):
    res = client.get("/my-reports")
    assert res.status_code == 302
    assert "/login" in res.location


def test_create_incident_api_unauthenticated(client):
    payload = {
        "location": "Shimla Mall Road",
        "latitude": 31.1048,
        "longitude": 77.1734,
        "incident_type": "Landslide",
        "severity": "High",
        "description": "Massive rockfall blocking northern passage.",
    }
    res = client.post("/api/incidents", json=payload)
    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False
    assert any("Authentication required" in err for err in data.get("errors", []))


def test_get_my_incidents_api_unauthenticated(client):
    res = client.get("/api/incidents/my")
    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False


def test_admin_incidents_page_unauthenticated(client):
    res = client.get("/admin/incidents")
    assert res.status_code in (302, 403)


def test_admin_incidents_page_forbidden_for_regular_user(user_client):
    res = user_client.get("/admin/incidents")
    assert res.status_code == 403


def test_admin_incidents_api_forbidden_for_regular_user(user_client):
    res = user_client.get("/api/admin/incidents")
    assert res.status_code == 403
    data = user_client.patch("/api/admin/incidents/1/status", json={"status": "Verified"})
    assert data.status_code == 403
    del_res = user_client.delete("/api/admin/incidents/1")
    assert del_res.status_code == 403


# ==============================================================================
# 2. INCIDENT CREATION & FORM VALIDATION TESTS
# ==============================================================================

def test_create_incident_valid_json(app, user_client):
    payload = {
        "location": "NH-58 Near Rishikesh",
        "latitude": 30.0869,
        "longitude": 78.2676,
        "incident_type": "Flooded Road",
        "severity": "High",
        "description": "Ganges river overflow has inundated the highway with 2 feet of water.",
    }
    res = user_client.post("/api/incidents", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    assert "incident" in data
    assert data["incident"]["location_name"] == "NH-58 Near Rishikesh"
    assert data["incident"]["incident_type"] == "Flooded Road"
    assert data["incident"]["severity"] == "High"
    assert data["incident"]["status"] == STATUS_REPORTED
    assert data["incident"]["is_verified"] is False

    with app.app_context():
        incident = IncidentReport.query.filter_by(location_name="NH-58 Near Rishikesh").first()
        assert incident is not None
        assert incident.latitude == pytest.approx(30.0869)
        assert incident.longitude == pytest.approx(78.2676)
        assert incident.user is not None
        assert incident.user.email == "citizen@example.com"


def test_create_incident_valid_multipart_form_with_photo(app, user_client):
    data = {
        "location": "Kedarnath Trek Route",
        "latitude": "30.7346",
        "longitude": "79.0669",
        "incident_type": "Landslide",
        "severity": "Critical",
        "description": "Debris and mud blocking the pedestrian path near Gaurikund.",
        "photo": (io.BytesIO(VALID_PNG_BYTES), "landslide_proof.png", "image/png"),
    }
    res = user_client.post("/api/incidents", data=data, content_type="multipart/form-data")
    assert res.status_code == 201
    resp_data = res.get_json()
    assert resp_data["success"] is True
    assert resp_data["incident"]["photo_url"] is not None
    assert resp_data["incident"]["photo_url"].startswith("/static/uploads/incidents/")


def test_create_incident_validation_missing_fields(user_client):
    # Missing location
    res = user_client.post("/api/incidents", json={
        "latitude": 30.0,
        "longitude": 78.0,
        "incident_type": "Flooded Road",
        "description": "Water on street",
    })
    assert res.status_code == 400
    err_str = res.get_json().get("error", "") or str(res.get_json().get("errors", []))
    assert "Location" in err_str

    # Missing coordinates
    res = user_client.post("/api/incidents", json={
        "location": "Haridwar",
        "incident_type": "Flooded Road",
        "description": "Water on street",
    })
    assert res.status_code == 400
    err_str = res.get_json().get("error", "") or str(res.get_json().get("errors", []))
    assert "Latitude" in err_str or "coordinate" in err_str

    # Missing incident type
    res = user_client.post("/api/incidents", json={
        "location": "Haridwar",
        "latitude": 30.0,
        "longitude": 78.0,
        "description": "Water on street",
    })
    assert res.status_code == 400
    err_str = res.get_json().get("error", "") or str(res.get_json().get("errors", []))
    assert "incident type" in err_str.lower()

    # Missing description
    res = user_client.post("/api/incidents", json={
        "location": "Haridwar",
        "latitude": 30.0,
        "longitude": 78.0,
        "incident_type": "Flooded Road",
    })
    assert res.status_code == 400
    err_str = res.get_json().get("error", "") or str(res.get_json().get("errors", []))
    assert "Description" in err_str


def test_create_incident_validation_invalid_coordinates(user_client):
    # Latitude out of range (> 90)
    res = user_client.post("/api/incidents", json={
        "location": "North Pole Extreme",
        "latitude": 95.5,
        "longitude": 78.0,
        "incident_type": "Other",
        "description": "Valid incident description text here.",
    })
    assert res.status_code == 400
    err_str = res.get_json().get("error", "") or str(res.get_json().get("errors", []))
    assert "Latitude" in err_str

    # Longitude out of range (> 180)
    res = user_client.post("/api/incidents", json={
        "location": "East Extreme",
        "latitude": 28.0,
        "longitude": 185.0,
        "incident_type": "Other",
        "description": "Valid incident description text here.",
    })
    assert res.status_code == 400
    err_str = res.get_json().get("error", "") or str(res.get_json().get("errors", []))
    assert "Longitude" in err_str

    # Non-numeric coordinate
    res = user_client.post("/api/incidents", json={
        "location": "Bad Coords",
        "latitude": "not_a_number",
        "longitude": 78.0,
        "incident_type": "Other",
        "description": "Valid incident description text here.",
    })
    assert res.status_code == 400
    err_str = res.get_json().get("error", "") or str(res.get_json().get("errors", []))
    assert "numeric" in err_str.lower() or "valid" in err_str.lower()


def test_create_incident_validation_invalid_type_and_severity(user_client):
    # Invalid incident type
    res = user_client.post("/api/incidents", json={
        "location": "Dehradun",
        "latitude": 30.3165,
        "longitude": 78.0322,
        "incident_type": "Alien Invasion",
        "description": "Unrecognized incident type description.",
    })
    assert res.status_code == 400
    err_str = res.get_json().get("error", "") or str(res.get_json().get("errors", []))
    assert "Invalid incident type" in err_str

    # Invalid severity
    res = user_client.post("/api/incidents", json={
        "location": "Dehradun",
        "latitude": 30.3165,
        "longitude": 78.0322,
        "incident_type": "Flooded Road",
        "severity": "Catastrophic",
        "description": "Valid incident description text.",
    })
    assert res.status_code == 400
    err_str = res.get_json().get("error", "") or str(res.get_json().get("errors", []))
    assert "Invalid severity" in err_str


def test_create_incident_validation_description_length(user_client):
    # Too short (< 5 chars)
    res = user_client.post("/api/incidents", json={
        "location": "Dehradun",
        "latitude": 30.3165,
        "longitude": 78.0322,
        "incident_type": "Flooded Road",
        "description": "Bad",
    })
    assert res.status_code == 400
    err_str = res.get_json().get("error", "") or str(res.get_json().get("errors", []))
    assert "5 characters" in err_str

    # Too long (> 5000 chars)
    long_desc = "A" * 5005
    res = user_client.post("/api/incidents", json={
        "location": "Dehradun",
        "latitude": 30.3165,
        "longitude": 78.0322,
        "incident_type": "Flooded Road",
        "description": long_desc,
    })
    assert res.status_code == 400
    err_str = res.get_json().get("error", "") or str(res.get_json().get("errors", []))
    assert "exceed" in err_str.lower()


# ==============================================================================
# 3. PHOTO UPLOAD SECURITY TESTS
# ==============================================================================

def test_upload_security_disallowed_extension(user_client):
    data = {
        "location": "Mussoorie Road",
        "latitude": "30.45",
        "longitude": "78.06",
        "incident_type": "Landslide",
        "description": "Testing dangerous file upload rejection.",
        "photo": (io.BytesIO(b"print('malicious script')"), "exploit.py", "text/x-python"),
    }
    res = user_client.post("/api/incidents", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    err_str = res.get_json().get("error", "") or str(res.get_json().get("errors", []))
    assert "Unsupported file type" in err_str or "Invalid file type" in err_str


def test_upload_security_fake_image_magic_bytes_rejected(user_client):
    # Text payload pretending to be a jpg image
    data = {
        "location": "Mussoorie Road",
        "latitude": "30.45",
        "longitude": "78.06",
        "incident_type": "Landslide",
        "description": "Testing spoofed mime type rejection.",
        "photo": (io.BytesIO(b"<html><script>alert(1)</script></html>"), "fake.jpg", "image/jpeg"),
    }
    res = user_client.post("/api/incidents", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    err_str = res.get_json().get("error", "") or str(res.get_json().get("errors", []))
    assert "Invalid image file header" in err_str or "valid image" in err_str


def test_upload_security_oversized_file_rejected(user_client):
    # Over 5 MB dummy payload
    oversized_data = b"\x89PNG\r\n\x1a\n" + (b"0" * (5 * 1024 * 1024 + 100))
    data = {
        "location": "Mussoorie Road",
        "latitude": "30.45",
        "longitude": "78.06",
        "incident_type": "Landslide",
        "description": "Testing oversized payload rejection.",
        "photo": (io.BytesIO(oversized_data), "giant.png", "image/png"),
    }
    res = user_client.post("/api/incidents", data=data, content_type="multipart/form-data")
    assert res.status_code in (400, 413)


# ==============================================================================
# 4. USER REPORTS LISTING TESTS
# ==============================================================================

def test_get_my_incidents_list(app, user_client):
    # Create 2 incidents
    user_client.post("/api/incidents", json={
        "location": "Report A",
        "latitude": 30.1,
        "longitude": 78.1,
        "incident_type": "Flooded Road",
        "description": "First report submitted.",
    })
    user_client.post("/api/incidents", json={
        "location": "Report B",
        "latitude": 30.2,
        "longitude": 78.2,
        "incident_type": "Road Blockage",
        "description": "Second report submitted.",
    })

    res = user_client.get("/api/incidents/my")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert len(data["incidents"]) == 2
    assert data["count"] == 2


# ==============================================================================
# 5. ADMIN INCIDENTS TRIAGE & MANAGEMENT TESTS
# ==============================================================================

def test_admin_incident_status_and_verification_workflow(app, admin_client):
    user_id = make_user(app, email="citizen_workflow@example.com", password="password12")
    with app.app_context():
        report = IncidentReport(
            user_id=user_id,
            location_name="Joshimath Main Bazar",
            latitude=30.5564,
            longitude=79.5664,
            incident_type="Landslide",
            severity="Critical",
            description="Road crack widened, urgent geotechnical survey needed.",
            status=STATUS_REPORTED,
            is_verified=False,
        )
        db.session.add(report)
        db.session.commit()
        incident_id = report.id

    # 2. Admin inspects list
    list_res = admin_client.get("/api/admin/incidents")
    assert list_res.status_code == 200
    list_data = list_res.get_json()
    assert list_data["success"] is True
    assert list_data["total"] >= 1

    # 3. Admin transitions to "Under Review"
    review_res = admin_client.patch(f"/api/admin/incidents/{incident_id}/status", json={
        "status": STATUS_UNDER_REVIEW,
        "admin_notes": "Assigned to SDRF team for on-site assessment.",
    })
    assert review_res.status_code == 200
    assert review_res.get_json()["incident"]["status"] == STATUS_UNDER_REVIEW

    # 4. Admin transitions to "Verified"
    verify_res = admin_client.patch(f"/api/admin/incidents/{incident_id}/status", json={
        "status": STATUS_VERIFIED,
        "is_verified": True,
        "admin_notes": "SDRF confirmed ground displacement.",
    })
    assert verify_res.status_code == 200
    v_data = verify_res.get_json()
    assert v_data["incident"]["status"] == STATUS_VERIFIED
    assert v_data["incident"]["is_verified"] is True

    # 5. Admin transitions to "Resolved"
    resolve_res = admin_client.patch(f"/api/admin/incidents/{incident_id}/status", json={
        "status": STATUS_RESOLVED,
        "admin_notes": "Retaining wall constructed and road reopened.",
    })
    assert resolve_res.status_code == 200
    assert resolve_res.get_json()["incident"]["status"] == STATUS_RESOLVED


def test_admin_delete_incident(app, admin_client):
    user_id = make_user(app, email="citizen_spam@example.com", password="password12")
    with app.app_context():
        report = IncidentReport(
            user_id=user_id,
            location_name="Spam Location",
            latitude=28.5,
            longitude=77.2,
            incident_type="Other",
            description="Inappropriate or spam test report to be purged.",
            status=STATUS_REPORTED,
        )
        db.session.add(report)
        db.session.commit()
        incident_id = report.id

    # Admin deletes it
    del_res = admin_client.delete(f"/api/admin/incidents/{incident_id}")
    assert del_res.status_code == 200
    assert del_res.get_json()["success"] is True

    # Confirm it's gone from database
    with app.app_context():
        report = db.session.get(IncidentReport, incident_id)
        assert report is None

    # Deleting non-existent incident returns 404
    del_404 = admin_client.delete(f"/api/admin/incidents/99999")
    assert del_404.status_code == 404


def test_admin_filter_incidents(app, admin_client):
    user_id = make_user(app, email="citizen_filter@example.com", password="password12")
    with app.app_context():
        r1 = IncidentReport(
            user_id=user_id,
            location_name="Bridge 101",
            latitude=30.1,
            longitude=78.1,
            incident_type="Bridge Issue",
            severity="High",
            description="Structural vibration detected.",
            status=STATUS_REPORTED,
        )
        r2 = IncidentReport(
            user_id=user_id,
            location_name="City Square",
            latitude=30.2,
            longitude=78.2,
            incident_type="Waterlogging",
            severity="Low",
            description="Drainage blocked near marketplace.",
            status=STATUS_REPORTED,
        )
        db.session.add_all([r1, r2])
        db.session.commit()

    # Filter by incident_type
    res_bridge = admin_client.get("/api/admin/incidents?incident_type=Bridge+Issue")
    assert res_bridge.status_code == 200
    assert all(inc["incident_type"] == "Bridge Issue" for inc in res_bridge.get_json()["incidents"])

    # Filter by search query
    res_search = admin_client.get("/api/admin/incidents?q=Marketplace")
    assert res_search.status_code == 200
    assert len(res_search.get_json()["incidents"]) == 1
    assert res_search.get_json()["incidents"][0]["incident_type"] == "Waterlogging"


# ==============================================================================
# 6. GIS PUBLIC ENDPOINT & METADATA TESTS
# ==============================================================================

def test_public_gis_incidents_geojson(app, client):
    user_id = make_user(app, email="citizen_gis@example.com", password="password12")
    with app.app_context():
        r1 = IncidentReport(
            user_id=user_id,
            location_name="Karanprayag Crossing",
            latitude=30.2600,
            longitude=79.2200,
            incident_type="Road Blockage",
            severity="Moderate",
            description="Tree fallen on electric wire and road.",
            status=STATUS_REPORTED,
            is_verified=False,
        )
        r2 = IncidentReport(
            user_id=user_id,
            location_name="Devprayag Confluence",
            latitude=30.1450,
            longitude=78.5980,
            incident_type="Flooded Road",
            severity="Critical",
            description="Water reached high-water mark.",
            status=STATUS_VERIFIED,
            is_verified=True,
        )
        db.session.add_all([r1, r2])
        db.session.commit()

    # Fetch public GIS layer as anonymous client
    gis_res = client.get("/api/gis/incidents")
    assert gis_res.status_code == 200
    geojson = gis_res.get_json()

    assert geojson["type"] == "FeatureCollection"
    assert "features" in geojson
    assert len(geojson["features"]) == 2

    # Check disclaimer and coordinate ordering [lon, lat]
    for feat in geojson["features"]:
        coords = feat["geometry"]["coordinates"]
        assert len(coords) == 2
        # Longitude in India is around 70-90, Latitude is around 20-35
        assert coords[0] > coords[1]
        assert "disclaimer" in feat["properties"]
        assert "community observations" in feat["properties"]["disclaimer"].lower()

        # Check that sensitive information is NOT leaked in GIS endpoint
        assert "password" not in feat["properties"]
        assert "password_hash" not in feat["properties"]
        assert "user_email" not in feat["properties"]


def test_incident_types_metadata_endpoint(client):
    res = client.get("/api/incidents/types")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert set(data["incident_types"]) == set(INCIDENT_TYPES)
    assert set(data["severity_levels"]) == set(SEVERITY_LEVELS)
