"""
hcpcs_processor.py
HCPCS sync using generic processor.
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HcpcsCode, HcpcsSyncLog
from app.sync.generic_processor import sync_generic, SyncStats

log = logging.getLogger(__name__)


class HcpcsSyncStats(SyncStats):
    """HCPCS sync stats (same as generic, for backward compatibility)."""
    pass


async def sync_hcpcs_codes(
    db: AsyncSession,
    records: list,
    cycle: str,
    source_url: str,
) -> HcpcsSyncStats:
    """Sync HCPCS codes using generic processor."""
    generic_stats = await sync_generic(db, records, HcpcsCode, "hcpc")
    return HcpcsSyncStats(
        added=generic_stats.added,
        updated=generic_stats.updated,
        deleted=generic_stats.deleted,
        skipped=generic_stats.skipped,
    )


async def record_hcpcs_sync_log(
    db: AsyncSession,
    source_url: str,
    zip_filename: str,
    update_cycle: str,
    total_codes: int,
    stats: HcpcsSyncStats,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """Record HCPCS sync log."""
    entry = HcpcsSyncLog(
        source_url=source_url,
        zip_filename=zip_filename,
        update_cycle=update_cycle,
        total_codes=total_codes,
        inserted=stats.added,
        updated=stats.updated,
        deleted=stats.deleted,
        skipped=stats.skipped,
        status=status,
        error_message=error_message,
    )
    db.add(entry)
    await db.commit()
