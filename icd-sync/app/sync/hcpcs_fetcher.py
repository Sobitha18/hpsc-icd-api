"""
sync/hcpcs_fetcher.py
---------------------
Downloads the latest HCPCS Alpha-Numeric ZIP from CMS and parses
the ANWEB Excel file inside it into separate lists of modifiers and codes.

Flow:
  1. GET CMS quarterly update page → scrape latest Alpha-Numeric ZIP URL
     (picks the one with the most recent "Updated MM/DD/YYYY" date)
  2. Download the ZIP into memory (no temp files on disk)
  3. Open ZIP → find the Excel file that has a SEQNUM column (= ANWEB file)
  4. Parse every row → separate modifiers (len==2) from codes (len>2)
  5. Return (modifiers, codes, cycle, zip_filename)

All network I/O is async (httpx). Pandas read_excel is sync — it runs
in a thread pool via run_in_executor so the event loop is never blocked.
"""

import asyncio
import io
import logging
import re
import zipfile
from datetime import date, datetime
from functools import partial
from typing import Dict, List, Optional, Tuple

import httpx
import pandas as pd
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CMS page URL — scraping starts here
# ---------------------------------------------------------------------------
CMS_HCPCS_QUARTERLY_URL = (
    "https://www.cms.gov/medicare/coding-billing/"
    "healthcare-common-procedure-system/quarterly-update"
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# ---------------------------------------------------------------------------
# Pure helper functions (sync — called inside thread pool or at import time)
# ---------------------------------------------------------------------------

def _parse_date(val) -> Optional[date]:
    """Convert CMS date int/float like 20260401 → Python date."""
    if val is None:
        return None
    try:
        import math
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return datetime.strptime(str(int(val)), "%Y%m%d").date()
    except Exception:
        return None


def _clean_str(val) -> Optional[str]:
    if val is None:
        return None
    try:
        import math
        if isinstance(val, float) and math.isnan(val):
            return None
    except Exception:
        pass
    s = str(val).strip()
    return s if s else None


def _clean_num(val) -> Optional[float]:
    if val is None:
        return None
    try:
        import math
        if isinstance(val, float) and math.isnan(val):
            return None
        return float(val)
    except Exception:
        return None


def _row_to_dict(row: "pd.Series") -> dict:
    """Map one ANWEB Excel row to our simplified DB column names."""
    return {
        "hcpc":              _clean_str(row.get("HCPC")),
        "seqnum":            int(row["SEQNUM"])   if pd.notna(row.get("SEQNUM"))  else None,
        "recid":             int(row["RECID"])    if pd.notna(row.get("RECID"))   else None,
        "long_description":  _clean_str(row.get("LONG DESCRIPTION")),
        "add_dt":            _parse_date(row.get("ADD DT")),
        "act_eff_dt":        _parse_date(row.get("ACT EFF DT")),
        "term_dt":           _parse_date(row.get("TERM DT")),
    }


def derive_cycle(filename: str) -> str:
    """
    Extract an update-cycle label from a filename.
      HCPC2026_APR_ANWEB.xlsx → APR2026
      april-2026-alpha-numeric-hcpcs-file.zip → APR2026
    Falls back to the first 30 chars of the filename.
    """
    m = re.search(r"HCPC(\d{4})_([A-Z]+)", filename, re.IGNORECASE)
    if m:
        return f"{m.group(2).upper()}{m.group(1)}"
    m2 = re.search(r"(\w+)-(\d{4})", filename, re.IGNORECASE)
    if m2:
        return f"{m2.group(1).upper()[:3]}{m2.group(2)}"
    return filename[:30]


def _scrape_latest_zip_url(html: str) -> Tuple[str, str]:
    """
    Parse CMS HTML and return (zip_url, zip_filename) for the most recently
    updated Alpha-Numeric HCPCS ZIP.
    """
    soup = BeautifulSoup(html, "lxml")
    candidates: List[Tuple] = []

    for link in soup.find_all("a", href=True):
        href: str = link["href"]
        text: str = link.get_text(strip=True)

        if not href.lower().endswith(".zip"):
            continue

        combined = (text + " " + href).lower()
        if not any(kw in combined for kw in ("alpha", "anweb", "alpha-numeric")):
            continue

        # Try to extract "Updated MM/DD/YYYY" from the link's parent element
        search_text = link.parent.get_text(" ", strip=True) if link.parent else text
        updated_date: Optional[datetime] = None
        m = re.search(
            r"updated\s+(\d{1,2}/\d{1,2}/\d{4})", search_text, re.IGNORECASE
        )
        if m:
            try:
                updated_date = datetime.strptime(m.group(1), "%m/%d/%Y")
            except ValueError:
                pass

        full_url = href if href.startswith("http") else f"https://www.cms.gov{href}"
        filename = full_url.split("/")[-1].split("?")[0]
        candidates.append((updated_date, full_url, filename))
        log.debug("HCPCS ZIP candidate: %s  updated=%s", filename, updated_date)

    if not candidates:
        raise RuntimeError(
            "No Alpha-Numeric HCPCS ZIP found on CMS quarterly update page. "
            f"Page layout may have changed. Check: {CMS_HCPCS_QUARTERLY_URL}"
        )

    # Most recently updated first
    candidates.sort(key=lambda x: x[0] or datetime.min, reverse=True)
    _, zip_url, zip_filename = candidates[0]
    log.info("Selected HCPCS ZIP: %s", zip_filename)
    return zip_url, zip_filename


def _parse_zip_to_records(zip_bytes: bytes) -> Tuple[List[dict], List[dict], str]:
    """
    Blocking function — runs in thread pool.
    Opens ZIP in memory, finds the ANWEB Excel (has SEQNUM column),
    parses every row, separates modifiers (len==2) from codes (len>2).
    Returns (modifiers, codes, excel_filename).
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        excel_files = [
            n for n in zf.namelist()
            if n.lower().endswith((".xlsx", ".xls")) and not n.startswith("__MACOSX")
        ]

        for name in excel_files:
            with zf.open(name) as f:
                try:
                    df = pd.read_excel(io.BytesIO(f.read()))
                except Exception as exc:
                    log.warning("Could not read %s: %s", name, exc)
                    continue

            df.columns = [str(c).strip().upper() for c in df.columns]

            if "SEQNUM" not in df.columns:
                continue

            # Normalise HCPCS → HCPC column name variation
            if "HCPCS" in df.columns and "HCPC" not in df.columns:
                df.rename(columns={"HCPCS": "HCPC"}, inplace=True)

            log.info("ANWEB file identified: %s (%d rows)", name, len(df))

            modifiers = []
            codes = []
            for _, row in df.iterrows():
                rec = _row_to_dict(row)
                if rec.get("hcpc"):          # skip rows with no code
                    hcpc = rec["hcpc"]
                    if len(hcpc) == 2:
                        modifiers.append(rec)
                        log.debug("Modifier: %s", hcpc)
                    elif len(hcpc) > 2:
                        codes.append(rec)
                        log.debug("Code: %s", hcpc)

            log.info("Separated into modifiers=%d, codes=%d", len(modifiers), len(codes))
            return modifiers, codes, name

    raise RuntimeError(
        f"No ANWEB Excel (SEQNUM column) found in ZIP. Files present: {excel_files}"
    )


# ---------------------------------------------------------------------------
# Public async entry point
# ---------------------------------------------------------------------------

async def fetch_hcpcs_codes(
    url: Optional[str] = None,
) -> Tuple[List[dict], List[dict], str, str]:
    """
    Download the latest HCPCS Alpha-Numeric file from CMS and parse it.

    Args:
      url: Optional direct ZIP URL. If None the CMS quarterly page is
           scraped to find the most recently updated file.

    Returns:
      (modifiers, codes, cycle, zip_filename)
        modifiers    — list of 2-char modifier dicts ready for the processor
        codes        — list of procedure code dicts ready for the processor
        cycle        — e.g. "APR2026"
        zip_filename — e.g. "april-2026-alpha-numeric-hcpcs-file.zip"

    Raises:
      httpx.HTTPStatusError  if any HTTP request fails
      RuntimeError           if no matching ZIP or Excel is found
    """
    async with httpx.AsyncClient(
        timeout=120.0,
        headers=_HEADERS,
        follow_redirects=True,
    ) as client:

        if url is None:
            log.info("Scraping CMS HCPCS quarterly page for latest ZIP URL")
            resp = await client.get(CMS_HCPCS_QUARTERLY_URL)
            resp.raise_for_status()
            zip_url, zip_filename = _scrape_latest_zip_url(resp.text)
        else:
            zip_url = url
            zip_filename = url.split("/")[-1].split("?")[0]

        log.info("Downloading HCPCS ZIP: %s", zip_url)
        resp = await client.get(zip_url)
        resp.raise_for_status()
        zip_bytes = resp.content
        log.info("Downloaded %.2f MB", len(zip_bytes) / 1_048_576)

    # pandas.read_excel is blocking — offload to thread pool
    loop = asyncio.get_event_loop()
    modifiers, codes, excel_filename = await loop.run_in_executor(
        None, partial(_parse_zip_to_records, zip_bytes)
    )

    cycle = derive_cycle(zip_filename)
    log.info(
        "Parsed %d HCPCS records (modifiers=%d, codes=%d) | cycle=%s | source=%s",
        len(modifiers) + len(codes), len(modifiers), len(codes), cycle, excel_filename,
    )
    return modifiers, codes, cycle, zip_filename
