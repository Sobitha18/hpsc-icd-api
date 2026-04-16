"""
sync/icd_pcs_fetcher.py
-----------------------
Downloads the CMS ICD-10-PCS order file ZIP and parses it into a list
of dicts ready for the processor to compare against the database.

Flow:
  1. HTTP GET  → download ZIP into memory (no temp files)
  2. Unzip     → find the *order*.txt file inside
  3. Parse     → each fixed-width line → Python dict
  4. Return    → list of dicts + version string

CMS ICD-10-PCS order file format (fixed-width, identical layout to ICD-10-CM):
  chars  1– 5  : order number          (ignored)
  char   6     : space
  chars  7–13  : PCS code (7 chars)    ← WE USE THIS
  char  14     : space
  char  15     : 0=header, 1=valid     ← WE USE THIS
  char  16     : space
  chars 17–77  : short description     ← WE USE THIS
  chars 78+    : long description      (ignored — short desc is sufficient)

Example line:
  00001 0016070 1 Bypass Cerebral Ventricle to Nasopharynx with Autologous Tissue Substitute, Open Approach

ICD-10-PCS code structure (7 characters, no dot notation):
  Char 1 — Section
  Char 2 — Body System
  Char 3 — Root Operation
  Char 4 — Body Part
  Char 5 — Approach
  Char 6 — Device
  Char 7 — Qualifier
"""

import io
import re
import zipfile
from datetime import date
from typing import Dict, List, Optional, Tuple

import httpx

# ---------------------------------------------------------------------------
# CMS default URL — FY2026 ICD-10-PCS order file (long + abbreviated titles)
# Updated annually; override via the ?url= query parameter on the sync endpoint.
# ---------------------------------------------------------------------------
CMS_ICD_PCS_URL = (
    "https://www.cms.gov/files/zip/"
    "2026-icd-10-pcs-order-file-long-and-abbreviated-titles.zip"
)

# ---------------------------------------------------------------------------
# PCS Section map — first character of the code → human-readable section name
# ---------------------------------------------------------------------------
PCS_SECTION_MAP: Dict[str, str] = {
    "0": "Medical and Surgical",
    "1": "Obstetrics",
    "2": "Placement",
    "3": "Administration",
    "4": "Measurement and Monitoring",
    "5": "Extracorporeal or Systemic Assistance and Performance",
    "6": "Extracorporeal or Systemic Therapies",
    "7": "Osteopathic",
    "8": "Other Procedures",
    "9": "Chiropractic",
    "B": "Imaging",
    "C": "Nuclear Medicine",
    "D": "Radiation Therapy",
    "F": "Physical Rehabilitation and Diagnostic Audiology",
    "G": "Mental Health",
    "H": "Substance Abuse Treatment",
    "X": "New Technology",
}


def get_section_name(code: str) -> Optional[str]:
    """Return the section name for the first character of a PCS code."""
    return PCS_SECTION_MAP.get(code[0].upper()) if code else None


def parse_version_from_filename(filename: str) -> str:
    """
    Extract the fiscal year from the CMS filename.
    e.g. "icd10pcs_order_2026.txt" → "2026"
    Falls back to "unknown" if no year found.
    """
    match = re.search(r"(\d{4})", filename)
    return match.group(1) if match else "unknown"


def get_effective_date(version: str) -> Optional[date]:
    """
    CMS ICD-10-PCS versions always take effect on October 1
    of the prior calendar year (same schedule as ICD-10-CM).
    e.g. version "2026" → effective 2025-10-01
    """
    try:
        year = int(version)
        return date(year - 1, 10, 1)
    except ValueError:
        return None


def parse_order_file(content: bytes, version: str) -> List[dict]:
    """
    Parse the raw bytes of a CMS ICD-10-PCS order file.
    Returns a list of dicts — one per code line.

    Each dict has:
      code, description, category, eff_date
    """
    records = []
    eff_date = get_effective_date(version)

    for raw_line in content.decode("utf-8", errors="replace").splitlines():
        # Lines shorter than 17 chars have no description — skip
        if len(raw_line) < 17:
            continue

        # Fixed-width column extraction (same offsets as ICD-10-CM order file)
        code        = raw_line[6:13].strip()   # chars 7-13 (0-indexed: 6-13)
        description = raw_line[16:77].strip()  # chars 17-77 (0-indexed: 16-77)

        if not code or not description:
            continue

        records.append({
            "code":        code,
            "description": description,
            "category":    code[0].upper() if code else None,
            "eff_date":    eff_date,
        })

    return records


async def fetch_icd_pcs_codes(zip_url: str = CMS_ICD_PCS_URL) -> Tuple[List[dict], str]:
    """
    Download the CMS ICD-10-PCS ZIP, extract the order file, parse it.

    Args:
      zip_url: Direct URL to the CMS ZIP file. Defaults to CMS_ICD_PCS_URL.

    Returns:
      (records, version)
        records — list of code dicts ready for the processor
        version — fiscal year string, e.g. "2026"

    Raises:
      httpx.HTTPError  if the download fails
      ValueError       if no order file is found inside the ZIP
    """
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        response = await client.get(zip_url)
        response.raise_for_status()
        zip_bytes = response.content

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # Find the order .txt file (filename contains "order")
        order_files = [
            name for name in zf.namelist()
            if "order" in name.lower() and name.endswith(".txt")
        ]

        if not order_files:
            raise ValueError(
                f"No order .txt file found inside ZIP. "
                f"Files present: {zf.namelist()}"
            )

        order_filename = order_files[0]
        version = parse_version_from_filename(order_filename)
        content = zf.read(order_filename)

    records = parse_order_file(content, version)
    return records, version
