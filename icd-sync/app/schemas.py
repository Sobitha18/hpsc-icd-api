"""
schemas.py
----------
Pydantic response models — the API's input/output contract.

ICD-10-CM:
  IcdCodeBase       — light list view
  IcdCodeDetail     — full single-code view
  SyncResult        — POST /sync/icd response

HCPCS:
  HcpcsCodeBase     — light list view
  HcpcsCodeDetail   — full single-code view
  HcpcsSyncResult   — POST /sync/hcpcs response

ICD-10-PCS:
  IcdPcsCodeBase       — light list view
  IcdPcsCodeDetail     — full single-code view
  IcdPcsSyncResult     — POST /sync/icd_pcs response

Shared:
  PaginatedIcdCodes / PaginatedHcpcsCodes / PaginatedIcdPcsCodes — paginated list wrappers
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# ICD-10-CM schemas
# ---------------------------------------------------------------------------

class IcdCodeBase(BaseModel):
    code:        str  = Field(example="A001")
    description: str  = Field(example="Cholera due to Vibrio cholerae 01, biovar eltor")
    category:    str  = Field(example="A00")

    class Config:
        from_attributes = True


class IcdCodeDetail(IcdCodeBase):
    eff_date:   Optional[date] = Field(None, example="2024-10-01")
    created_at: datetime
    updated_at: datetime

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


class HcpcsCodeBase(BaseModel):
    """Light view returned in paginated list responses."""
    code:        str            = Field(example="J1100")
    description: Optional[str]  = Field(None, example="Injection, dexamethasone sodium phosphate, 1 mg")
    category:    Optional[str]  = Field(None, example="O")
    eff_date:    Optional[date] = Field(None, example="1985-04-01")
    term_dt:     Optional[date] = Field(None, example=None)

    class Config:
        from_attributes = True


class HcpcsCodeDetail(HcpcsCodeBase):
    """Full view returned for single-code lookups."""
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
    status:              str           = Field(example="success")
    update_cycle:        Optional[str] = Field(None, example="APR2026")
    zip_filename:        Optional[str] = Field(None, example="april-2026-alpha-numeric-hcpcs-file.zip")
    modifiers_inserted:  int           = Field(example=10)
    modifiers_updated:   int           = Field(example=2)
    modifiers_deleted:   int           = Field(example=0)
    modifiers_skipped:   int           = Field(example=90)
    codes_inserted:      int           = Field(example=50)
    codes_updated:       int           = Field(example=120)
    codes_deleted:       int           = Field(example=10)
    codes_skipped:       int           = Field(example=6800)
    message:             str           = Field(example="HCPCS sync completed successfully")


# ---------------------------------------------------------------------------
# ICD-10-PCS schemas
# ---------------------------------------------------------------------------

class IcdPcsCodeBase(BaseModel):
    code:        str           = Field(example="0016070")
    description: str           = Field(example="Bypass Cerebral Ventricle to Nasopharynx with Autologous Tissue Substitute, Open Approach")
    category:    Optional[str] = Field(None, example="0")

    class Config:
        from_attributes = True


class IcdPcsCodeDetail(IcdPcsCodeBase):
    eff_date:   Optional[date] = Field(None, example="2025-10-01")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedIcdPcsCodes(BaseModel):
    total:   int                  = Field(example=78000)
    page:    int                  = Field(example=1)
    size:    int                  = Field(example=50)
    results: List[IcdPcsCodeBase]


class IcdPcsSyncResult(BaseModel):
    status:        str           = Field(example="success")
    version:       Optional[str] = Field(None, example="2026")
    codes_added:   int           = Field(example=200)
    codes_updated: int           = Field(example=400)
    codes_deleted: int           = Field(example=20)
    codes_skipped: int           = Field(example=77000)
    message:       str           = Field(example="ICD-10-PCS sync completed successfully")


