"""
공통 상담 분석 모듈
- ConsultCategory, ConsultRequest, _get_saju_data
- CATEGORY_PROMPTS, SYSTEM_PROMPT
- _stream_groq (Groq SSE 스트리밍 공통 함수)
"""
from __future__ import annotations
import httpx
import json
import logging
from enum import Enum
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.database import get_pool

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/consult", tags=["상담분석"])


class ConsultCategory(str, Enum):
    CAREER = "career"
    LOVE = "love"
    HEALTH = "health"
    RELATIONSHIP = "relationship"
    FINANCE = "finance"
    STUDY = "study"
    FAMILY = "family"
    FORTUNE = "fortune"
    DAILY = "daily"
    CUSTOM = "custom"


CATEGORY_PROMPTS = {
    "career": "직장과 진로에 대해 봅니다. 타고난 기질과 재능, 일에서의 강점을 짚어주고 지금 시기 방향을 제시해주세요.",
    "love": "연애와 인연에 대해 봅니다. 성격적 특징과 관계 패턴, 잘 맞는 상대상과 주의할 점을 말해주세요.",
    "health": "건강에 대해 봅니다. 체질적으로 주의할 부위나 시기, 일상에서 실천할 관리법을 말해주세요.",
    "relationship": "대인관계에 대해 봅니다. 인간관계에서의 성향과 장단점, 더 나은 관계를 위한 조언을 해주세요.",
    "finance": "재물과 돈에 대해 봅니다. 재물운의 흐름과 성향, 유리한 시기와 방향을 말해주세요.",
    "study": "학업과 공부에 대해 봅니다. 잘 맞는 학습 방식과 분야, 집중력과 이해력 패턴을 살펴보고 조언해주세요.",
    "family": "가족과 가정에 대해 봅니다. 가족 관계에서의 역할과 성향, 더 편안한 관계를 위한 조언을 해주세요.",
    "fortune": "올해 전체 운세에 대해 봅니다. 대운과 세운을 고려하여 기회와 주의할 점을 말해주세요.",
    "daily": "",
    "custom": "",
}

SYSTEM_PROMPT = """당신은 사주명리 기반 심리상담사입니다. 사주 정보(4주, 십신, 오행)를 바탕으로 심리적 통찰과 조언을 제공합니다.

규칙:
- 인사말 없이 바로 본문 시작
- 마지막에 추가 질문 유도하지 말고 자연스럽게 마무리
- 600~800자로 충실하게, 따뜻하고 공감적인 어조로
- 존댓말 사용"""


class ConsultRequest(BaseModel):
    google_id: str
    category: ConsultCategory = Field(default="custom")
    question: str = ""
    saju_result: dict | None = None
    temperature: float | None = None


async def _get_saju_data(req: ConsultRequest) -> dict:
    """사주 데이터 조회 (saju_profiles 테이블)"""
    saju = req.saju_result
    if saju:
        return saju

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT sp.saju_data FROM users u "
                "JOIN saju_profiles sp ON sp.user_id = u.id AND sp.is_primary = 1 "
                "WHERE u.google_id = %s LIMIT 1",
                (req.google_id,),
            )
            row = await cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    saju = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    if not saju:
        raise HTTPException(status_code=400, detail="사주 데이터가 없습니다. 먼저 사주를 계산해주세요.")
    return saju


async def _stream_groq(saju: dict, req: ConsultRequest, override_system: str = None, override_prompt: str = None, override_temperature: float = None) -> AsyncGenerator[str, None]:
    """Groq 스트리밍 응답을 SSE 형식으로 변환 (override 파라미터 지원)"""
    system_prompt = override_system or SYSTEM_PROMPT
    temperature = override_temperature if override_temperature is not None else 0.7

    if override_prompt:
        user_prompt = override_prompt
    else:
        category_instruction = CATEGORY_PROMPTS.get(req.category.value, "")
        extra_question = f"\n\n사용자의 추가 질문: {req.question}" if req.question else ""
        user_prompt = f"""사주 정보: {json.dumps(saju, ensure_ascii=False, indent=2)}

상담 주제: {category_instruction}{extra_question}

사주 정보를 바탕으로 상담 답변을 해주세요."""

    import httpx

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": 2048,
                    "stream": True,
                },
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    yield f"data: {json.dumps({'error': error_body.decode()[:200]})}\n\n"
                    return

                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:].strip()
                        if chunk == "[DONE]":
                            continue
                        try:
                            data = json.loads(chunk)
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield f"data: {json.dumps({'text': content})}\n\n"
                        except (json.JSONDecodeError, KeyError):
                            continue
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)[:200]})}\n\n"
    finally:
        yield "data: [DONE]\n\n"


