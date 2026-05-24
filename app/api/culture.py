"""
문화행사 정보 프록시 (광주교통공사 오픈API CORS 우회)
- GET /culture/events?year=2026&month=5
"""
from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException, Query
import httpx

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/culture", tags=["문화행사"])

GRTC_BASE = "https://www.grtc.co.kr/subway/openapi/json/monthEventInformation"


@router.get("/events")
async def get_culture_events(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
):
    """광주도시철도 문화행사 정보 (공연 + 전시 통합)"""
    month_str = f"{year}{month:02d}"
    results = []
    async with httpx.AsyncClient(timeout=15) as client:
        for eventtype in (99, 100):
            try:
                resp = await client.get(
                    GRTC_BASE,
                    params={"listcount": 50, "month": month_str, "eventtype": eventtype},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        results.extend(data)
            except Exception as e:
                logger.warning(f"GRTC API error (type={eventtype}): {e}")
    return results
