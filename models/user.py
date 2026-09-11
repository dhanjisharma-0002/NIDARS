from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db

ROLE_USER = "user"
ROLE_ADMIN = "admin"
VALID_ROLES = (ROLE_USER, ROLE_ADMIN)


def utc_now():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_USER, server_default=ROLE_USER)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    predictions = db.relationship("PredictionHistory", back_populates="user", lazy="dynamic")

    __table_args__ = (
        db.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == ROLE_ADMIN

    def __repr__(self):
        return f"<User {self.email}>"
