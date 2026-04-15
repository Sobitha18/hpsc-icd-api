"""
fetcher.py
----------
Downloads the CMS ICD-10-CM order file ZIP and parses it into a list
of dicts ready for the processor to compare against the database.

Flow:
  1. HTTP GET  → download ZIP into memory (no temp files)
  2. Unzip     → find the *_order_*.txt file inside
  3. Parse     → each fixed-width line → Python dict
  4. Return    → list of dicts + version string

CMS order file format (fixed-width, not CSV):
  chars  1– 5  : order number          (ignored)
  char   6     : space
  chars  7–13  : ICD code              ← WE USE THIS
  char  14     : space
  char  15     : 0=header, 1=billable  ← WE USE THIS
  char  16     : space
  chars 17–77  : short description     ← WE USE THIS
  chars 78+    : long description      (ignored — short desc is enough)

Example line:
  00004 A001  1 Cholera due to Vibrio cholerae 01, biovar eltor
"""

import io
import re
import zipfile
from datetime import date
from typing import Dict, List, Optional, Tuple

import httpx

# ---------------------------------------------------------------------------
# ICD-10-CM chapter map
# Maps a code's first character(s) to its chapter name.
# ICD-10 has 21 chapters defined by code ranges.
# ---------------------------------------------------------------------------
CHAPTER_MAP = [
    (re.compile(r"^[AB]"),          "Certain infectious and parasitic diseases"),
    (re.compile(r"^C|^D[0-4]"),     "Neoplasms"),
    (re.compile(r"^D[5-8]"),        "Diseases of the blood and blood-forming organs"),
    (re.compile(r"^E"),             "Endocrine, nutritional and metabolic diseases"),
    (re.compile(r"^F"),             "Mental, Behavioral and Neurodevelopmental disorders"),
    (re.compile(r"^G"),             "Diseases of the nervous system"),
    (re.compile(r"^H[0-5]"),        "Diseases of the eye and adnexa"),
    (re.compile(r"^H[6-9]"),        "Diseases of the ear and mastoid process"),
    (re.compile(r"^I"),             "Diseases of the circulatory system"),
    (re.compile(r"^J"),             "Diseases of the respiratory system"),
    (re.compile(r"^K"),             "Diseases of the digestive system"),
    (re.compile(r"^L"),             "Diseases of the skin and subcutaneous tissue"),
    (re.compile(r"^M"),             "Diseases of the musculoskeletal system and connective tissue"),
    (re.compile(r"^N"),             "Diseases of the genitourinary system"),
    (re.compile(r"^O"),             "Pregnancy, childbirth and the puerperium"),
    (re.compile(r"^P"),             "Certain conditions originating in the perinatal period"),
    (re.compile(r"^Q"),             "Congenital malformations, deformations and chromosomal abnormalities"),
    (re.compile(r"^R"),             "Symptoms, signs and abnormal clinical and laboratory findings"),
    (re.compile(r"^[ST]"),          "Injury, poisoning and certain other consequences of external causes"),
    (re.compile(r"^[VWX Y]"),       "External causes of morbidity"),
    (re.compile(r"^Z"),             "Factors influencing health status and contact with health services"),
]


def get_chapter(code: str) -> Optional[str]:
    """Return the chapter name for a given ICD code, or None if unknown."""
    for pattern, chapter_name in CHAPTER_MAP:
        if pattern.match(code):
            return chapter_name
    return None


def parse_version_from_filename(filename: str) -> str:
    """
    Extract the fiscal year from the CMS filename.
    e.g. "icd10cm_order_2025.txt" → "2025"
    Falls back to "unknown" if no year found.
    """
    match = re.search(r"(\d{4})", filename)
    return match.group(1) if match else "unknown"


def get_effective_date(version: str) -> Optional[date]:
    """
    CMS ICD-10-CM versions always take effect on October 1
    of the prior calendar year.
    e.g. version "2025" → effective 2024-10-01
    """
    try:
        year = int(version)
        return date(year - 1, 10, 1)
    except ValueError:
        return None


def parse_order_file(content: bytes, version: str) -> List[dict]:
    """
    Parse the raw bytes of a CMS ICD-10-CM order file.
    Returns a list of dicts — one per code line.

    Each dict has:
      code, description, category, chapter,
      is_billable, version, effective_date
    """
    records = []
    effective_date = get_effective_date(version)

    for raw_line in content.decode("utf-8", errors="replace").splitlines():
        # Lines shorter than 17 chars have no description — skip
        if len(raw_line) < 17:
            continue

        # Fixed-width column extraction
        code        = raw_line[6:13].strip()   # chars 7-13 (0-indexed: 6-13)
        billable    = raw_line[14:15].strip()  # char 15   (0-indexed: 14)
        description = raw_line[16:77].strip()  # chars 17-77 (0-indexed: 16-77)

        if not code or not description:
            continue

        records.append({
            "code":           code,
            "description":    description,
            "category":       code[:3],
            "chapter":        get_chapter(code),
            "is_billable":    billable == "1",
            "version":        version,
            "effective_date": effective_date,
        })

    return records


async def fetch_icd_codes(zip_url: str) -> Tuple[List[dict], str]:
    """
    Download the CMS ZIP, extract the order file, parse it.

    Returns:
      (records, version)
        records — list of code dicts ready for the processor
        version — fiscal year string, e.g. "2025"

    Raises:
      httpx.HTTPError       if the download fails
      ValueError            if no order file is found inside the ZIP
    """
    # Download ZIP into memory — no temp files on disk
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(zip_url, follow_redirects=True)
        response.raise_for_status()
        zip_bytes = response.content

    # Open ZIP from memory
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

        # Use the first match (there should only be one)
        order_filename = order_files[0]
        version = parse_version_from_filename(order_filename)
        content = zf.read(order_filename)

    records = parse_order_file(content, version)
    return records, version
