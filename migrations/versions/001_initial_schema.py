"""Initial users, locations, and prediction_history tables.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa


revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_locations_state", "locations", ["state"], unique=False)
    op.create_index("ix_locations_district", "locations", ["district"], unique=False)

    op.create_table(
        "prediction_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("prediction_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prediction_history_user_id", "prediction_history", ["user_id"], unique=False)
    op.create_index("ix_prediction_history_location_id", "prediction_history", ["location_id"], unique=False)
    op.create_index(
        "ix_prediction_history_prediction_type",
        "prediction_history",
        ["prediction_type"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_prediction_history_prediction_type", table_name="prediction_history")
    op.drop_index("ix_prediction_history_location_id", table_name="prediction_history")
    op.drop_index("ix_prediction_history_user_id", table_name="prediction_history")
    op.drop_table("prediction_history")
    op.drop_index("ix_locations_district", table_name="locations")
    op.drop_index("ix_locations_state", table_name="locations")
    op.drop_table("locations")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
