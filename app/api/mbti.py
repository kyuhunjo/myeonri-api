"""
MBTI 예측 API (지표별 분리)
사주 원국 → MBTI 4가지 지표 각각 분석 (SSE 스트리밍)
"""

from __future__ import annotations
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.api.consult import _get_saju_data, _stream_groq

logger = logging.getLogger("myeonri-api")
router = APIRouter(prefix="/consult", tags=["MBTI"])


class MbtiDimensionRequest(BaseModel):
    google_id: str = ""
    saju_result: dict | None = None


# 지표별 시스템 프롬프트
DIMENSION_PROMPTS = {
    "ei": {
        "label": "에너지 방향 (E/I)",
        "system": "당신은 사주명리와 MBTI를 연결하는 분석 전문가입니다. 사용자의 사주 원국을 분석하여 에너지 방향(E/I)을 예측하고 그 근거를 설명합니다.\n\n규칙:\n- 인사말 없이 바로 본문 시작\n- 마지막에 추가 질문 유도 금지\n- 300~500자, 존댓말\n- 반드시 사주 원국의 근거를 들어 설명\n- E(외향형)인지 I(내향형)인지 결론부터 명확히 제시",
        "prompt_suffix": "\n\n이 사주의 일간 음양(음/양)과 오행 활동성, 십신 구성을 바탕으로 에너지 방향(E/I)을 분석해주세요.\n\n1. 일간(일주 천간)의 음양과 오행 특성\n2. 십신 중 비겁(비견/겁재)과 인성(정인/편인)의 배치가 활동성에 미치는 영향\n3. 전체 오행 구성이 주는 에너지의 방향성\n\n분석 후 E(외향형)인지 I(내향형)인지 명확히 결론을 내주세요.",
    },
    "sn": {
        "label": "인식 기능 (S/N)",
        "system": "당신은 사주명리와 MBTI를 연결하는 분석 전문가입니다. 사용자의 사주 원국을 분석하여 인식 기능(S/N)을 예측하고 그 근거를 설명합니다.\n\n규칙:\n- 인사말 없이 바로 본문 시작\n- 마지막에 추가 질문 유도 금지\n- 300~500자, 존댓말\n- 반드시 사주 원국의 근거를 들어 설명\n- S(감각형)인지 N(직관형)인지 결론부터 명확히 제시",
        "prompt_suffix": "\n\n이 사주의 지장간 구성, 오행의 조합, 십신 배치를 바탕으로 인식 기능(S/N)을 분석해주세요.\n\n1. 일지(일주 지지)와 지장간이 주는 내면의 인식 패턴\n2. 십신 중 식상(식신/상관)과 인성(정인/편인)의 역할\n3. 오행의 조화와 편중이 인식 방식에 미치는 영향\n\n분석 후 S(감각형)인지 N(직관형)인지 명확히 결론을 내주세요.",
    },
    "tf": {
        "label": "판단 기능 (T/F)",
        "system": "당신은 사주명리와 MBTI를 연결하는 분석 전문가입니다. 사용자의 사주 원국을 분석하여 판단 기능(T/F)을 예측하고 그 근거를 설명합니다.\n\n규칙:\n- 인사말 없이 바로 본문 시작\n- 마지막에 추가 질문 유도 금지\n- 300~500자, 존댓말\n- 반드시 사주 원국의 근거를 들어 설명\n- T(사고형)인지 F(감정형)인지 결론부터 명확히 제시",
        "prompt_suffix": "\n\n이 사주의 십신 구성, 특히 관성(편관/정관)과 인성(정인/편인)의 배치를 바탕으로 판단 기능(T/F)을 분석해주세요.\n\n1. 관성(편관/정관)의 강약이 판단 기준에 미치는 영향\n2. 인성(정인/편인)과 식상(식신/상관)의 조화\n3. 일간의 오행과 십신 조합이 의사 결정 방식에 주는 영향\n\n분석 후 T(사고형)인지 F(감정형)인지 명확히 결론을 내주세요.",
    },
    "jp": {
        "label": "생활 양식 (J/P)",
        "system": "당신은 사주명리와 MBTI를 연결하는 분석 전문가입니다. 사용자의 사주 원국을 분석하여 생활 양식(J/P)을 예측하고 그 근거를 설명합니다.\n\n규칙:\n- 인사말 없이 바로 본문 시작\n- 마지막에 추가 질문 유도 금지\n- 300~500자, 존댓말\n- 반드시 사주 원국의 근거를 들어 설명\n- J(판단형)인지 P(인식형)인지 결론부터 명확히 제시",
        "prompt_suffix": "\n\n이 사주의 십신 강약, 합충 관계, 오행 구성을 바탕으로 생활 양식(J/P)을 분석해주세요.\n\n1. 십신 중 비겁(비견/겁재)과 재성(정재/편재)의 배치가 계획성에 미치는 영향\n2. 합(合)과 충(冲) 관계가 생활 패턴에 주는 영향\n3. 오행의 흐름과 대운의 흐름이 삶의 방식에 주는 영향\n\n분석 후 J(판단형)인지 P(인식형)인지 명확히 결론을 내주세요.",
    },
}


