"""
랜딩페이지 AI 인트로 엔드포인트
- POST /consult/landing-intro/stream (공개, SSE 스트리밍)
"""
from __future__ import annotations
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.api.consult import _stream_groq

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/consult", tags=["상담분석"])


class LandingIntroRequest(BaseModel):
    weather_description: str = ""
    weather_temp: float | None = None
    pm10: float | None = None
    pm25: float | None = None
    sunrise_time: str = ""
    sunset_time: str = ""
    today_ganzi_kr: str = ""
    today_ganzi_cn: str = ""
    today_ddi: str = ""


@router.post("/landing-intro/stream")
async def landing_intro_stream(req: LandingIntroRequest):
    """랜딩페이지 AI 소개 (SSE 스트리밍) - 공개 엔드포인트"""
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")

    weather_str = req.weather_description or "정보 없음"
    weather_temp = req.weather_temp or "?"
    pm10_str = f"{req.pm10:.0f}" if req.pm10 is not None else "정보 없음"
    pm25_str = f"{req.pm25:.0f}" if req.pm25 is not None else "정보 없음"
    sunrise_str = req.sunrise_time or "--:--"
    sunset_str = req.sunset_time or "--:--"
    ganzi_info = f"{req.today_ganzi_kr or ''} / {req.today_ganzi_cn or ''}" if req.today_ganzi_kr else "정보 없음"

    system_prompt = """당신은 명리심리상담사(Myeonri)의 AI 어시스턴트입니다.
방문자에게 오늘의 기운과 서비스를 자연스럽게 소개해주세요.

규칙:
- 200~300자 이내로 간결하게
- 따뜻하고 부드러운 어조, 존댓말
- 날씨와 일진 정보를 자연스럽게 연결
- 서비스 소개를 마지막에 한 문장으로 포함
- 인사말로 시작"""

    user_prompt = f"""오늘 날짜 정보:
- 날씨: {weather_str}, {weather_temp}°C
- 미세먼지: PM10 {pm10_str}㎍/m³ / PM2.5 {pm25_str}㎍/m³
- 일출: {sunrise_str} / 일몰: {sunset_str}
- 오늘의 일진: {ganzi_info}

오늘의 기운과 분위기를 반영하여 방문자에게 짧은 인사말과 함께 이 서비스(명리심리상담사 - AI 기반 사주명리 분석 및 심리상담 서비스)를 자연스럽게 소개해주세요."""

    return StreamingResponse(
        _stream_groq({}, None, override_system=system_prompt, override_prompt=user_prompt, override_temperature=0.7),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
