from __future__ import annotations
import logging
logger = logging.getLogger("myeonri-api")

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.database import get_pool
from app.utils.saju import EARTHLY_BY_HANJA

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
    result = []
    for row in rows:
        item = dict(zip(columns, row))
        # 일진 기준 띠 정보 추가
        hdganjee = item.get("hdganjee", "")
        if hdganjee and len(hdganjee) >= 2:
            branch_hanja = hdganjee[1]  # 지지 한자 (예: 亥)
            branch_info = EARTHLY_BY_HANJA().get(branch_hanja)
            if branch_info:
                item["day_ddi"] = branch_info.get("zodiac", "")
                item["day_branch_hanja"] = branch_info.get("hanja", "")
                item["day_branch_hangul"] = branch_info.get("hangul", "")
            else:
                item["day_ddi"] = ""
                item["day_branch_hanja"] = ""
                item["day_branch_hangul"] = ""
        else:
            item["day_ddi"] = ""
            item["day_branch_hanja"] = ""
            item["day_branch_hangul"] = ""
        result.append(item)
    return {"data": result}
