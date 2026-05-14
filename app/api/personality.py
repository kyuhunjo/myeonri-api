"""
성격 분석 API
사주 원국 기반 기본 성격/성향/장단점 상세 분석 (SSE 스트리밍)
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
router = APIRouter(prefix="/consult", tags=["성격분석"])


PERSONALITY_SYSTEM_PROMPT = """당신은 사주명리 기반 성격 분석 전문가입니다. 사주 원국을 깊이 해석하여 그 사람의 타고난 기질, 성격적 강점과 약점, 대인관계 스타일, 내면의 심리를 상세히 분석합니다.

규칙:
- 인사말 없이 바로 본문 시작
- 마지막에 추가 질문 유도하지 말고 자연스럽게 마무리
- 800~1000자로 충실하게
- 존댓말 사용
- 분석 내용은 반드시 사주 근거를 포함할 것
- 따뜻하고 공감적인 어조로, 단점도 발전 가능성으로 풀어낼 것"""


class PersonalityRequest(BaseModel):
    google_id: str = ""
    saju_result: dict | None = None


def _build_personality_prompt(saju: dict) -> str:
    """사주 데이터 → 성격 분석 프롬프트 구성"""
    hanja = saju.get("hanja", {}) if isinstance(saju.get("hanja"), dict) else {}
    hangeul = saju.get("hangeul", {}) if isinstance(saju.get("hangeul"), dict) else {}
    sibsin_data = saju.get("sibsin", {}) if isinstance(saju.get("sibsin"), dict) else {}
    ssaju = saju.get("ssaju", {}) if isinstance(saju.get("ssaju"), dict) else {}
    input_data = saju.get("input", {}) if isinstance(saju.get("input"), dict) else {}

    # 4주
    four_pillars = {}
    for k in ["yeonju", "wolju", "ilju", "siju"]:
        hj = hanja.get(k, "")
        hg = hangeul.get(k, "")
        four_pillars[k] = {"hanja": hj, "hangeul": hg}

    # 십신 상세
    sibsin_detail = {}
    for k, v in sibsin_data.items():
        if isinstance(v, dict):
            sibsin_detail[k] = v

    # 지장간
    jijanggan = None
    if ssaju and isinstance(ssaju.get("pillarDetails"), dict):
        pd = ssaju["pillarDetails"]
        if isinstance(pd.get("jijanggan"), dict):
            jijanggan = pd["jijanggan"]

    # 대운
    daeun = ssaju.get("daeun", {}) if ssaju else {}

    # 오행 통계
    element_stats = {}
    if sibsin_detail:
        for elem in ["목", "화", "토", "금", "수"]:
            count = sum(1 for v in sibsin_detail.values() if isinstance(v, dict) and v.get("element") == elem)
            if count > 0:
                element_stats[elem] = count

    return f"""사주 정보:
4주: {json.dumps(four_pillars, ensure_ascii=False)}
십신: {json.dumps(sibsin_detail, ensure_ascii=False)}
지장간: {json.dumps(jijanggan, ensure_ascii=False) if jijanggan else "없음"}
오행 통계: {json.dumps(element_stats, ensure_ascii=False)}
대운: {json.dumps(daeun, ensure_ascii=False) if daeun else "없음"}
생년월일: {json.dumps(input_data, ensure_ascii=False)}

이 사주 정보를 바탕으로 다음을 분석해주세요:

1️⃣ **기본 성격 & 기질**
- 일간(일주 천간)의 오행과 음양이 성격에 미치는 영향
- 일지(일주 지지)가 주는 내면의 성향
- 전체 오행 구성이 만드는 성격적 조화와 불균형

2️⃣ **강점 (장점)**
- 타고난 재능과 강점이 되는 십신
- 대인관계와 사회생활에서 돋보이는 부분
- 활용하면 좋은 성격적 자산

3️⃣ **약점 & 성장 포인트**
- 보완이 필요한 성격적 경향
- 스트레스 상황에서 나타나는 패턴
- 균형을 위한 조언

4️⃣ **대인관계 스타일**
- 인간관계에서의 자연스러운 역할과 패턴
- 잘 맞는/주의할 상대 유형
- 관계에서 더 나은 소통을 위한 팁"""


@router.post("/personality")
async def consult_personality(req: PersonalityRequest):
    """사주 기반 성격 상세 분석 (SSE 스트리밍)"""
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API 키가 설정되지 않았습니다")

    saju = req.saju_result
    if not saju and req.google_id:
        saju = await _get_saju_data(req)
    if not saju:
        raise HTTPException(status_code=400, detail="사주 데이터가 필요합니다")

    prompt = _build_personality_prompt(saju)

    from app.api.consult import _stream_groq as _sg

    class _Req:
        category = "custom"
        question = ""

    _req = _Req()

    return StreamingResponse(
        _sg(saju, _req, override_system=PERSONALITY_SYSTEM_PROMPT, override_prompt=prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
