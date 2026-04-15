"""
processor.py
------------
Compares freshly parsed CMS records against the current DB state
and applies versioning-based updates to bring the DB in sync.

Logic (with versioning):
  new_codes  = codes in CMS file  but NOT in DB  → INSERT with is_active=True
  changed    = codes in both,     but data differs → mark old inactive, INSERT new version
  retired    = codes in DB        but NOT in CMS file → mark inactive, set term_dt

Why versioning?
  ICD-10-CM codes can change (e.g., description updates, billable status).
  Instead of modifying the old record, we deactivate it and create a new
  version. This preserves full audit history while keeping only 1 active
  version per code at any time.

Returns a SyncStats object that the router uses to build the response.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IcdCode, SyncHistory
from app.sync.utils import hash_row  # shared with HCPCS processor

logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    """Counts of what changed during a sync run."""
    added:   int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0
    version: str = ""


async def sync_icd_codes(
    db: AsyncSession,
    records: List[dict],
    version: str,
    source_url: str,
) -> SyncStats:
    """
    Apply versioning-based sync between `records` (from CMS) and the current DB.

    Steps:
      1. Load all ACTIVE existing codes from DB into memory
      2. Build a lookup dict from the new CMS records
      3. INSERT codes that are new (is_active=True)
      4. For codes that changed: mark old as inactive, INSERT new version
      5. SOFT-DELETE codes not in CMS: mark inactive, set term_dt
      6. Write a SyncHistory row regardless of success/failure

    Versioning: Multiple rows per code are allowed. Only one is marked is_active=True
    at any time. Old versions remain in DB with is_active=False for audit trail.

    Args:
      db         : async DB session
      records    : list of dicts from fetcher.parse_order_file()
      version    : fiscal year string, e.g. "2025"
      source_url : the CMS URL we downloaded from (stored in history)

    Returns:
      SyncStats with counts of what changed (added/updated/deleted/skipped)
    """
    stats = SyncStats(version=version)

    # ------------------------------------------------------------------
    # Step 1: Load existing ACTIVE DB codes into a dict  { code: IcdCode row }
    # We only track the active version of each code.
    # ------------------------------------------------------------------
    result = await db.execute(select(IcdCode).where(IcdCode.is_active == True))
    existing_rows: Dict[str, IcdCode] = {
        row.code: row for row in result.scalars().all()
    }
    logger.info("Loaded %d existing ACTIVE codes from DB", len(existing_rows))

    # ------------------------------------------------------------------
    # Step 2: Build a lookup dict from the new CMS records
    # { code: record_dict }
    # ------------------------------------------------------------------
    new_records: Dict[str, dict] = {r["code"]: r for r in records}
    logger.info("Parsed %d codes from CMS file", len(new_records))

    # ------------------------------------------------------------------
    # Step 3 + 4: INSERT new codes / mark old as inactive when changed
    # Uses versioning: when a code changes, mark the old one inactive
    # and insert a new row with the new data.
    # ------------------------------------------------------------------
    to_insert: List[IcdCode] = []

    for code, rec in new_records.items():
        new_hash = hash_row(rec)

        if code not in existing_rows:
            # Brand new code — insert with is_active=True
            to_insert.append(IcdCode(**rec, data_hash=new_hash, is_active=True))
            stats.added += 1
        else:
            existing = existing_rows[code]
            if existing.data_hash is not None and existing.data_hash == new_hash:
                # Nothing changed — skip
                stats.skipped += 1
            else:
                # Changed — mark old version as inactive and insert new version
                existing.is_active = False  # deactivate old version

                # Insert new version with new data, is_active=True
                new_version = IcdCode(
                    **rec,
                    data_hash=new_hash,
                    is_active=True,
                )
                to_insert.append(new_version)
                stats.updated += 1
                logger.debug(
                    "Code %s changed — deactivated old version, inserted new version",
                    code,
                )

    if to_insert:
        db.add_all(to_insert)
        logger.info("Inserting %d new code versions", len(to_insert))

    # ------------------------------------------------------------------
    # Step 5: SOFT-DELETE retired codes
    # Any code in the DB that is NOT in the new CMS file is retired.
    # Mark as inactive instead of hard-deleting.
    # ------------------------------------------------------------------
    retired_codes = [code for code in existing_rows if code not in new_records]

    if retired_codes:
        today = date.today()
        for code in retired_codes:
            existing_rows[code].is_active = False
            existing_rows[code].term_dt = today
        stats.deleted = len(retired_codes)
        logger.info("Soft-deleted %d retired codes (marked inactive)", stats.deleted)

    # ------------------------------------------------------------------
    # Step 6: Commit all changes atomically
    # If anything fails above, the exception propagates and nothing
    # is committed — the DB stays in its prior clean state.
    # ------------------------------------------------------------------
    await db.commit()
    logger.info(
        "Sync complete — added: %d, updated: %d, deleted: %d, skipped: %d",
        stats.added, stats.updated, stats.deleted, stats.skipped,
    )

    return stats


async def record_sync_history(
    db: AsyncSession,
    source_url: str,
    version: str,
    stats: SyncStats,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """
    Write one row to sync_history.
    Called after every sync attempt — success or failure.
    """
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
