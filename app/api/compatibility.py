"""
궁합 분석 API
두 사람의 사주 데이터 비교 + Groq 스트리밍
"""

from __future__ import annotations
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.utils.saju import get_sibsin, calc_compatibility

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/consult", tags=["궁합"])

COMPAT_SYSTEM_PROMPT = """당신은 사주명리 기반 심리상담사입니다. 두 사람의 사주를 비교하여 궁합을 분석합니다.

규칙:
- 인사말 없이 바로 본문 시작
- 마지막에 추가 질문 유도하지 말고 자연스럽게 마무리
- 500~700자로 충실하게, 따뜻하고 공감적인 어조로
- 존댓말 사용"""


class CompatibilityRequest(BaseModel):
    saju_a: dict
    saju_b: dict
    name_a: str = "A"
    name_b: str = "B"


async def _stream_compatibility(
    saju_a: dict, saju_b: dict,
    name_a: str, name_b: str,
    compat: dict,
) -> AsyncGenerator[str, None]:
    """궁합 분석 Groq 스트리밍"""
    day_stem_a = compat["day_stem_a"]
    day_stem_b = compat["day_stem_b"]
    stem_relation = get_sibsin(day_stem_a, day_stem_b) if day_stem_a and day_stem_b else ""
    stem_relation_rev = get_sibsin(day_stem_b, day_stem_a) if day_stem_b and day_stem_a else ""

    user_prompt = f"""[A님 사주]
{json.dumps(saju_a, ensure_ascii=False, indent=2)}

[B님 사주]
{json.dumps(saju_b, ensure_ascii=False, indent=2)}

[궁합 분석 결과]
- 점수: {compat['score']}점 / 100점
- 등급: {compat['grade']}
- {name_a}의 일간: {day_stem_a}({compat['stem_element_a']}) · {name_b}의 일간: {day_stem_b}({compat['stem_element_b']})
- {name_a}의 일지: {compat['day_branch_a']}({compat['branch_element_a']}) · {name_b}의 일지: {compat['day_branch_b']}({compat['branch_element_b']})
- 일간 관계: {name_a}가 보는 {name_b} → {stem_relation}, {name_b}가 보는 {name_a} → {stem_relation_rev}

두 사람의 사주를 비교하여 궁합을 상세히 분석해주세요. 일간과 일지의 오행 관계, 십신 관계를 바탕으로 서로에게 주는 영향, 잘 맞는 점, 주의할 점, 관계 발전을 위한 조언을 포함해주세요."""

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
                        {"role": "system", "content": COMPAT_SYSTEM_PROMPT},
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


@router.post("/compatibility")
async def consult_compatibility(req: CompatibilityRequest):
    """궁합 분석 (SSE 스트리밍 + 점수)"""
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")

    compat = calc_compatibility(req.saju_a, req.saju_b)

    async def event_stream():
        yield f"data: {json.dumps({'meta': compat})}\n\n"
        async for chunk in _stream_compatibility(
            req.saju_a, req.saju_b,
            req.name_a, req.name_b,
            compat,
        ):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
