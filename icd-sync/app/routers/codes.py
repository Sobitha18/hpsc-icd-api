"""
routers/codes.py
----------------
Read-only endpoints for querying ICD-10-CM, HCPCS, and ICD-10-PCS codes.

ICD-10-CM:
  GET /codes/icd                    paginated list with filters
  GET /codes/icd/{code}             single code lookup
  GET /codes/icd/category/{cat}     all codes in a 3-char category

HCPCS:
  GET /codes/hcpcs                  paginated list with filters
  GET /codes/hcpcs/{code}           single code lookup

ICD-10-PCS:
  GET /codes/icd_pcs                paginated list with filters
  GET /codes/icd_pcs/{code}         single code lookup
  GET /codes/icd_pcs/section/{sec}  all codes in a PCS section
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import HcpcsCode, IcdCode, IcdPcsCode
from app.schemas import (
    HcpcsCodeDetail,
    IcdCodeDetail,
    IcdPcsCodeDetail,
    PaginatedHcpcsCodes,
    PaginatedIcdCodes,
    PaginatedIcdPcsCodes,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/codes", tags=["Codes"])


# ---------------------------------------------------------------------------
# ICD-10-CM endpoints
# ---------------------------------------------------------------------------

@router.get("/icd", response_model=PaginatedIcdCodes, summary="List ICD-10-CM codes")
async def list_icd_codes(
    q:             Optional[str] = Query(None,  description="Search in description (case-insensitive)"),
    category:      Optional[str] = Query(None,  description="3-char category, e.g. A00"),
    chapter:       Optional[str] = Query(None,  description="Chapter name substring"),
    billable_only: bool          = Query(False,  description="Return only billable codes"),
    page:          int           = Query(1,  ge=1,        description="Page number (1-based)"),
    size:          int           = Query(50, ge=1, le=200, description="Results per page"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search and paginate ICD-10-CM codes.

    Examples:
      GET /codes/icd?q=cholera
      GET /codes/icd?category=A00&billable_only=true
      GET /codes/icd?chapter=respiratory&page=2&size=100
    """
    query = select(IcdCode)

    if q:
        query = query.where(IcdCode.description.ilike(f"%{q}%"))
    if category:
        query = query.where(IcdCode.category == category.upper())

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()

    offset = (page - 1) * size
    rows = (
        await db.execute(query.order_by(IcdCode.code).offset(offset).limit(size))
    ).scalars().all()

    return PaginatedIcdCodes(total=total, page=page, size=size, results=rows)


@router.get("/icd/{code}", response_model=IcdCodeDetail, summary="Get ICD-10-CM code")
async def get_icd_code(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch a single ICD-10-CM code.
    Accepts both dot and no-dot formats: "A001" or "A00.1".
    """
    raw = code.upper().replace(".", "")
    row = (
        await db.execute(select(IcdCode).where(IcdCode.code == raw))
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"ICD code '{code}' not found")
    return row


@router.get(
    "/icd/category/{category}",
    response_model=List[IcdCodeDetail],
    summary="Get all codes in an ICD-10-CM category",
)
async def get_icd_codes_by_category(
    category: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Return all codes within a 3-character ICD-10-CM category.

    Example:
      GET /codes/icd/category/A00 → returns A00, A00.0, A00.1, A00.9
    """
    rows = (
        await db.execute(
            select(IcdCode)
            .where(IcdCode.category == category.upper())
            .order_by(IcdCode.code)
        )
    ).scalars().all()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No ICD-10-CM codes found for category '{category.upper()}'",
        )
    return rows


