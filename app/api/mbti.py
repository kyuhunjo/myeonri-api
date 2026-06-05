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
    temperature: float = 0.7


# 지표별 시스템 프롬프트
# 사주명리-MBTI 연관성에 집중: 육신(십신), 음양오행, 합충형해파, 지장간
DIMENSION_PROMPTS = {
    "ei": {
        "label": "에너지 방향 (E/I)",
        "system": "당신은 사주명리와 MBTI를 정밀하게 연결하는 분석 전문가입니다.\n\n[분석 원리]\n- E(외향): 비겁 강하면 자신을 밖으로 드러냄, 식상 발달이면 표현력 ↑, 재성 왕성하면 대인관계 적극적\n- I(내향): 인성 강하면 내면 성찰, 관다신강이면 혼자 집중하는 성향, 지장간에 수(水) 지장간 많으면 내향\n- 일간 양(陽): 갑병무경임 → 활동적, 밖으로 향하는 에너지 / 일간 음(陰): 을정기신계 → 내면적, 수렴하는 에너지\n- 비견/겁재 많음 → 주체적·사회적, 인성 많음 → 사색적·내향적\n- 월지(月支)가 사주에서 가장 큰 비중 → 월지 지장간의 오행이 외향/내향 핵심 지표\n\n💡 결정적 지표: 일간 음양 + 월지 오행 + 비겁vs인성 세기\n\n규칙:\n- '결론: E(외향형)' 또는 '결론: I(내향형)' 으로 시작\n- 350~500자, 존댓말\n- 사주 구성요소 2~3개를 구체적으로 언급하며 근거 제시",
        "prompt_suffix": "\n\n위 사주 원국을 분석해주세요. 일간의 음양, 월지 오행 특성, 비겁과 인성의 강약, 지장간 구성을 바탕으로 에너지 방향(E/I)을 판단하고 근거를 설명해주세요.",
    },
    "sn": {
        "label": "인식 기능 (S/N)",
        "system": "당신은 사주명리와 MBTI를 정밀하게 연결하는 분석 전문가입니다.\n\n[분석 원리]\n- S(감각): 토(土)·금(金) 오행 강함 → 현실적·구체적, 일지가 진술축미(辰戌丑未 토지지)이면 실용적, 식신은 구체적 경험 중시\n- N(직관): 수(水)·화(火) 오행 강함 → 상상력·통찰, 상관 발달이면 기존 틀을 깨는 직관, 편인은 비전통적 사고\n- 지장간: 일지 지장간이 식신+정재이면 S, 상관+편재이면 N 경향\n- 토(土) 오행 편중 → 감각적·현실적 / 수(水) 오행 편중 → 직관적·추상적\n- 재성(정재/편재)과 식상(식신/상관)의 비율: 식신>상관 → S, 상관>식신 → N\n\n💡 결정적 지표: 일지 지장간 구성 + 토/수 오행 비율 + 식신vs상관 강약\n\n규칙:\n- '결론: S(감각형)' 또는 '결론: N(직관형)' 으로 시작\n- 350~500자, 존댓말\n- 사주 구성요소 2~3개를 구체적으로 언급하며 근거 제시",
        "prompt_suffix": "\n\n위 사주 원국을 분석해주세요. 일지 지장간 구성, 오행 중 토와 수의 분포, 식신과 상관의 강약을 바탕으로 인식 기능(S/N)을 판단하고 근거를 설명해주세요.",
    },
    "tf": {
        "label": "판단 기능 (T/F)",
        "system": "당신은 사주명리와 MBTI를 정밀하게 연결하는 분석 전문가입니다.\n\n[분석 원리]\n- T(사고): 관성(편관/정관) 강함 → 논리적·원칙적 판단, 금(金) 오행 강함 → 객관적·공정한 기준, 재성 발달 → 효율성 중시\n- F(감정): 인성(정인/편인) 강함 → 공감적 판단, 목(木)·화(火) 오행 → 따뜻함과 배려, 식상 중 식신 → 정서적 표현\n- 편관 강하면 엄격한 논리와 원칙, 정관이면 사회적 규범 중시 → T 성향\n- 정인이면 수용적 공감, 편인이면 독창적 감수성 → F 성향\n- 일간이 화(火)이면 정서적·직관적 판단(F), 금(金)이면 논리적 판단(T)\n- 충(冲) 많은 사주 → 즉각적 판단(T), 합(合) 많은 사주 → 관계 고려한 판단(F)\n\n💡 결정적 지표: 일간 오행(금/화) + 관성vs인성 강약 + 충합 비율\n\n규칙:\n- '결론: T(사고형)' 또는 '결론: F(감정형)' 으로 시작\n- 350~500자, 존댓말\n- 사주 구성요소 2~3개를 구체적으로 언급하며 근거 제시",
        "prompt_suffix": "\n\n위 사주 원국을 분석해주세요. 일간 오행(금/화 여부), 관성과 인성의 강약, 충과 합의 비율을 바탕으로 판단 기능(T/F)을 판단하고 근거를 설명해주세요.",
    },
    "jp": {
        "label": "생활 양식 (J/P)",
        "system": "당신은 사주명리와 MBTI를 정밀하게 연결하는 분석 전문가입니다.\n\n[분석 원리]\n- J(판단): 정관·정인·정재(정격 십신) 강함 → 계획적·구조적, 토(土) 오행 → 안정성과 마무리 중시, 관인상생(관이 인을 생) → 체계적 생활\n- P(인식): 편관·편인·편재(편격 십신) 강함 → 유연함·즉흥적, 수(水) 오행 → 순응적·흐름에 맡김, 식상 발달 → 자유로운 생활 패턴\n- 지지에 충(冲)이 있으면 → 변화에 민첩(P), 합(合)이 많으면 → 안정적 루틴(J)\n- 정재 강하면 계획적 소비와 생활(J), 편재 강하면 즉흥적·융통성(P)\n- 월지와 시지(시간 지지): 월지가 구조의 핵심, 시지가 행동 패턴\n- 비겁이 왕성하면 자신의 계획대로 밀고 나감(J), 식상이 왕성하면 상황에 따라 유연하게(P)\n\n💡 결정적 지표: 정격vs편격 십신 비율 + 충합 유무 + 토/수 오행 분포\n\n규칙:\n- '결론: J(판단형)' 또는 '결론: P(인식형)' 으로 시작\n- 350~500자, 존댓말\n- 사주 구성요소 2~3개를 구체적으로 언급하며 근거 제시",
        "prompt_suffix": "\n\n위 사주 원국을 분석해주세요. 정격 십신(정관/정인/정재)과 편격 십신(편관/편인/편재)의 비율, 충과 합의 유무, 토와 수 오행의 분포를 바탕으로 생활 양식(J/P)을 판단하고 근거를 설명해주세요.",
    },
}


