"""
routers/sync.py
---------------
Endpoints that trigger or inspect ICD sync runs.

  POST /sync/icd            — run a sync right now (manual trigger)
  GET  /sync/history        — list past sync runs
  GET  /sync/history/latest — show the most recent sync run

The actual sync work happens in:
  fetcher.py   → download + parse
  processor.py → diff + update DB
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import SyncHistory
from app.schemas import SyncHistoryItem, SyncResult
from app.sync.fetcher import fetch_icd_codes
from app.sync.processor import SyncStats, record_sync_history, sync_icd_codes

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["Sync"])

# ---------------------------------------------------------------------------
# CMS download URL for ICD-10-CM order file.
# CMS publishes a new ZIP each year. This URL points to the FY2025 release.
# Update this URL each year when CMS publishes a new release.
# ---------------------------------------------------------------------------
CMS_ICD10CM_URL = (
    "https://www.cms.gov/files/zip/2025-code-descriptions-tabular-order.zip"
)


@router.post("/icd", response_model=SyncResult)
async def trigger_icd_sync(
    url: str = Query(
        default=CMS_ICD10CM_URL,
        description="Override the CMS download URL (leave blank to use default)",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Download the latest ICD-10-CM codes from CMS and sync to the database.

    What happens:
      1. Downloads the CMS ZIP file (~4 MB)
      2. Parses ~75,000 code lines from the order file
      3. Diffs against current DB state
      4. Inserts new, updates changed, deletes retired codes
      5. Records the result in sync_history

    Returns counts of what changed and whether it succeeded.
    This call can take 10–30 seconds depending on CMS server speed.
    """
    stats = SyncStats()
    status = "failed"
    error_msg = None
    version = "unknown"

    try:
        logger.info("Starting ICD sync from: %s", url)

        # Step 1 + 2: Download ZIP + parse order file
        records, version = await fetch_icd_codes(url)
        logger.info("Fetched %d records for version %s", len(records), version)

        # Step 3 + 4 + 5: Diff + update DB
        stats = await sync_icd_codes(db, records, version, url)
        status = "success"

    except Exception as exc:
        error_msg = str(exc)
        logger.exception("ICD sync failed: %s", error_msg)

    finally:
        # Always record the outcome — even on failure
        await record_sync_history(
            db=db,
            source_url=url,
            version=version,
            stats=stats,
            status=status,
            error_message=error_msg,
        )

    if status == "failed":
        # Return a 200 with status="failed" so the caller still gets details.
        # Alternatively you could raise HTTPException(500) — your call.
        return SyncResult(
            status="failed",
            version=version,
            codes_added=stats.added,
            codes_updated=stats.updated,
            codes_deleted=stats.deleted,
            message=f"Sync failed: {error_msg}",
        )

    return SyncResult(
        status="success",
        version=version,
        codes_added=stats.added,
        codes_updated=stats.updated,
        codes_deleted=stats.deleted,
        message=f"Sync completed. FY{version} loaded into database.",
    )


@router.get("/history", response_model=list[SyncHistoryItem])
async def list_sync_history(
    limit: int = Query(20, ge=1, le=100, description="Max rows to return"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the most recent sync history rows, newest first.

    Useful for checking:
      - When was the last successful sync?
      - How many codes changed in the last run?
      - Did any run fail?
    """
    result = await db.execute(
        select(SyncHistory)
        .order_by(SyncHistory.synced_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/history/latest", response_model=SyncHistoryItem)
async def get_latest_sync(db: AsyncSession = Depends(get_db)):
    """
    Return the single most recent sync run.
    Quick way to check current DB state.
    """
    from fastapi import HTTPException

    result = await db.execute(
        select(SyncHistory).order_by(SyncHistory.synced_at.desc()).limit(1)
    )
    latest = result.scalar_one_or_none()

    if latest is None:
        raise HTTPException(status_code=404, detail="No sync runs recorded yet")

    return latest
