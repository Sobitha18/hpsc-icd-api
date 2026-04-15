"""
routers/sync.py
---------------
Endpoints for triggering sync runs.

ICD-10-CM:
  POST /sync/icd                   — trigger ICD sync

HCPCS:
  POST /sync/hcpcs                 — trigger HCPCS sync

(Sync history is stored in DB tables — check via pgAdmin if needed)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    HcpcsSyncResult,
    SyncResult,
)
from app.sync.fetcher import fetch_icd_codes
from app.sync.hcpcs_fetcher import CMS_HCPCS_QUARTERLY_URL, fetch_hcpcs_codes
from app.sync.hcpcs_processor import (
    HcpcsSyncStats,
    record_hcpcs_sync_log,
    sync_hcpcs_codes,
)
from app.sync.processor import SyncStats, record_sync_history, sync_icd_codes

log = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["Sync"])

# Default CMS source URLs — override via query param if needed
_ICD_URL = "https://www.cms.gov/files/zip/2026-code-descriptions-tabular-order.zip"


# ---------------------------------------------------------------------------
# ICD-10-CM sync endpoints
# ---------------------------------------------------------------------------

@router.post("/icd", response_model=SyncResult, summary="Trigger ICD-10-CM sync")
async def trigger_icd_sync(
    url: str = Query(
        default=_ICD_URL,
        description="CMS ZIP download URL. Defaults to the current FY release.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Download the latest ICD-10-CM codes from CMS and sync to the database.

    - Downloads the CMS ZIP (~4 MB)
    - Parses ~97 000 fixed-width lines from the order file
    - Compares each code's MD5 hash against the stored hash
    - Inserts new codes, updates changed codes, deletes retired codes
    - Skips unchanged codes (hash match)
    - Records the result in icd_sync_history

    Can take 15–45 seconds on the first run.
    Subsequent runs are faster because most codes are skipped.
    """
    stats   = SyncStats()
    status  = "failed"
    err_msg: Optional[str] = None
    version = "unknown"

    try:
        log.info("ICD sync triggered from: %s", url)
        records, version = await fetch_icd_codes(url)
        log.info("Fetched %d ICD records (FY%s)", len(records), version)
        stats  = await sync_icd_codes(db, records, version, url)
        status = "success"

    except Exception as exc:
        err_msg = str(exc)
        log.exception("ICD sync failed: %s", err_msg)

    finally:
        await record_sync_history(
            db=db, source_url=url, version=version,
            stats=stats, status=status, error_message=err_msg,
        )

    return SyncResult(
        status=status,
        version=version,
        codes_added=stats.added,
        codes_updated=stats.updated,
        codes_deleted=stats.deleted,
        codes_skipped=stats.skipped,
        message=(
            f"Sync completed. FY{version} loaded into database."
            if status == "success"
            else f"Sync failed: {err_msg}"
        ),
    )


# ---------------------------------------------------------------------------
# HCPCS sync endpoints
# ---------------------------------------------------------------------------

@router.post("/hcpcs", response_model=HcpcsSyncResult, summary="Trigger HCPCS sync")
async def trigger_hcpcs_sync(
    url: Optional[str] = Query(
        default=None,
        description=(
            "Direct ZIP download URL. "
            "Leave blank to auto-detect the latest file from the CMS quarterly page."
        ),
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Download the latest HCPCS Alpha-Numeric file from CMS and sync to the database.

    - Scrapes the CMS quarterly update page to find the most recently updated ZIP
      (or uses the URL you provide directly)
    - Downloads the ZIP, extracts the ANWEB Excel inside
    - Compares each code's MD5 hash against the stored hash
    - Inserts new codes, updates changed codes, deletes retired codes
    - Skips unchanged codes (hash match)
    - Records the result in hcpcs_sync_log

    Can take 30–90 seconds on first run (large Excel file).
    Subsequent runs are much faster because most codes are skipped.
    """
    stats        = HcpcsSyncStats()
    status       = "failed"
    err_msg:  Optional[str] = None
    cycle        = "unknown"
    zip_filename = "unknown"
    total_codes  = 0

    try:
        log.info("HCPCS sync triggered (url=%s)", url or "auto-detect")
        records, cycle, zip_filename = await fetch_hcpcs_codes(url)
        total_codes = len(records)
        log.info("Fetched %d HCPCS records (cycle=%s)", total_codes, cycle)
        stats  = await sync_hcpcs_codes(db, records, cycle, CMS_HCPCS_QUARTERLY_URL)
        status = "success"

    except Exception as exc:
        err_msg = str(exc)
        log.exception("HCPCS sync failed: %s", err_msg)

    finally:
        await record_hcpcs_sync_log(
            db=db,
            source_url=url or CMS_HCPCS_QUARTERLY_URL,
            zip_filename=zip_filename,
            update_cycle=cycle,
            total_codes=total_codes,
            stats=stats,
            status=status,
            error_message=err_msg,
        )

    return HcpcsSyncResult(
        status=status,
        update_cycle=cycle,
        zip_filename=zip_filename,
        codes_inserted=stats.inserted,
        codes_updated=stats.updated,
        codes_deleted=stats.deleted,
        codes_skipped=stats.skipped,
        message=(
            f"HCPCS sync completed. Cycle {cycle} loaded into database."
            if status == "success"
            else f"HCPCS sync failed: {err_msg}"
        ),
    )
