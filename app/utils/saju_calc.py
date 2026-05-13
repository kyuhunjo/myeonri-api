"""
사주 계산 엔진
- 시주 계산
- 만세력 DB 로우 → 사주 데이터 변환
"""

from __future__ import annotations

from app.utils.constants import (
    get_heavenly_by_hanja,
    get_heavenly_by_index,
    get_earthly_by_index,
)
from app.utils.sipshin import get_sibsin, get_sibsin_for_branch


def get_branch_by_hour(hour: int, minute: int = 0) -> int:
    """
    시간 → 지지 인덱스
    자시(子時) = 23:00~00:59 → index 0
    축시(丑時) = 01:00~02:59 → index 1
    ...
    해시(亥時) = 21:00~22:59 → index 11
    """
    total_minutes = hour * 60 + minute
    if total_minutes >= 23 * 60 or total_minutes < 1 * 60:
        return 0
    return ((total_minutes - 60) // 120) + 1


def get_siju_stem(day_stem_index: int, branch_index: int) -> int:
    """
    시천간 계산
    일간(day_stem_index)을 기준으로 시지(branch_index)에 따른 천간 인덱스 반환
    """
    start_map = [0, 2, 4, 6, 8]  # 갑(0), 병(2), 무(4), 경(6), 임(8)
    start = start_map[day_stem_index % 5]
    return (start + branch_index) % 10


async def calculate_saju_from_calenda(
    calenda_row: dict,
    hour: int,
    minute: int,
):
    """
    만세력 DB 로우 + 시간 → 사주 계산
    calenda_row에는 cd_hdganjee(일주한자), cd_hyganjee(년주한자),
    cd_hmganjee(월주한자), cd_kdganjee(일주한글), 등
    """
    # 1. 4주 한자 추출
    yeonju_hanja = calenda_row.get("cd_hyganjee", "")
    wolju_hanja = calenda_row.get("cd_hmganjee", "")
    ilju_hanja = calenda_row.get("cd_hdganjee", "")
    yeonju_hangul = calenda_row.get("cd_kyganjee", "")
    wolju_hangul = calenda_row.get("cd_kmganjee", "")
    ilju_hangul = calenda_row.get("cd_kdganjee", "")

    # 2. 일간 분리 (천간만)
    day_stem_hanja = ilju_hanja[0]

    # 3. 시주 계산
    branch_idx = get_branch_by_hour(hour, minute)
    heavenly_by_hanja = await get_heavenly_by_hanja()
    heavenly_by_index = await get_heavenly_by_index()
    earthly_by_index = await get_earthly_by_index()

    day_stem_info = heavenly_by_hanja[day_stem_hanja]
    siju_stem_idx = get_siju_stem(day_stem_info["index"], branch_idx)

    siju_hanja = heavenly_by_index[siju_stem_idx]["hanja"] + earthly_by_index[branch_idx]["hanja"]
    siju_hangul = heavenly_by_index[siju_stem_idx]["hangul"] + earthly_by_index[branch_idx]["hangul"]

    # 4. 십신 계산 (4주 각각)
    pillars = {
        "yeonju": {"hanja": yeonju_hanja, "hangul": yeonju_hangul},
        "wolju": {"hanja": wolju_hanja, "hangul": wolju_hangul},
        "ilju": {"hanja": ilju_hanja, "hangul": ilju_hangul},
        "siju": {"hanja": siju_hanja, "hangul": siju_hangul},
    }

    sibsin = {}
    for key, pillar in pillars.items():
        gan = pillar["hanja"][0]
        ji = pillar["hanja"][1]
        if key == "ilju":
            sibsin[key] = {"gan": "나", "ji": await get_sibsin_for_branch(day_stem_hanja, ji)}
        else:
            sibsin[key] = {
                "gan": await get_sibsin(day_stem_hanja, gan),
                "ji": await get_sibsin_for_branch(day_stem_hanja, ji),
            }

    return {
        "hanja": {
            "yeonju": yeonju_hanja,
            "wolju": wolju_hanja,
            "ilju": ilju_hanja,
            "siju": siju_hanja,
        },
        "hangeul": {
            "yeonju": yeonju_hangul,
            "wolju": wolju_hangul,
            "ilju": ilju_hangul,
            "siju": siju_hangul,
        },
        "sibsin": sibsin,
        "yang": {
            "year": calenda_row.get("cd_sy"),
            "month": calenda_row.get("cd_sm"),
            "day": calenda_row.get("cd_sd"),
        },
        "eum": {
            "year": calenda_row.get("cd_ly"),
            "month": calenda_row.get("cd_lm"),
            "day": calenda_row.get("cd_ld"),
        },
        "hour": f"{hour:02d}:{minute:02d}",
    }
