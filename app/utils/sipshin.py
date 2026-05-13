"""
십신(十神) 계산 — 일간 기준 십신 관계 연산
DB 캐시된 데이터 사용 (sync)
"""

from __future__ import annotations

from app.utils.constants import (
    get_heavenly_by_hanja_sync,
    get_earthly_by_hanja_sync,
    get_generated,
    get_generator,
    get_controlled,
    get_controller,
)


def get_sibsin(day_stem_hanja: str, target_stem_hanja: str) -> str:
    """십신(十神) 계산 — 천간 vs 천간"""
    heavenly = get_heavenly_by_hanja_sync()
    day = heavenly[day_stem_hanja]
    target = heavenly[target_stem_hanja]

    same_element = day["element"] == target["element"]
    same_yinyang = day["yinyang"] == target["yinyang"]

    if same_element:
        return "비견" if same_yinyang else "겁재"
    if get_generated(day["element"]) == target["element"]:
        return "식신" if same_yinyang else "상관"
    if get_generator(day["element"]) == target["element"]:
        return "편인" if same_yinyang else "정인"
    if get_controlled(day["element"]) == target["element"]:
        return "편재" if same_yinyang else "정재"
    if get_controller(day["element"]) == target["element"]:
        return "편관" if same_yinyang else "정관"
    return ""


def get_sibsin_for_branch(day_stem_hanja: str, branch_hanja: str) -> str:
    """십신 계산 — 일간 vs 지지 (지지의 오행 기준)"""
    heavenly = get_heavenly_by_hanja_sync()
    earthly = get_earthly_by_hanja_sync()
    day = heavenly[day_stem_hanja]
    branch = earthly[branch_hanja]

    same_element = day["element"] == branch["element"]
    same_yinyang = day["yinyang"] == branch["yinyang"]

    if same_element:
        return "비견" if same_yinyang else "겁재"
    if get_generated(day["element"]) == branch["element"]:
        return "식신" if same_yinyang else "상관"
    if get_generator(day["element"]) == branch["element"]:
        return "편인" if same_yinyang else "정인"
    if get_controlled(day["element"]) == branch["element"]:
        return "편재" if same_yinyang else "정재"
    if get_controller(day["element"]) == branch["element"]:
        return "편관" if same_yinyang else "정관"
    return ""
