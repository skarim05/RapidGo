import asyncio
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta  

from sqlalchemy import text              
from app.analytics.delays import recompute_delay_aggregates
from app.api import admin_api, analytics_api, map_api, predict_api, routes_api
from app.config import get_settings
from app.db.session import SessionLocal
from app.ingest.gtfs_rt_poller import poll_once

logger = logging.getLogger(__name__)
settings = get_settings()
scheduler = AsyncIOScheduler()


async def _scheduled_rt_poll():
    db = SessionLocal()
    try:
        await asyncio.to_thread(poll_once, db)
    except Exception:
        logger.exception("Scheduled RT poll failed")
        db.rollback()
    finally:
        db.close()


async def _scheduled_recompute_aggregates():
    db = SessionLocal()
    try:
        await asyncio.to_thread(recompute_delay_aggregates, db, 30)
    except Exception:
        logger.exception("Aggregate recompute failed")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    scheduler.add_job(
        _scheduled_rt_poll,
        "interval",
        seconds=settings.poll_interval_seconds,
        id="gtfs_rt_poll",
        replace_existing=True,
    )
    
    scheduler.add_job(
        _scheduled_recompute_aggregates,
        "cron",
        hour=3,
        minute=0,
        id="recompute_aggregates",
        replace_existing=True,
    )

    scheduler.add_job(
        _scheduled_prune_data,
        "cron",
        hour=4,
        minute=0,
        id="prune_old_data",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("RapidGo started; RT poll every %ss", settings.poll_interval_seconds)
    yield
    scheduler.shutdown(wait=False)

def prune_old_records(db):
    """Deletes delay_observations older than 3 days."""
    cutoff_time = datetime.utcnow() - timedelta(days=3)
    db.execute(
        text("DELETE FROM delay_observations WHERE recorded_at < :cutoff"),
        {"cutoff": cutoff_time}
    )
    db.commit()
    logger.info(f"Pruned data older than {cutoff_time}")

async def _scheduled_prune_data():
    """Async wrapper to run the pruning logic in a separate thread."""
    db = SessionLocal()
    try:
        await asyncio.to_thread(prune_old_records, db)
    except Exception:
        logger.exception("Data pruning failed")
        db.rollback()
    finally:
        db.close()

app = FastAPI(title="RapidGo API", description="Edmonton ETS analytics", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_api.router)
app.include_router(map_api.router)
app.include_router(analytics_api.router)
app.include_router(predict_api.router)
app.include_router(admin_api.router)


@app.get("/health")
def health():
    return {"status": "ok"}
