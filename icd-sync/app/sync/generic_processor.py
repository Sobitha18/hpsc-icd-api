"""
generic_processor.py
Generic sync logic for any code type (ICD or HCPCS).
Handles: versioning, hash comparison, soft deletes, atomic commits.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.sync.utils import hash_row

logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    """Generic sync statistics."""
    added: int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0


async def sync_generic(
    db: AsyncSession,
    records: List[dict],
    code_model: Type,
    code_field: str,
) -> SyncStats:
    """
    Generic sync logic for any code type.

    Args:
      db: Database session
      records: List of code dicts from fetcher
      code_model: SQLAlchemy model (IcdCode or HcpcsCode)
      code_field: Field name for code ID ("code" or "hcpc")

    Returns:
      SyncStats with counts of changes
    """
    stats = SyncStats()

    # Load existing ACTIVE codes
    result = await db.execute(select(code_model).where(code_model.is_active == True))
    existing_rows: Dict[str, Any] = {
        getattr(row, code_field): row for row in result.scalars().all()
    }
    logger.info("Loaded %d existing ACTIVE codes from DB", len(existing_rows))

    # Build lookup from new records
    new_records: Dict[str, dict] = {r[code_field]: r for r in records}
    logger.info("Parsed %d codes from CMS file", len(new_records))

    # Process: INSERT new / UPDATE changed / SKIP unchanged
    to_insert: List[Any] = []

    for code_val, rec in new_records.items():
        new_hash = hash_row(rec)

        if code_val not in existing_rows:
            # New code
            to_insert.append(code_model(**rec, data_hash=new_hash, is_active=True))
            stats.added += 1
        else:
            existing = existing_rows[code_val]
            if existing.data_hash is not None and existing.data_hash == new_hash:
                # No change
                stats.skipped += 1
            else:
                # Changed — mark old inactive, insert new version
                existing.is_active = False
                to_insert.append(code_model(**rec, data_hash=new_hash, is_active=True))
                stats.updated += 1

    if to_insert:
        db.add_all(to_insert)
        logger.info("Inserting %d new code versions", len(to_insert))

    # Soft-delete retired codes
    retired = [code_val for code_val in existing_rows if code_val not in new_records]

    if retired:
        today = date.today()
        for code_val in retired:
            existing_rows[code_val].is_active = False
            existing_rows[code_val].term_dt = today
        stats.deleted = len(retired)
        logger.info("Soft-deleted %d retired codes", stats.deleted)

    # Atomic commit
    await db.commit()
    logger.info(
        "Sync complete — added: %d, updated: %d, deleted: %d, skipped: %d",
        stats.added, stats.updated, stats.deleted, stats.skipped,
    )

    return stats
