from __future__ import annotations
import logging
logger = logging.getLogger("myeonri-api")

from fastapi import APIRouter, HTTPException
from app.api.schemas import SajuRequest, SajuResponse
from app.core.database import get_pool
from app.utils.saju import calculate_saju_from_calenda

router = APIRouter(prefix="/saju", tags=["사주"])


@router.post("/calculate", response_model=SajuResponse)
async def calculate_saju(req: SajuRequest):
    """사주 계산 API — 만세력 DB 조회 + 시주/십신 계산"""
    logger.info(f"Saju calculate: {req.year}-{req.month}-{req.day} {req.hour}:{req.minute}")
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # 만세력 조회
            await cur.execute(
                "SELECT * FROM calenda_data_fixed "
                "WHERE cd_sy = %s AND cd_sm = %s AND cd_sd = %s "
                "LIMIT 1",
                (req.year, req.month, req.day),
            )
            row = await cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="해당 날짜의 만세력 데이터가 없습니다")

    # 컬럼명 매핑
    columns = [
        "cd_no", "cd_sgi", "cd_sy", "cd_sm", "cd_sd",
        "cd_ly", "cd_lm", "cd_ld",
        "cd_hyganjee", "cd_kyganjee",
        "cd_hmganjee", "cd_kmganjee",
        "cd_hdganjee", "cd_kdganjee",
        "cd_hweek", "cd_kweek",
        "cd_stars", "cd_moon_state", "cd_moon_time",
        "cd_leap_month", "cd_month_size",
        "cd_hterms", "cd_kterms", "cd_terms_time",
        "cd_keventday", "cd_ddi", "cd_sol_plan", "cd_lun_plan",
        "holiday",
    ]
    calenda_row = dict(zip(columns, row))

    result = calculate_saju_from_calenda(
        calenda_row,
        hour=req.hour,
        minute=req.minute,
    )

    return SajuResponse(**result)


@router.get("/stems")
async def get_heavenly_stems():
    """천간 목록"""
    from app.utils.saju import HEAVENLY_STEMS
    return HEAVENLY_STEMS


@router.get("/branches")
async def get_earthly_branches():
    """지지 목록"""
    from app.utils.saju import EARTHLY_BRANCHES
    return EARTHLY_BRANCHES
