"""Phase 7 emergency_facilities and emergency_requests tables.

Revision ID: 002_phase7_emergency_tables
Revises: 001_initial_schema
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa


revision = "002_phase7_emergency_tables"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "emergency_facilities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("facility_type", sa.String(length=32), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("phone", sa.String(length=100), nullable=True),
        sa.Column("opening_hours", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="OpenStreetMap"),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("facility_type IN ('hospital', 'police', 'shelter')", name="ck_emergency_facilities_type"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_emergency_facilities_facility_type", "emergency_facilities", ["facility_type"], unique=False)
    op.create_index("ix_emergency_facilities_latitude", "emergency_facilities", ["latitude"], unique=False)
    op.create_index("ix_emergency_facilities_longitude", "emergency_facilities", ["longitude"], unique=False)
    op.create_index("ix_emergency_facilities_external_id", "emergency_facilities", ["external_id"], unique=False)

    op.create_table(
        "emergency_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("request_type", sa.String(length=50), nullable=False),
        sa.Column("facility_type", sa.String(length=32), nullable=True),
        sa.Column("risk_level", sa.String(length=20), nullable=True),
        sa.Column("flood_probability", sa.Float(), nullable=True),
        sa.Column("landslide_probability", sa.Float(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_emergency_requests_user_id", "emergency_requests", ["user_id"], unique=False)
    op.create_index("ix_emergency_requests_request_type", "emergency_requests", ["request_type"], unique=False)
    op.create_index("ix_emergency_requests_created_at", "emergency_requests", ["created_at"], unique=False)


def downgrade():
    op.drop_index("ix_emergency_requests_created_at", table_name="emergency_requests")
    op.drop_index("ix_emergency_requests_request_type", table_name="emergency_requests")
    op.drop_index("ix_emergency_requests_user_id", table_name="emergency_requests")
    op.drop_table("emergency_requests")

    op.drop_index("ix_emergency_facilities_external_id", table_name="emergency_facilities")
    op.drop_index("ix_emergency_facilities_longitude", table_name="emergency_facilities")
    op.drop_index("ix_emergency_facilities_latitude", table_name="emergency_facilities")
    op.drop_index("ix_emergency_facilities_facility_type", table_name="emergency_facilities")
    op.drop_table("emergency_facilities")
