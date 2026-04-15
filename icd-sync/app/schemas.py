"""
schemas.py
----------
Pydantic models — the API's input/output contract.

Why separate from models.py?
  - models.py defines the DATABASE shape (SQLAlchemy)
  - schemas.py defines the API shape (what JSON goes in and out)
  - They are intentionally different:
      e.g. the DB has created_at / updated_at, but the list response
      doesn't need to expose those fields to the caller.

Three response shapes:
  IcdCodeBase      — minimal fields for list views (fast, light)
  IcdCodeDetail    — full fields for single-code lookup
  SyncResult       — what the /sync/icd endpoint returns
  SyncHistoryItem  — one row from the sync_history table
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# ICD Code responses
# ---------------------------------------------------------------------------

class IcdCodeBase(BaseModel):
    """
    Returned in paginated list responses.
    Keeps the payload small — no audit timestamps.
    """
    code:         str  = Field(example="A001")
    code_with_dot: str = Field(example="A00.1")
    description:  str  = Field(example="Cholera due to Vibrio cholerae 01, biovar eltor")
    category:     str  = Field(example="A00")
    is_billable:  bool = Field(example=True)

    class Config:
        from_attributes = True   # lets Pydantic read SQLAlchemy model objects directly


class IcdCodeDetail(IcdCodeBase):
    """
    Returned when fetching a single code.
    Includes chapter, version, dates — the full picture.
    """
    chapter:        Optional[str]      = Field(None, example="Certain infectious and parasitic diseases")
    version:        str                = Field(example="2025")
    effective_date: Optional[date]     = Field(None, example="2024-10-01")
    created_at:     datetime
    updated_at:     datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Sync responses
# ---------------------------------------------------------------------------

class SyncResult(BaseModel):
    """
    Returned immediately after POST /sync/icd completes.
    Tells the caller exactly what changed.
    """
    status:        str = Field(example="success")
    version:       Optional[str] = Field(None, example="2025")
    codes_added:   int = Field(example=120)
    codes_updated: int = Field(example=340)
    codes_deleted: int = Field(example=15)
    message:       str = Field(example="Sync completed successfully")


class SyncHistoryItem(BaseModel):
    """
    One row from the sync_history table.
    Returned in GET /sync/history list.
    """
    id:            int
    synced_at:     datetime
    source_url:    str
    version:       Optional[str]
    codes_added:   int
    codes_updated: int
    codes_deleted: int
    status:        str
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Paginated list wrapper
# Used by GET /codes/icd so callers know total count + page info
# ---------------------------------------------------------------------------

class PaginatedIcdCodes(BaseModel):
    total:   int               = Field(example=75000)
    page:    int               = Field(example=1)
    size:    int               = Field(example=50)
    results: list[IcdCodeBase]
