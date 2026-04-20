import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from sqlalchemy import text

from .database import AsyncSessionLocal, Base, engine
from .models import HcpcsCode, HcpcsModifier, HcpcsModifierSyncLog, HcpcsSyncLog, IcdCode, IcdPcsCode, IcdPcsSyncHistory, SyncHistory  # noqa: F401
from .routers import sync
from .routers.sync import _SYNCERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_icd_sync():
    async with AsyncSessionLocal() as db:
        result = await _SYNCERS["icd"](db).sync()
        logger.info("Scheduled ICD sync done — status=%s", result.status)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready")

    scheduler.add_job(
        scheduled_icd_sync,
        trigger=CronTrigger(month=10, day=1, hour=6, minute=0),
        id="annual_icd_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started")

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(
    title="CMS Medical Codes Sync API",
    version="2.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.include_router(sync.router)


@app.get("/health", tags=["Health"])
async def health():
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT 1"))
    return {"status": "ok"}
