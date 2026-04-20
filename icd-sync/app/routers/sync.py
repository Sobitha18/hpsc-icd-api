from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import IcdCode, IcdPcsCode, IcdPcsSyncHistory, SyncHistory
from app.schemas import HcpcsSyncResult, SyncResult
from app.sync.icd_and_icd_pcs import OrderFileSyncer
from app.sync.hcpcs import HcpcsSyncer

router = APIRouter(prefix="/sync", tags=["Sync"])

_SYNCERS = {
    "icd": lambda db: OrderFileSyncer(
        db,
        url_template="https://www.cms.gov/files/zip/{year}-code-descriptions-tabular-order.zip",
        model=IcdCode,
        history_model=SyncHistory,
        category_fn=lambda _: "ICD",
    ),
    "icd_pcs": lambda db: OrderFileSyncer(
        db,
        url_template="https://www.cms.gov/files/zip/{year}-icd-10-pcs-order-file-long-and-abbreviated-titles.zip",
        model=IcdPcsCode,
        history_model=IcdPcsSyncHistory,
        category_fn=lambda _: "ICD_PCS",
    ),
    "hcpcs": HcpcsSyncer,
}


@router.post("/codes", response_model=Union[SyncResult, HcpcsSyncResult])
async def sync_codes(
    code_type: str           = Query(..., description="Code type: 'icd', 'hcpcs', or 'icd_pcs'"),
    url:       Optional[str] = Query(None, description="Optional custom CMS URL"),
    db: AsyncSession = Depends(get_db),
):
    cls = _SYNCERS.get(code_type)
    if not cls:
        raise HTTPException(status_code=400, detail=f"Invalid code_type '{code_type}'. Use: icd, hcpcs, icd_pcs")
    return await cls(db).sync(url)
