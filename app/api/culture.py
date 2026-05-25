from __future__ import annotations
import logging
logger = logging.getLogger("myeonri-api")

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.core.config import settings

router = APIRouter(prefix="/culture", tags=["문화공간"])

# 공공데이터 API 키 (환경 변수에서 로드)
KMA_API_KEY = settings.KMA_API_KEY or ""


class CultureSpace(BaseModel):
    facnm: str | None = None  # 시설명
    rdnWhlAddr: str | None = None  # 도로명주소
    facMngrNm: str | None = None  # 관리자명
    facMngrTel: str | None = None  # 관리자연락처
    latitude: float | None = None
    longitude: float | None = None
    distance: float | None = None  # 거리 (미터)


@router.get("/nearby")
async def get_nearby_culture(lat: float = Query(...), lon: float = Query(...), radius: int = Query(default=3000, description="반경 (미터)")):
    """
    공공데이터 문화공간 조회 (주변 시설)
    """
    if not KMA_API_KEY:
        raise HTTPException(status_code=500, detail="공공데이터 API 키가 설정되지 않았습니다")

    url = "http://apis.data.go.kr/B551011/KorService1/searchArea1"
    params = {
        "serviceKey": KMA_API_KEY,
        "pageNo": 1,
        "numOfRows": 20,
        "dataType": "JSON",
        "mapX": str(lon),
        "mapY": str(lat),
        "radius": radius,
        "listYN": "Y",
        "MobileOS": "ETC",
        "MobileApp": "Myeonri",
        "_type": "json",
        "contentTypeId": "14",  # 문화시설
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="문화공간 API 타임아웃")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="문화공간 API 오류")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"문화공간 조회 실패: {str(e)}")

    return data
