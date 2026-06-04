"""Spatial analytics: collisions near stops and routes."""
from __future__ import annotations

import math

from sqlalchemy.orm import Session

from app.db.models import CollisionPoint, ShapePoint, Stop, StopTime, Trip


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def collisions_geojson(db: Session) -> dict:
    points = db.query(CollisionPoint).all()
    features = []
    for p in points:
        weight = p.collision_count or 1
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [p.lon, p.lat]},
                "properties": {
                    "id": p.id,
                    "location_name": p.location_name,
                    "year": p.year,
                    "collision_count": weight,
                    "intensity": weight,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def stops_near_collisions(
    db: Session, route_id: str, radius_m: float = 150.0
) -> list[dict]:
    collisions = db.query(CollisionPoint).all()
    if not collisions:
        return []
    trip_ids = [t.trip_id for t in db.query(Trip).filter(Trip.route_id == route_id).limit(50).all()]
    if not trip_ids:
        return []
    stop_ids = {
        st.stop_id
        for st in db.query(StopTime.stop_id)
        .filter(StopTime.trip_id.in_(trip_ids))
        .distinct()
        .all()
    }
    stops = db.query(Stop).filter(Stop.stop_id.in_(stop_ids)).all()
    results = []
    for stop in stops:
        if stop.stop_lat is None or stop.stop_lon is None:
            continue
        nearby = 0
        total_collisions = 0
        for c in collisions:
            d = _haversine_m(stop.stop_lat, stop.stop_lon, c.lat, c.lon)
            if d <= radius_m:
                nearby += 1
                total_collisions += c.collision_count or 1
        if nearby > 0:
            results.append(
                {
                    "stop_id": stop.stop_id,
                    "stop_name": stop.stop_name,
                    "lat": stop.stop_lat,
                    "lon": stop.stop_lon,
                    "nearby_collision_sites": nearby,
                    "total_reported_collisions": total_collisions,
                }
            )
    results.sort(key=lambda x: x["total_reported_collisions"], reverse=True)
    return results[:25]


def route_collision_density(db: Session, route_id: str, radius_m: float = 100.0) -> dict:
    trips = db.query(Trip).filter(Trip.route_id == route_id).all()
    shape_ids = {t.shape_id for t in trips if t.shape_id}
    if not shape_ids:
        return {"route_id": route_id, "points_checked": 0, "nearby_collision_sites": 0}
    shape_id = next(iter(shape_ids))
    pts = (
        db.query(ShapePoint)
        .filter(ShapePoint.shape_id == shape_id)
        .order_by(ShapePoint.shape_pt_sequence)
        .all()
    )
    collisions = db.query(CollisionPoint).all()
    nearby_sites = set()
    for pt in pts[::5]:  # sample every 5th point
        for c in collisions:
            if _haversine_m(pt.shape_pt_lat, pt.shape_pt_lon, c.lat, c.lon) <= radius_m:
                nearby_sites.add(c.id)
    return {
        "route_id": route_id,
        "points_checked": len(pts[::5]),
        "nearby_collision_sites": len(nearby_sites),
    }
