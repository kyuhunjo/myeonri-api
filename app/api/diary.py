"""
사주 일기 API
— 사용자가 고민/심리상태 입력 → AI가 분석 → 태그 저장
— 목록 조회/상세/삭제
"""

from __future__ import annotations
import json
import logging
import re
from datetime import date, datetime
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.database import get_pool
from app.utils.saju import (
    get_sibsin, get_sibsin_for_branch, EARTHLY_BY_HANJA,
)

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/diary", tags=["사주일기"])

SYSTEM_PROMPT = """당신은 사주명리 기반 심리상담사입니다. 사주 정보(4주, 십신, 오행)를 바탕으로 심리적 통찰과 조언을 제공합니다.

규칙:
- 인사말 없이 바로 본문 시작
- 마지막에 추가 질문 유도하지 말고 자연스럽게 마무리
- 300~500자로 간결하게
- 공감적인 어조로, 존댓말 사용
- 사용자의 고민이나 질문에 집중해서 답변
- 분석은 일간(나)과 오늘의 일진 관계(십신)를 중심으로
- 답변 마지막에 반드시 "핵심 키워드:"로 시작하는 태그 라인을 추가 (키워드는 2~4개, 쉼표 구분)"""


# ── Request / Response Models ──

class DiaryWriteRequest(BaseModel):
    google_id: str = ""
    content: str
    tags: list[str] = Field(default_factory=list)
    analysis_result: str = ""
    saju_result: dict | None = None


class DiaryListRequest(BaseModel):
    google_id: str = ""
    tag: str = ""
    page: int = 1
    limit: int = 20


class DiaryDeleteRequest(BaseModel):
    google_id: str = ""
    diary_id: int


class DiaryResponse(BaseModel):
    id: int
    content: str
    analysis_result: str | dict | None
    tags: list[str]
    created_date: str
    created_at: str


# ── Helpers ──

async def _get_user_id(pool, google_id: str) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM users WHERE google_id = %s LIMIT 1", (google_id,))
            row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    return row[0]


def _extract_tags(text: str) -> list[str]:
    """AI 응답에서 '핵심 키워드:' 라인을 찾아 태그 추출"""
    match = re.search(r'핵심\s*키워드\s*:\s*(.+)', text)
    if match:
        tags = [t.strip() for t in match.group(1).split(',') if t.strip()]
        if tags:
            return tags
    return []


def _clean_analysis_text(text: str) -> str:
    """AI 응답에서 태그 라인 제거"""
    return re.sub(r'\n*핵심\s*키워드\s*:.*$', '', text, flags=re.MULTILINE).strip()


# ── AI 분석 스트리밍 ──

async def _stream_diary_groq(saju: dict, content: str) -> AsyncGenerator[str, None]:
    """사주 일기 Groq 스트리밍"""
    from app.core.database import get_pool
    from datetime import datetime, timezone
    import datetime as dt

    now = datetime.now(timezone.utc).astimezone()
    kst_now = now.replace(tzinfo=None) + dt.timedelta(hours=9)
    year = kst_now.year
    month = kst_now.month
    day = kst_now.day
    weekdays = ["일요일", "월요일", "화요일", "수요일", "목요일", "금요일", "토요일"]
    weekday_str = weekdays[kst_now.weekday()]

    # 오늘 일진 조회
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
            "hdganjee": row[0], "kdganjee": row[1],
            "hyganjee": row[2], "kyganjee": row[3],
            "lm": row[4], "ld": row[5],
            "sol_plan": row[6], "kterms": row[7], "ddi": row[8],
        }

    hanja_pillars = saju.get("hanja", {}) if isinstance(saju.get("hanja"), dict) else {}
    ilju = hanja_pillars.get("ilju", "")
    day_stem_hanja = ilju[0] if ilju and len(ilju) >= 1 else ""

    stems_hanja_to_kr = {"甲":"갑","乙":"을","丙":"병","丁":"정","戊":"무","己":"기","庚":"경","辛":"신","壬":"임","癸":"계"}
    branches_hanja_to_kr = {"子":"자","丑":"축","寅":"인","卯":"묘","辰":"진","巳":"사","午":"오","未":"미","申":"신","酉":"유","戌":"술","亥":"해"}
    elements_map = {"갑":"목","을":"목","병":"화","정":"화","무":"토","기":"토","경":"금","신":"금","임":"수","계":"수"}

    day_stem_kr = stems_hanja_to_kr.get(day_stem_hanja, "")
    day_stem_elem = elements_map.get(day_stem_kr, "")

    today_stem_sibsin = ""
    today_branch_sibsin = ""
    hd = iljin.get("hdganjee", "") if iljin else ""
    kd = iljin.get("kdganjee", "") if iljin else ""
    today_stem_hanja = hd[0] if hd and len(hd) >= 1 else ""
    today_branch_hanja = hd[1] if hd and len(hd) >= 2 else ""
    today_stem_kr = stems_hanja_to_kr.get(today_stem_hanja, "")
    today_stem_elem = elements_map.get(today_stem_kr, "")
    today_branch_kr = branches_hanja_to_kr.get(today_branch_hanja, "")
    branch_elem = EARTHLY_BY_HANJA().get(today_branch_hanja, {}).get("element", "") if today_branch_hanja else ""

    if day_stem_hanja and today_stem_hanja:
        today_stem_sibsin = get_sibsin(day_stem_hanja, today_stem_hanja)
    if day_stem_hanja and today_branch_hanja:
        today_branch_sibsin = get_sibsin_for_branch(day_stem_hanja, today_branch_hanja)

    today_str = f"{year}년 {month}월 {day}일 {weekday_str}"

    user_prompt = f"""[사용자 사주]
일간: {day_stem_hanja}({day_stem_kr}) · 오행: {day_stem_elem}

[오늘 - {today_str}]
일진: {hd}({kd})
천간: {today_stem_hanja}({today_stem_kr}) · 오행: {today_stem_elem} → 나와의 관계: {today_stem_sibsin}
지지: {today_branch_hanja}({today_branch_kr}) · 오행: {branch_elem} → 나와의 관계: {today_branch_sibsin}

[사용자의 오늘 고민/생각]
{content}

위 사용자의 일간(나)과 오늘의 기운(일진) 관계를 고려하여, 사용자의 고민에 대한 공감과 조언을 해주세요. 답변 마지막에 반드시 "핵심 키워드:"로 시작하는 줄을 추가해 관련 태그 2~4개를 쉼표로 구분해주세요."""

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
                    "max_tokens": 1024,
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
                            content_chunk = delta.get("content", "")
                            if content_chunk:
                                yield f"data: {json.dumps({'text': content_chunk})}\n\n"
                        except (json.JSONDecodeError, KeyError):
                            continue
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)[:200]})}\n\n"
    finally:
        yield "data: [DONE]\n\n"


