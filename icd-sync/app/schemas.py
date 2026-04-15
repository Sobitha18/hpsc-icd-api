"""
schemas.py
----------
Pydantic response models — the API's input/output contract.

ICD-10-CM:
  IcdCodeBase       — light list view
  IcdCodeDetail     — full single-code view
  SyncResult        — POST /sync/icd response
  SyncHistoryItem   — GET /sync/history row

HCPCS:
  HcpcsCodeBase     — light list view
  HcpcsCodeDetail   — full single-code view
  HcpcsSyncResult   — POST /sync/hcpcs response
  HcpcsSyncLogItem  — GET /sync/hcpcs/history row

Shared:
  PaginatedIcdCodes / PaginatedHcpcsCodes — paginated list wrappers
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# ICD-10-CM schemas
# ---------------------------------------------------------------------------

class IcdCodeBase(BaseModel):
    code:          str  = Field(example="A001")
    code_with_dot: str  = Field(example="A00.1")
    description:   str  = Field(example="Cholera due to Vibrio cholerae 01, biovar eltor")
    category:      str  = Field(example="A00")
    is_billable:   bool = Field(example=True)

    class Config:
        from_attributes = True


class IcdCodeDetail(IcdCodeBase):
    chapter:        Optional[str]  = Field(None, example="Certain infectious and parasitic diseases")
    version:        str            = Field(example="2025")
    effective_date: Optional[date] = Field(None, example="2024-10-01")
    created_at:     datetime
    updated_at:     datetime

    class Config:
        from_attributes = True


class PaginatedIcdCodes(BaseModel):
    total:   int              = Field(example=97584)
    page:    int              = Field(example=1)
    size:    int              = Field(example=50)
    results: List[IcdCodeBase]


class SyncResult(BaseModel):
    status:        str           = Field(example="success")
    version:       Optional[str] = Field(None, example="2025")
    codes_added:   int           = Field(example=120)
    codes_updated: int           = Field(example=340)
    codes_deleted: int           = Field(example=15)
    codes_skipped: int           = Field(example=97000)
    message:       str           = Field(example="Sync completed successfully")


class SyncHistoryItem(BaseModel):
    id:            int
    synced_at:     datetime
    source_url:    str
    version:       Optional[str]
    codes_added:   int
    codes_updated: int
    codes_deleted: int
    codes_skipped: int
    status:        str
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# HCPCS schemas
# ---------------------------------------------------------------------------

class HcpcsCodeBase(BaseModel):
    """Light view returned in paginated list responses."""
    hcpc:              str            = Field(example="J1100")
    short_description: Optional[str]  = Field(None, example="Inj dexamethasone sodium phos")
    long_description:  Optional[str]  = Field(None, example="Injection, dexamethasone sodium phosphate, 1 mg")
    betos:             Optional[str]  = Field(None, example="O1A")
    cov:               Optional[str]  = Field(None, example="C")
    action_cd:         Optional[str]  = Field(None, example="N")
    add_dt:            Optional[date] = Field(None, example="1985-04-01")
    term_dt:           Optional[date] = Field(None, example=None)

    class Config:
        from_attributes = True


class HcpcsCodeDetail(HcpcsCodeBase):
    """Full view returned for single-code lookups."""
    seqnum:    Optional[int]     = None
    recid:     Optional[int]     = None

    price1:    Optional[Decimal] = None
    price2:    Optional[Decimal] = None
    price3:    Optional[Decimal] = None
    price4:    Optional[Decimal] = None

    mult_pi:   Optional[str]     = None
    cim1:      Optional[str]     = None
    cim2:      Optional[str]     = None
    cim3:      Optional[str]     = None
    mcm1:      Optional[str]     = None
    mcm2:      Optional[str]     = None
    mcm3:      Optional[str]     = None
    statute:   Optional[str]     = None

    labcert1:  Optional[Decimal] = None
    labcert2:  Optional[Decimal] = None
    labcert3:  Optional[Decimal] = None
    labcert4:  Optional[Decimal] = None
    labcert5:  Optional[Decimal] = None
    labcert6:  Optional[Decimal] = None
    labcert7:  Optional[Decimal] = None
    labcert8:  Optional[Decimal] = None

    xref1:     Optional[str]     = None
    xref2:     Optional[str]     = None
    xref3:     Optional[str]     = None
    xref4:     Optional[str]     = None
    xref5:     Optional[str]     = None

    asc_grp:   Optional[str]     = None
    asc_dt:    Optional[date]    = None
    opps:      Optional[Decimal] = None
    opps_pi:   Optional[str]     = None
    opps_dt:   Optional[date]    = None
    procnote:  Optional[str]     = None

    tos1:      Optional[str]     = None
    tos2:      Optional[str]     = None
    tos3:      Optional[str]     = None
    tos4:      Optional[str]     = None
    tos5:      Optional[str]     = None

    anest_bu:  Optional[Decimal] = None
    act_eff_dt: Optional[date]   = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaginatedHcpcsCodes(BaseModel):
    total:   int               = Field(example=7000)
    page:    int               = Field(example=1)
    size:    int               = Field(example=50)
    results: List[HcpcsCodeBase]


class HcpcsSyncResult(BaseModel):
    status:         str           = Field(example="success")
    update_cycle:   Optional[str] = Field(None, example="APR2026")
    zip_filename:   Optional[str] = Field(None, example="april-2026-alpha-numeric-hcpcs-file.zip")
    codes_inserted: int           = Field(example=50)
    codes_updated:  int           = Field(example=120)
    codes_deleted:  int           = Field(example=10)
    codes_skipped:  int           = Field(example=6800)
    message:        str           = Field(example="HCPCS sync completed successfully")


class HcpcsSyncLogItem(BaseModel):
    id:            int
    synced_at:     datetime
    source_url:    Optional[str]
    zip_filename:  Optional[str]
    update_cycle:  Optional[str]
    total_codes:   Optional[int]
    inserted:      int
    updated:       int
    deleted:       int
    skipped:       int
    status:        str
    error_message: Optional[str] = None

    class Config:
        from_attributes = True
