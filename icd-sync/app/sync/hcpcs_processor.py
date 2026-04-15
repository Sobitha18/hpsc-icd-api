"""
sync/hcpcs_processor.py
-----------------------
Applies the diff between freshly parsed HCPCS records and the current
DB state using hash-based change detection.

Logic:
  code not in DB              → INSERT  (with data_hash, is_active=True)
  code in DB, hash matches    → SKIP
  code in DB, hash differs    → UPDATE  (all fields + new hash)
  code in DB, not in new file → SOFT-DELETE (set is_active=False, term_dt=today)

All changes are committed in a single atomic transaction.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HcpcsCode, HcpcsSyncLog
from app.sync.utils import hash_row

log = logging.getLogger(__name__)


@dataclass
class HcpcsSyncStats:
    """Counts of what changed during one HCPCS sync run."""
    inserted: int = 0
    updated:  int = 0
    deleted:  int = 0
    skipped:  int = 0


async def sync_hcpcs_codes(
    db: AsyncSession,
    records: List[dict],
    cycle: str,
    source_url: str,
) -> HcpcsSyncStats:
    """
    Diff `records` (from CMS) against the current DB and apply changes.

    Steps:
      1. Load all existing HcpcsCode rows keyed by hcpc
      2. For each incoming record compute hash and compare
         - Missing  → INSERT with is_active=True
         - Mismatch → UPDATE all fields + new hash
         - Match    → SKIP
      3. SOFT-DELETE any code in DB absent from new file (is_active=False, term_dt=today)
      4. Single atomic commit

    Returns HcpcsSyncStats with counts of each operation.
    """
    stats = HcpcsSyncStats()

    # ------------------------------------------------------------------
    # 1. Load existing ACTIVE rows
    # ------------------------------------------------------------------
    result = await db.execute(select(HcpcsCode).where(HcpcsCode.is_active == True))
    existing: Dict[str, HcpcsCode] = {
        row.hcpc: row for row in result.scalars().all()
    }
    log.info("Loaded %d existing ACTIVE HCPCS codes from DB", len(existing))

    # ------------------------------------------------------------------
    # 2. Build lookup from new records
    # ------------------------------------------------------------------
    new_records: Dict[str, dict] = {r["hcpc"]: r for r in records}
    log.info("Received %d HCPCS records from CMS", len(new_records))

    # ------------------------------------------------------------------
    # 3. INSERT / UPDATE (with versioning) / SKIP
    # ------------------------------------------------------------------
    to_insert: List[HcpcsCode] = []

    for hcpc, rec in new_records.items():
        new_hash = hash_row(rec)

        if hcpc not in existing:
            to_insert.append(HcpcsCode(**rec, data_hash=new_hash, is_active=True))
            stats.inserted += 1

        else:
            row = existing[hcpc]
            if row.data_hash is not None and row.data_hash == new_hash:
                stats.skipped += 1
            else:
                # Changed — mark old version as inactive and insert new version
                row.is_active = False  # deactivate old version

                # Insert new version with new data, is_active=True
                new_version = HcpcsCode(
                    **rec,
                    data_hash=new_hash,
                    is_active=True,
                )
                to_insert.append(new_version)
                stats.updated += 1
                log.debug(
                    "Code %s changed — deactivated old version, inserted new version",
                    hcpc,
                )

    if to_insert:
        db.add_all(to_insert)
        log.info("Queued %d HCPCS new code versions", len(to_insert))

    # ------------------------------------------------------------------
    # 4. SOFT-DELETE retired codes (mark inactive + set term_dt)
    # ------------------------------------------------------------------
    retired = [hcpc for hcpc in existing if hcpc not in new_records]
    if retired:
        today = date.today()
        for hcpc in retired:
            row = existing[hcpc]
            row.is_active = False
            row.term_dt = today
            stats.deleted += 1
        log.info("Queued %d HCPCS soft-deletes (marked inactive)", stats.deleted)

    # ------------------------------------------------------------------
    # 5. Atomic commit
    # ------------------------------------------------------------------
    await db.commit()
    log.info(
        "HCPCS sync complete — inserted=%d updated=%d deleted=%d skipped=%d",
        stats.inserted, stats.updated, stats.deleted, stats.skipped,
    )
    return stats


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
    """
    Write one row to hcpcs_sync_log.
    Called after every sync attempt — success or failure.
    """
    entry = HcpcsSyncLog(
        source_url=source_url,
        zip_filename=zip_filename,
        update_cycle=update_cycle,
        total_codes=total_codes,
        inserted=stats.inserted,
        updated=stats.updated,
        deleted=stats.deleted,
        skipped=stats.skipped,
        status=status,
        error_message=error_message,
    )
    db.add(entry)
    await db.commit()
