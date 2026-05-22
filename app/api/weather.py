"""날씨 / 일출일몰 / 대기질 API 라우터"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger("myeonri-api")

router = APIRouter(prefix="/weather", tags=["weather"])

KST = timezone(timedelta(hours=9))

# 화순/광주 좌표 (랜딩페이지 기본값)
DEFAULT_LAT = 35.1595  # 광주광역시 위도
DEFAULT_LON = 126.8526  # 광주광역시 경도


class WeatherCurrent(BaseModel):
    temperature: float
    temp_min: float
    temp_max: float
    humidity: int
    rainfall: float
    windSpeed: float
    windDirection: float
    description: str
    icon: str
    kstDateTime: str


class WeatherForecast(BaseModel):
    dt: int
    kstDateTime: str
    main: dict
    weather: list
    wind: dict
    rain: float | None = None


class SunriseSunset(BaseModel):
    sunrise: str
    sunset: str
    location: str
    date: str
    longitude: str
    latitude: str
    coordinates: dict
    moonrise: str
    moonset: str
    moontransit: str
    suntransit: str
    civilTwilight: dict
    nauticalTwilight: dict
    astronomicalTwilight: dict


# ──────────────────────────────────────────
#  OpenWeatherMap — 현재 날씨 + 5일 예보
# ──────────────────────────────────────────

@router.get("/current", response_model=WeatherCurrent)
async def get_current_weather(
    lat: float = Query(DEFAULT_LAT, description="위도"),
    lon: float = Query(DEFAULT_LON, description="경도"),
):
    """현재 날씨 정보 (OpenWeatherMap)"""
    owm_key = settings.OPENWEATHER_API_KEY
    if not owm_key:
        raise HTTPException(503, "OpenWeatherMap API key not configured")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 현재 날씨
            resp = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"lat": lat, "lon": lon, "appid": owm_key, "units": "metric", "lang": "kr"},
            )
            resp.raise_for_status()
            current = resp.json()

            # 5일 예보 (오늘 최고/최저 계산용)
            fc_resp = await client.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params={"lat": lat, "lon": lon, "appid": owm_key, "units": "metric", "lang": "kr"},
            )
            fc_resp.raise_for_status()
            forecast = fc_resp.json()

    except httpx.HTTPError as e:
        logger.error(f"OpenWeatherMap API error: {e}")
        raise HTTPException(502, "Failed to fetch weather data")

    utc_dt = datetime.fromtimestamp(current["dt"], tz=timezone.utc)
    kst_dt = utc_dt.astimezone(KST)

    # 오늘 최고/최저 계산
    today_start_kst = kst_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start_kst.astimezone(timezone.utc)
    today_end_utc = (today_start_kst + timedelta(days=1)).astimezone(timezone.utc)

    temp_min = current["main"]["temp"]
    temp_max = current["main"]["temp"]
    for item in forecast.get("list", []):
        item_dt = datetime.fromtimestamp(item["dt"], tz=timezone.utc)
        if today_start_utc <= item_dt < today_end_utc:
            temp_min = min(temp_min, item["main"]["temp"])
            temp_max = max(temp_max, item["main"]["temp"])

    kst_str = kst_dt.strftime("%Y년 %m월 %d일 %H:%M")
    rain_1h = current.get("rain", {}).get("1h", 0) if isinstance(current.get("rain"), dict) else 0

    return WeatherCurrent(
        temperature=round(current["main"]["temp"], 1),
        temp_min=round(temp_min, 1),
        temp_max=round(temp_max, 1),
        humidity=current["main"]["humidity"],
        rainfall=rain_1h,
        windSpeed=round(current["wind"]["speed"], 1),
        windDirection=current["wind"]["deg"],
        description=current["weather"][0]["description"],
        icon=current["weather"][0]["icon"],
        kstDateTime=kst_str,
    )


@router.get("/forecast", response_model=list[WeatherForecast])
async def get_forecast(
    lat: float = Query(DEFAULT_LAT, description="위도"),
    lon: float = Query(DEFAULT_LON, description="경도"),
):
    """5일 날씨 예보"""
    owm_key = settings.OPENWEATHER_API_KEY
    if not owm_key:
        raise HTTPException(503, "OpenWeatherMap API key not configured")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params={"lat": lat, "lon": lon, "appid": owm_key, "units": "metric", "lang": "kr"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.error(f"OpenWeatherMap forecast API error: {e}")
        raise HTTPException(502, "Failed to fetch forecast data")

    # 정오(12:00 KST) 데이터 기준으로 하루 하나씩, 최대 5일
    daily: dict[str, WeatherForecast] = {}
    temp_data: dict[str, dict[str, Any]] = {}

    now_kst = datetime.now(KST)
    today_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)

    for item in data.get("list", []):
        item_utc = datetime.fromtimestamp(item["dt"], tz=timezone.utc)
        item_kst = item_utc.astimezone(KST)
        date_key = item_kst.strftime("%Y-%m-%d")

        if date_key not in temp_data:
            temp_data[date_key] = {"temps": [], "max": -999, "min": 999, "noon": None, "noon_data": None}

        t = item["main"]["temp"]
        temp_data[date_key]["temps"].append(t)
        temp_data[date_key]["max"] = max(temp_data[date_key]["max"], t)
        temp_data[date_key]["min"] = min(temp_data[date_key]["min"], t)

        if item_kst.hour == 12:
            temp_data[date_key]["noon"] = t
            temp_data[date_key]["noon_data"] = {
                "dt": item["dt"],
                "main": {
                    "temp": t,
                    "temp_min": None,  # 채워짐
                    "temp_max": None,
                    "humidity": item["main"]["humidity"],
                },
                "weather": item["weather"],
                "wind": {"speed": round(item["wind"]["speed"], 1), "deg": item["wind"]["deg"]},
                "rain": round(item.get("rain", {}).get("3h", 0), 1) if isinstance(item.get("rain"), dict) else 0,
            }

    for date_key, td in temp_data.items():
        if td["noon_data"]:
            td["noon_data"]["main"]["temp_min"] = round(td["min"], 1)
            td["noon_data"]["main"]["temp_max"] = round(td["max"], 1)
            td["noon_data"]["kstDateTime"] = date_key.replace("-", "년 ", 1).replace("-", "월 ", 1) + "일"
            daily[date_key] = WeatherForecast(**td["noon_data"])

    # 오늘 이후 데이터만, 최대 5일
    result = sorted(
        [v for k, v in daily.items() if k > now_kst.strftime("%Y-%m-%d")],
        key=lambda x: str(x.dt),
    )[:5]

    return result


# ──────────────────────────────────────────
#  한국천문연구원 — 일출/일몰
# ──────────────────────────────────────────

@router.get("/sunrise", response_model=SunriseSunset)
async def get_sunrise_sunset(
    date: str = Query(None, description="YYYYMMDD 형식 (기본: 오늘)"),
    longitude: float = Query(126.8526, description="경도 (도 단위)"),
    latitude: float = Query(35.1595, description="위도 (도 단위)"),
):
    """일출/일몰/월출/월몰/박명 정보 (한국천문연구원)"""
    api_key = settings.SUNRISE_API_KEY
    if not api_key:
        raise HTTPException(503, "Sunrise API key not configured")

    if date and len(date) == 8 and date.isdigit():
        locdate = date
    else:
        locdate = datetime.now(KST).strftime("%Y%m%d")

    # 도 → 도분 변환
    lon_deg = int(longitude)
    lon_min = int(round((longitude - lon_deg) * 60))
    lat_deg = int(latitude)
    lat_min = int(round((latitude - lat_deg) * 60))

    params = {
        "serviceKey": api_key,
        "locdate": locdate,
        "longitude": str(lon_deg),
        "latitude": str(lat_deg),
        "dnYn": "N",  # 도분 형식
        "longitudeMin": str(lon_min),
        "latitudeMin": str(lat_min),
        "_type": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "http://apis.data.go.kr/B090041/openapi/service/RiseSetInfoService/getLCRiseSetInfo",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.error(f"Sunrise API error: {e}")
        raise HTTPException(502, "Failed to fetch sunrise/sunset data")

    try:
        item = data["response"]["body"]["items"]["item"]
    except (KeyError, TypeError):
        logger.error(f"Unexpected sunrise API response: {data}")
        raise HTTPException(502, "Invalid response from sunrise API")

    def g(key: str) -> str:
        val = item.get(key)
        return str(val).strip() if val is not None else ""

    return SunriseSunset(
        sunrise=g("sunrise"),
        sunset=g("sunset"),
        location=g("location"),
        date=g("locdate"),
        longitude=g("longitudeNum"),
        latitude=g("latitudeNum"),
        coordinates={
            "longitude": f"{lon_deg}도 {lon_min}분",
            "latitude": f"{lat_deg}도 {lat_min}분",
        },
        moonrise=g("moonrise"),
        moonset=g("moonset"),
        moontransit=g("moontransit"),
        suntransit=g("suntransit"),
        civilTwilight={"morning": g("civilm"), "evening": g("civile")},
        nauticalTwilight={"morning": g("nautm"), "evening": g("naute")},
        astronomicalTwilight={"morning": g("astm"), "evening": g("aste")},
    )
