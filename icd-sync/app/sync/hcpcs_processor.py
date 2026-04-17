"""
hcpcs_processor.py
Unified HCPCS sync for codes and modifiers using generic processor.
"""

import logging
from typing import Optional, Type

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.models import HcpcsCode, HcpcsSyncLog, HcpcsModifier, HcpcsModifierSyncLog
from app.sync.generic_processor import sync_generic, SyncStats

log = logging.getLogger(__name__)


class HcpcsSyncStats(SyncStats):
    """HCPCS sync stats (same as generic, for backward compatibility)."""
    pass


async def sync_hcpcs_data(
    db: AsyncSession,
    records: list,
    model: Type[DeclarativeBase],
    cycle: str,
    source_url: str,
) -> HcpcsSyncStats:
    """Sync HCPCS data (codes or modifiers) using generic processor."""
    generic_stats = await sync_generic(db, records, model, "code")
    return HcpcsSyncStats(
        added=generic_stats.added,
        updated=generic_stats.updated,
        deleted=generic_stats.deleted,
        skipped=generic_stats.skipped,
    )


async def _record_hcpcs_sync_log_unified(
    db: AsyncSession,
    source_url: str,
    zip_filename: str,
    update_cycle: str,
    total_codes: int,
    stats: HcpcsSyncStats,
    status: str,
    log_model: Type[DeclarativeBase],
    error_message: Optional[str] = None,
) -> None:
    """Internal unified HCPCS sync log recorder (codes or modifiers)."""
    entry = log_model(
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


# Backward compatibility wrappers
async def sync_hcpcs_codes(
    db: AsyncSession,
    records: list,
    cycle: str,
    source_url: str,
) -> HcpcsSyncStats:
    """Sync HCPCS codes (backward compatibility wrapper)."""
    return await sync_hcpcs_data(db, records, HcpcsCode, cycle, source_url)


async def sync_hcpcs_modifiers(
    db: AsyncSession,
    records: list,
    cycle: str,
    source_url: str,
) -> HcpcsSyncStats:
    """Sync HCPCS modifiers (backward compatibility wrapper)."""
    return await sync_hcpcs_data(db, records, HcpcsModifier, cycle, source_url)


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
    """Record HCPCS code sync log (backward compatibility wrapper)."""
    await _record_hcpcs_sync_log_unified(
        db, source_url, zip_filename, update_cycle, total_codes,
        stats, status, HcpcsSyncLog, error_message
    )


async def record_hcpcs_modifier_sync_log(
    db: AsyncSession,
    source_url: str,
    zip_filename: str,
    update_cycle: str,
    total_codes: int,
    stats: HcpcsSyncStats,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """Record HCPCS modifier sync log (backward compatibility wrapper)."""
    await _record_hcpcs_sync_log_unified(
        db, source_url, zip_filename, update_cycle, total_codes,
        stats, status, HcpcsModifierSyncLog, error_message
    )
