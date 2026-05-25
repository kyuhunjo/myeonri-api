"""
상담 분석 엔드포인트
- POST /consult/analyze (비스트리밍)
- POST /consult/analyze/stream (SSE 스트리밍)
"""
from __future__ import annotations
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.api.consult import ConsultRequest, _get_saju_data, _stream_groq, CATEGORY_PROMPTS, SYSTEM_PROMPT

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/consult", tags=["상담분석"])


@router.post("/analyze")
async def consult_analyze(req: ConsultRequest):
    """상담 분석 (비스트리밍)"""
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
    return {
        "category": req.category.value,
        "answer": data["choices"][0]["message"]["content"],
        "model": settings.GROQ_MODEL,
    }


@router.post("/analyze/stream")
async def consult_analyze_stream(req: ConsultRequest):
    """카테고리 상담 분석 (SSE 스트리밍)"""
    saju = await _get_saju_data(req)
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")

    return StreamingResponse(
        _stream_groq(saju, req, override_temperature=req.temperature),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
