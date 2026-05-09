from __future__ import annotations

import json
from enum import Enum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings

router = APIRouter(prefix="/consult", tags=["상담분석"])


class ConsultCategory(str, Enum):
    """상담 카테고리"""
    CAREER = "career"            # 사업운 / 직장운
    LOVE = "love"                # 연애운 / 결혼운
    HEALTH = "health"            # 건강운
    RELATIONSHIP = "relationship"  # 대인관계
    FINANCE = "finance"          # 재물운
    STUDY = "study"              # 학업 / 적성
    FAMILY = "family"            # 가족운
    FORTUNE = "fortune"          # 총운 / 올해 운세
    CUSTOM = "custom"            # 자유주제


CATEGORY_PROMPTS = {
    "career": "사용자의 사주를 분석하여 직장운, 사업운, 진로 방향에 대해 상담해주세요. 적성에 맞는 직업군, 유리한 시기, 주의할 점을 포함해주세요.",
    "love": "사용자의 사주를 분석하여 연애운, 결혼운, 이성관계에 대해 상담해주세요. 성격적 특징, 궁합이 잘 맞는 상대상, 관계에서 주의할 점을 포함해주세요.",
    "health": "사용자의 사주를 분석하여 건강운에 대해 상담해주세요. 특히 주의해야 할 신체 부위나 질환, 건강 관리 방법을 포함해주세요.",
    "relationship": "사용자의 사주를 분석하여 대인관계에 대해 상담해주세요. 인간관계에서의 장단점, 주의할 점, 조언을 포함해주세요.",
    "finance": "사용자의 사주를 분석하여 재물운, 돈과 관련된 운세에 대해 상담해주세요. 재테크 방향, 유리한 시기, 주의할 점을 포함해주세요.",
    "study": "사용자의 사주를 분석하여 학업운, 적성, 공부 방향에 대해 상담해주세요. 잘 맞는 학습 방법, 유리한 분야를 포함해주세요.",
    "family": "사용자의 사주를 분석하여 가족운, 가정환경에 대해 상담해주세요. 가족 관계에서의 조언을 포함해주세요.",
    "fortune": "사용자의 현재 사주(세운)를 분석하여 올해의 전체적인 운세 흐름에 대해 상담해주세요. 기회가 되는 시기와 주의할 점을 포함해주세요.",
    "custom": "",
}


class ConsultRequest(BaseModel):
    google_id: str
    category: ConsultCategory = Field(default="custom")
    question: str = ""
    saju_result: dict | None = None


@router.post("/analyze")
async def consult_analyze(req: ConsultRequest):
    from app.core.database import get_pool

    # 사주 데이터 준비
    saju = req.saju_result
    if not saju:
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT saju_data, birth_year, birth_month, birth_day, "
                    "birth_hour, birth_minute, gender, name "
                    "FROM users WHERE google_id = %s LIMIT 1",
                    (req.google_id,),
                )
                row = await cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

        columns = [
            "saju_data", "birth_year", "birth_month", "birth_day",
            "birth_hour", "birth_minute", "gender", "name",
        ]
        user = dict(zip(columns, row))
        if user.get("saju_data"):
            saju = (
                json.loads(user["saju_data"])
                if isinstance(user["saju_data"], str)
                else user["saju_data"]
            )

    if not saju:
        raise HTTPException(status_code=400, detail="사주 데이터가 없습니다. 먼저 사주를 계산해주세요.")

    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")

    # 카테고리별 프롬프트
    category_instruction = CATEGORY_PROMPTS.get(req.category.value, "")

    # 사용자 추가 질문
    extra_question = f"\n\n사용자의 추가 질문: {req.question}" if req.question else ""

    system_prompt = """당신은 사주명리 기반 심리상담사입니다.
사용자의 사주 정보(4주, 십신, 오행)를 바탕으로 전문적인 심리상담을 제공합니다.

다음 규칙을 따라주세요:
1. 사주 분석을 바탕으로 심리적 특징과 조언을 제공
2. 지나치게 운명론적인 표현은 피하고, 심리학적 관점을 함께 제시
3. 존댓말을 사용하고, 따뜻하고 공감적인 톤 유지
4. 500자 이내로 간결하게 답변"""

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
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 1000,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Groq API 오류: {resp.status_code} {resp.text[:200]}",
        )

    data = resp.json()
    answer = data["choices"][0]["message"]["content"]

    return {
        "category": req.category.value,
        "answer": answer,
        "model": settings.GROQ_MODEL,
    }
