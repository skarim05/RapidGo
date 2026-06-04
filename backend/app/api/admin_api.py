from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ingest.gtfs_static import refresh_static_gtfs
from app.ingest.socrata_collisions import refresh_collisions

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/refresh-gtfs")
def admin_refresh_gtfs(db: Session = Depends(get_db)):
    counts = refresh_static_gtfs(db)
    return {"ok": True, "counts": counts}


@router.post("/refresh-collisions")
def admin_refresh_collisions(db: Session = Depends(get_db)):
    n = refresh_collisions(db)
    return {"ok": True, "collision_points": n}