def _build_saju_context(saju: dict) -> str:
    """사주 데이터를 컨텍스트 문자열로 변환"""
    hanja = saju.get("hanja", {}) if isinstance(saju.get("hanja"), dict) else {}
    hangeul = saju.get("hangeul", {}) if isinstance(saju.get("hangeul"), dict) else {}
    sibsin_data = saju.get("sibsin", {}) if isinstance(saju.get("sibsin"), dict) else {}
    ssaju = saju.get("ssaju", {}) if isinstance(saju.get("ssaju"), dict) else {}

    four_pillars = {}
    for k in ["yeonju", "wolju", "ilju", "siju"]:
        hj = hanja.get(k, "")
        hg = hangeul.get(k, "")
        four_pillars[k] = {"hanja": hj, "hangeul": hg}

    elements = {}
    for k, v in sibsin_data.items():
        if isinstance(v, dict):
            elements[k] = v

    # 지장간
    jijanggan = None
    if ssaju and isinstance(ssaju.get("pillarDetails"), dict):
        pd = ssaju["pillarDetails"]
        if isinstance(pd.get("jijanggan"), dict):
            jijanggan = pd["jijanggan"]

    return f"""사주 정보:
4주: {json.dumps(four_pillars, ensure_ascii=False)}
십신: {json.dumps(elements, ensure_ascii=False)}
지장간: {json.dumps(jijanggan, ensure_ascii=False) if jijanggan else "없음"}
상세정보: {json.dumps(ssaju, ensure_ascii=False)}"""


async def _stream_dimension(saju: dict, dimension: str) -> str:
    """지표별 스트리밍 처리"""
    ctx = DIMENSION_PROMPTS[dimension]
    saju_context = _build_saju_context(saju)
    user_prompt = f"{saju_context}{ctx['prompt_suffix']}"

    from app.api.consult import _stream_groq as _sg

    class _Req:
        category = "custom"
        question = ""

    return _sg(saju, _Req(), override_system=ctx["system"], override_prompt=user_prompt, override_temperature=0.1)


# 각 지표별 엔드포인트
@router.post("/mbti/ei")
async def mbti_ei(req: MbtiDimensionRequest):
    """에너지 방향 (E/I) 분석"""
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")
    saju = req.saju_result
    if not saju and req.google_id:
        saju = await _get_saju_data(req)
    if not saju:
        raise HTTPException(status_code=400, detail="사주 데이터가 필요합니다")
    return StreamingResponse(
        await _stream_dimension(saju, "ei"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/mbti/sn")
async def mbti_sn(req: MbtiDimensionRequest):
    """인식 기능 (S/N) 분석"""
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")
    saju = req.saju_result
    if not saju and req.google_id:
        saju = await _get_saju_data(req)
    if not saju:
        raise HTTPException(status_code=400, detail="사주 데이터가 필요합니다")
    return StreamingResponse(
        await _stream_dimension(saju, "sn"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/mbti/tf")
async def mbti_tf(req: MbtiDimensionRequest):
    """판단 기능 (T/F) 분석"""
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")
    saju = req.saju_result
    if not saju and req.google_id:
        saju = await _get_saju_data(req)
    if not saju:
        raise HTTPException(status_code=400, detail="사주 데이터가 필요합니다")
    return StreamingResponse(
        await _stream_dimension(saju, "tf"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/mbti/jp")
async def mbti_jp(req: MbtiDimensionRequest):
    """생활 양식 (J/P) 분석"""
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")
    saju = req.saju_result
    if not saju and req.google_id:
        saju = await _get_saju_data(req)
    if not saju:
        raise HTTPException(status_code=400, detail="사주 데이터가 필요합니다")
    return StreamingResponse(
        await _stream_dimension(saju, "jp"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
