import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.sync.utils import hash_row

log = logging.getLogger(__name__)


@dataclass
class SyncStats:
    added:   int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0


async def sync_generic(db: AsyncSession, records: List[dict], model: Type, code_field: str) -> SyncStats:
    stats = SyncStats()

    existing: Dict[str, Any] = {
        getattr(row, code_field): row
        for row in (await db.execute(select(model).where(model.is_active == True))).scalars().all()
    }
    incoming: Dict[str, dict] = {r[code_field]: r for r in records}

    to_insert = []
    for code_val, rec in incoming.items():
        new_hash = hash_row(rec)
        if code_val not in existing:
            to_insert.append(model(**rec, data_hash=new_hash, is_active=True))
            stats.added += 1
        elif existing[code_val].data_hash != new_hash:
            existing[code_val].is_active = False
            to_insert.append(model(**rec, data_hash=new_hash, is_active=True))
            stats.updated += 1
        else:
            stats.skipped += 1

    if to_insert:
        db.add_all(to_insert)

    today = date.today()
    for code_val in existing:
        if code_val not in incoming:
            existing[code_val].is_active = False
            existing[code_val].term_dt = today
            stats.deleted += 1

    await db.commit()
    log.info("%s — added:%d updated:%d deleted:%d skipped:%d", model.__name__, stats.added, stats.updated, stats.deleted, stats.skipped)
    return stats
