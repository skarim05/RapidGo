"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "routes",
        sa.Column("route_id", sa.String(64), primary_key=True),
        sa.Column("route_short_name", sa.String(32)),
        sa.Column("route_long_name", sa.String(255)),
        sa.Column("route_type", sa.Integer()),
        sa.Column("route_color", sa.String(16)),
        sa.Column("route_text_color", sa.String(16)),
    )
    op.create_table(
        "stops",
        sa.Column("stop_id", sa.String(64), primary_key=True),
        sa.Column("stop_name", sa.String(255)),
        sa.Column("stop_lat", sa.Float()),
        sa.Column("stop_lon", sa.Float()),
    )
    op.create_table(
        "trips",
        sa.Column("trip_id", sa.String(64), primary_key=True),
        sa.Column("route_id", sa.String(64), index=True),
        sa.Column("service_id", sa.String(64)),
        sa.Column("shape_id", sa.String(64)),
        sa.Column("trip_headsign", sa.String(255)),
        sa.Column("direction_id", sa.Integer()),
    )
    op.create_table(
        "stop_times",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("trip_id", sa.String(64), index=True),
        sa.Column("stop_id", sa.String(64), index=True),
        sa.Column("stop_sequence", sa.Integer()),
        sa.Column("arrival_time", sa.String(16)),
        sa.Column("departure_time", sa.String(16)),
    )
    op.create_table(
        "shape_points",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("shape_id", sa.String(64), index=True),
        sa.Column("shape_pt_lat", sa.Float()),
        sa.Column("shape_pt_lon", sa.Float()),
        sa.Column("shape_pt_sequence", sa.Integer()),
    )
    op.create_table(
        "calendar",
        sa.Column("service_id", sa.String(64), primary_key=True),
        sa.Column("monday", sa.Integer()),
        sa.Column("tuesday", sa.Integer()),
        sa.Column("wednesday", sa.Integer()),
        sa.Column("thursday", sa.Integer()),
        sa.Column("friday", sa.Integer()),
        sa.Column("saturday", sa.Integer()),
        sa.Column("sunday", sa.Integer()),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
    )
    op.create_table(
        "calendar_dates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("service_id", sa.String(64), index=True),
        sa.Column("date", sa.Date()),
        sa.Column("exception_type", sa.Integer()),
    )
    op.create_table(
        "vehicle_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), index=True),
        sa.Column("vehicle_id", sa.String(64), index=True),
        sa.Column("trip_id", sa.String(64)),
        sa.Column("route_id", sa.String(64), index=True),
        sa.Column("lat", sa.Float()),
        sa.Column("lon", sa.Float()),
        sa.Column("bearing", sa.Float()),
        sa.Column("speed", sa.Float()),
    )
    op.create_table(
        "delay_observations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), index=True),
        sa.Column("trip_id", sa.String(64), index=True),
        sa.Column("route_id", sa.String(64), index=True),
        sa.Column("stop_id", sa.String(64), index=True),
        sa.Column("delay_seconds", sa.Integer()),
        sa.Column("hour_local", sa.Integer(), index=True),
        sa.Column("day_of_week", sa.Integer(), index=True),
    )
    op.create_index("ix_delay_obs_route_hour", "delay_observations", ["route_id", "hour_local"])
    op.create_table(
        "service_alerts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("alert_id", sa.String(128), unique=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True)),
        sa.Column("header_text", sa.Text()),
        sa.Column("description_text", sa.Text()),
        sa.Column("route_ids", sa.Text()),
    )
    op.create_table(
        "collision_points",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("external_id", sa.String(128)),
        sa.Column("lat", sa.Float()),
        sa.Column("lon", sa.Float()),
        sa.Column("location_name", sa.String(512)),
        sa.Column("year", sa.Integer()),
        sa.Column("collision_count", sa.Integer()),
        sa.Column("severity", sa.String(64)),
    )
    op.create_table(
        "delay_aggregates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("route_id", sa.String(64), index=True),
        sa.Column("hour_local", sa.Integer()),
        sa.Column("day_of_week", sa.Integer()),
        sa.Column("median_delay_seconds", sa.Float()),
        sa.Column("p90_delay_seconds", sa.Float()),
        sa.Column("sample_count", sa.Integer()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("route_id", "hour_local", "day_of_week", name="uq_delay_agg"),
    )
    op.create_table(
        "ingest_meta",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    for t in (
        "ingest_meta",
        "delay_aggregates",
        "collision_points",
        "service_alerts",
        "delay_observations",
        "vehicle_snapshots",
        "calendar_dates",
        "calendar",
        "shape_points",
        "stop_times",
        "trips",
        "stops",
        "routes",
    ):
        op.drop_table(t)
