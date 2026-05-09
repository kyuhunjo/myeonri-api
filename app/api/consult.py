from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/consult", tags=["상담분석"])


class ConsultRequest(BaseModel):
    google_id: str
    question: str
    saju_result: dict | None = None  # 사주 데이터 (없으면 DB에서 조회)


@router.post("/analyze")
async def consult_analyze(req: ConsultRequest):
    """
    상담 분석 — Groq API (Llama)를 통해 사주 기반 심리 분석
    """
    from app.core.database import get_pool

    # 사주 데이터 준비
    saju = req.saju_result
    if not saju:
        # 사용자 DB에서 사주 데이터 조회
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

        columns = ["saju_data", "birth_year", "birth_month", "birth_day",
                    "birth_hour", "birth_minute", "gender", "name"]
        user = dict(zip(columns, row))
        if user.get("saju_data"):
            saju = json.loads(user["saju_data"]) if isinstance(user["saju_data"], str) else user["saju_data"]

    if not saju:
        raise HTTPException(status_code=400, detail="사주 데이터가 없습니다. 먼저 사주를 계산해주세요.")

    # Groq API 호출
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")

    import httpx

    system_prompt = """당신은 사주명리 기반 심리상담사입니다.
사용자의 사주 정보(4주, 십신, 오행)를 바탕으로 전문적인 심리상담을 제공합니다.

다음 규칙을 따라주세요:
1. 사주 분석을 바탕으로 심리적 특징과 조언을 제공
2. 지나치게 운명론적인 표현은 피하고, 심리학적 관점을 함께 제시
3. 존댓말을 사용하고, 따뜻하고 공감적인 톤 유지
4. 500자 이내로 간결하게 답변"""

    user_prompt = f"""사주 정보: {json.dumps(saju, ensure_ascii=False, indent=2)}

질문: {req.question}

사주 정보를 바탕으로 심리상담 답변을 해주세요."""

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
        "answer": answer,
        "model": settings.GROQ_MODEL,
    }
