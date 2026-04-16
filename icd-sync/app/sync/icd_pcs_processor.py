"""
sync/icd_pcs_processor.py
-------------------------
ICD-10-PCS sync using the generic processor.
Handles inserting new codes, updating changed ones (soft versioning),
soft-deleting retired codes, and writing an audit row to icd_pcs_sync_history.
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IcdPcsCode, IcdPcsSyncHistory
from app.sync.generic_processor import sync_generic, SyncStats

log = logging.getLogger(__name__)


async def sync_icd_pcs_codes(
    db: AsyncSession,
    records: list,
    version: str,
    source_url: str,
) -> SyncStats:
    """Sync ICD-10-PCS codes using the generic processor."""
    return await sync_generic(db, records, IcdPcsCode, "code")


async def record_pcs_sync_history(
    db: AsyncSession,
    source_url: str,
    version: str,
    stats: SyncStats,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """Write one audit row to icd_pcs_sync_history."""
    history = IcdPcsSyncHistory(
        source_url=source_url,
        version=version,
        codes_added=stats.added,
        codes_updated=stats.updated,
        codes_deleted=stats.deleted,
        codes_skipped=stats.skipped,
        status=status,
        error_message=error_message,
    )
    db.add(history)
    await db.commit()
