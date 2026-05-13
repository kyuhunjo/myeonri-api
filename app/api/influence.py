"""
3자 사주 영향 분석 API
내 사주 + 선택한 다른 사람 사주 → 십신 관계 + Groq 분석
"""

from __future__ import annotations
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.utils.saju import (
    get_sibsin, get_sibsin_for_branch, HEAVENLY_BY_HANJA, EARTHLY_BY_HANJA,
)

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/consult", tags=["3자영향"])

INFLUENCE_SYSTEM_PROMPT = """당신은 사주명리 기반 심리상담사입니다. 내 사주와 다른 사람(3자)의 사주를 비교하여, 이 사람이 나에게 미치는 영향을 분석합니다.

규칙:
- 인사말 없이 바로 본문 시작
- 마지막에 추가 질문 유도하지 말고 자연스럽게 마무리
- 500~700자로 충실하게, 따뜻하고 공감적인 어조로
- 존댓말 사용"""


class InfluenceRequest(BaseModel):
    my_saju: dict           # 내 사주 (saju_result 형식)
    target_saju: dict       # 상대방 사주
    nickname: str = ""      # 상대방 별칭


async def _stream_influence(
    my_saju: dict,
    target_saju: dict,
    nickname: str,
) -> AsyncGenerator[str, None]:
    """3자 영향 분석 Groq 스트리밍"""

    # ── 내 일간 정보 ──
    my_hanja = my_saju.get("hanja", {}) if isinstance(my_saju.get("hanja"), dict) else {}
    my_ilju = my_hanja.get("ilju", "")
    my_day_stem = my_ilju[0] if my_ilju and len(my_ilju) >= 1 else ""
    my_day_branch = my_ilju[1] if my_ilju and len(my_ilju) >= 2 else ""

    # ── 상대방 일간 정보 ──
    target_hanja = target_saju.get("hanja", {}) if isinstance(target_saju.get("hanja"), dict) else {}
    target_ilju = target_hanja.get("ilju", "")
    target_day_stem = target_ilju[0] if target_ilju and len(target_ilju) >= 1 else ""
    target_day_branch = target_ilju[1] if target_ilju and len(target_ilju) >= 2 else ""

    # ── 상대방 4주 전체 정보 ──
    target_yeonju = target_hanja.get("yeonju", "")
    target_wolju = target_hanja.get("wolju", "")
    target_siju_hanja = target_hanja.get("siju", "")

    target_hangeul = target_saju.get("hangeul", {}) if isinstance(target_saju.get("hangeul"), dict) else {}
    target_siju_hangul = target_hangeul.get("siju", "")

    # ── 십신 관계 계산 (내가 상대방을 바라볼 때) ──
    heavenly = HEAVENLY_BY_HANJA()
    earthly = EARTHLY_BY_HANJA()

    my_stem_info = heavenly.get(my_day_stem, {})
    my_branch_info = earthly.get(my_day_branch, {})
    target_stem_info = heavenly.get(target_day_stem, {})
    target_branch_info = earthly.get(target_day_branch, {})

    stem_relation = get_sibsin(my_day_stem, target_day_stem) if my_day_stem and target_day_stem else ""
    branch_relation = get_sibsin_for_branch(my_day_stem, target_day_branch) if my_day_stem and target_day_branch else ""

    # 상대방 4주 기준 십신
    target_yeonju_stem = target_yeonju[0] if len(target_yeonju) >= 1 else ""
    target_wolju_stem = target_wolju[0] if len(target_wolju) >= 1 else ""
    target_siju_stem = target_siju_hanja[0] if len(target_siju_hanja) >= 1 else ""

    yeonju_rel = get_sibsin(my_day_stem, target_yeonju_stem) if my_day_stem and target_yeonju_stem else ""
    wolju_rel = get_sibsin(my_day_stem, target_wolju_stem) if my_day_stem and target_wolju_stem else ""
    siju_rel = get_sibsin(my_day_stem, target_siju_stem) if my_day_stem and target_siju_stem else ""

    # ── 메타데이터 SSE 전송 ──
    meta = {
        "my_day_stem": my_day_stem,
        "my_day_stem_elem": my_stem_info.get("element", ""),
        "my_day_stem_yinyang": my_stem_info.get("yinyang", ""),
        "target_nickname": nickname,
        "target_day_stem": target_day_stem,
        "target_day_stem_elem": target_stem_info.get("element", ""),
        "target_day_stem_yinyang": target_stem_info.get("yinyang", ""),
        "stem_relation": stem_relation,          # 내 일간 vs 상대 일간
        "branch_relation": branch_relation,      # 내 일간 vs 상대 일지
        "yeonju_relation": yeonju_rel,           # 내 일간 vs 상대 년주
        "wolju_relation": wolju_rel,             # 내 일간 vs 상대 월주
        "siju_relation": siju_rel,               # 내 일간 vs 상대 시주
    }
    yield f"data: {json.dumps({'meta': meta})}\n\n"

    # ── 프롬프트 구성 ──
    stems_hanja_to_kr = {"甲":"갑","乙":"을","丙":"병","丁":"정","戊":"무","己":"기","庚":"경","辛":"신","壬":"임","癸":"계"}
    branches_hanja_to_kr = {"子":"자","丑":"축","寅":"인","卯":"묘","辰":"진","巳":"사","午":"오","未":"미","申":"신","酉":"유","戌":"술","亥":"해"}

    my_day_stem_kr = stems_hanja_to_kr.get(my_day_stem, "")
    target_day_stem_kr = stems_hanja_to_kr.get(target_day_stem, "")
    target_day_branch_kr = branches_hanja_to_kr.get(target_day_branch, "")

    user_prompt = f"""[내 사주 정보]
일간: {my_day_stem}({my_day_stem_kr}) · {my_stem_info.get('element','')} · {my_stem_info.get('yinyang','')}
일지: {my_day_branch}
4주: {json.dumps(my_hanja, ensure_ascii=False)}

[{nickname}님의 사주 정보]
일간: {target_day_stem}({target_day_stem_kr}) · {target_stem_info.get('element','')} · {target_stem_info.get('yinyang','')}
일지: {target_day_branch}({target_day_branch_kr})
4주: {json.dumps(target_hanja, ensure_ascii=False)}

[나(일간)가 보는 {nickname}님과의 십신 관계]
- {nickname}님의 일간 → 나에게 '{stem_relation}'
- {nickname}님의 일지 → 나에게 '{branch_relation}'
- {nickname}님의 년주 → 나에게 '{yeonju_rel}'
- {nickname}님의 월주 → 나에게 '{wolju_rel}'
- {nickname}님의 시주 → 나에게 '{siju_rel}'

이 {nickname}님이 나에게 어떤 영향을 미치는지 분석해주세요. 특히:
1️⃣ 이 사람이 나에게 주는 영향력 (좋은 점, 나쁜 점)
2️⃣ 십신 관계를 바탕으로 한 성격적 상호작용
3️⃣ 이 사람과의 관계에서 내가 주의할 점
4️⃣ 이 사람이 내 인생에서 가지는 의미와 시사점

사주 정보와 십신 관계를 바탕으로 깊이 있게 분석해주세요."""

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
                        {"role": "system", "content": INFLUENCE_SYSTEM_PROMPT},
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


@router.post("/influence")
async def consult_influence(req: InfluenceRequest):
    """3자 사주가 내게 미치는 영향 분석 (SSE 스트리밍)"""
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")

    if not req.my_saju or not req.target_saju:
        raise HTTPException(status_code=400, detail="내 사주와 상대방 사주 데이터가 필요합니다")

    return StreamingResponse(
        _stream_influence(req.my_saju, req.target_saju, req.nickname),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
