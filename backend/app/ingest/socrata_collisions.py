"""Ingest Edmonton collision location data from Socrata open data API."""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import CollisionPoint, IngestMeta
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
SETTINGS = get_settings()

POINT_RE = re.compile(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", re.I)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def _parse_location(loc: str | None) -> tuple[float, float] | None:
    if not loc:
        return None
    m = POINT_RE.search(loc)
    if m:
        return float(m.group(2)), float(m.group(1))
    return None


def fetch_collision_rows(limit: int = 50000) -> list[dict]:
    url = f"{SETTINGS.socrata_base_url}/{SETTINGS.socrata_collision_dataset}.json"
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(url, params={"$limit": limit})
        resp.raise_for_status()
        return resp.json()


def _geocode_edmonton(name: str, client: httpx.Client) -> tuple[float, float] | None:
    """Geocode a collision location name within Edmonton (Nominatim, 1 req/s)."""
    query = f"{name}, Edmonton, Alberta, Canada"
    try:
        resp = client.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "RapidGo-ETS-Analytics/1.0 (edmonton-transit-study)"},
        )
        resp.raise_for_status()
        results = resp.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        logger.warning("Geocode failed for %s: %s", name, e)
    return None


def _load_geocode_cache(db: Session) -> dict[str, list[float]]:
    meta = db.get(IngestMeta, "collision_geocode_cache")
    if meta and meta.value:
        try:
            return json.loads(meta.value)
        except json.JSONDecodeError:
            pass
    return {}


def _save_geocode_cache(db: Session, cache: dict[str, list[float]]) -> None:
    now = datetime.now(timezone.utc)
    meta = db.get(IngestMeta, "collision_geocode_cache")
    payload = json.dumps(cache)
    if meta:
        meta.value = payload
        meta.updated_at = now
    else:
        db.add(IngestMeta(key="collision_geocode_cache", value=payload, updated_at=now))


def load_collisions(
    db: Session, rows: list[dict] | None = None, max_new_geocodes: int = 200
) -> int:
    if rows is None:
        rows = fetch_collision_rows()
    db.execute(delete(CollisionPoint))
    cache = _load_geocode_cache(db)
    count = 0
    new_geocodes = 0

    with httpx.Client(timeout=30.0) as client:
        for i, row in enumerate(rows):
            lat = row.get("latitude") or row.get("lat")
            lon = row.get("longitude") or row.get("lon") or row.get("long")
            if lat is None or lon is None:
                loc = row.get("location") or row.get("the_geom") or row.get("geom")
                if isinstance(loc, dict) and loc.get("coordinates"):
                    lon, lat = loc["coordinates"][0], loc["coordinates"][1]
                elif isinstance(loc, str):
                    parsed = _parse_location(loc)
                    if parsed:
                        lat, lon = parsed

            location_name = (
                row.get("location_description")
                or row.get("location")
                or row.get("intersection")
                or row.get("primary_street")
                or row.get("description")
            )

            if (lat is None or lon is None) and location_name:
                key = str(location_name).strip().upper()
                if key in cache:
                    lat, lon = cache[key][0], cache[key][1]
                elif new_geocodes < max_new_geocodes:
                    coords = _geocode_edmonton(key, client)
                    time.sleep(1.05)
                    new_geocodes += 1
                    if coords:
                        lat, lon = coords
                        cache[key] = [lat, lon]

            if lat is None or lon is None:
                continue
            try:
                lat_f, lon_f = float(lat), float(lon)
            except (TypeError, ValueError):
                continue

            year = row.get("year") or row.get("report_year") or row.get("collision_report_year")
            try:
                year_i = int(year) if year is not None else None
            except (TypeError, ValueError):
                year_i = None
            cnt = row.get("collision_count") or row.get("collisions") or row.get("total_collisions")
            try:
                cnt_i = int(cnt) if cnt is not None else 1
            except (TypeError, ValueError):
                cnt_i = 1

            db.add(
                CollisionPoint(
                    external_id=str(row.get(":id") or row.get("id") or f"{i}-{location_name}"),
                    lat=lat_f,
                    lon=lon_f,
                    location_name=str(location_name)[:512] if location_name else None,
                    year=year_i,
                    collision_count=cnt_i,
                    severity=row.get("severity") or row.get("collision_severity"),
                )
            )
            count += 1

    _save_geocode_cache(db, cache)
    now = datetime.now(timezone.utc)
    meta = db.get(IngestMeta, "collisions_loaded_at")
    if meta:
        meta.value = now.isoformat()
        meta.updated_at = now
    else:
        db.add(IngestMeta(key="collisions_loaded_at", value=now.isoformat(), updated_at=now))
    db.commit()
    return count


def refresh_collisions(db: Session | None = None, max_new_geocodes: int = 200) -> int:
    """Load collisions; geocode up to max_new_geocodes uncached location names per run."""
    close = False
    if db is None:
        db = SessionLocal()
        close = True
    try:
        rows = fetch_collision_rows()
        rows.sort(
            key=lambda r: int(r.get("collision_count") or r.get("collisions") or 0),
            reverse=True,
        )
        return load_collisions(db, rows, max_new_geocodes=max_new_geocodes)
    finally:
        if close:
            db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    n = refresh_collisions(max_new_geocodes=50)
    logger.info("Loaded %d collision points", n)


if __name__ == "__main__":
    main()
