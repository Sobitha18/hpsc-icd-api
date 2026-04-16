"""
routers/sync.py
Unified sync endpoint for ICD-10-CM, HCPCS, and ICD-10-PCS codes.
Routes to appropriate handler based on code_type parameter.
"""

import logging
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import HcpcsSyncResult, IcdPcsSyncResult, SyncResult
from app.sync.icd_fetcher import fetch_icd_codes
from app.sync.hcpcs_fetcher import CMS_HCPCS_QUARTERLY_URL, fetch_hcpcs_codes
from app.sync.hcpcs_processor import HcpcsSyncStats, record_hcpcs_sync_log, sync_hcpcs_codes
from app.sync.icd_processor import SyncStats, record_sync_history, sync_icd_codes
from app.sync.icd_pcs_fetcher import CMS_ICD_PCS_URL, fetch_icd_pcs_codes
from app.sync.icd_pcs_processor import record_pcs_sync_history, sync_icd_pcs_codes

log = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["Sync"])

_ICD_URL = "https://www.cms.gov/files/zip/2026-code-descriptions-tabular-order.zip"

# Handler registry for code type routing
_sync_handlers = {
    "icd":     lambda url, db: _sync_icd(url or _ICD_URL, db),
    "hcpcs":   lambda url, db: _sync_hcpcs(url, db),
    "icd_pcs": lambda url, db: _sync_icd_pcs(url or CMS_ICD_PCS_URL, db),
}


@router.post("/codes", response_model=Union[SyncResult, HcpcsSyncResult, IcdPcsSyncResult])
async def sync_codes(
    code_type: str = Query(..., description="Code type: 'icd', 'hcpcs', or 'icd_pcs'"),
    url: Optional[str] = Query(None, description="Optional custom CMS URL"),
    db: AsyncSession = Depends(get_db),
):
    """
    Unified endpoint to sync medical codes from CMS.

    Parameters:
    - code_type: 'icd' for ICD-10-CM diagnosis codes, 'hcpcs' for HCPCS procedure codes,
                 'icd_pcs' for ICD-10-PCS inpatient procedure codes
    - url: Optional custom download URL (defaults to latest CMS release)

    Examples:
    - POST /sync/codes?code_type=icd
    - POST /sync/codes?code_type=hcpcs
    - POST /sync/codes?code_type=icd_pcs
    - POST /sync/codes?code_type=icd_pcs&url=https://...
    """

    handler = _sync_handlers.get(code_type)
    if not handler:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid code_type: '{code_type}'. Use 'icd', 'hcpcs', or 'icd_pcs'"
        )

    return await handler(url, db)


async def _sync_icd(url: str, db: AsyncSession) -> SyncResult:
    """Sync ICD-10-CM codes."""
    stats, status, err_msg, version = SyncStats(), "failed", None, "unknown"

    try:
        log.info("ICD sync triggered")
        records, version = await fetch_icd_codes(url)
        stats = await sync_icd_codes(db, records, version, url)
        status = "success"
    except Exception as exc:
        err_msg = str(exc)
        log.exception("ICD sync failed: %s", err_msg)
    finally:
        await record_sync_history(db, url, version, stats, status, err_msg)

    return SyncResult(
        status=status,
        version=version,
        codes_added=stats.added,
        codes_updated=stats.updated,
        codes_deleted=stats.deleted,
        codes_skipped=stats.skipped,
        message=f"Sync completed. FY{version} loaded." if status == "success" else f"Sync failed: {err_msg}",
    )


async def _sync_hcpcs(url: Optional[str], db: AsyncSession) -> HcpcsSyncResult:
    """Sync HCPCS codes."""
    stats, status, err_msg = HcpcsSyncStats(), "failed", None
    cycle, zip_filename, total_codes = "unknown", "unknown", 0

    try:
        log.info("HCPCS sync triggered")
        records, cycle, zip_filename = await fetch_hcpcs_codes(url)
        total_codes = len(records)
        stats = await sync_hcpcs_codes(db, records, cycle, CMS_HCPCS_QUARTERLY_URL)
        status = "success"
    except Exception as exc:
        err_msg = str(exc)
        log.exception("HCPCS sync failed: %s", err_msg)
    finally:
        await record_hcpcs_sync_log(db, url or CMS_HCPCS_QUARTERLY_URL, zip_filename, cycle, total_codes, stats, status, err_msg)

    return HcpcsSyncResult(
        status=status,
        update_cycle=cycle,
        zip_filename=zip_filename,
        codes_inserted=stats.added,
        codes_updated=stats.updated,
        codes_deleted=stats.deleted,
        codes_skipped=stats.skipped,
        message=f"HCPCS sync completed. Cycle {cycle} loaded." if status == "success" else f"Sync failed: {err_msg}",
    )


async def _sync_icd_pcs(url: str, db: AsyncSession) -> IcdPcsSyncResult:
    """Sync ICD-10-PCS codes."""
    stats, status, err_msg, version = SyncStats(), "failed", None, "unknown"

    try:
        log.info("ICD-10-PCS sync triggered")
        records, version = await fetch_icd_pcs_codes(url)
        stats = await sync_icd_pcs_codes(db, records, version, url)
        status = "success"
    except Exception as exc:
        err_msg = str(exc)
        log.exception("ICD-10-PCS sync failed: %s", err_msg)
    finally:
        await record_pcs_sync_history(db, url, version, stats, status, err_msg)

    return IcdPcsSyncResult(
        status=status,
        version=version,
        codes_added=stats.added,
        codes_updated=stats.updated,
        codes_deleted=stats.deleted,
        codes_skipped=stats.skipped,
        message=f"ICD-10-PCS sync completed. FY{version} loaded." if status == "success" else f"Sync failed: {err_msg}",
    )
