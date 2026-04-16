"""
routers/sync.py
Unified sync endpoint for ICD-10-CM and HCPCS codes.
Routes to appropriate handler based on code_type parameter.
"""

import logging
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import HcpcsSyncResult, SyncResult
from app.sync.icd_fetcher import fetch_icd_codes
from app.sync.hcpcs_fetcher import CMS_HCPCS_QUARTERLY_URL, fetch_hcpcs_codes
from app.sync.hcpcs_processor import HcpcsSyncStats, record_hcpcs_sync_log, sync_hcpcs_codes
from app.sync.hcpcs_modifier_processor import HcpcsModifierSyncStats, record_hcpcs_modifier_sync_log, sync_hcpcs_modifiers
from app.sync.icd_processor import SyncStats, record_sync_history, sync_icd_codes

log = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["Sync"])

_ICD_URL = "https://www.cms.gov/files/zip/2026-code-descriptions-tabular-order.zip"

# Handler registry for code type routing
_sync_handlers = {
    "icd": lambda url, db: _sync_icd(url or _ICD_URL, db),
    "hcpcs": lambda url, db: _sync_hcpcs(url, db),
}


@router.post("/codes", response_model=Union[SyncResult, HcpcsSyncResult])
async def sync_codes(
    code_type: str = Query(..., description="Code type: 'icd' or 'hcpcs'"),
    url: Optional[str] = Query(None, description="Optional custom CMS URL"),
    db: AsyncSession = Depends(get_db),
):
    """
    Unified endpoint to sync medical codes from CMS.

    Parameters:
    - code_type: 'icd' for ICD-10-CM diagnosis codes, 'hcpcs' for HCPCS procedure codes
    - url: Optional custom download URL (defaults to latest CMS release)

    Examples:
    - POST /sync/codes?code_type=icd
    - POST /sync/codes?code_type=hcpcs
    - POST /sync/codes?code_type=icd&url=https://...
    """

    handler = _sync_handlers.get(code_type)
    if not handler:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid code_type: {code_type}. Use 'icd' or 'hcpcs'"
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
    """Sync HCPCS modifiers and codes."""
    mod_stats = HcpcsModifierSyncStats()
    code_stats = HcpcsSyncStats()
    status, err_msg = "failed", None
    cycle, zip_filename = "unknown", "unknown"

    try:
        log.info("HCPCS sync triggered")
        modifiers, codes, cycle, zip_filename = await fetch_hcpcs_codes(url)

        # Sync modifiers
        if modifiers:
            log.info("Syncing %d modifiers", len(modifiers))
            mod_stats = await sync_hcpcs_modifiers(db, modifiers, cycle, CMS_HCPCS_QUARTERLY_URL)
            await record_hcpcs_modifier_sync_log(
                db, url or CMS_HCPCS_QUARTERLY_URL, zip_filename, cycle,
                len(modifiers), mod_stats, "success", None
            )

        # Sync codes
        if codes:
            log.info("Syncing %d codes", len(codes))
            code_stats = await sync_hcpcs_codes(db, codes, cycle, CMS_HCPCS_QUARTERLY_URL)
            await record_hcpcs_sync_log(
                db, url or CMS_HCPCS_QUARTERLY_URL, zip_filename, cycle,
                len(codes), code_stats, "success", None
            )

        status = "success"
    except Exception as exc:
        err_msg = str(exc)
        log.exception("HCPCS sync failed: %s", err_msg)
    finally:
        # Only record error if sync failed (no partial success logs)
        if status == "failed":
            await record_hcpcs_modifier_sync_log(
                db, url or CMS_HCPCS_QUARTERLY_URL, zip_filename, cycle,
                0, mod_stats, status, err_msg
            )
            await record_hcpcs_sync_log(
                db, url or CMS_HCPCS_QUARTERLY_URL, zip_filename, cycle,
                0, code_stats, status, err_msg
            )

    return HcpcsSyncResult(
        status=status,
        update_cycle=cycle,
        zip_filename=zip_filename,
        modifiers_inserted=mod_stats.added,
        modifiers_updated=mod_stats.updated,
        modifiers_deleted=mod_stats.deleted,
        modifiers_skipped=mod_stats.skipped,
        codes_inserted=code_stats.added,
        codes_updated=code_stats.updated,
        codes_deleted=code_stats.deleted,
        codes_skipped=code_stats.skipped,
        message=f"HCPCS sync completed. Cycle {cycle} loaded." if status == "success" else f"Sync failed: {err_msg}",
    )
