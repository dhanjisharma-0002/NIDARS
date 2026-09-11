"""
NIDARS — Phase 17: Automatic Disaster Report Generation Test Suite
Validates PDF generation, authentication protection, parameter validation,
prediction DB linking, and security privacy controls.
"""

import pytest
import io
from app import create_app
from config import TestConfig
from extensions import db
from models import User, PredictionHistory
from tests.conftest import login, make_user
from services.report_service import generate_disaster_pdf_report


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_unauthenticated_get_rejected(client):
    """Unauthenticated GET requests to /api/reports/disaster must be blocked."""
    response = client.get("/api/reports/disaster?latitude=31.1048&longitude=77.1734")
    assert response.status_code in (302, 401)
    if response.status_code == 302:
        assert "/login" in response.headers.get("Location", "")


def test_unauthenticated_post_rejected(client):
    """Unauthenticated POST requests to /api/reports/disaster must be blocked."""
    response = client.post(
        "/api/reports/disaster",
        json={"latitude": 31.1048, "longitude": 77.1734, "flood_probability": 0.8},
    )
    assert response.status_code in (302, 401)
    if response.status_code == 302:
        assert "/login" in response.headers.get("Location", "")


def test_authenticated_pdf_generation_via_get(app, client):
    """Authenticated user can generate a disaster PDF report via GET query parameters."""
    make_user(app)
    login(client)

    response = client.get(
        "/api/reports/disaster?location_name=Shimla+District&latitude=31.1048&longitude=77.1734"
        "&elevation=2276&rainfall_24h=110.0&rainfall_72h=240.0&rainfall_7d=410.0"
        "&temperature=16.0&wind_speed=14.5&air_pressure=982.0"
        "&flood_probability=0.75&landslide_probability=0.82&combined_risk=0.785&risk_level=HIGH"
    )

    assert response.status_code == 200
    assert response.headers.get("Content-Type") == "application/pdf"
    assert "attachment" in response.headers.get("Content-Disposition", "")
    assert "NIDARS_Disaster_Report_" in response.headers.get("Content-Disposition", "")
    assert response.data.startswith(b"%PDF")
    assert len(response.data) > 1000  # Substantial PDF payload


def test_authenticated_pdf_generation_via_post(app, client):
    """Authenticated user can generate a disaster PDF report via POST JSON."""
    make_user(app)
    login(client)

    payload = {
        "location_name": "Manali Valley High Risk Zone",
        "latitude": 32.2432,
        "longitude": 77.1892,
        "elevation": 2050,
        "rainfall_24h": 95.0,
        "rainfall_72h": 180.0,
        "rainfall_7d": 320.0,
        "temperature": 14.0,
        "wind_speed": 18.0,
        "air_pressure": 978.0,
        "flood_probability": 0.68,
        "flood_risk": "HIGH",
        "landslide_probability": 0.88,
        "landslide_risk": "CRITICAL",
        "combined_risk": 0.78,
        "risk_level": "CRITICAL",
        "explainability": {
            "top_factors": [
                {"feature": "rainfall_72h", "label": "Rainfall 72h", "impact": "HIGH", "value": 180.0, "unit": "mm"},
                {"feature": "rainfall_24h", "label": "Rainfall 24h", "impact": "HIGH", "value": 95.0, "unit": "mm"},
                {"feature": "elevation", "label": "Elevation", "impact": "MODERATE", "value": 2050, "unit": "m"},
            ]
        },
    }

    response = client.post("/api/reports/disaster", json=payload)

    assert response.status_code == 200
    assert response.headers.get("Content-Type") == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert len(response.data) > 1000


def test_authenticated_pdf_generation_by_prediction_id(app, client):
    """Authenticated user can generate PDF report from existing database PredictionHistory record."""
    user_id = make_user(app)
    login(client)

    # Insert a prediction
    with app.app_context():
        pred = PredictionHistory(
            user_id=user_id,
            prediction_type="flood",
            status="completed",
            result_json={
                "flood_probability": 0.742,
                "risk_level": "HIGH",
                "inputs": {
                    "location_name": "Yamuna Floodplain",
                    "latitude": 28.6139,
                    "longitude": 77.2090,
                    "rainfall_24h": 120.0,
                    "rainfall_72h": 210.0,
                    "rainfall_7d": 350.0,
                    "temperature": 26.0,
                    "wind_speed": 4.5,
                    "air_pressure": 1008.2,
                    "elevation": 450.0,
                },
            },
        )
        db.session.add(pred)
        db.session.commit()
        pred_id = pred.id

    response = client.get(f"/api/reports/disaster?prediction_id={pred_id}")

    assert response.status_code == 200
    assert response.headers.get("Content-Type") == "application/pdf"
    assert response.data.startswith(b"%PDF")


def test_missing_prediction_id_and_coordinates(app, client):
    """Request missing both prediction_id and coordinates must return 400 Bad Request."""
    make_user(app)
    login(client)

    response = client.get("/api/reports/disaster")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Latitude and longitude coordinates are required" in data["error"]


def test_nonexistent_prediction_id(app, client):
    """Request with non-existent prediction_id returns 404."""
    make_user(app)
    login(client)

    response = client.get("/api/reports/disaster?prediction_id=999999")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert "Prediction history record #999999 not found" in data["error"]


