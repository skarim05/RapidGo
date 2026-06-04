"""Delay aggregation queries."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import DelayAggregate, DelayObservation, Route


def recompute_delay_aggregates(db: Session, days: int = 30) -> int:
    """Refresh delay_aggregates from raw observations."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    subq = (
        select(
            DelayObservation.route_id,
            DelayObservation.hour_local,
            DelayObservation.day_of_week,
            func.percentile_cont(0.5).within_group(DelayObservation.delay_seconds).label("median"),
            func.percentile_cont(0.9).within_group(DelayObservation.delay_seconds).label("p90"),
            func.count().label("cnt"),
        )
        .where(
            DelayObservation.recorded_at >= cutoff,
            DelayObservation.route_id.isnot(None),
        )
        .group_by(
            DelayObservation.route_id,
            DelayObservation.hour_local,
            DelayObservation.day_of_week,
        )
    )
    rows = db.execute(subq).all()
    db.query(DelayAggregate).delete()
    now = datetime.now(timezone.utc)
    for row in rows:
        if not row.route_id:
            continue
        db.add(
            DelayAggregate(
                route_id=row.route_id,
                hour_local=row.hour_local,
                day_of_week=row.day_of_week,
                median_delay_seconds=float(row.median or 0),
                p90_delay_seconds=float(row.p90 or 0),
                sample_count=int(row.cnt or 0),
                updated_at=now,
            )
        )
    db.commit()
    return len(rows)


def delays_by_hour(
    db: Session, route_id: str, days: int = 7
) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        select(
            DelayObservation.hour_local,
            func.percentile_cont(0.5).within_group(DelayObservation.delay_seconds).label("median"),
            func.percentile_cont(0.9).within_group(DelayObservation.delay_seconds).label("p90"),
            func.count().label("samples"),
        )
        .where(
            DelayObservation.route_id == route_id,
            DelayObservation.recorded_at >= cutoff,
        )
        .group_by(DelayObservation.hour_local)
        .order_by(DelayObservation.hour_local)
    )
    return [
        {
            "hour": r.hour_local,
            "median_delay_seconds": float(r.median or 0),
            "p90_delay_seconds": float(r.p90 or 0),
            "samples": int(r.samples or 0),
        }
        for r in db.execute(q).all()
    ]


def delay_heatmap(
    db: Session, route_id: str, days: int = 14
) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        select(
            DelayObservation.day_of_week,
            DelayObservation.hour_local,
            func.percentile_cont(0.9).within_group(DelayObservation.delay_seconds).label("p90"),
            func.count().label("samples"),
        )
        .where(
            DelayObservation.route_id == route_id,
            DelayObservation.recorded_at >= cutoff,
        )
        .group_by(DelayObservation.day_of_week, DelayObservation.hour_local)
    )
    return [
        {
            "day_of_week": r.day_of_week,
            "hour": r.hour_local,
            "p90_delay_seconds": float(r.p90 or 0),
            "samples": int(r.samples or 0),
        }
        for r in db.execute(q).all()
    ]


def route_ranking(db: Session, days: int = 7, limit: int = 20) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        select(
            DelayObservation.route_id,
            func.percentile_cont(0.5).within_group(DelayObservation.delay_seconds).label("median"),
            func.percentile_cont(0.9).within_group(DelayObservation.delay_seconds).label("p90"),
            func.count().label("samples"),
        )
        .where(
            DelayObservation.recorded_at >= cutoff,
            DelayObservation.route_id.isnot(None),
        )
        .group_by(DelayObservation.route_id)
        .order_by(func.percentile_cont(0.9).within_group(DelayObservation.delay_seconds).desc())
        .limit(limit)
    )
    route_names = {r.route_id: r.route_short_name for r in db.query(Route).all()}
    return [
        {
            "route_id": r.route_id,
            "route_short_name": route_names.get(r.route_id),
            "median_delay_seconds": float(r.median or 0),
            "p90_delay_seconds": float(r.p90 or 0),
            "samples": int(r.samples or 0),
        }
        for r in db.execute(q).all()
    ]


def worst_stops_on_route(db: Session, route_id: str, days: int = 7, limit: int = 10) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        select(
            DelayObservation.stop_id,
            func.percentile_cont(0.5).within_group(DelayObservation.delay_seconds).label("median"),
            func.count().label("samples"),
        )
        .where(
            DelayObservation.route_id == route_id,
            DelayObservation.recorded_at >= cutoff,
            DelayObservation.stop_id.isnot(None),
        )
        .group_by(DelayObservation.stop_id)
        .order_by(func.percentile_cont(0.5).within_group(DelayObservation.delay_seconds).desc())
        .limit(limit)
    )
    return [
        {
            "stop_id": r.stop_id,
            "median_delay_seconds": float(r.median or 0),
            "samples": int(r.samples or 0),
        }
        for r in db.execute(q).all()
    ]
