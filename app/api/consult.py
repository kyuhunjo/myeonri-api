from __future__ import annotations
import logging
logger = logging.getLogger("myeonri-api")

import json
from enum import Enum
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import settings

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
    CUSTOM = "custom"


CATEGORY_PROMPTS = {
    "career": "직장과 진로에 대해 봅니다. 타고난 기질과 재능, 일에서의 강점을 짚어주고 지금 시기 방향을 제시해주세요.",
    "love": "연애와 인연에 대해 봅니다. 성격적 특징과 관계 패턴, 잘 맞는 상대상과 주의할 점을 말해주세요.",
    "health": "건강에 대해 봅니다. 체질적으로 주의할 부위나 시기, 일상에서 실천할 관리법을 말해주세요.",
    "relationship": "대인관계에 대해 봅니다. 인간관계에서의 성향과 장단점, 더 나은 관계를 위한 조언을 해주세요.",
    "finance": "재물과 돈에 대해 봅니다. 재물운의 흐름과 성향, 유리한 시기와 방향을 말해주세요.",
    "study": "학업과 공부에 대해 봅니다. 잘 맞는 학습 방식과 분야, 집중력과 이해력 패턴을 살펴보고 조언해주세요.",
    "family": "가족과 가정에 대해 봅니다. 가족 관계에서의 역할과 성향, 더 편안한 관계를 위한 조언을 해주세요.",
    "fortune": "올해 전체 운세 흐름에 대해 봅니다. 세운과 대운을 고려하여 기회와 주의할 점을 말해주세요.",
    "custom": "",
}

SYSTEM_PROMPT = """당신은 사주명리 기반 심리상담사입니다. 사주 정보(4주, 십신, 오행)를 바탕으로 심리적 통찰과 조언을 제공합니다.

규칙:
- 인사말 없이 바로 본문 시작
- 마지막에 추가 질문 유도하지 말고 자연스럽게 마무리
- 3~5문장, 300자 내외로 간결하게
- 존댓말, 따뜻하고 공감적인 톤"""


class ConsultRequest(BaseModel):
    google_id: str
    category: ConsultCategory = Field(default="custom")
    question: str = ""
    saju_result: dict | None = None


async def _get_saju_data(req: ConsultRequest) -> dict:
    """사주 데이터 조회 (파라미터 or DB)"""
    saju = req.saju_result
    if saju:
        return saju

    from app.core.database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT saju_data FROM users WHERE google_id = %s LIMIT 1",
                (req.google_id,),
            )
            row = await cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    saju = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    if not saju:
        raise HTTPException(status_code=400, detail="사주 데이터가 없습니다. 먼저 사주를 계산해주세요.")
    return saju


@router.post("/analyze")
async def consult_analyze(req: ConsultRequest):
    """상담 분석 (비스트리밍, 기존 유지)"""
    saju = await _get_saju_data(req)
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")

    category_instruction = CATEGORY_PROMPTS.get(req.category.value, "")
    extra_question = f"\n\n사용자의 추가 질문: {req.question}" if req.question else ""

    user_prompt = f"""사주 정보: {json.dumps(saju, ensure_ascii=False, indent=2)}

상담 주제: {category_instruction}{extra_question}

사주 정보를 바탕으로 상담 답변을 해주세요."""

    import httpx

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 2048,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Groq API 오류: {resp.status_code} {resp.text[:200]}")

    data = resp.json()
    return {"category": req.category.value, "answer": data["choices"][0]["message"]["content"], "model": settings.GROQ_MODEL}


async def _stream_groq(saju: dict, req: ConsultRequest) -> AsyncGenerator[str, None]:
    """Groq 스트리밍 응답을 SSE 형식으로 변환"""
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
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
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


@router.post("/analyze/stream")
async def consult_analyze_stream(req: ConsultRequest):
    """상담 분석 (SSE 스트리밍)"""
    saju = await _get_saju_data(req)
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")

    return StreamingResponse(
        _stream_groq(saju, req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
