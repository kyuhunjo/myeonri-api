"""
광주교통공사 역 인근 문화공간 API (공공데이터포털)
- GET /culture/station-spaces?station={역명}
"""
from __future__ import annotations
import logging

from fastapi import APIRouter, Query, HTTPException
import httpx

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/culture", tags=["문화공간"])

# 공공데이터포털 API 키 (환경변수)
from app.core.config import settings

API_URL = "https://apis.data.go.kr/B551232/OAMS_CLTPLCE_01/GET_OAMS_CLTPLCE_01"

# 문화 관련 카테고리만 필터링 (실제 데이터 기준)
CULTURE_CATEGORIES = {
    "예술", "볼거리/산책", "체험",
}


@router.get("/station-spaces")
async def get_station_spaces(
    station: str = Query(default="", description="역명 (예: 상무역, 남광주역)"),
    page_no: int = Query(default=1, ge=1),
    num_of_rows: int = Query(default=50, ge=1, le=100),
):
    """광주 도시철도 역 인근 문화공간 조회"""
    params = {
        "serviceKey": settings.SUNRISE_API_KEY,
        "pageNo": str(page_no),
        "numOfRows": str(num_of_rows),
        "apiType": "json",
    }
    if station:
        params["STATION_NAME"] = station

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(API_URL, params=params)
            data = resp.json()
        except Exception as e:
            logger.warning(f"Culture API error: {e}")
            return {"items": [], "totalCount": 0}

    # 응답 구조 파싱 (items: [{"item": {...}}, ...])
    items_raw = body.get("items", [])
    items = []
    if isinstance(items_raw, list):
        for entry in items_raw:
            if isinstance(entry, dict) and "item" in entry:
                items.append(entry["item"])
    elif isinstance(items_raw, dict):
        single = items_raw.get("item", {})
        if isinstance(single, dict):
            items = [single]
        elif isinstance(single, list):
            items = single
    total_count = int(body.get("totalCount", 0))

    # 문화 관련 카테고리만 필터링
    filtered = []
    for item in items:
        ctgry = (item.get("ctgry") or "").strip()
        # 문화 관련 카테고리만 포함
        if any(cat in ctgry for cat in CULTURE_CATEGORIES):
            filtered.append({
                "stationName": item.get("stationName", ""),
                "placeName": item.get("plcNm", ""),
                "category": ctgry,
                "distance": item.get("dstncDt", ""),
                "address": item.get("locplc", ""),
                "latitude": item.get("latitude", ""),
                "longitude": item.get("longitude", ""),
                "tel": item.get("siteTel", ""),
                "operTime": item.get("operTime", ""),
                "homepage": item.get("hmpg", ""),
                "image": item.get("image", ""),
                "keyword": item.get("kwrd", ""),
            })

    return {"items": filtered, "totalCount": len(filtered), "rawTotal": total_count}