def test_invalid_coordinate_bounds(app, client):
    """Coordinates outside valid geographic range return 400."""
    make_user(app)
    login(client)

    response = client.get("/api/reports/disaster?latitude=999.0&longitude=77.2")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Coordinates out of valid bounds" in data["error"]


def test_invalid_data_type(app, client):
    """Non-numeric coordinate inputs return 400."""
    make_user(app)
    login(client)

    response = client.get("/api/reports/disaster?latitude=not_a_number&longitude=77.2")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Invalid numeric coordinates" in data["error"]


def test_security_no_sensitive_credentials_in_pdf(app, client):
    """Generated PDF must never leak user password hashes or secret tokens."""
    make_user(app, email="secret_agent@nidars.gov.in", password="UltraSecretPassword123!")
    login(client, email="secret_agent@nidars.gov.in", password="UltraSecretPassword123!")

    response = client.get(
        "/api/reports/disaster?location_name=Dehradun&latitude=30.3165&longitude=78.0322"
        "&elevation=640&rainfall_24h=50.0&temperature=22.0&flood_probability=0.45&risk_level=MODERATE"
    )

    assert response.status_code == 200
    pdf_bytes = response.data
    assert b"UltraSecretPassword123!" not in pdf_bytes
    assert b"pbkdf2:sha256" not in pdf_bytes
    assert b"scrypt:" not in pdf_bytes


def test_report_service_direct_unit():
    """Direct unit test of generate_disaster_pdf_report function."""
    report_data = {
        "report_id": "NIDARS-TEST-001",
        "generated_at": "2026-09-08 12:00:00 UTC",
        "generated_by": "Dr. Test Analyst",
        "location_name": "Rishikesh Foothills",
        "latitude": 30.0869,
        "longitude": 78.2676,
        "elevation": 372.0,
        "flood_probability": 0.65,
        "flood_risk": "HIGH",
        "landslide_probability": 0.40,
        "landslide_risk": "MODERATE",
        "combined_risk": 0.525,
        "risk_level": "HIGH",
        "weather": {
            "rainfall_24h": 75.0,
            "rainfall_72h": 160.0,
            "rainfall_7d": 290.0,
            "temperature": 23.5,
            "wind_speed": 11.2,
            "air_pressure": 995.0,
        },
        "explainability": {
            "top_factors": [
                {"label": "Rainfall 72h", "impact": "HIGH", "value": 160.0, "unit": "mm"},
                {"label": "Elevation", "impact": "MODERATE", "value": 372.0, "unit": "m"},
            ]
        },
    }

    pdf_buffer = generate_disaster_pdf_report(report_data)
    assert isinstance(pdf_buffer, io.BytesIO)
    pdf_bytes = pdf_buffer.getvalue()
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 2000


def test_empty_prediction_id_rejected(app, client):
    """Request with empty prediction_id parameter gives useful validation error."""
    make_user(app)
    login(client)

    response = client.get("/api/reports/disaster?prediction_id=")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert data["error"] == "INVALID_PREDICTION_ID"


def test_unauthorized_user_cannot_access_other_user_prediction_report(app, client):
    """A regular user must be blocked (HTTP 403) from accessing another user's prediction report."""
    user1_id = make_user(app, email="user1@nidars.gov.in", password="Password123!")
    user2_id = make_user(app, email="user2@nidars.gov.in", password="Password123!")

    # Create prediction owned by user 1
    with app.app_context():
        pred = PredictionHistory(
            user_id=user1_id,
            prediction_type="flood",
            status="completed",
            result_json={
                "flood_probability": 0.65,
                "risk_level": "HIGH",
                "inputs": {"latitude": 30.123, "longitude": 78.456, "location_name": "Rishikesh Safe Point"},
            },
        )
        db.session.add(pred)
        db.session.commit()
        pred_id = pred.id

    # Log in as user 2 and attempt to download user 1's report
    login(client, email="user2@nidars.gov.in", password="Password123!")
    response = client.get(f"/api/reports/disaster?prediction_id={pred_id}")
    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False
    assert data["error"] == "UNAUTHORIZED"


def test_admin_can_access_other_user_prediction_report(app, client):
    """Admin user is permitted to generate disaster report for any prediction record."""
    user_id = make_user(app, email="citizen@nidars.gov.in", password="Password123!")
    with app.app_context():
        admin = User(name="Admin Officer", email="admin_officer@nidars.gov.in", role="admin")
        admin.set_password("Password123!")
        db.session.add(admin)
        db.session.commit()

    with app.app_context():
        pred = PredictionHistory(
            user_id=user_id,
            prediction_type="landslide",
            status="completed",
            result_json={
                "landslide_probability": 0.72,
                "risk_level": "HIGH",
                "inputs": {"latitude": 31.1048, "longitude": 77.1734, "location_name": "Shimla Ridge"},
            },
        )
        db.session.add(pred)
        db.session.commit()
        pred_id = pred.id

    # Log in as admin
    login(client, email="admin_officer@nidars.gov.in", password="Password123!")
    response = client.get(f"/api/reports/disaster?prediction_id={pred_id}")
    assert response.status_code == 200
    assert response.headers.get("Content-Type") == "application/pdf"
    assert response.data.startswith(b"%PDF")

