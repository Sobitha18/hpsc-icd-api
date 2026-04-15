"""
routers/codes.py
----------------
Read-only endpoints for querying ICD-10-CM codes.

Endpoints:
  GET /codes/icd                  list codes (filter + paginate)
  GET /codes/icd/{code}           fetch one specific code
  GET /codes/icd/category/{cat}   all codes within a 3-char category

Query params for the list endpoint:
  q            — search in description (case-insensitive substring)
  category     — filter by 3-char category, e.g. "A00"
  chapter      — filter by chapter name (substring match)
  billable_only — true/false, default false
  page         — page number, starts at 1
  size         — codes per page, default 50, max 200
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import IcdCode
from app.schemas import IcdCodeDetail, PaginatedIcdCodes

router = APIRouter(prefix="/codes", tags=["ICD Codes"])


@router.get("/icd", response_model=PaginatedIcdCodes)
async def list_icd_codes(
    q:             str  | None = Query(None,  description="Search in description"),
    category:      str  | None = Query(None,  description="3-char category, e.g. A00"),
    chapter:       str  | None = Query(None,  description="Chapter name substring"),
    billable_only: bool        = Query(False, description="Return only billable codes"),
    page:          int         = Query(1,     ge=1,   description="Page number"),
    size:          int         = Query(50,    ge=1, le=200, description="Results per page"),
    db: AsyncSession = Depends(get_db),
):
    """
    List ICD-10-CM codes with optional filters and pagination.

    Example calls:
      GET /codes/icd?q=cholera
      GET /codes/icd?category=A00&billable_only=true
      GET /codes/icd?chapter=respiratory&page=2&size=100
    """
    query = select(IcdCode)

    # Apply filters
    if q:
        query = query.where(IcdCode.description.ilike(f"%{q}%"))
    if category:
        query = query.where(IcdCode.category == category.upper())
    if chapter:
        query = query.where(IcdCode.chapter.ilike(f"%{chapter}%"))
    if billable_only:
        query = query.where(IcdCode.is_billable == True)  # noqa: E712

    # Count total matching rows (for the response)
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    # Apply pagination and fetch
    offset = (page - 1) * size
    query = query.order_by(IcdCode.code).offset(offset).limit(size)
    result = await db.execute(query)
    codes = result.scalars().all()

    return PaginatedIcdCodes(total=total, page=page, size=size, results=codes)


@router.get("/icd/{code}", response_model=IcdCodeDetail)
async def get_icd_code(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch a single ICD-10-CM code by its raw code value.
    Accepts both formats: "A001" or "A00.1" (dot is stripped automatically).

    Example calls:
      GET /codes/icd/A001
      GET /codes/icd/A00.1
    """
    # Strip dot so both "A001" and "A00.1" work
    raw_code = code.upper().replace(".", "")

    result = await db.execute(
        select(IcdCode).where(IcdCode.code == raw_code)
    )
    icd = result.scalar_one_or_none()

    if icd is None:
        raise HTTPException(status_code=404, detail=f"ICD code '{code}' not found")

    return icd


@router.get("/icd/category/{category}", response_model=list[IcdCodeDetail])
async def get_codes_by_category(
    category: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Return all codes within a 3-character category.

    Example:
      GET /codes/icd/category/A00
      → returns A00, A00.0, A00.1, A00.9
    """
    result = await db.execute(
        select(IcdCode)
        .where(IcdCode.category == category.upper())
        .order_by(IcdCode.code)
    )
    codes = result.scalars().all()

    if not codes:
        raise HTTPException(
            status_code=404,
            detail=f"No codes found for category '{category}'"
        )

    return codes
