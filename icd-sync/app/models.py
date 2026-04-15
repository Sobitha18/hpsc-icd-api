"""
models.py
---------
Two tables:
  icd_codes     — holds the LATEST version of all ICD-10-CM codes only.
                  Old/retired codes are deleted on each sync.
                  Only one version lives here at any time.

  sync_history  — one row per sync run (audit log of what changed).
"""

from sqlalchemy import (
    Boolean, Column, Date, DateTime,
    Integer, String, Text, func,
)
from app.database import Base


class IcdCode(Base):
    __tablename__ = "icd_codes"

    # ------------------------------------------------------------------
    # Primary key
    # ------------------------------------------------------------------
    id = Column(Integer, primary_key=True, autoincrement=True)

    # ------------------------------------------------------------------
    # Core code fields — sourced from the CMS order file
    # ------------------------------------------------------------------

    # Raw code, no dot — what goes on insurance claims
    # e.g. "A001", "Z8249"
    code = Column(String(10), unique=True, nullable=False, index=True)

    # Same code with a dot added after the 3rd character — for display
    # e.g. "A00.1", "Z82.49"
    # Derived once during sync so reads never recalculate it
    code_with_dot = Column(String(12), nullable=False)

    # Short description from the CMS file
    # e.g. "Cholera due to Vibrio cholerae 01, biovar eltor"
    description = Column(Text, nullable=False)

    # ------------------------------------------------------------------
    # Classification fields — all derived during sync
    # ------------------------------------------------------------------

    # First 3 characters — the "category"
    # e.g. "A001" → category = "A00"
    # Lets you group or filter all codes within a category
    category = Column(String(3), nullable=False, index=True)

    # One of the 21 ICD-10-CM chapter names, derived from code range
    # e.g. codes A00–B99 → "Certain infectious and parasitic diseases"
    chapter = Column(String(80), nullable=True)

    # True  = valid for HIPAA claim submission
    # False = header/grouping code, cannot go on a claim by itself
    # Source: column 15 of the CMS order file (1 = billable, 0 = not)
    is_billable = Column(Boolean, nullable=False, default=False, index=True)

    # ------------------------------------------------------------------
    # Version metadata — tells us WHICH CMS release is currently loaded.
    # Only one version lives in this table at a time.
    # e.g. "2025" means the FY2025 (Oct 1 2024) release is loaded.
    # ------------------------------------------------------------------
    version = Column(String(10), nullable=False)

    # The date this CMS version became effective — always Oct 1
    # e.g. 2024-10-01 for the FY2025 release
    effective_date = Column(Date, nullable=True)

    # ------------------------------------------------------------------
    # Audit timestamps
    # ------------------------------------------------------------------
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self):
        return f"<IcdCode {self.code_with_dot} | {self.description[:40]}>"


class SyncHistory(Base):
    """
    One row per sync run — an immutable audit log.
    Tells you: when did we sync, what version did we pull,
    how many codes changed, and did it succeed?
    """
    __tablename__ = "sync_history"

    id = Column(Integer, primary_key=True, autoincrement=True)

    synced_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    source_url = Column(Text, nullable=False)       # CMS URL we downloaded
    version    = Column(String(10), nullable=True)  # e.g. "2025"

    # What changed during this run
    codes_added   = Column(Integer, default=0, nullable=False)
    codes_updated = Column(Integer, default=0, nullable=False)
    codes_deleted = Column(Integer, default=0, nullable=False)

    status        = Column(String(20), nullable=False)   # "success" | "failed"
    error_message = Column(Text, nullable=True)          # set only on failure

    def __repr__(self):
        return (
            f"<SyncHistory {self.version} | {self.status} | "
            f"+{self.codes_added} ~{self.codes_updated} -{self.codes_deleted}>"
        )