# ── 랜딩페이지 영역별 AI 설명 (Ollama Cloud 경량모델 스트리밍) ──

from app.utils.ollama import ollama_stream
from fastapi.responses import StreamingResponse


def _sse_response(generator):
    return StreamingResponse(generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no",
    })


@router.post("/landing-weather/stream")
async def stream_landing_weather(data: dict):
    temperature = data.get("temperature")
    description = data.get("description")
    humidity = data.get("humidity")
    windSpeed = data.get("windSpeed")

    prompt = f"""날씨: 온도 {temperature}°C, {description}, 습도 {humidity}%, 풍속 {windSpeed}m/s.
1~2문장으로 오늘 날씨 한줄평 해줘. 따뜻하고 친근하게."""
    async def gen():
        async for chunk in ollama_stream(prompt, system="당신은 친근한 날씨 해설가입니다."):
            yield chunk
    return _sse_response(gen)


@router.post("/landing-sunrise/stream")
async def stream_landing_sunrise(data: dict):
    sunrise = data.get("sunrise")
    sunset = data.get("sunset")

    prompt = f"""일출 {sunrise}, 일몰 {sunset}. 1~2문장으로 오늘 해 뜨고 지는 시간 한줄평 해줘. 따뜻하고 친근하게."""
    async def gen():
        async for chunk in ollama_stream(prompt, system="당신은 친근한 천문 해설가입니다."):
            yield chunk
    return _sse_response(gen)


@router.post("/landing-air/stream")
async def stream_landing_air(data: dict):
    pm10 = data.get("pm10")
    pm25 = data.get("pm25")

    prompt = f"""미세먼지 PM10 {pm10}, 초미세먼지 PM25 {pm25}. 1~2문장으로 오늘 대기질 한줄평 해줘. 건강 팁 포함해서 따뜻하게."""
    async def gen():
        async for chunk in ollama_stream(prompt, system="당신은 친근한 건강 상담가입니다."):
            yield chunk
    return _sse_response(gen)


@router.post("/landing-culture/stream")
async def stream_landing_culture(data: dict):
    spaces = data.get("spaces", [])
    weather = data.get("weather", "맑음")
    temperature = data.get("temperature", "")
    air = data.get("air", "")
    ganzi = data.get("ganzi", "")

    # 명소 상세 정보 포함
    spot_details = []
    for s in spaces[:8]:
        name = s.get('placeName', '')
        cat = s.get('category', '')
        desc = s.get('desc', '')
        why = s.get('why', '')
        spot_details.append(f"- {name} | {cat} | {desc} | 추천이유: {why}")
    spot_list = "\n".join(spot_details)

    # 부가 정보
    extra = []
    if ganzi:
        extra.append(f"만세력: {ganzi}")
    if air:
        extra.append(f"대기질: {air}")
    if temperature:
        extra.append(f"기온: {temperature}°C")
    extra_str = "\n".join(extra) if extra else ""

    prompt = f"""
[명소 리스트 (이름 | 분류 | 설명 | 추천이유)]
{spot_list}

[오늘의 조건]
날씨: {weather}
{extra_str}

규칙:
- 위 명소 중 오늘 날씨·대기질·만세력 조건을 종합해서 **가장 잘 어울리는 한 곳**을 골라 추천해줘.
- 장소의 추천이유(why)를 참고하되, 오늘 조건과 연결해서 자연스럽게 설명.
- 3~4문장으로 구체적인 추천.
- "오늘 같은 {weather} 날씨엔" 으로 시작.
- 장소명과 emoji 반드시 포함.
"""
    return _sse_response(lambda: _stream_groq_culture(prompt))


async def _stream_groq_culture(prompt: str):
    """Groq cloud 모델로 문화공간 추천 스트리밍"""
    import httpx
    system = "당신은 친근한 문화 큐레이터입니다. 날씨·대기질·만세력을 종합해 딱 한 곳만 추천하세요. 반드시 명소명을 포함해 자연스러운 문장으로 응답하세요."
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 512,
                    "stream": True,
                },
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    yield f"data: {json.dumps({'error': error_body.decode()[:200]})}\n\n"
                    return

                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:].strip()
                        if chunk == "[DONE]":
                            yield f"data: {json.dumps({'text': '', 'done': True})}\n\n"
                            yield "data: [DONE]\n\n"
                            return
                        try:
                            delta = json.loads(chunk)
                            content = delta.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield f"data: {json.dumps({'text': content})}\n\n"
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)[:200]})}\n\n"
