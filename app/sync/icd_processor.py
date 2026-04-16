"""
icd_processor.py
ICD-10-CM sync using generic processor.
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IcdCode, SyncHistory
from app.sync.generic_processor import sync_generic, SyncStats

logger = logging.getLogger(__name__)


async def sync_icd_codes(
    db: AsyncSession,
    records: list,
    version: str,
    source_url: str,
) -> SyncStats:
    """Sync ICD codes using generic processor."""
    return await sync_generic(db, records, IcdCode, "code")


async def record_sync_history(
    db: AsyncSession,
    source_url: str,
    version: str,
    stats: SyncStats,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """Record ICD sync history."""
    history = SyncHistory(
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
