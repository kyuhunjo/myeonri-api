"""
MBTI 예측 API
사주 원국 → MBTI 유형 예측 (SSE 스트리밍)
"""

from __future__ import annotations
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.api.consult import _get_saju_data, _stream_groq
from app.utils.saju import HEAVENLY_BY_HANJA, EARTHLY_BY_HANJA

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/consult", tags=["MBTI"])


MBTI_SYSTEM_PROMPT = """당신은 사주명리와 MBTI를 연결하는 분석 전문가입니다. 사주 원국(4주, 오행, 십신)을 분석하여 MBTI 유형을 예측하고 그 근거를 설명합니다.

규칙:
- 인사말 없이 바로 본문 시작
- 마지막에 추가 질문 유도하지 말고 자연스럽게 마무리
- 500~700자
- 존댓말 사용
- MBTI 4가지 지표(E/I, S/N, T/F, J/P) 각각에 대해 사주 근거를 설명
- 최종 예측 MBTI와 그 이유를 종합적으로 제시"""


class MbtiRequest(BaseModel):
    google_id: str = ""
    saju_result: dict | None = None


def _build_mbti_prompt(saju: dict) -> str:
    """사주 데이터 → MBTI 프롬프트 구성"""
    hanja = saju.get("hanja", {}) if isinstance(saju.get("hanja"), dict) else {}
    hangeul = saju.get("hangeul", {}) if isinstance(saju.get("hangeul"), dict) else {}
    sibsin_data = saju.get("sibsin", {}) if isinstance(saju.get("sibsin"), dict) else {}
    ssaju = saju.get("ssaju", {}) if isinstance(saju.get("ssaju"), dict) else {}

    # 사주 원문(4주)
    four_pillars = {}
    for k in ["yeonju", "wolju", "ilju", "siju"]:
        hj = hanja.get(k, "")
        hg = hangeul.get(k, "")
        four_pillars[k] = {"hanja": hj, "hangeul": hg}

    # 오행 통계
    elements = {}
    for k, v in sibsin_data.items():
        if isinstance(v, dict):
            elements[k] = v

    return f"""사주 정보:
4주: {json.dumps(four_pillars, ensure_ascii=False)}
십신: {json.dumps(elements, ensure_ascii=False)}
상세정보: {json.dumps(ssaju, ensure_ascii=False)}

이 사주의 오행 구성, 십신 배치, 일간의 특징을 바탕으로 MBTI 유형을 예측해주세요.

1️⃣ 에너지 방향 (E/I): 일간의 음양 + 오행의 활동성을 기준으로 분석
2️⃣ 인식 기능 (S/N): 지장간/육친 구성과 오행의 조합을 기준으로 분석
3️⃣ 판단 기능 (T/F): 십신 중 관성(편관/정관)과 인성(편인/정인)의 배치를 기준으로 분석
4️⃣ 생활 양식 (J/P): 십신의 강약과 합충 관계를 기준으로 분석

각 지표별로 사주 근거를 설명하고, 최종 MBTI 유형을 예측해주세요."""


@router.post("/mbti")
async def consult_mbti(req: MbtiRequest):
    """사주 기반 MBTI 예측 (SSE 스트리밍)"""
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")

    saju = req.saju_result
    if not saju and req.google_id:
        saju = await _get_saju_data(req)
    if not saju:
        raise HTTPException(status_code=400, detail="사주 데이터가 필요합니다")

    prompt = _build_mbti_prompt(saju)

    # _stream_groq는 consult.py의 내부 함수 — 직접 호출
    from app.api.consult import _stream_groq as _sg

    # ConsultRequest 흉내내기
    class _Req:
        category = "custom"
        question = ""

    _req = _Req()

    return StreamingResponse(
        _sg(saju, _req, override_system=MBTI_SYSTEM_PROMPT, override_prompt=prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
