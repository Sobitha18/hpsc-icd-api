"""
processor.py
------------
Compares freshly parsed CMS records against the current DB state
and applies the minimum set of changes needed to bring the DB in sync.

Logic (3-way diff):
  new_codes  = codes in CMS file  but NOT in DB  → INSERT
  updated    = codes in both,     but desc changed → UPDATE
  deleted    = codes in DB        but NOT in CMS file → DELETE

Why "minimum set of changes"?
  ICD-10-CM has ~75,000 codes. Each year only a few hundred actually change.
  Doing a full wipe + re-insert every year is wasteful and loses created_at
  audit dates. The diff approach touches only what actually changed.

Returns a SyncStats object that the router uses to build the response.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IcdCode, SyncHistory

logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    """Counts of what changed during a sync run."""
    added:   int = 0
    updated: int = 0
    deleted: int = 0
    version: str = ""


async def sync_icd_codes(
    db: AsyncSession,
    records: list[dict],
    version: str,
    source_url: str,
) -> SyncStats:
    """
    Apply the diff between `records` (from CMS) and the current DB.

    Steps:
      1. Load all existing codes from DB into memory (just code + description)
      2. Build a lookup dict from the new CMS records
      3. INSERT codes that are new
      4. UPDATE codes whose description changed
      5. DELETE codes that no longer exist in the CMS file
      6. Write a SyncHistory row regardless of success/failure

    Args:
      db         : async DB session
      records    : list of dicts from fetcher.parse_order_file()
      version    : fiscal year string, e.g. "2025"
      source_url : the CMS URL we downloaded from (stored in history)

    Returns:
      SyncStats with counts of what changed
    """
    stats = SyncStats(version=version)

    # ------------------------------------------------------------------
    # Step 1: Load existing DB codes into a dict  { code: IcdCode row }
    # We only need code + description to detect changes — no need to
    # load all fields.
    # ------------------------------------------------------------------
    result = await db.execute(select(IcdCode))
    existing_rows: dict[str, IcdCode] = {
        row.code: row for row in result.scalars().all()
    }
    logger.info("Loaded %d existing codes from DB", len(existing_rows))

    # ------------------------------------------------------------------
    # Step 2: Build a lookup dict from the new CMS records
    # { code: record_dict }
    # ------------------------------------------------------------------
    new_records: dict[str, dict] = {r["code"]: r for r in records}
    logger.info("Parsed %d codes from CMS file", len(new_records))

    # ------------------------------------------------------------------
    # Step 3 + 4: INSERT new codes / UPDATE changed codes
    # ------------------------------------------------------------------
    to_insert: list[IcdCode] = []

    for code, rec in new_records.items():
        if code not in existing_rows:
            # Brand new code — add it
            to_insert.append(IcdCode(**rec))
            stats.added += 1
        else:
            existing = existing_rows[code]
            # Compare every field that CMS can change.
            # We skip: id, code (it's the key), created_at, updated_at
            changed = (
                existing.code_with_dot  != rec["code_with_dot"]
                or existing.description != rec["description"]
                or existing.category    != rec["category"]
                or existing.chapter     != rec["chapter"]
                or existing.is_billable != rec["is_billable"]
                or existing.version     != rec["version"]
                or existing.effective_date != rec["effective_date"]
            )
            if changed:
                existing.code_with_dot  = rec["code_with_dot"]
                existing.description    = rec["description"]
                existing.category       = rec["category"]
                existing.chapter        = rec["chapter"]
                existing.is_billable    = rec["is_billable"]
                existing.version        = rec["version"]
                existing.effective_date = rec["effective_date"]
                stats.updated += 1

    if to_insert:
        db.add_all(to_insert)
        logger.info("Inserting %d new codes", len(to_insert))

    # ------------------------------------------------------------------
    # Step 5: DELETE retired codes
    # Any code in the DB that is NOT in the new CMS file is retired.
    # ------------------------------------------------------------------
    retired_codes = [code for code in existing_rows if code not in new_records]

    if retired_codes:
        await db.execute(
            delete(IcdCode).where(IcdCode.code.in_(retired_codes))
        )
        stats.deleted = len(retired_codes)
        logger.info("Deleting %d retired codes", stats.deleted)

    # ------------------------------------------------------------------
    # Step 6: Commit all changes atomically
    # If anything fails above, the exception propagates and nothing
    # is committed — the DB stays in its prior clean state.
    # ------------------------------------------------------------------
    await db.commit()
    logger.info(
        "Sync complete — added: %d, updated: %d, deleted: %d",
        stats.added, stats.updated, stats.deleted,
    )

    return stats


async def record_sync_history(
    db: AsyncSession,
    source_url: str,
    version: str,
    stats: SyncStats,
    status: str,
    error_message: str | None = None,
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
        status=status,
        error_message=error_message,
    )
    db.add(history)
    await db.commit()
