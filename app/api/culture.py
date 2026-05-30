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
    radius: int = Query(default=3000, ge=100, le=10000, description="검색 반경 (미터)"),
    page_no: int = Query(default=1, ge=1),
    num_of_rows: int = Query(default=50, ge=1, le=100),
):
    """광주 도시철도 역 인근 문화공간 조회 — 좌표 기준 근처 역 자동 검색"""
    params_base = {
        "serviceKey": settings.SUNRISE_API_KEY,
        "pageNo": str(page_no),
        "numOfRows": str(num_of_rows),
        "apiType": "json",
    }

    # 1. 좌표가 있으면 근처 역 찾기, 없으면 전체 조회
    stations = []
    if lat is not None and lon is not None:
        # 광주 도시철도 주요 역 목록 (대략적인 좌표)
        import math
        GWANGJU_STATIONS = [
            ("소태역", 35.1225, 126.9322),
            ("학동증심사입구역", 35.1319, 126.9314),
            ("남광주역", 35.1394, 126.9236),
            ("문화전당역", 35.1464, 126.9200),
            ("금남로4가역", 35.1511, 126.9153),
            ("금남로5가역", 35.1539, 126.9100),
            ("양동시장역", 35.1547, 126.9014),
            ("돌고개역", 35.1514, 126.8950),
            ("농성역", 35.1528, 126.8886),
            ("화정역", 35.1519, 126.8781),
            ("쌍촌역", 35.1517, 126.8686),
            ("운천역", 35.1508, 126.8583),
            ("상무역", 35.1461, 126.8489),
            ("김대중컨벤션센터역", 35.1436, 126.8408),
            ("공항역", 35.1439, 126.8125),
            ("송정공원역", 35.1436, 126.8050),
            ("광주송정역", 35.1375, 126.7919),
            ("도산역", 35.1314, 126.7878),
            ("평동역", 35.1242, 126.7694),
            ("녹동역", 35.1069, 126.9347),
        ]

        def haversine(la1, lo1, la2, lo2):
            R = 6371000
            phi1, phi2 = math.radians(la1), math.radians(la2)
            dphi = math.radians(la2 - la1)
            dlam = math.radians(lo2 - lo1)
            a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        # 반경 내 역 찾기
        for name, slat, slon in GWANGJU_STATIONS:
            dist = haversine(lat, lon, slat, slon)
            if dist <= radius:
                stations.append((name, dist))
        stations.sort(key=lambda x: x[1])  # 가까운 순
    
    # 2. 각 역별로 문화공간 조회
    all_items = []
    if stations:
        # 근처 역이 있으면 각각 조회 (최대 5개 역)
        for st_name, dist in stations[:5]:
            params = {**params_base, "STATION_NAME": st_name}
            async with httpx.AsyncClient(timeout=15) as client:
                try:
                    resp = await client.get(API_URL, params=params)
                    data = resp.json()
                    body = data.get("body", {})
                    items_raw = body.get("items", [])
                    if isinstance(items_raw, list):
                        for entry in items_raw:
                            if isinstance(entry, dict) and "item" in entry:
                                item = entry["item"]
                                item["_station_dist"] = dist
                                all_items.append(item)
                    elif isinstance(items_raw, dict):
                        single = items_raw.get("item", {})
                        if isinstance(single, dict):
                            single["_station_dist"] = dist
                            all_items.append(single)
                        elif isinstance(single, list):
                            for s in single:
                                s["_station_dist"] = dist
                                all_items.append(s)
                except Exception as e:
                    logger.warning(f"Culture API error for station {st_name}: {e}")
    else:
        # 좌표 없으면 전체 조회
        params = {**params_base}
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(API_URL, params=params)
                data = resp.json()
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

    # 카테고리 필터링 (완화: 더 많은 문화 카테고리 허용)
    CULTURE_CATEGORIES = {
        "예술", "볼거리/산책", "체험", "문화", "공연", "전시",
        "역사", "관광", "공원", "도서관", "박물관", "미술관", "기념관",
        "영화관", "음악", "무용", "연극", "카페", "갤러리", "전시관",
    }
    filtered = []
    for item in all_items:
        ctgry = (item.get("ctgry") or "").strip()
        if any(cat in ctgry for cat in CULTURE_CATEGORIES):
            filtered.append({
                "stationName": item.get("stationName", ""),
                "placeName": item.get("plcNm", ""),
                "category": ctgry,
                "distance": item.get("dstncDt", "") or f"{item.get('_station_dist', 0):.0f}m",
                "address": item.get("locplc", ""),
                "latitude": item.get("latitude", ""),
                "longitude": item.get("longitude", ""),
                "tel": item.get("siteTel", ""),
                "operTime": item.get("operTime", ""),
                "homepage": item.get("hmpg", ""),
                "image": item.get("image", ""),
                "keyword": item.get("kwrd", ""),
            })

    return {"items": filtered, "totalCount": len(filtered)}
