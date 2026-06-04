"""Poll Edmonton GTFS-RT feeds and persist vehicle positions and delays."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx
import pytz
from google.transit import gtfs_realtime_pb2
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import DelayObservation, IngestMeta, ServiceAlert, Trip, VehicleSnapshot
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
SETTINGS = get_settings()
TZ = pytz.timezone(SETTINGS.timezone)


def _local_parts(dt_utc: datetime) -> tuple[int, int]:
    local = dt_utc.astimezone(TZ)
    return local.hour, local.weekday()


def fetch_pb_sync(url: str) -> bytes:
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content


def _trip_route_map(db: Session) -> dict[str, str]:
    trips = db.query(Trip.trip_id, Trip.route_id).all()
    return {t.trip_id: t.route_id for t in trips}


def ingest_vehicle_positions(db: Session, data: bytes, recorded_at: datetime) -> int:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(data)
    trip_routes = _trip_route_map(db)
    count = 0
    for entity in feed.entity:
        if not entity.HasField("vehicle"):
            continue
        v = entity.vehicle
        trip_id = v.trip.trip_id if v.HasField("trip") and v.trip.trip_id else None
        route_id = (
            v.trip.route_id
            if v.HasField("trip") and v.trip.route_id
            else trip_routes.get(trip_id) if trip_id else None
        )
        pos = v.position if v.HasField("position") else None
        db.add(
            VehicleSnapshot(
                recorded_at=recorded_at,
                vehicle_id=v.vehicle.id if v.HasField("vehicle") and v.vehicle.id else entity.id,
                trip_id=trip_id,
                route_id=route_id,
                lat=pos.latitude if pos else None,
                lon=pos.longitude if pos else None,
                bearing=pos.bearing if pos and pos.bearing else None,
                speed=pos.speed if pos and pos.speed else None,
            )
        )
        count += 1
    return count


def ingest_trip_updates(db: Session, data: bytes, recorded_at: datetime) -> int:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(data)
    trip_routes = _trip_route_map(db)
    hour_local, dow = _local_parts(recorded_at)
    count = 0
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        tu = entity.trip_update
        trip_id = tu.trip.trip_id if tu.HasField("trip") and tu.trip.trip_id else None
        route_id = (
            tu.trip.route_id
            if tu.HasField("trip") and tu.trip.route_id
            else trip_routes.get(trip_id) if trip_id else None
        )
        for stu in tu.stop_time_update:
            delay = None
            if stu.HasField("arrival") and stu.arrival.HasField("delay"):
                delay = int(stu.arrival.delay)
            elif stu.HasField("departure") and stu.departure.HasField("delay"):
                delay = int(stu.departure.delay)
            if delay is None:
                continue
            stop_id = stu.stop_id if stu.stop_id else None
            db.add(
                DelayObservation(
                    recorded_at=recorded_at,
                    trip_id=trip_id,
                    route_id=route_id,
                    stop_id=stop_id,
                    delay_seconds=delay,
                    hour_local=hour_local,
                    day_of_week=dow,
                )
            )
            count += 1
    return count


def ingest_alerts(db: Session, data: bytes, recorded_at: datetime) -> int:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(data)
    count = 0
    for entity in feed.entity:
        if not entity.HasField("alert"):
            continue
        alert = entity.alert
        header = ""
        desc = ""
        if alert.HasField("header_text") and alert.header_text.translation:
            header = alert.header_text.translation[0].text
        if alert.HasField("description_text") and alert.description_text.translation:
            desc = alert.description_text.translation[0].text
        route_ids = []
        for ie in alert.informed_entity:
            if ie.route_id:
                route_ids.append(ie.route_id)
        alert_id = entity.id or f"{recorded_at.timestamp()}-{count}"
        existing = db.query(ServiceAlert).filter(ServiceAlert.alert_id == alert_id).first()
        if existing:
            existing.recorded_at = recorded_at
            existing.header_text = header
            existing.description_text = desc
            existing.route_ids = ",".join(route_ids) if route_ids else None
        else:
            db.add(
                ServiceAlert(
                    alert_id=alert_id,
                    recorded_at=recorded_at,
                    header_text=header,
                    description_text=desc,
                    route_ids=",".join(route_ids) if route_ids else None,
                )
            )
        count += 1
    return count


def poll_once(db: Session) -> dict[str, int]:
    recorded_at = datetime.now(timezone.utc)
    results: dict[str, int] = {}
    vehicle_data = fetch_pb_sync(SETTINGS.gtfs_rt_vehicle_url)
    trip_data = fetch_pb_sync(SETTINGS.gtfs_rt_trip_url)
    alert_data = fetch_pb_sync(SETTINGS.gtfs_rt_alert_url)
    results["vehicles"] = ingest_vehicle_positions(db, vehicle_data, recorded_at)
    results["delays"] = ingest_trip_updates(db, trip_data, recorded_at)
    results["alerts"] = ingest_alerts(db, alert_data, recorded_at)

    meta = db.get(IngestMeta, "gtfs_rt_last_poll")
    now = recorded_at
    if meta:
        meta.value = now.isoformat()
        meta.updated_at = now
    else:
        db.add(IngestMeta(key="gtfs_rt_last_poll", value=now.isoformat(), updated_at=now))
    db.commit()
    return results


async def poll_loop(stop_event: asyncio.Event | None = None) -> None:
    while True:
        db = SessionLocal()
        try:
            await asyncio.to_thread(poll_once, db)
        except Exception:
            logger.exception("GTFS-RT poll failed")
            db.rollback()
        finally:
            db.close()
        if stop_event and stop_event.is_set():
            break
        await asyncio.sleep(SETTINGS.poll_interval_seconds)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(poll_loop())


if __name__ == "__main__":
    main()
