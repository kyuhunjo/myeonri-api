from __future__ import annotations
import logging
logger = logging.getLogger("myeonri-api")

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.core.config import settings

router = APIRouter(prefix="/weather", tags=["날씨/일출일몰/대기질"])

# OpenWeatherMap API 키 (환경 변수에서 로드)
OPENWEATHER_API_KEY = settings.OPENWEATHER_API_KEY or ""

# 공공데이터 API 키 (환경 변수에서 로드)
KMA_API_KEY = settings.KMA_API_KEY or ""


class WeatherResponse(BaseModel):
    temperature: float | None = None
    description: str | None = None
    humidity: int | None = None
    windSpeed: float | None = None
    windDirection: int | None = None
    icon: str | None = None
    kstDateTime: str | None = None


class SunriseResponse(BaseModel):
    sunrise: str | None = None
    sunset: str | None = None
    moonrise: str | None = None


class AirQualityResponse(BaseModel):
    pm10Value: str | None = None
    pm25Value: str | None = None
    so2Value: str | None = None
    coValue: str | None = None
    o3Value: str | None = None
    kstDateTime: str | None = None


@router.get("/openweather", response_model=WeatherResponse)
async def get_openweather(lat: float = Query(...), lon: float = Query(...)):
    """
    OpenWeatherMap 현재 날씨 조회
    """
    if not OPENWEATHER_API_KEY:
        raise HTTPException(status_code=500, detail="OpenWeatherMap API 키가 설정되지 않았습니다")

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "kr",
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="날씨 API 타임아웃")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="날씨 API 오류")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"날씨 조회 실패: {str(e)}")

    # KST 시간 변환
    from datetime import datetime, timezone, timedelta
    kst = datetime.now(timezone(timedelta(hours=9)))
    kst_str = kst.strftime("%m/%d %H:%M")

    weather = data.get("weather", [{}])[0]
    main = data.get("main", {})
    wind = data.get("wind", {})

    return WeatherResponse(
        temperature=main.get("temp"),
        description=weather.get("description"),
        humidity=main.get("humidity"),
        windSpeed=wind.get("speed"),
        windDirection=wind.get("deg"),
        icon=weather.get("icon"),
        kstDateTime=kst_str,
    )


@router.get("/sunrise")
async def get_sunrise(date: str = Query(...), lat: float = Query(...), lon: float = Query(...)):
    """
    공공데이터 일출일몰 조회
    date: YYYYMMDD 형식
    """
    if not KMA_API_KEY:
        raise HTTPException(status_code=500, detail="공공데이터 API 키가 설정되지 않았습니다")

    url = "http://apis.data.go.kr/B090041/openapi/SolrLstCdeService/getSolrLst"
    params = {
        "serviceKey": KMA_API_KEY,
        "pageNo": 1,
        "numOfRows": 10,
        "dataType": "JSON",
        "date": date,
        "lat": str(lat),
        "lon": str(lon),
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="일출일몰 API 타임아웃")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="일출일몰 API 오류")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"일출일몰 조회 실패: {str(e)}")

    return data


@router.get("/air-quality")
async def get_air_quality(obsrrTpcd: str = Query(default="0051", description="관측소 코드 (광주: 0051)")):
    """
    산림청 청정넷 대기질 조회
    """
    # 청정넷 API 키 (환경 변수)
    CHEONGJEONG_API_KEY = settings.CHEONGJEONG_API_KEY or ""

    if not CHEONGJEONG_API_KEY:
        raise HTTPException(status_code=500, detail="청정넷 API 키가 설정되지 않았습니다")

    url = "https://apis.korea.kr/service/ForestInfoService/openapi/getAirPollutionInfo"
    params = {
        "serviceKey": CHEONGJEONG_API_KEY,
        "pageNo": 1,
        "numOfRows": 10,
        "dataType": "JSON",
        "obsrrTpcd": obsrrTpcd,
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="대기질 API 타임아웃")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="대기질 API 오류")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"대기질 조회 실패: {str(e)}")

    return data
