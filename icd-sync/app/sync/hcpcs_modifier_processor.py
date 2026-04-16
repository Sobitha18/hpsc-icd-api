"""
hcpcs_modifier_processor.py
HCPCS modifier sync using generic processor.
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HcpcsModifier, HcpcsModifierSyncLog
from app.sync.generic_processor import sync_generic, SyncStats

log = logging.getLogger(__name__)


class HcpcsModifierSyncStats(SyncStats):
    """HCPCS modifier sync stats (same as generic, for backward compatibility)."""
    pass


async def sync_hcpcs_modifiers(
    db: AsyncSession,
    records: list,
    cycle: str,
    source_url: str,
) -> HcpcsModifierSyncStats:
    """Sync HCPCS modifiers using generic processor."""
    generic_stats = await sync_generic(db, records, HcpcsModifier, "code")
    return HcpcsModifierSyncStats(
        added=generic_stats.added,
        updated=generic_stats.updated,
        deleted=generic_stats.deleted,
        skipped=generic_stats.skipped,
    )


async def record_hcpcs_modifier_sync_log(
    db: AsyncSession,
    source_url: str,
    zip_filename: str,
    update_cycle: str,
    total_codes: int,
    stats: HcpcsModifierSyncStats,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """Record HCPCS modifier sync log."""
    entry = HcpcsModifierSyncLog(
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
