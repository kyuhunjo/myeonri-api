from __future__ import annotations
import logging
logger = logging.getLogger("myeonri-api")

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.database import get_pool

router = APIRouter(prefix="/calendar", tags=["만세력달력"])


class CalendarRequest(BaseModel):
    year: int
    month: int


@router.post("/month")
async def get_calendar_month(req: CalendarRequest):
    """특정 월의 만세력 데이터 조회 (달력용)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT cd_sd AS sd, cd_hdganjee AS hdganjee, cd_kdganjee AS kdganjee, "
                "cd_hyganjee AS hyganjee, cd_kyganjee AS kyganjee, "
                "cd_hmganjee AS hmganjee, cd_kmganjee AS kmganjee, "
                "cd_sy AS sy, cd_sm AS sm, "
                "cd_ly AS ly, cd_lm AS lm, cd_ld AS ld, "
                "holiday, cd_sol_plan AS sol_plan, cd_ddi AS ddi "
                "FROM calenda_data_fixed "
                "WHERE cd_sy = %s AND cd_sm = %s "
                "ORDER BY cd_sd ASC",
                (req.year, req.month),
            )
            rows = await cur.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="해당 월의 데이터가 없습니다")

    columns = [
        "sd", "hdganjee", "kdganjee",
        "hyganjee", "kyganjee", "hmganjee", "kmganjee",
        "sy", "sm", "ly", "lm", "ld",
        "holiday", "sol_plan", "ddi",
    ]
    result = [dict(zip(columns, row)) for row in rows]
    return {"data": result}
