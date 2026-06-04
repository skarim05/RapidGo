"""CLI: python -m app.analytics.train"""
import logging

from app.analytics.delays import recompute_delay_aggregates
from app.analytics.predict import train_sklearn_model
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    db = SessionLocal()
    try:
        n = recompute_delay_aggregates(db, 30)
        logger.info("Recomputed %d aggregate rows", n)
        result = train_sklearn_model(db)
        logger.info("Train result: %s", result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