# ── API Endpoints ──

@router.post("/analyze/stream")
async def diary_analyze_stream(req: DiaryWriteRequest):
    """사주 일기 AI 분석 (SSE 스트리밍)"""
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
        _stream_diary_groq(saju, req.content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/save")
async def diary_save(req: DiaryWriteRequest):
    """사주 일기 저장 (분석 결과와 태그 포함)"""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="내용을 입력해주세요.")

    pool = await get_pool()
    user_id = await _get_user_id(pool, req.google_id)

    # 사주 스냅샷 저장
    saju = req.saju_result
    if not saju:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT sp.saju_data FROM users u "
                    "JOIN saju_profiles sp ON sp.user_id = u.id AND sp.is_primary = 1 "
                    "WHERE u.google_id = %s LIMIT 1",
                    (req.google_id,),
                )
                row = await cur.fetchone()
        if row:
            saju = json.loads(row[0]) if isinstance(row[0], str) else row[0]

    # 오늘 일진 데이터 조회
    today_data = None
    from datetime import datetime, timezone
    import datetime as dt
    now = datetime.now(timezone.utc).astimezone()
    kst_now = now.replace(tzinfo=None) + dt.timedelta(hours=9)

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT cd_hdganjee, cd_kdganjee, cd_lm, cd_ld, cd_ddi "
                "FROM calenda_data_fixed "
                "WHERE cd_sy = %s AND cd_sm = %s AND cd_sd = %s LIMIT 1",
                (kst_now.year, kst_now.month, kst_now.day),
            )
            row = await cur.fetchone()
    if row:
        today_data = {
            "hdganjee": row[0], "kdganjee": row[1],
            "lm": row[2], "ld": row[3], "ddi": row[4],
        }

    tags_json = json.dumps(req.tags, ensure_ascii=False)
    # analysis_result: 문자열이면 그냥 저장, dict/json이면 json.dumps
    if isinstance(req.analysis_result, str):
        analysis_json = req.analysis_result.strip() if req.analysis_result else None
    elif req.analysis_result:
        analysis_json = json.dumps(req.analysis_result, ensure_ascii=False)
    else:
        analysis_json = None
    saju_snapshot_json = json.dumps(saju, ensure_ascii=False) if saju else None
    today_data_json = json.dumps(today_data, ensure_ascii=False) if today_data else None

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO saju_diaries "
                "(user_id, content, analysis_result, tags, saju_snapshot, today_data, created_date) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (user_id, req.content.strip(), analysis_json, tags_json,
                 saju_snapshot_json, today_data_json, kst_now.date()),
            )
            diary_id = cur.lastrowid

    return {"id": diary_id, "message": "일기가 저장되었습니다."}


