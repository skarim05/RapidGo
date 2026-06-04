from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Route, ShapePoint, Stop, StopTime, Trip
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["routes"])


@router.get("/routes")
def list_routes(db: Session = Depends(get_db)):
    routes = db.query(Route).order_by(Route.route_short_name).all()
    return [
        {
            "route_id": r.route_id,
            "route_short_name": r.route_short_name,
            "route_long_name": r.route_long_name,
            "route_color": r.route_color,
            "route_text_color": r.route_text_color,
        }
        for r in routes
    ]


@router.get("/routes/{route_id}/stops")
def route_stops(route_id: str, db: Session = Depends(get_db)):
    trip_ids = [t.trip_id for t in db.query(Trip).filter(Trip.route_id == route_id).limit(20).all()]
    if not trip_ids:
        raise HTTPException(404, "Route not found or has no trips")
    stop_ids = {
        st.stop_id
        for st in db.query(StopTime.stop_id).filter(StopTime.trip_id.in_(trip_ids)).distinct()
    }
    stops = db.query(Stop).filter(Stop.stop_id.in_(stop_ids)).all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s.stop_lon, s.stop_lat]},
                "properties": {"stop_id": s.stop_id, "stop_name": s.stop_name},
            }
            for s in stops
            if s.stop_lat is not None and s.stop_lon is not None
        ],
    }


@router.get("/routes/{route_id}/shape")
def route_shape(route_id: str, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.route_id == route_id, Trip.shape_id.isnot(None)).first()
    if not trip or not trip.shape_id:
        raise HTTPException(404, "No shape for route")
    pts = (
        db.query(ShapePoint)
        .filter(ShapePoint.shape_id == trip.shape_id)
        .order_by(ShapePoint.shape_pt_sequence)
        .all()
    )
    coords = [[p.shape_pt_lon, p.shape_pt_lat] for p in pts]
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {"route_id": route_id, "shape_id": trip.shape_id},
    }
