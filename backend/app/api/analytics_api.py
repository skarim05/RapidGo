from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics import delays, spatial
from app.analytics.delays import recompute_delay_aggregates
from app.db.session import get_db

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/route/{route_id}/delays-by-hour")
def route_delays_by_hour(
    route_id: str,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    return delays.delays_by_hour(db, route_id, days)


@router.get("/route/{route_id}/heatmap")
def route_delay_heatmap(
    route_id: str,
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
):
    return delays.delay_heatmap(db, route_id, days)


@router.get("/routes/ranking")
def routes_ranking(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return delays.route_ranking(db, days, limit)


@router.get("/route/{route_id}/worst-stops")
def route_worst_stops(
    route_id: str,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    return delays.worst_stops_on_route(db, route_id, days)


@router.get("/collisions")
def collisions_geojson(db: Session = Depends(get_db)):
    return spatial.collisions_geojson(db)


@router.get("/route/{route_id}/collision-risk")
def route_collision_risk(route_id: str, db: Session = Depends(get_db)):
    return {
        "density": spatial.route_collision_density(db, route_id),
        "stops_near_collisions": spatial.stops_near_collisions(db, route_id),
    }


@router.post("/recompute-aggregates")
def recompute_aggregates(days: int = Query(30, ge=1, le=90), db: Session = Depends(get_db)):
    n = recompute_delay_aggregates(db, days)
    return {"updated_rows": n}
