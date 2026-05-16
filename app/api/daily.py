"""
오늘의 운세 API
일진 + 대운 + 년운/월운 기준 사용자 사주 분석 → Groq 스트리밍
"""

from __future__ import annotations
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_pool
from app.utils.saju import (
    get_sibsin, get_sibsin_for_branch, EARTHLY_BY_HANJA,
)

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/consult", tags=["오늘의운세"])

SYSTEM_PROMPT = """당신은 사주명리 기반 심리상담사입니다. 사주 원국, 대운, 년운, 월운, 일진 정보를 종합하여 오늘 하루의 운세를 분석합니다.

규칙:
- 인사말 없이 바로 본문 시작
- 마지막에 추가 질문 유도하지 말고 자연스럽게 마무리
- 600~800자로 충실하게, 따뜻하고 공감적인 어조로
- 존댓말 사용"""


class DailyFortuneRequest(BaseModel):
    google_id: str
    saju_result: dict | None = None
    today_data: dict | None = None
    current_daeun: dict | None = None
    temperature: float | None = None
    google_id: str
    saju_result: dict | None = None
    today_data: dict | None = None
    current_daeun: dict | None = None


async def _stream_daily_groq(saju: dict, today_data: dict | None = None, current_daeun: dict | None = None, temperature: float | None = None) -> AsyncGenerator[str, None]:
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
                "SELECT cd_hyganjee, cd_kyganjee, cd_hmganjee, cd_kmganjee, "
                "cd_hdganjee, cd_kdganjee, "
                "cd_lm, cd_ld, cd_sol_plan, cd_kterms, cd_ddi "
                "FROM calenda_data_fixed "
                "WHERE cd_sy = %s AND cd_sm = %s AND cd_sd = %s "
                "LIMIT 1",
                (year, month, day),
            )
            row = await cur.fetchone()

    if row:
        iljin = {
            "hyganjee": row[0], "kyganjee": row[1],
            "hmganjee": row[2], "kmganjee": row[3],
            "hdganjee": row[4], "kdganjee": row[5],
            "lm": row[6], "ld": row[7],
            "sol_plan": row[8], "kterms": row[9], "ddi": row[10],
        }

    if not iljin:
        yield f"data: {json.dumps({'error': '오늘의 일진 데이터를 찾을 수 없습니다'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    hanja_pillars = saju.get("hanja", {}) if isinstance(saju.get("hanja"), dict) else {}
    ilju = hanja_pillars.get("ilju", "")
    day_stem_hanja = ilju[0] if ilju and len(ilju) >= 1 else ""

    stems_hanja_to_kr = {"甲":"갑","乙":"을","丙":"병","丁":"정","戊":"무","己":"기","庚":"경","辛":"신","壬":"임","癸":"계"}
    branches_hanja_to_kr = {"子":"자","丑":"축","寅":"인","卯":"묘","辰":"진","巳":"사","午":"오","未":"미","申":"신","酉":"유","戌":"술","亥":"해"}
    elements_map = {"갑":"목","을":"목","병":"화","정":"화","무":"토","기":"토","경":"금","신":"금","임":"수","계":"수"}

    day_stem_kr = stems_hanja_to_kr.get(day_stem_hanja, "")
    day_stem_elem = elements_map.get(day_stem_kr, "")

    # 일진 (한자 기준)
    hd = iljin.get("hdganjee", "")
    kd = iljin.get("kdganjee", "")
    today_stem_hanja = hd[0] if hd and len(hd) >= 1 else ""
    today_branch_hanja = hd[1] if hd and len(hd) >= 2 else ""
    today_stem_kr = stems_hanja_to_kr.get(today_stem_hanja, "")
    today_stem_elem = elements_map.get(today_stem_kr, "")
    today_branch_kr = branches_hanja_to_kr.get(today_branch_hanja, "")
    branch_elem = EARTHLY_BY_HANJA().get(today_branch_hanja, {}).get("element", "") if today_branch_hanja else ""

    stem_sibsin = ""
    branch_sibsin = ""
    if day_stem_hanja and today_stem_hanja:
        stem_sibsin = get_sibsin(day_stem_hanja, today_stem_hanja)
    if day_stem_hanja and today_branch_hanja:
        branch_sibsin = get_sibsin_for_branch(day_stem_hanja, today_branch_hanja)

    # 년주 (한자)
    hy = iljin.get("hyganjee", "")
    year_stem_hanja = hy[0] if hy and len(hy) >= 1 else ""
    year_branch_hanja = hy[1:] if hy and len(hy) >= 2 else ""
    year_stem_kr = stems_hanja_to_kr.get(year_stem_hanja, "")
    year_branch_kr = branches_hanja_to_kr.get(year_branch_hanja, "")

    # 월주 (한자)
    hm = iljin.get("hmganjee", "")
    month_stem_hanja = hm[0] if hm and len(hm) >= 1 else ""
    month_branch_hanja = hm[1:] if hm and len(hm) >= 2 else ""
    month_stem_kr = stems_hanja_to_kr.get(month_stem_hanja, "")
    month_branch_kr = branches_hanja_to_kr.get(month_branch_hanja, "")

    # 대운 정보
    daeun_str = "없음"
    daeun_current = saju.get("ssaju", {}).get("daeun", {}).get("current", {})
    if current_daeun:
        daeun_current = current_daeun
    if daeun_current:
        dg = daeun_current.get("ganzhi", "")
        ds = daeun_current.get("stemTenGod", "")
        db = daeun_current.get("branchTenGod", "")
        start = daeun_current.get("startAge", "")
        end = daeun_current.get("endAge", "")
        if dg:
            daeun_str = f"{dg} (십신: {ds}/{db}, {start}~{end}세)"

    # 메타 전송
    meta = {
        "day_stem_hanja": day_stem_hanja, "day_stem_kr": day_stem_kr,
        "today_stem_hanja": today_stem_hanja, "today_stem_kr": today_stem_kr,
        "today_branch_hanja": today_branch_hanja, "today_branch_kr": today_branch_kr,
        "stem_sibsin": stem_sibsin, "branch_sibsin": branch_sibsin,
        "year_stem_hanja": year_stem_hanja, "year_stem_kr": year_stem_kr,
        "year_branch_hanja": year_branch_hanja, "year_branch_kr": year_branch_kr,
        "month_stem_hanja": month_stem_hanja, "month_stem_kr": month_stem_kr,
        "month_branch_hanja": month_branch_hanja, "month_branch_kr": month_branch_kr,
        "daeun_ganzhi": daeun_current.get("ganzhi", "") if daeun_current else "",
        "daeun_stem_ten_god": daeun_current.get("stemTenGod", "") if daeun_current else "",
    }
    yield f"data: {json.dumps({'meta': meta})}\n\n"

    # 십신 관계
    year_stem_sibsin = get_sibsin(day_stem_hanja, year_stem_hanja) if day_stem_hanja and year_stem_hanja else ""
    year_branch_sibsin = get_sibsin_for_branch(day_stem_hanja, year_branch_hanja) if day_stem_hanja and year_branch_hanja else ""
    month_stem_sibsin = get_sibsin(day_stem_hanja, month_stem_hanja) if day_stem_hanja and month_stem_hanja else ""
    month_branch_sibsin = get_sibsin_for_branch(day_stem_hanja, month_branch_hanja) if day_stem_hanja and month_branch_hanja else ""

    user_prompt = f"""[사용자 사주]
일간: {day_stem_hanja}({day_stem_kr}) · 오행: {day_stem_elem}

[현재 대운]
{year}년 현재 대운: {daeun_str}

[년운 - {year}년]
년주(한자): {hy}
천간: {year_stem_hanja}({year_stem_kr}) → 나와의 관계: {year_stem_sibsin}
지지: {year_branch_hanja}({year_branch_kr}) → 나와의 관계: {year_branch_sibsin}

[월운 - {year}년 {month}월]
월주(한자): {hm}
천간: {month_stem_hanja}({month_stem_kr}) → 나와의 관계: {month_stem_sibsin}
지지: {month_branch_hanja}({month_branch_kr}) → 나와의 관계: {month_branch_sibsin}

[오늘의 일진 - {year}년 {month}월 {day}일 {weekday_str}]
일진: {hd}({kd})
천간: {today_stem_hanja}({today_stem_kr}) · 오행: {today_stem_elem} → 나와의 관계: {stem_sibsin}
지지: {today_branch_hanja}({today_branch_kr}) · 오행: {branch_elem} → 나와의 관계: {branch_sibsin}
음력: {iljin.get('lm','')}월 {iljin.get('ld','')}일

오늘의 운세를 분석할 때 대운과 년운, 월운의 큰 흐름을 먼저 고려하고, 일진이 그 흐름 속에서 어떤 의미를 가지는지 종합적으로 분석해주세요. 대운과 년운이 현재 삶의 큰 방향을 결정하고, 월운이 최근의 흐름을, 일진이 오늘 하루의 구체적인 에너지를 나타냅니다.

다음 항목을 모두 포함해주세요 (2~3문장씩):

💼 **사업/직장운** — 오늘 일의 흐름, 집중력, 의사결정에 관한 조언
💰 **재물운** — 금전의 흐름, 소비/저축 패턴
❤️ **연애/인연운** — 감정의 기복, 상대와의 교류, 인연의 기운
🏥 **건강운** — 체력, 컨디션, 주의할 신체 부위
🤝 **대인관계** — 주변 사람들과의 소통, 협력, 충돌 가능성
📚 **학업/적성** — 배움과 성장의 기회, 집중력, 아이디어

마지막에 오늘을 위한 한 줄 조언과 함께 "당신의 하루가 빛나길 바랍니다"로 마무리해주세요."""

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
                    "temperature": temperature if temperature is not None else 0.7,
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


@router.post("/daily")
async def consult_daily(req: DailyFortuneRequest):
    """오늘의 운세 (대운 + 년운/월운 + 일진 통합, SSE 스트리밍)"""
    saju = req.saju_result
    if not saju:
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
            raise HTTPException(status_code=400, detail="사주 데이터가 없습니다.")

    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")

    return StreamingResponse(
        _stream_daily_groq(saju, req.today_data, req.current_daeun, req.temperature),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
