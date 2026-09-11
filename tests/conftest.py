from config import TestConfig
from extensions import db
from models import User


def login(client, email="tester@example.com", password="password12"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def make_user(app, email="tester@example.com", password="password12"):
    with app.app_context():
        user = User(name="Tester", email=email, role="user")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


VALID_FLOOD_PAYLOAD = {
    "rainfall_24h": 120.0,
    "rainfall_72h": 210.0,
    "rainfall_7d": 350.0,
    "temperature": 26.0,
    "wind_speed": 4.5,
    "air_pressure": 1008.2,
    "elevation": 450.0,
    "latitude": 28.6139,
    "longitude": 77.2090,
}