def _build_saju_context(saju: dict) -> str:
    """사주 데이터를 MBTI 분석에 최적화된 컨텍스트로 변환"""
    hanja = saju.get("hanja", {}) if isinstance(saju.get("hanja"), dict) else {}
    hangeul = saju.get("hangeul", {}) if isinstance(saju.get("hangeul"), dict) else {}
    sibsin_data = saju.get("sibsin", {}) if isinstance(saju.get("sibsin"), dict) else {}
    ssaju = saju.get("ssaju", {}) if isinstance(saju.get("ssaju"), dict) else {}

    # 4주 한글
    four_pillars = {}
    pillar_labels = {"yeonju": "년주", "wolju": "월주", "ilju": "일주", "siju": "시주"}
    for k in ["yeonju", "wolju", "ilju", "siju"]:
        hj = hanja.get(k, "")
        hg = hangeul.get(k, "")
        four_pillars[pillar_labels[k]] = hg if hg else hj

    # 십신 요약 (년월일시별 천간+지지 십신)
    sibsin_summary = {}
    for k, v in sibsin_data.items():
        if isinstance(v, dict):
            stem = v.get("stem", "")
            branch = v.get("branch", "")
            if stem or branch:
                label = pillar_labels.get(k, k)
                parts = []
                if stem: parts.append(f"천간:{stem}")
                if branch: parts.append(f"지지:{branch}")
                sibsin_summary[label] = ", ".join(parts)

    # 지장간 요약 (일주만 핵심)
    jijanggan_str = "없음"
    if ssaju and isinstance(ssaju.get("pillarDetails"), dict):
        pd = ssaju["pillarDetails"]
        day_pd = pd.get("day", {}) if isinstance(pd, dict) else {}
        if isinstance(day_pd, dict):
            hs = day_pd.get("hiddenStems", {})
            if isinstance(hs, dict) and hs:
                parts = [f"{k}:{v}" for k, v in hs.items()]
                jijanggan_str = ", ".join(parts)

    # 오행 분포
    five_elements = ssaju.get("fiveElements", {}) if isinstance(ssaju, dict) else {}
    elem_str = ""
    if five_elements:
        elem_str = ", ".join(f"{k}:{v}개" for k, v in five_elements.items())

    # 합충 관계
    branch_relations = ssaju.get("branchRelations", {}) if isinstance(ssaju, dict) else {}
    relations_str = "없음"
    if branch_relations:
        rel_parts = []
        for rtype, rval in branch_relations.items():
            if isinstance(rval, dict) and rval:
                details = ", ".join(f"{k}:{v}" for k, v in rval.items())
                rel_parts.append(f"{rtype}({details})")
        if rel_parts:
            relations_str = "; ".join(rel_parts)

    return f"""사주 정보:
4주: {json.dumps(four_pillars, ensure_ascii=False)}
십신(육신): {json.dumps(sibsin_summary, ensure_ascii=False)}
일주 지장간: {jijanggan_str}
오행 분포: {elem_str}
지지 관계(합충형파해): {relations_str}"""


async def _stream_dimension(saju: dict, dimension: str, temperature: float = 0.7) -> str:
    """지표별 스트리밍 처리"""
    ctx = DIMENSION_PROMPTS[dimension]
    saju_context = _build_saju_context(saju)
    user_prompt = f"{saju_context}{ctx['prompt_suffix']}"

    from app.api.consult import _stream_groq as _sg

    class _Req:
        category = "custom"
        question = ""

    return _sg(saju, _Req(), override_system=ctx["system"], override_prompt=user_prompt, override_temperature=temperature)


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
        await _stream_dimension(saju, "ei", temperature=req.temperature),
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
        await _stream_dimension(saju, "sn", temperature=req.temperature),
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
        await _stream_dimension(saju, "tf", temperature=req.temperature),
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
        await _stream_dimension(saju, "jp", temperature=req.temperature),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
