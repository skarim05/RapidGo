from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics.predict import predict_delay, predict_with_model, train_sklearn_model
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["predict"])


@router.get("/predict")
def predict(
    route_id: str,
    hour: int | None = Query(None, ge=0, le=23),
    day_of_week: int | None = Query(None, ge=0, le=6),
    db: Session = Depends(get_db),
):
    result = predict_delay(db, route_id, hour, day_of_week)
    ml = None
    if hour is not None and day_of_week is not None:
        ml = predict_with_model(route_id, hour, day_of_week)
    elif result.get("hour") is not None:
        ml = predict_with_model(route_id, result["hour"], result["day_of_week"])
    if ml is not None:
        result["ml_predicted_delay_seconds"] = round(ml)
    return result


@router.post("/predict/train")
def train_model(db: Session = Depends(get_db)):
    return train_sklearn_model(db)