# ---------------------------------------------------------------------------
# HCPCS endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/hcpcs",
    response_model=PaginatedHcpcsCodes,
    summary="List HCPCS codes",
)
async def list_hcpcs_codes(
    q:         Optional[str] = Query(None, description="Search in short or long description (case-insensitive)"),
    betos:     Optional[str] = Query(None, description="Filter by BETOS code (exact match)"),
    cov:       Optional[str] = Query(None, description="Filter by coverage indicator (exact match)"),
    action_cd: Optional[str] = Query(None, description="Filter by action code (exact match)"),
    page:      int = Query(1,  ge=1,        description="Page number (1-based)"),
    size:      int  = Query(50, ge=1, le=200, description="Results per page"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search and paginate HCPCS Level II codes.

    Examples:
      GET /codes/hcpcs?q=insulin
      GET /codes/hcpcs?betos=O1A
      GET /codes/hcpcs?cov=C&page=2
      GET /codes/hcpcs?action_cd=N
    """
    query = select(HcpcsCode)

    if q:
        query = query.where(
            or_(
                HcpcsCode.short_description.ilike(f"%{q}%"),
                HcpcsCode.description.ilike(f"%{q}%"),
            )
        )
    if betos:
        query = query.where(HcpcsCode.betos == betos.upper())
    if cov:
        query = query.where(HcpcsCode.cov == cov.upper())
    if action_cd:
        query = query.where(HcpcsCode.action_cd == action_cd.upper())

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()

    offset = (page - 1) * size
    rows = (
        await db.execute(query.order_by(HcpcsCode.code).offset(offset).limit(size))
    ).scalars().all()

    return PaginatedHcpcsCodes(total=total, page=page, size=size, results=rows)


@router.get(
    "/hcpcs/{code}",
    response_model=HcpcsCodeDetail,
    summary="Get HCPCS code",
)
async def get_hcpcs_code(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch a single HCPCS Level II code.

    Example:
      GET /codes/hcpcs/J1100
    """
    row = (
        await db.execute(
            select(HcpcsCode).where(HcpcsCode.code == code.upper())
        )
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"HCPCS code '{code.upper()}' not found")
    return row


# ---------------------------------------------------------------------------
# ICD-10-PCS endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/icd_pcs",
    response_model=PaginatedIcdPcsCodes,
    summary="List ICD-10-PCS codes",
)
async def list_icd_pcs_codes(
    q:          Optional[str] = Query(None,  description="Search in description (case-insensitive)"),
    section:    Optional[str] = Query(None,  description="Single-char section, e.g. '0' for Medical and Surgical"),
    valid_only: bool          = Query(False,  description="Return only valid (billable) codes"),
    page:       int           = Query(1,  ge=1,        description="Page number (1-based)"),
    size:       int           = Query(50, ge=1, le=200, description="Results per page"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search and paginate ICD-10-PCS inpatient procedure codes.

    Examples:
      GET /codes/icd_pcs?q=bypass
      GET /codes/icd_pcs?section=0&valid_only=true
      GET /codes/icd_pcs?q=cardiac&page=2&size=100
    """
    query = select(IcdPcsCode).where(IcdPcsCode.is_active.is_(True))

    if q:
        query = query.where(IcdPcsCode.description.ilike(f"%{q}%"))
    if section:
        query = query.where(IcdPcsCode.category == section.upper())

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()

    offset = (page - 1) * size
    rows = (
        await db.execute(query.order_by(IcdPcsCode.code).offset(offset).limit(size))
    ).scalars().all()

    return PaginatedIcdPcsCodes(total=total, page=page, size=size, results=rows)


@router.get(
    "/icd_pcs/section/{section}",
    response_model=List[IcdPcsCodeDetail],
    summary="Get all ICD-10-PCS codes in a section",
)
async def get_icd_pcs_codes_by_section(
    section: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Return all active codes within a single-character ICD-10-PCS section.

    Example:
      GET /codes/icd_pcs/section/0  → all Medical and Surgical codes
      GET /codes/icd_pcs/section/B  → all Imaging codes
    """
    rows = (
        await db.execute(
            select(IcdPcsCode)
            .where(IcdPcsCode.category == section.upper())
            .where(IcdPcsCode.is_active.is_(True))
            .order_by(IcdPcsCode.code)
        )
    ).scalars().all()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No ICD-10-PCS codes found for section '{section.upper()}'",
        )
    return rows


@router.get(
    "/icd_pcs/{code}",
    response_model=IcdPcsCodeDetail,
    summary="Get ICD-10-PCS code",
)
async def get_icd_pcs_code(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch a single active ICD-10-PCS code (7 characters, no dots).

    Example:
      GET /codes/icd_pcs/0016070
    """
    row = (
        await db.execute(
            select(IcdPcsCode)
            .where(IcdPcsCode.code == code.upper())
            .where(IcdPcsCode.is_active.is_(True))
        )
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"ICD-10-PCS code '{code.upper()}' not found")
    return row
