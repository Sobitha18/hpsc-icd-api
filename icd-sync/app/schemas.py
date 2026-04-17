"""
schemas.py
----------
Pydantic response models for sync endpoints.

SyncResult         — POST /sync/codes?code_type=icd response
HcpcsSyncResult    — POST /sync/codes?code_type=hcpcs response
IcdPcsSyncResult   — POST /sync/codes?code_type=icd_pcs response
"""

from typing import Optional

from pydantic import BaseModel, Field


class SyncResult(BaseModel):
    status:        str           = Field(example="success")
    version:       Optional[str] = Field(None, example="2025")
    codes_added:   int           = Field(example=120)
    codes_updated: int           = Field(example=340)
    codes_deleted: int           = Field(example=15)
    codes_skipped: int           = Field(example=97000)
    message:       str           = Field(example="Sync completed successfully")


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


class IcdPcsSyncResult(BaseModel):
    status:        str           = Field(example="success")
    version:       Optional[str] = Field(None, example="2026")
    codes_added:   int           = Field(example=200)
    codes_updated: int           = Field(example=400)
    codes_deleted: int           = Field(example=20)
    codes_skipped: int           = Field(example=77000)
    message:       str           = Field(example="ICD-10-PCS sync completed successfully")


