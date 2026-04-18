import io
import logging
import re
import zipfile
from datetime import date
from typing import Callable, List, Optional, Tuple

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import SyncResult
from app.sync.generic_processor import SyncStats, sync_generic

log = logging.getLogger(__name__)


class OrderFileSyncer:
    def __init__(self, db: AsyncSession, url_template: str, model, history_model, category_fn: Callable):
        self.db             = db
        self._url_template  = url_template
        self._model         = model
        self._history_model = history_model
        self._category_fn   = category_fn

    async def sync(self, url: Optional[str] = None) -> SyncResult:
        actual_url = url or self._url_template.format(year=date.today().year)
        stats, status, err, version = SyncStats(), "failed", None, "unknown"
        try:
            content, version = await self._download(actual_url)
            records = self._parse(content, version)
            stats = await sync_generic(self.db, records, self._model, "code")
            status = "success"
        except Exception as exc:
            err = str(exc)
            log.exception("%s sync failed: %s", self._model.__name__, err)
        finally:
            await self._audit(actual_url, version, stats, status, err)
        msg = f"Sync completed. FY{version} loaded." if status == "success" else f"Sync failed: {err}"
        return SyncResult(
            status=status, version=version,
            codes_added=stats.added, codes_updated=stats.updated,
            codes_deleted=stats.deleted, codes_skipped=stats.skipped,
            message=msg,
        )

    @staticmethod
    async def _download(url: str) -> Tuple[bytes, str]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.get(url, follow_redirects=True)
            r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            order_files = [n for n in zf.namelist() if "order" in n.lower() and n.endswith(".txt")]
            if not order_files:
                raise ValueError(f"No order .txt file in ZIP. Found: {zf.namelist()}")
            fname = order_files[0]
            m = re.search(r"(\d{4})", fname)
            return zf.read(fname), m.group(1) if m else "unknown"

    def _parse(self, content: bytes, version: str) -> List[dict]:
        eff_date = date(int(version) - 1, 10, 1) if version.isdigit() else None
        records = []
        for line in content.decode("utf-8", errors="replace").splitlines():
            if len(line) < 17:
                continue
            code = line[6:13].strip()
            desc = line[16:77].strip()
            if code and desc:
                records.append({"code": code, "description": desc, "category": self._category_fn(code), "eff_date": eff_date})
        return records

    async def _audit(self, url: str, version: str, stats: SyncStats, status: str, error: Optional[str]) -> None:
        self.db.add(self._history_model(
            source_url=url, version=version,
            codes_added=stats.added, codes_updated=stats.updated,
            codes_deleted=stats.deleted, codes_skipped=stats.skipped,
            status=status, error_message=error,
        ))
        await self.db.commit()