@router.post("/update")
async def diary_update(req: DiaryWriteRequest):
    """사주 일기 수정 (분석 결과 + 태그 업데이트)"""
    if not req.tags and not req.content:
        raise HTTPException(status_code=400, detail="수정할 내용이 없습니다.")

    pool = await get_pool()
    user_id = await _get_user_id(pool, req.google_id)

    # 분석 결과에서 태그 추출
    tags = req.tags

    tags_json = json.dumps(tags, ensure_ascii=False)

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE saju_diaries SET tags = %s "
                "WHERE id = %s AND user_id = %s",
                (tags_json, req.id, user_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="일기를 찾을 수 없습니다.")

    return {"message": "일기가 수정되었습니다."}


@router.post("/list")
async def diary_list(req: DiaryListRequest):
    """사주 일기 목록 조회 (태그 필터 + 페이징)"""
    pool = await get_pool()
    user_id = await _get_user_id(pool, req.google_id)

    offset = (req.page - 1) * req.limit

    diaries = []
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            if req.tag:
                await cur.execute(
                    "SELECT id, content, analysis_result, tags, created_date, created_at "
                    "FROM saju_diaries "
                    "WHERE user_id = %s AND tags LIKE %s "
                    "ORDER BY created_date DESC, created_at DESC "
                    "LIMIT %s OFFSET %s",
                    (user_id, f'%{req.tag}%', req.limit, offset),
                )
            else:
                await cur.execute(
                    "SELECT id, content, analysis_result, tags, created_date, created_at "
                    "FROM saju_diaries "
                    "WHERE user_id = %s "
                    "ORDER BY created_date DESC, created_at DESC "
                    "LIMIT %s OFFSET %s",
                    (user_id, req.limit, offset),
                )

            for row in await cur.fetchall():
                tags_raw = row[3]
                tags_list = json.loads(tags_raw) if tags_raw and isinstance(tags_raw, str) else (tags_raw or [])
                analysis = None
                if row[2]:
                    try:
                        analysis = json.loads(row[2]) if isinstance(row[2], str) else row[2]
                    except (json.JSONDecodeError, TypeError):
                        analysis = {"text": str(row[2])}

                diaries.append(DiaryResponse(
                    id=row[0],
                    content=row[1],
                    analysis_result=analysis,
                    tags=tags_list,
                    created_date=str(row[4]),
                    created_at=str(row[5]),
                ))

    # 전체 태그 집계
    all_tags = set()
    for d in diaries:
        all_tags.update(d.tags)

    return {
        "diaries": [d.model_dump() for d in diaries],
        "all_tags": sorted(all_tags),
        "page": req.page,
        "limit": req.limit,
    }


@router.post("/get")
async def diary_get(req: DiaryDeleteRequest):
    """사주 일기 상세 조회"""
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT d.id, d.content, d.analysis_result, d.tags, "
                "d.created_date, d.created_at, d.saju_snapshot, d.today_data "
                "FROM saju_diaries d "
                "JOIN users u ON u.id = d.user_id "
                "WHERE d.id = %s AND u.google_id = %s",
                (req.diary_id, req.google_id),
            )
            row = await cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="일기를 찾을 수 없습니다.")

    tags_raw = row[3]
    tags_list = json.loads(tags_raw) if tags_raw and isinstance(tags_raw, str) else (tags_raw or [])
    analysis = None
    if row[2]:
        try:
            analysis = json.loads(row[2]) if isinstance(row[2], str) else row[2]
        except (json.JSONDecodeError, TypeError):
            analysis = {"text": str(row[2])}
    saju_snapshot = None
    if row[6]:
        try:
            saju_snapshot = json.loads(row[6]) if isinstance(row[6], str) else row[6]
        except (json.JSONDecodeError, TypeError):
            pass
    today_data = None
    if row[7]:
        try:
            today_data = json.loads(row[7]) if isinstance(row[7], str) else row[7]
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "id": row[0],
        "content": row[1],
        "analysis_result": analysis,
        "tags": tags_list,
        "created_date": str(row[4]),
        "created_at": str(row[5]),
        "saju_snapshot": saju_snapshot,
        "today_data": today_data,
    }


@router.post("/delete")
async def diary_delete(req: DiaryDeleteRequest):
    """사주 일기 삭제"""
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE d FROM saju_diaries d "
                "JOIN users u ON u.id = d.user_id "
                "WHERE d.id = %s AND u.google_id = %s",
                (req.diary_id, req.google_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="일기를 찾을 수 없습니다.")

    return {"message": "일기가 삭제되었습니다."}


@router.get("/tags")
async def diary_tags(google_id: str):
    """사용자의 모든 태그 목록 조회"""
    pool = await get_pool()
    user_id = await _get_user_id(pool, google_id)

    all_tags = set()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT tags FROM saju_diaries WHERE user_id = %s AND tags IS NOT NULL",
                (user_id,),
            )
            for row in await cur.fetchall():
                if row[0]:
                    try:
                        tags = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                        if isinstance(tags, list):
                            all_tags.update(tags)
                    except (json.JSONDecodeError, TypeError):
                        pass

    return {"tags": sorted(all_tags)}
