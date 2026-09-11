"""
NIDARS — Phase 18: Notification and Alert System Test Suite.
Validates notification creation, anti-spam deduplication, state transitions,
user isolation, threshold evaluation, and resilient email dispatch.
"""

import pytest
from app import create_app
from config import TestConfig
from extensions import db
from models import (
    TYPE_COMBINED_RISK_INCREASE,
    TYPE_EMERGENCY_ADVISORY,
    TYPE_FLOOD_RISK_INCREASE,
    TYPE_LANDSLIDE_RISK_INCREASE,
    TYPE_ROUTE_RISK_WARNING,
    User,
    UserNotification,
)
from services.notification_service import (
    create_notification,
    evaluate_and_notify_risk_change,
    get_unread_count,
    get_user_notifications,
    mark_all_notifications_as_read,
    mark_notification_as_read,
    send_email_notification,
)
from tests.conftest import login, make_user


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


def test_unauthenticated_notifications_access_rejected(client):
    """Anonymous requests to notification endpoints must be blocked."""
    assert client.get("/api/notifications").status_code in (302, 401)
    assert client.get("/api/notifications/stats").status_code in (302, 401)
    assert client.post("/api/notifications/1/read").status_code in (302, 401)
    assert client.post("/api/notifications/read-all").status_code in (302, 401)
    assert client.post("/api/notifications/trigger", json={}).status_code in (302, 401)


def test_create_and_retrieve_notifications(app, client):
    """Authenticated user can receive and list notifications via API."""
    user_id = make_user(app)
    login(client)

    with app.app_context():
        notif, created = create_notification(
            user_id=user_id,
            notification_type=TYPE_FLOOD_RISK_INCREASE,
            title="Flood Alert — Yamuna Floodplain",
            message="Flood probability increased to 78.5% following heavy precipitation.",
            risk_level="HIGH",
            location_name="Yamuna Floodplain, Delhi",
            latitude=28.6139,
            longitude=77.2090,
            hazard_probability=0.785,
        )
        assert created is True
        assert notif.id is not None
        assert notif.is_read is False

    response = client.get("/api/notifications")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["unread_count"] == 1
    assert data["total"] == 1
    assert len(data["notifications"]) == 1

    item = data["notifications"][0]
    assert item["title"] == "Flood Alert — Yamuna Floodplain"
    assert item["risk_level"] == "HIGH"
    assert item["hazard_probability"] == 0.785
    assert item["is_read"] is False


def test_all_five_notification_types_supported(app):
    """Verifies all five required notification types can be created and stored."""
    user_id = make_user(app)

    with app.app_context():
        types_to_test = [
            (TYPE_FLOOD_RISK_INCREASE, "Flood Risk Surge", "CRITICAL"),
            (TYPE_LANDSLIDE_RISK_INCREASE, "Landslide Slope Instability", "HIGH"),
            (TYPE_COMBINED_RISK_INCREASE, "Joint Hazard Escalation", "HIGH"),
            (TYPE_ROUTE_RISK_WARNING, "Route NH-58 Flooding Warning", "MODERATE"),
            (TYPE_EMERGENCY_ADVISORY, "Evacuation Protocol Advisory", "CRITICAL"),
        ]

        for ntype, title, risk in types_to_test:
            notif, created = create_notification(
                user_id=user_id,
                notification_type=ntype,
                title=title,
                message=f"Test advisory message for {ntype}.",
                risk_level=risk,
                location_name="Rishikesh",
                cooldown_minutes=0,
            )
            assert created is True
            assert notif.notification_type == ntype
            assert notif.risk_level == risk

        count = get_unread_count(user_id)
        assert count == 5


def test_cooldown_deduplication_prevents_spam(app):
    """Creating duplicate notifications within cooldown window reuses existing notification."""
    user_id = make_user(app)

    with app.app_context():
        # First creation
        notif1, created1 = create_notification(
            user_id=user_id,
            notification_type=TYPE_FLOOD_RISK_INCREASE,
            title="Flood Risk Increase",
            message="Precipitation rising.",
            risk_level="HIGH",
            location_name="Shimla",
            cooldown_minutes=30,
        )
        assert created1 is True

        # Second creation immediately after for same user/type/risk/location
        notif2, created2 = create_notification(
            user_id=user_id,
            notification_type=TYPE_FLOOD_RISK_INCREASE,
            title="Flood Risk Increase",
            message="Precipitation rising again.",
            risk_level="HIGH",
            location_name="Shimla",
            cooldown_minutes=30,
        )
        assert created2 is False
        assert notif1.id == notif2.id

        # Total unread count should remain 1
        assert get_unread_count(user_id) == 1


def test_mark_single_notification_as_read(app, client):
    """Marking a single notification as read updates its state and decrements unread counter."""
    user_id = make_user(app)
    login(client)

    with app.app_context():
        notif, _ = create_notification(
            user_id=user_id,
            notification_type=TYPE_ROUTE_RISK_WARNING,
            title="NH-58 Warning",
            message="High water level on highway route.",
            risk_level="HIGH",
        )
        notif_id = notif.id

    # Verify unread before
    res_stats = client.get("/api/notifications/stats")
    assert res_stats.get_json()["unread_count"] == 1

    # Mark as read
    res_read = client.post(f"/api/notifications/{notif_id}/read")
    assert res_read.status_code == 200
    assert res_read.get_json()["success"] is True
    assert res_read.get_json()["unread_count"] == 0

    # Verify via DB
    with app.app_context():
        n = db.session.get(UserNotification, notif_id)
        assert n.is_read is True
        assert n.read_at is not None


