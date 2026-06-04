from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Route(Base):
    __tablename__ = "routes"

    route_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    route_short_name: Mapped[str | None] = mapped_column(String(32))
    route_long_name: Mapped[str | None] = mapped_column(String(255))
    route_type: Mapped[int | None] = mapped_column(Integer)
    route_color: Mapped[str | None] = mapped_column(String(16))
    route_text_color: Mapped[str | None] = mapped_column(String(16))


class Stop(Base):
    __tablename__ = "stops"

    stop_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    stop_name: Mapped[str | None] = mapped_column(String(255))
    stop_lat: Mapped[float | None] = mapped_column(Float)
    stop_lon: Mapped[float | None] = mapped_column(Float)


class Trip(Base):
    __tablename__ = "trips"

    trip_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    route_id: Mapped[str] = mapped_column(String(64), index=True)
    service_id: Mapped[str | None] = mapped_column(String(64))
    shape_id: Mapped[str | None] = mapped_column(String(64))
    trip_headsign: Mapped[str | None] = mapped_column(String(255))
    direction_id: Mapped[int | None] = mapped_column(Integer)


class StopTime(Base):
    __tablename__ = "stop_times"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_id: Mapped[str] = mapped_column(String(64), index=True)
    stop_id: Mapped[str] = mapped_column(String(64), index=True)
    stop_sequence: Mapped[int] = mapped_column(Integer)
    arrival_time: Mapped[str | None] = mapped_column(String(16))
    departure_time: Mapped[str | None] = mapped_column(String(16))


class ShapePoint(Base):
    __tablename__ = "shape_points"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shape_id: Mapped[str] = mapped_column(String(64), index=True)
    shape_pt_lat: Mapped[float] = mapped_column(Float)
    shape_pt_lon: Mapped[float] = mapped_column(Float)
    shape_pt_sequence: Mapped[int] = mapped_column(Integer)


class Calendar(Base):
    __tablename__ = "calendar"

    service_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    monday: Mapped[int] = mapped_column(Integer)
    tuesday: Mapped[int] = mapped_column(Integer)
    wednesday: Mapped[int] = mapped_column(Integer)
    thursday: Mapped[int] = mapped_column(Integer)
    friday: Mapped[int] = mapped_column(Integer)
    saturday: Mapped[int] = mapped_column(Integer)
    sunday: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)


class CalendarDate(Base):
    __tablename__ = "calendar_dates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    service_id: Mapped[str] = mapped_column(String(64), index=True)
    date: Mapped[date] = mapped_column(Date)
    exception_type: Mapped[int] = mapped_column(Integer)


class VehicleSnapshot(Base):
    __tablename__ = "vehicle_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    vehicle_id: Mapped[str | None] = mapped_column(String(64), index=True)
    trip_id: Mapped[str | None] = mapped_column(String(64))
    route_id: Mapped[str | None] = mapped_column(String(64), index=True)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    bearing: Mapped[float | None] = mapped_column(Float)
    speed: Mapped[float | None] = mapped_column(Float)


class DelayObservation(Base):
    __tablename__ = "delay_observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    trip_id: Mapped[str | None] = mapped_column(String(64), index=True)
    route_id: Mapped[str | None] = mapped_column(String(64), index=True)
    stop_id: Mapped[str | None] = mapped_column(String(64), index=True)
    delay_seconds: Mapped[int] = mapped_column(Integer)
    hour_local: Mapped[int] = mapped_column(Integer, index=True)
    day_of_week: Mapped[int] = mapped_column(Integer, index=True)


class ServiceAlert(Base):
    __tablename__ = "service_alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(String(128), unique=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    header_text: Mapped[str | None] = mapped_column(Text)
    description_text: Mapped[str | None] = mapped_column(Text)
    route_ids: Mapped[str | None] = mapped_column(Text)


class CollisionPoint(Base):
    __tablename__ = "collision_points"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(128))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    location_name: Mapped[str | None] = mapped_column(String(512))
    year: Mapped[int | None] = mapped_column(Integer)
    collision_count: Mapped[int | None] = mapped_column(Integer)
    severity: Mapped[str | None] = mapped_column(String(64))


class DelayAggregate(Base):
    """Precomputed route x hour x dow medians for fast prediction."""

    __tablename__ = "delay_aggregates"
    __table_args__ = (
        UniqueConstraint("route_id", "hour_local", "day_of_week", name="uq_delay_agg"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    route_id: Mapped[str] = mapped_column(String(64), index=True)
    hour_local: Mapped[int] = mapped_column(Integer)
    day_of_week: Mapped[int] = mapped_column(Integer)
    median_delay_seconds: Mapped[float] = mapped_column(Float)
    p90_delay_seconds: Mapped[float] = mapped_column(Float)
    sample_count: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IngestMeta(Base):
    __tablename__ = "ingest_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index("ix_delay_obs_route_hour", DelayObservation.route_id, DelayObservation.hour_local)
Index("ix_vehicle_snap_recorded", VehicleSnapshot.recorded_at.desc())
