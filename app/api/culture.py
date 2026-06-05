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
    lat: float = Query(default=None, description="위도"),
    lon: float = Query(default=None, description="경도"),
    page_no: int = Query(default=1, ge=1),
    num_of_rows: int = Query(default=200, ge=1, le=500),
):
    """광주 도시철도 역 인근 문화공간 조회 — 좌표 기준 거리순 정렬"""
    params = {
        "serviceKey": settings.SUNRISE_API_KEY,
        "pageNo": str(page_no),
        "numOfRows": str(num_of_rows),
        "apiType": "json",
    }

    # 문화 카테고리 필터
    CULTURE_CATEGORIES = {
        "예술", "볼거리/산책", "체험", "문화", "공연", "전시",
        "역사", "관광", "공원", "도서관", "박물관", "미술관", "기념관",
        "영화관", "음악", "무용", "연극", "갤러리", "전시관",
    }

    all_items = []
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(API_URL, params=params)
            data = resp.json()
            header = data.get("header", {})
            if header.get("resultCode", "") not in ("", "00"):
                logger.warning(f"Culture API resultCode={header.get('resultCode')} msg={header.get('resultMsg')}")
                return {"items": [], "totalCount": 0}
            body = data.get("body", {})
            items_raw = body.get("items", [])
            if isinstance(items_raw, list):
                for entry in items_raw:
                    if isinstance(entry, dict) and "item" in entry:
                        all_items.append(entry["item"])
            elif isinstance(items_raw, dict):
                single = items_raw.get("item", {})
                if isinstance(single, dict):
                    all_items = [single]
                elif isinstance(single, list):
                    all_items = single
        except Exception as e:
            logger.warning(f"Culture API error: {e}")
            return {"items": [], "totalCount": 0}

    # 카테고리 필터링
    filtered = []
    for item in all_items:
        ctgry = (item.get("ctgry") or "").strip()
        if not ctgry:
            continue
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

    # 좌표가 있으면 거리순 정렬
    if lat is not None and lon is not None and filtered:
        import math
        def haversine(la1, lo1, la2, lo2):
            R = 6371000
            phi1, phi2 = math.radians(la1), math.radians(la2)
            dphi = math.radians(la2 - la1)
            dlam = math.radians(lo2 - lo1)
            a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        for item in filtered:
            try:
                plat = float(item["latitude"])
                plon = float(item["longitude"])
                item["_user_dist"] = haversine(lat, lon, plat, plon)
            except (ValueError, KeyError):
                item["_user_dist"] = 999999
        filtered.sort(key=lambda x: x.get("_user_dist", 999999))
        # 반경 10km 이내만
        filtered = [x for x in filtered if x.get("_user_dist", 999999) <= 10000]
        for x in filtered:
            x["distance"] = f"{x['_user_dist']:.0f}m"
            del x["_user_dist"]

    return {"items": filtered, "totalCount": len(filtered)}
