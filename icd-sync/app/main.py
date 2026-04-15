"""
main.py
-------
FastAPI application entry point.

Responsibilities:
  1. Create the FastAPI app and register all routers
  2. On startup: create DB tables if they don't exist
  3. On startup: start the APScheduler job that auto-syncs annually
  4. On shutdown: stop the scheduler cleanly

APScheduler job:
  Runs once per year on October 1 at 06:00 UTC.
  CMS publishes the new ICD-10-CM version on October 1 each year.
  The job calls the same sync logic as POST /sync/icd.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from sqlalchemy import text

from app.database import AsyncSessionLocal, Base, engine
from app.routers import codes, sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ICD-10-CM Sync API",
    description=(
        "Fetches ICD-10-CM codes from CMS, syncs them to PostgreSQL, "
        "and exposes a query API."
    ),
    version="1.0.0",
)

# Register routers
app.include_router(sync.router)
app.include_router(codes.router)

# ---------------------------------------------------------------------------
# Scheduler (auto-sync every year on Oct 1)
# ---------------------------------------------------------------------------
scheduler = AsyncIOScheduler()


async def scheduled_icd_sync():
    """
    Called automatically by the scheduler on October 1 each year.
    Reuses the same sync logic as the manual POST /sync/icd endpoint.
    """
    logger.info("Scheduled ICD sync starting...")
    from app.sync.fetcher import fetch_icd_codes
    from app.sync.processor import SyncStats, record_sync_history, sync_icd_codes
    from app.routers.sync import CMS_ICD10CM_URL

    stats = SyncStats()
    status = "failed"
    error_msg = None
    version = "unknown"

    async with AsyncSessionLocal() as db:
        try:
            records, version = await fetch_icd_codes(CMS_ICD10CM_URL)
            stats = await sync_icd_codes(db, records, version, CMS_ICD10CM_URL)
            status = "success"
            logger.info(
                "Scheduled sync done — +%d ~%d -%d",
                stats.added, stats.updated, stats.deleted,
            )
        except Exception as exc:
            error_msg = str(exc)
            logger.exception("Scheduled ICD sync failed: %s", error_msg)
        finally:
            await record_sync_history(
                db=db,
                source_url=CMS_ICD10CM_URL,
                version=version,
                stats=stats,
                status=status,
                error_message=error_msg,
            )


# ---------------------------------------------------------------------------
# Startup / shutdown lifecycle
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    # Create all tables in PostgreSQL if they don't already exist.
    # In production you'd use Alembic migrations instead — but this is
    # a safe fallback for first-run / development.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready")

    # Schedule the annual sync: every year on Oct 1 at 06:00 UTC
    scheduler.add_job(
        scheduled_icd_sync,
        trigger=CronTrigger(month=10, day=1, hour=6, minute=0),
        id="annual_icd_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — annual ICD sync scheduled for Oct 1 06:00 UTC")


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


# ---------------------------------------------------------------------------
# Health check — useful for load balancers / Docker healthchecks
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health():
    """Returns 200 if the app and DB connection are alive."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT 1"))
    return {"status": "ok"}
