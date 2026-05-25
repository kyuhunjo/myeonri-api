"""
공통 상담 분석 모듈
- ConsultCategory, ConsultRequest, _get_saju_data
- CATEGORY_PROMPTS, SYSTEM_PROMPT
- _stream_groq (Groq SSE 스트리밍 공통 함수)
"""
from __future__ import annotations
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