def test_mark_all_notifications_as_read(app, client):
    """Batch marking all notifications as read updates all unread items."""
    user_id = make_user(app)
    login(client)

    with app.app_context():
        for i in range(4):
            create_notification(
                user_id=user_id,
                notification_type=TYPE_COMBINED_RISK_INCREASE,
                title=f"Multi-Hazard Alert #{i}",
                message="Test alert batch.",
                risk_level="HIGH",
                location_name=f"Zone {i}",
                cooldown_minutes=0,
            )

    assert client.get("/api/notifications/stats").get_json()["unread_count"] == 4

    res_all = client.post("/api/notifications/read-all")
    assert res_all.status_code == 200
    data = res_all.get_json()
    assert data["success"] is True
    assert data["updated_count"] == 4
    assert data["unread_count"] == 0

    assert client.get("/api/notifications/stats").get_json()["unread_count"] == 0


def test_user_isolation_security(app, client):
    """User A cannot access or mark User B's notifications as read."""
    user_a = make_user(app, email="user_a@nidars.gov.in")
    user_b = make_user(app, email="user_b@nidars.gov.in")

    with app.app_context():
        notif_b, _ = create_notification(
            user_id=user_b,
            notification_type=TYPE_EMERGENCY_ADVISORY,
            title="User B Private Advisory",
            message="Confidential alert for User B.",
            risk_level="CRITICAL",
        )
        notif_b_id = notif_b.id

    # Login as User A
    login(client, email="user_a@nidars.gov.in")

    # User A listing should NOT contain User B's notification
    res_list = client.get("/api/notifications")
    assert res_list.status_code == 200
    assert len(res_list.get_json()["notifications"]) == 0

    # User A attempting to mark User B's notification as read must fail (404/unauthorized)
    res_read = client.post(f"/api/notifications/{notif_b_id}/read")
    assert res_read.status_code == 404
    assert res_read.get_json()["success"] is False

    # User B's notification should remain unread
    with app.app_context():
        n = db.session.get(UserNotification, notif_b_id)
        assert n.is_read is False


def test_evaluate_and_notify_risk_change_triggers(app):
    """Automatic threshold evaluator generates notifications on HIGH/CRITICAL or sharp probability increases."""
    user_id = make_user(app)

    with app.app_context():
        # High flood risk -> should trigger
        notif_flood = evaluate_and_notify_risk_change(
            user_id=user_id,
            hazard_type="flood",
            current_probability=0.82,
            previous_probability=0.60,
            risk_level="HIGH",
            location_name="Haridwar Ghat",
        )
        assert notif_flood is not None
        assert notif_flood.notification_type == TYPE_FLOOD_RISK_INCREASE
        assert notif_flood.risk_level == "HIGH"

        # Low risk with small delta -> should NOT trigger
        notif_low = evaluate_and_notify_risk_change(
            user_id=user_id,
            hazard_type="landslide",
            current_probability=0.04,
            previous_probability=0.03,
            risk_level="LOW",
            location_name="Dehradun",
        )
        assert notif_low is None

        # Landslide risk escalation -> should trigger
        notif_ls = evaluate_and_notify_risk_change(
            user_id=user_id,
            hazard_type="landslide",
            current_probability=0.45,
            previous_probability=0.10,
            risk_level="MODERATE",
            location_name="Manali Hills",
        )
        assert notif_ls is not None
        assert notif_ls.notification_type == TYPE_LANDSLIDE_RISK_INCREASE


def test_trigger_api_validation(app, client):
    """Validates the /api/notifications/trigger validation and error responses."""
    make_user(app)
    login(client)

    # Missing title & message
    res_empty = client.post("/api/notifications/trigger", json={})
    assert res_empty.status_code == 400
    assert "required" in res_empty.get_json()["error"]

    # Invalid notification type
    res_inv_type = client.post(
        "/api/notifications/trigger",
        json={"notification_type": "invalid_type", "title": "T", "message": "M"},
    )
    assert res_inv_type.status_code == 400

    # Valid trigger request
    res_valid = client.post(
        "/api/notifications/trigger",
        json={
            "notification_type": TYPE_EMERGENCY_ADVISORY,
            "title": "Severe Weather Advisory",
            "message": "Continuous heavy rainfall predicted across Kangra.",
            "risk_level": "HIGH",
            "location_name": "Kangra District",
            "latitude": 32.10,
            "longitude": 76.27,
            "hazard_probability": 0.72,
        },
    )
    assert res_valid.status_code == 200
    assert res_valid.get_json()["success"] is True
    assert res_valid.get_json()["created"] is True


def test_email_dispatch_graceful_failure():
    """Email dispatcher handles missing config and connection failures gracefully without raising exceptions."""
    # When MAIL_SERVER is not set
    success, msg = send_email_notification(
        recipient_email="analyst@nidars.gov.in",
        subject="Test Advisory",
        body_text="Test Message",
    )
    assert success is False
    assert "MAIL_SERVER" in msg or "not configured" in msg


def test_security_no_credentials_leakage(app, client):
    """Notification API responses must never leak user password hashes or secret tokens."""
    make_user(app, email="top_secret@nidars.gov.in", password="SuperSecretPassword123!")
    login(client, email="top_secret@nidars.gov.in", password="SuperSecretPassword123!")

    # Trigger a notification
    client.post(
        "/api/notifications/trigger",
        json={
            "notification_type": TYPE_COMBINED_RISK_INCREASE,
            "title": "Security Audit Advisory",
            "message": "Routine telemetry check.",
            "risk_level": "LOW",
        },
    )

    response = client.get("/api/notifications")
    raw_response = response.data.decode("utf-8")

    assert "SuperSecretPassword123!" not in raw_response
    assert "pbkdf2:sha256" not in raw_response
    assert "scrypt:" not in raw_response
    assert "password_hash" not in raw_response
