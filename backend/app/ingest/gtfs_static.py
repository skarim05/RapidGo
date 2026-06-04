"""Download and load Edmonton static GTFS into the database."""
from __future__ import annotations

import io
import logging
import zipfile
from datetime import date, datetime, timezone

import httpx
import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import (
    Calendar,
    CalendarDate,
    IngestMeta,
    Route,
    ShapePoint,
    Stop,
    StopTime,
    Trip,
)
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
SETTINGS = get_settings()

GTFS_FILES = {
    "routes": Route,
    "stops": Stop,
    "trips": Trip,
    "stop_times": StopTime,
    "shapes": ShapePoint,
    "calendar": Calendar,
    "calendar_dates": CalendarDate,
}


def _parse_date(val) -> date | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(int(val)) if isinstance(val, float) else str(val).strip()
    if len(s) == 8:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return None


def _read_csv_from_zip(zf: zipfile.ZipFile, name: str) -> pd.DataFrame | None:
    candidates = [n for n in zf.namelist() if n.lower().endswith(name.lower()) or n.endswith(f"/{name}")]
    if not candidates:
        for n in zf.namelist():
            if n.split("/")[-1].lower() == name.lower():
                candidates = [n]
                break
    if not candidates:
        return None
    with zf.open(candidates[0]) as f:
        return pd.read_csv(f, dtype=str, low_memory=False)


def download_gtfs_zip() -> bytes:
    logger.info("Downloading static GTFS from %s", SETTINGS.gtfs_static_url)
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        resp = client.get(SETTINGS.gtfs_static_url)
        resp.raise_for_status()
        return resp.content


def load_gtfs_into_db(db: Session, zip_bytes: bytes) -> dict[str, int]:
    counts: dict[str, int] = {}
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))

    # Routes
    df = _read_csv_from_zip(zf, "routes.txt")
    if df is not None:
        db.execute(delete(Route))
        rows = []
        for _, r in df.iterrows():
            rows.append(
                Route(
                    route_id=str(r["route_id"]),
                    route_short_name=r.get("route_short_name") or None,
                    route_long_name=r.get("route_long_name") or None,
                    route_type=int(r["route_type"]) if pd.notna(r.get("route_type")) else None,
                    route_color=r.get("route_color") or None,
                    route_text_color=r.get("route_text_color") or None,
                )
            )
        db.bulk_save_objects(rows)
        counts["routes"] = len(rows)

    # Stops
    df = _read_csv_from_zip(zf, "stops.txt")
    if df is not None:
        db.execute(delete(Stop))
        rows = []
        for _, r in df.iterrows():
            rows.append(
                Stop(
                    stop_id=str(r["stop_id"]),
                    stop_name=r.get("stop_name") or None,
                    stop_lat=float(r["stop_lat"]) if pd.notna(r.get("stop_lat")) else None,
                    stop_lon=float(r["stop_lon"]) if pd.notna(r.get("stop_lon")) else None,
                )
            )
        db.bulk_save_objects(rows)
        counts["stops"] = len(rows)

    # Trips
    df = _read_csv_from_zip(zf, "trips.txt")
    if df is not None:
        db.execute(delete(Trip))
        rows = []
        for _, r in df.iterrows():
            rows.append(
                Trip(
                    trip_id=str(r["trip_id"]),
                    route_id=str(r["route_id"]),
                    service_id=r.get("service_id") or None,
                    shape_id=r.get("shape_id") or None,
                    trip_headsign=r.get("trip_headsign") or None,
                    direction_id=int(r["direction_id"]) if pd.notna(r.get("direction_id")) else None,
                )
            )
        db.bulk_save_objects(rows)
        counts["trips"] = len(rows)

    # Stop times (chunked)
    df = _read_csv_from_zip(zf, "stop_times.txt")
    if df is not None:
        db.execute(delete(StopTime))
        batch: list[StopTime] = []
        batch_size = 5000
        total = 0
        for _, r in df.iterrows():
            batch.append(
                StopTime(
                    trip_id=str(r["trip_id"]),
                    stop_id=str(r["stop_id"]),
                    stop_sequence=int(r["stop_sequence"]),
                    arrival_time=r.get("arrival_time") or None,
                    departure_time=r.get("departure_time") or None,
                )
            )
            if len(batch) >= batch_size:
                db.bulk_save_objects(batch)
                total += len(batch)
                batch.clear()
        if batch:
            db.bulk_save_objects(batch)
            total += len(batch)
        counts["stop_times"] = total

    # Shapes
    df = _read_csv_from_zip(zf, "shapes.txt")
    if df is not None:
        db.execute(delete(ShapePoint))
        rows = []
        for _, r in df.iterrows():
            rows.append(
                ShapePoint(
                    shape_id=str(r["shape_id"]),
                    shape_pt_lat=float(r["shape_pt_lat"]),
                    shape_pt_lon=float(r["shape_pt_lon"]),
                    shape_pt_sequence=int(r["shape_pt_sequence"]),
                )
            )
        db.bulk_save_objects(rows)
        counts["shape_points"] = len(rows)

    # Calendar
    df = _read_csv_from_zip(zf, "calendar.txt")
    if df is not None:
        db.execute(delete(Calendar))
        rows = []
        for _, r in df.iterrows():
            rows.append(
                Calendar(
                    service_id=str(r["service_id"]),
                    monday=int(r["monday"]),
                    tuesday=int(r["tuesday"]),
                    wednesday=int(r["wednesday"]),
                    thursday=int(r["thursday"]),
                    friday=int(r["friday"]),
                    saturday=int(r["saturday"]),
                    sunday=int(r["sunday"]),
                    start_date=_parse_date(r["start_date"]),
                    end_date=_parse_date(r["end_date"]),
                )
            )
        db.bulk_save_objects(rows)
        counts["calendar"] = len(rows)

    # Calendar dates
    df = _read_csv_from_zip(zf, "calendar_dates.txt")
    if df is not None:
        db.execute(delete(CalendarDate))
        rows = []
        for _, r in df.iterrows():
            d = _parse_date(r["date"])
            if d:
                rows.append(
                    CalendarDate(
                        service_id=str(r["service_id"]),
                        date=d,
                        exception_type=int(r["exception_type"]),
                    )
                )
        db.bulk_save_objects(rows)
        counts["calendar_dates"] = len(rows)

    meta = db.get(IngestMeta, "gtfs_static_loaded_at")
    now = datetime.now(timezone.utc)
    if meta:
        meta.value = now.isoformat()
        meta.updated_at = now
    else:
        db.add(IngestMeta(key="gtfs_static_loaded_at", value=now.isoformat(), updated_at=now))
    db.commit()
    return counts


def refresh_static_gtfs(db: Session | None = None) -> dict[str, int]:
    close = False
    if db is None:
        db = SessionLocal()
        close = True
    try:
        zip_bytes = download_gtfs_zip()
        return load_gtfs_into_db(db, zip_bytes)
    finally:
        if close:
            db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    counts = refresh_static_gtfs()
    logger.info("GTFS load complete: %s", counts)


if __name__ == "__main__":
    main()
