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
- 3~5문장, 300자 내외로 간결하게
- 존댓말, 따뜻하고 공감적인 톤"""


class DailyFortuneRequest(BaseModel):
    google_id: str
    saju_result: dict | None = None


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


async def _stream_daily_groq(saju: dict) -> AsyncGenerator[str, None]:
    """오늘의 운세 전용 Groq 스트리밍 (DB에서 오늘 일진 조회 후 일진 기준 분석)"""
    from app.core.database import get_pool
    from app.utils.saju import get_sibsin, get_sibsin_for_branch, HEAVENLY_BY_HANJA, EARTHLY_BY_HANJA

    # ── 오늘 일진 데이터 DB에서 조회 ──
    from datetime import datetime, timezone
    import datetime as dt
    now = datetime.now(timezone.utc).astimezone()
    kst_now = now.replace(tzinfo=None) + dt.timedelta(hours=9)
    year = kst_now.year
    month = kst_now.month
    day = kst_now.day
    weekdays = ["일요일", "월요일", "화요일", "수요일", "목요일", "금요일", "토요일"]
    weekday_str = weekdays[kst_now.weekday()]

    iljin = None
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT cd_hdganjee, cd_kdganjee, cd_hyganjee, cd_kyganjee, "
                "cd_lm, cd_ld, cd_sol_plan, cd_kterms, cd_ddi "
                "FROM calenda_data_fixed "
                "WHERE cd_sy = %s AND cd_sm = %s AND cd_sd = %s "
                "LIMIT 1",
                (year, month, day),
            )
            row = await cur.fetchone()

    if row:
        iljin = {
            "hdganjee": row[0],
            "kdganjee": row[1],
            "hyganjee": row[2],
            "kyganjee": row[3],
            "lm": row[4],
            "ld": row[5],
            "sol_plan": row[6],
            "kterms": row[7],
            "ddi": row[8],
        }

    if not iljin:
        yield f"data: {json.dumps({'error': '오늘의 일진 데이터를 찾을 수 없습니다'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # ── 사용자의 일간 정보 추출 ──
    hanja_pillars = saju.get("hanja", {}) if isinstance(saju.get("hanja"), dict) else {}
    ilju = hanja_pillars.get("ilju", "")
    day_stem_hanja = ilju[0] if ilju and len(ilju) >= 1 else ""

    stems_hanja_to_kr = {"甲":"갑","乙":"을","丙":"병","丁":"정","戊":"무","己":"기","庚":"경","辛":"신","壬":"임","癸":"계"}
    branches_hanja_to_kr = {"子":"자","丑":"축","寅":"인","卯":"묘","辰":"진","巳":"사","午":"오","未":"미","申":"신","酉":"유","戌":"술","亥":"해"}
    elements_map = {"갑":"목","을":"목","병":"화","정":"화","무":"토","기":"토","경":"금","신":"금","임":"수","계":"수"}

    day_stem_kr = stems_hanja_to_kr.get(day_stem_hanja, "")
    day_stem_elem = elements_map.get(day_stem_kr, "")

    # ── 오늘 일진의 천간/지지 ──
    hd = iljin.get("hdganjee", "")
    kd = iljin.get("kdganjee", "")
    today_stem_hanja = hd[0] if hd and len(hd) >= 1 else ""
    today_branch_hanja = hd[1] if hd and len(hd) >= 2 else ""
    today_stem_kr = stems_hanja_to_kr.get(today_stem_hanja, "")
    today_stem_elem = elements_map.get(today_stem_kr, "")
    today_branch_kr = branches_hanja_to_kr.get(today_branch_hanja, "")
    branch_elem = EARTHLY_BY_HANJA.get(today_branch_hanja, {}).get("element", "") if today_branch_hanja else ""

    # ── 십신 관계 계산 ──
    stem_sibsin = ""
    branch_sibsin = ""
    if day_stem_hanja and today_stem_hanja:
        stem_sibsin = get_sibsin(day_stem_hanja, today_stem_hanja)
    if day_stem_hanja and today_branch_hanja:
        branch_sibsin = get_sibsin_for_branch(day_stem_hanja, today_branch_hanja)

    # ── SSE 시작: 십신 메타데이터 먼저 전송 ──
    meta = {
        "day_stem_hanja": day_stem_hanja,
        "day_stem_kr": day_stem_kr,
        "today_stem_hanja": today_stem_hanja,
        "today_stem_kr": today_stem_kr,
        "today_branch_hanja": today_branch_hanja,
        "today_branch_kr": today_branch_kr,
        "stem_sibsin": stem_sibsin,
        "branch_sibsin": branch_sibsin,
    }
    yield f"data: {json.dumps({'meta': meta})}\n\n"

    # ── 프롬프트 구성 ──
    user_prompt = f"""[사용자 사주]
일간: {day_stem_hanja}({day_stem_kr}) · 오행: {day_stem_elem}

[오늘의 일진 - {year}년 {month}월 {day}일 {weekday_str}]
일진: {hd}({kd})
천간: {today_stem_hanja}({today_stem_kr}) · 오행: {today_stem_elem} → 나와의 관계: {stem_sibsin}
지지: {today_branch_hanja}({today_branch_kr}) · 오행: {branch_elem} → 나와의 관계: {branch_sibsin}
음력: {iljin.get('lm','')}월 {iljin.get('ld','')}일

오늘의 일진(천간+지지)이 나(일간)에게 어떤 의미인지 분석해주세요. 일진의 천간은 나에게 {stem_sibsin}이 되고, 지지는 나에게 {branch_sibsin}이 됩니다. 이 관계를 바탕으로 오늘 하루의 운세를 풀이해주세요."""

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


async def _stream_groq(saju: dict, req: ConsultRequest) -> AsyncGenerator[str, None]:
    """카테고리 상담 스트리밍"""
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
    """카테고리 상담 분석 (SSE 스트리밍)"""
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


@router.post("/daily")
async def consult_daily(req: DailyFortuneRequest):
    """오늘의 운세 (일진 기준, SSE 스트리밍)"""
    saju = req.saju_result
    if not saju:
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
            raise HTTPException(status_code=400, detail="사주 데이터가 없습니다.")

    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")

    return StreamingResponse(
        _stream_daily_groq(saju),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
