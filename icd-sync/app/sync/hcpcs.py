import asyncio
import io
import logging
import math
import re
import zipfile
from datetime import date, datetime
from functools import partial
from typing import List, Optional, Tuple

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HcpcsCode, HcpcsSyncLog, HcpcsModifier, HcpcsModifierSyncLog
from app.schemas import HcpcsSyncResult
from app.sync.generic_processor import SyncStats, sync_generic

log = logging.getLogger(__name__)

_CMS_QUARTERLY_URL = (
    "https://www.cms.gov/medicare/coding-billing/"
    "healthcare-common-procedure-system/quarterly-update"
)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class HcpcsSyncer:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync(self, url: Optional[str] = None) -> HcpcsSyncResult:
        mod_stats, code_stats = SyncStats(), SyncStats()
        status, err, cycle, zip_filename = "failed", None, "unknown", "unknown"

        try:
            modifiers, codes, cycle, zip_filename, term_date = await self._fetch(url)
            if modifiers:
                mod_stats = await sync_generic(self.db, modifiers, HcpcsModifier, "code", term_date)
                await self._audit(HcpcsModifierSyncLog, url, zip_filename, cycle, len(modifiers), mod_stats, "success", None)
            if codes:
                code_stats = await sync_generic(self.db, codes, HcpcsCode, "code", term_date)
                await self._audit(HcpcsSyncLog, url, zip_filename, cycle, len(codes), code_stats, "success", None)
            status = "success"
        except Exception as exc:
            err = str(exc)
            log.exception("HCPCS sync failed: %s", err)
            await self._audit(HcpcsModifierSyncLog, url, zip_filename, cycle, 0, mod_stats, status, err)
            await self._audit(HcpcsSyncLog, url, zip_filename, cycle, 0, code_stats, status, err)

        msg = f"HCPCS sync completed. Cycle {cycle} loaded." if status == "success" else f"Sync failed: {err}"
        return HcpcsSyncResult(
            status=status, update_cycle=cycle, zip_filename=zip_filename,
            modifiers_inserted=mod_stats.added, modifiers_updated=mod_stats.updated,
            modifiers_deleted=mod_stats.deleted, modifiers_skipped=mod_stats.skipped,
            codes_inserted=code_stats.added, codes_updated=code_stats.updated,
            codes_deleted=code_stats.deleted, codes_skipped=code_stats.skipped,
            message=msg,
        )

    async def _fetch(self, url: Optional[str]) -> Tuple[List[dict], List[dict], str, str, Optional[date]]:
        async with httpx.AsyncClient(timeout=120.0, headers=_HEADERS, follow_redirects=True) as client:
            updated_date = None
            if url is None:
                resp = await client.get(_CMS_QUARTERLY_URL)
                resp.raise_for_status()
                zip_url, zip_filename, updated_date = self._scrape_latest_zip_url(resp.text)
            else:
                zip_url, zip_filename = url, url.split("/")[-1].split("?")[0]
            resp = await client.get(zip_url)
            resp.raise_for_status()
            zip_bytes = resp.content

        modifiers, codes, _ = await asyncio.get_event_loop().run_in_executor(
            None, partial(self._parse_zip_to_records, zip_bytes)
        )
        return modifiers, codes, self._derive_cycle(zip_filename), zip_filename, updated_date

    async def _audit(self, log_model, source_url, zip_filename, cycle, total, stats, status, error) -> None:
        self.db.add(log_model(
            source_url=source_url or _CMS_QUARTERLY_URL,
            zip_filename=zip_filename, update_cycle=cycle, total_codes=total,
            inserted=stats.added, updated=stats.updated,
            deleted=stats.deleted, skipped=stats.skipped,
            status=status, error_message=error,
        ))
        await self.db.commit()

    @staticmethod
    def _scrape_latest_zip_url(html: str) -> Tuple[str, str, Optional[date]]:
        soup = BeautifulSoup(html, "lxml")
        candidates = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if not href.lower().endswith(".zip"):
                continue
            if not any(kw in (link.get_text(strip=True) + href).lower() for kw in ("alpha", "anweb", "alpha-numeric")):
                continue
            updated_date = None
            m = re.search(r"updated\s+(\d{1,2}/\d{1,2}/\d{4})", link.parent.get_text(" ", strip=True) if link.parent else "", re.IGNORECASE)
            if m:
                try:
                    updated_date = datetime.strptime(m.group(1), "%m/%d/%Y").date()
                except ValueError:
                    pass
            full_url = href if href.startswith("http") else f"https://www.cms.gov{href}"
            candidates.append((updated_date, full_url, full_url.split("/")[-1].split("?")[0]))

        if not candidates:
            raise RuntimeError(f"No Alpha-Numeric HCPCS ZIP found on CMS page. Check: {_CMS_QUARTERLY_URL}")

        candidates.sort(key=lambda x: x[0] or date.min, reverse=True)
        updated_date, zip_url, zip_filename = candidates[0]
        return zip_url, zip_filename, updated_date

    @staticmethod
    def _parse_zip_to_records(zip_bytes: bytes) -> Tuple[List[dict], List[dict], str]:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in [n for n in zf.namelist() if n.lower().endswith((".xlsx", ".xls")) and not n.startswith("__MACOSX")]:
                with zf.open(name) as f:
                    try:
                        df = pd.read_excel(io.BytesIO(f.read()))
                    except Exception:
                        continue
                df.columns = [str(c).strip().upper() for c in df.columns]
                if "SEQNUM" not in df.columns:
                    continue
                if "HCPCS" in df.columns and "HCPC" not in df.columns:
                    df.rename(columns={"HCPCS": "HCPC"}, inplace=True)
                modifiers, codes = [], []
                for _, row in df.iterrows():
                    rec = HcpcsSyncer._row_to_dict(row)
                    if rec.get("code"):
                        (modifiers if len(rec["code"]) == 2 else codes).append(rec)
                return modifiers, codes, name
        raise RuntimeError("No ANWEB Excel (SEQNUM column) found in ZIP.")

    @staticmethod
    def _row_to_dict(row) -> dict:
        return {
            "code":        HcpcsSyncer._clean(row.get("HCPC")),
            "description": HcpcsSyncer._clean(row.get("LONG DESCRIPTION")),
            "category":    "HCPCS",
            "eff_date":    HcpcsSyncer._parse_date(row.get("ACT EFF DT")),
            "term_dt":     HcpcsSyncer._parse_date(row.get("TERM DT")),
        }

    @staticmethod
    def _parse_date(val) -> Optional[date]:
        if val is None:
            return None
        try:
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                return None
            return datetime.strptime(str(int(val)), "%Y%m%d").date()
        except Exception:
            return None

    @staticmethod
    def _clean(val) -> Optional[str]:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
        s = str(val).strip()
        return s if s else None

    @staticmethod
    def _derive_cycle(filename: str) -> str:
        m = re.search(r"HCPC(\d{4})_([A-Z]+)", filename, re.IGNORECASE)
        if m:
            return f"{m.group(2).upper()}{m.group(1)}"
        m2 = re.search(r"(\w+)-(\d{4})", filename, re.IGNORECASE)
        if m2:
            return f"{m2.group(1).upper()[:3]}{m2.group(2)}"
        return filename[:30]
