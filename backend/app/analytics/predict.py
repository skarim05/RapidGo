"""Delay prediction: historical median + optional sklearn model."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pytz
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import DelayAggregate, DelayObservation
from app.analytics.delays import recompute_delay_aggregates

logger = logging.getLogger(__name__)
SETTINGS = get_settings()
MODEL_PATH = Path(__file__).resolve().parents[2] / "data" / "delay_model.joblib"


def _confidence(sample_count: int) -> str:
    if sample_count >= 100:
        return "high"
    if sample_count >= 30:
        return "medium"
    return "low"


def predict_delay(
    db: Session,
    route_id: str,
    hour: int | None = None,
    day_of_week: int | None = None,
) -> dict:
    tz = pytz.timezone(SETTINGS.timezone)
    now = datetime.now(timezone.utc).astimezone(tz)
    hour = hour if hour is not None else now.hour
    dow = day_of_week if day_of_week is not None else now.weekday()

    agg = (
        db.query(DelayAggregate)
        .filter(
            DelayAggregate.route_id == route_id,
            DelayAggregate.hour_local == hour,
            DelayAggregate.day_of_week == dow,
        )
        .first()
    )
    if agg and agg.sample_count >= 5:
        return {
            "route_id": route_id,
            "hour": hour,
            "day_of_week": dow,
            "predicted_delay_seconds": round(agg.median_delay_seconds),
            "p90_delay_seconds": round(agg.p90_delay_seconds),
            "confidence": _confidence(agg.sample_count),
            "sample_count": agg.sample_count,
            "method": "historical_median",
            "insufficient_data": agg.sample_count < 30,
        }

    # Fallback: route-wide median for that hour any day
    from sqlalchemy import func, select

    q = (
        select(
            func.percentile_cont(0.5).within_group(DelayObservation.delay_seconds),
            func.count(),
        )
        .where(
            DelayObservation.route_id == route_id,
            DelayObservation.hour_local == hour,
        )
    )
    row = db.execute(q).one()
    median, cnt = row[0], row[1] or 0
    if cnt >= 5 and median is not None:
        return {
            "route_id": route_id,
            "hour": hour,
            "day_of_week": dow,
            "predicted_delay_seconds": round(float(median)),
            "p90_delay_seconds": None,
            "confidence": _confidence(int(cnt)),
            "sample_count": int(cnt),
            "method": "hour_median_any_day",
            "insufficient_data": int(cnt) < 30,
        }

    # Cold start heuristic: peak hours assume higher delay
    peak = hour in (7, 8, 9, 16, 17, 18)
    heuristic = 180 if peak else 60
    return {
        "route_id": route_id,
        "hour": hour,
        "day_of_week": dow,
        "predicted_delay_seconds": heuristic,
        "p90_delay_seconds": None,
        "confidence": "low",
        "sample_count": int(cnt),
        "method": "heuristic_peak_hours",
        "insufficient_data": True,
    }


def train_sklearn_model(db: Session) -> dict:
    """Train HistGradientBoostingRegressor when enough data exists."""
    try:
        import numpy as np
        from sklearn.ensemble import HistGradientBoostingRegressor
    except ImportError as e:
        return {"ok": False, "error": str(e)}

    recompute_delay_aggregates(db)
    aggs = db.query(DelayAggregate).filter(DelayAggregate.sample_count >= 10).all()
    if len(aggs) < 50:
        return {"ok": False, "error": f"Need more aggregate rows, have {len(aggs)}"}

    X = np.array([[a.hour_local, a.day_of_week, 1 if a.day_of_week >= 5 else 0] for a in aggs])
    # Encode route as numeric hash bucket
    route_ids = list({a.route_id for a in aggs})
    route_map = {rid: i for i, rid in enumerate(route_ids)}
    X = np.hstack([X, np.array([[route_map[a.route_id]] for a in aggs])])
    y = np.array([a.median_delay_seconds for a in aggs])

    model = HistGradientBoostingRegressor(max_depth=6, random_state=42)
    model.fit(X, y)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "route_map": route_map}, MODEL_PATH)
    return {"ok": True, "samples": len(aggs), "path": str(MODEL_PATH)}


def predict_with_model(route_id: str, hour: int, day_of_week: int) -> float | None:
    if not MODEL_PATH.exists():
        return None
    data = joblib.load(MODEL_PATH)
    model = data["model"]
    route_map = data["route_map"]
    if route_id not in route_map:
        return None
    import numpy as np

    x = np.array([[hour, day_of_week, 1 if day_of_week >= 5 else 0, route_map[route_id]]])
    return float(model.predict(x)[0])
