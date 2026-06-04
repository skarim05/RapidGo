from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import IngestMeta, ServiceAlert, VehicleSnapshot
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["map"])


@router.get("/vehicles")
def live_vehicles(db: Session = Depends(get_db)):
    """Latest vehicle position per vehicle_id from recent snapshots."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    subq = (
        db.query(
            VehicleSnapshot.vehicle_id,
            func.max(VehicleSnapshot.id).label("max_id"),
        )
        .filter(
            VehicleSnapshot.recorded_at >= cutoff,
            VehicleSnapshot.lat.isnot(None),
            VehicleSnapshot.lon.isnot(None),
        )
        .group_by(VehicleSnapshot.vehicle_id)
        .subquery()
    )
    snaps = (
        db.query(VehicleSnapshot)
        .join(subq, VehicleSnapshot.id == subq.c.max_id)
        .all()
    )
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s.lon, s.lat]},
                "properties": {
                    "vehicle_id": s.vehicle_id,
                    "trip_id": s.trip_id,
                    "route_id": s.route_id,
                    "bearing": s.bearing,
                    "speed": s.speed,
                    "recorded_at": s.recorded_at.isoformat() if s.recorded_at else None,
                },
            }
            for s in snaps
        ],
        "count": len(snaps),
    }


@router.get("/alerts")
def service_alerts(db: Session = Depends(get_db)):
    alerts = db.query(ServiceAlert).order_by(ServiceAlert.recorded_at.desc()).limit(20).all()
    return [
        {
            "alert_id": a.alert_id,
            "header_text": a.header_text,
            "description_text": a.description_text,
            "route_ids": a.route_ids.split(",") if a.route_ids else [],
            "recorded_at": a.recorded_at.isoformat() if a.recorded_at else None,
        }
        for a in alerts
    ]


@router.get("/status")
def ingest_status(db: Session = Depends(get_db)):
    keys = ["gtfs_static_loaded_at", "gtfs_rt_last_poll", "collisions_loaded_at"]
    meta = {m.key: m.value for m in db.query(IngestMeta).filter(IngestMeta.key.in_(keys)).all()}
    last_poll = meta.get("gtfs_rt_last_poll")
    stale = True
    if last_poll:
        try:
            ts = datetime.fromisoformat(last_poll.replace("Z", "+00:00"))
            stale = (datetime.now(timezone.utc) - ts) > timedelta(minutes=5)
        except ValueError:
            pass
    return {
        "gtfs_static_loaded_at": meta.get("gtfs_static_loaded_at"),
        "gtfs_rt_last_poll": last_poll,
        "collisions_loaded_at": meta.get("collisions_loaded_at"),
        "rt_feed_stale": stale,
    }
