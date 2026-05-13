"""
사주 계산 엔진 (Saju Calculation Engine)
— 천간/지지 데이터는 DB에서 로드 (앱 startup 시 캐시)
— 오행 순환 함수는 내장
"""

from app.utils.constants import (
    get_heavenly_sync,
    get_heavenly_by_hanja_sync,
    get_heavenly_by_index_sync,
    get_earthly_sync,
    get_earthly_by_hanja_sync,
    get_earthly_by_index_sync,
    ELEMENT_CYCLE,
    ELEMENT_INDEX,
    get_generated,
    get_generator,
    get_controlled,
    get_controller,
)

# ── sync alias (기존 import 호환) ──
HEAVENLY_STEMS = get_heavenly_sync
HEAVENLY_BY_HANJA = get_heavenly_by_hanja_sync
HEAVENLY_BY_INDEX = get_heavenly_by_index_sync
EARTHLY_BRANCHES = get_earthly_sync
EARTHLY_BY_HANJA = get_earthly_by_hanja_sync
EARTHLY_BY_INDEX = get_earthly_by_index_sync


# ── 십신 ──


def get_sibsin(day_stem_hanja: str, target_stem_hanja: str) -> str:
    """십신(十神) 계산 — 천간 vs 천간"""
    heavenly = HEAVENLY_BY_HANJA()
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
    heavenly = HEAVENLY_BY_HANJA()
    earthly = EARTHLY_BY_HANJA()
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


# ── 시간/사주 계산 ──


def get_branch_by_hour(hour: int, minute: int = 0) -> int:
    """시간 → 지지 인덱스"""
    total_minutes = hour * 60 + minute
    if total_minutes >= 23 * 60 or total_minutes < 1 * 60:
        return 0
    return ((total_minutes - 60) // 120) + 1


def get_siju_stem(day_stem_index: int, branch_index: int) -> int:
    """시천간 계산"""
    start_map = [0, 2, 4, 6, 8]
    start = start_map[day_stem_index % 5]
    return (start + branch_index) % 10


def calculate_saju_from_calenda(calenda_row: dict, hour: int, minute: int):
    """만세력 DB 로우 + 시간 → 사주 계산"""
    heavenly_by_hanja = HEAVENLY_BY_HANJA()
    heavenly_by_index = HEAVENLY_BY_INDEX()
    earthly_by_index = EARTHLY_BY_INDEX()

    yeonju_hanja = calenda_row.get("cd_hyganjee", "")
    wolju_hanja = calenda_row.get("cd_hmganjee", "")
    ilju_hanja = calenda_row.get("cd_hdganjee", "")
    yeonju_hangul = calenda_row.get("cd_kyganjee", "")
    wolju_hangul = calenda_row.get("cd_kmganjee", "")
    ilju_hangul = calenda_row.get("cd_kdganjee", "")

    day_stem_hanja = ilju_hanja[0]

    branch_idx = get_branch_by_hour(hour, minute)
    day_stem_info = heavenly_by_hanja[day_stem_hanja]
    siju_stem_idx = get_siju_stem(day_stem_info["index"], branch_idx)

    siju_hanja = heavenly_by_index[siju_stem_idx]["hanja"] + earthly_by_index[branch_idx]["hanja"]
    siju_hangul = heavenly_by_index[siju_stem_idx]["hangul"] + earthly_by_index[branch_idx]["hangul"]

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
            sibsin[key] = {"gan": "나", "ji": get_sibsin_for_branch(day_stem_hanja, ji)}
        else:
            sibsin[key] = {
                "gan": get_sibsin(day_stem_hanja, gan),
                "ji": get_sibsin_for_branch(day_stem_hanja, ji),
            }

    return {
        "hanja": {
            "yeonju": yeonju_hanja, "wolju": wolju_hanja,
            "ilju": ilju_hanja, "siju": siju_hanja,
        },
        "hangeul": {
            "yeonju": yeonju_hangul, "wolju": wolju_hangul,
            "ilju": ilju_hangul, "siju": siju_hangul,
        },
        "sibsin": sibsin,
        "yang": {
            "year": calenda_row.get("cd_sy"), "month": calenda_row.get("cd_sm"),
            "day": calenda_row.get("cd_sd"),
        },
        "eum": {
            "year": calenda_row.get("cd_ly"), "month": calenda_row.get("cd_lm"),
            "day": calenda_row.get("cd_ld"),
        },
        "hour": f"{hour:02d}:{minute:02d}",
    }


# ── 궁합 ──


def calc_compatibility(saju_a: dict, saju_b: dict) -> dict:
    """두 사람의 사주 데이터로 궁합 점수와 해설 계산"""
    heavenly_by_hanja = HEAVENLY_BY_HANJA()
    earthly_by_hanja = EARTHLY_BY_HANJA()

    def _get_pillar(saju, key):
        hanja = saju.get("hanja", {}) if isinstance(saju.get("hanja"), dict) else {}
        return hanja.get(key, "")

    def _get_day_stem(saju):
        ilju = _get_pillar(saju, "ilju")
        return ilju[0] if ilju and len(ilju) >= 1 else ""

    def _get_day_branch(saju):
        ilju = _get_pillar(saju, "ilju")
        return ilju[1] if ilju and len(ilju) >= 2 else ""

    def _element_score(e1, e2):
        if e1 == e2:
            return 1
        if get_generated(e1) == e2 or get_generator(e1) == e2:
            return 3
        return -1

    day_stem_a = _get_day_stem(saju_a)
    day_stem_b = _get_day_stem(saju_b)
    day_branch_a = _get_day_branch(saju_a)
    day_branch_b = _get_day_branch(saju_b)

    stem_info_a = heavenly_by_hanja.get(day_stem_a, {})
    stem_info_b = heavenly_by_hanja.get(day_stem_b, {})
    branch_info_a = earthly_by_hanja.get(day_branch_a, {})
    branch_info_b = earthly_by_hanja.get(day_branch_b, {})

    stem_elem_a = stem_info_a.get("element", "")
    stem_elem_b = stem_info_b.get("element", "")
    branch_elem_a = branch_info_a.get("element", "")
    branch_elem_b = branch_info_b.get("element", "")

    score = 50
    score += _element_score(stem_elem_a, stem_elem_b) * 5
    score += _element_score(branch_elem_a, branch_elem_b) * 5
    score += _element_score(stem_elem_a, branch_elem_b) * 3
    score += _element_score(stem_elem_b, branch_elem_a) * 3

    LHA = {"子":"丑","丑":"子","寅":"亥","亥":"寅","卯":"戌","戌":"卯",
           "辰":"酉","酉":"辰","巳":"申","申":"巳","午":"未","未":"午"}
    CHUNG = {"子":"午","午":"子","丑":"未","未":"丑","寅":"申","申":"寅",
             "卯":"酉","酉":"卯","辰":"戌","戌":"辰","巳":"亥","亥":"巳"}
    if LHA.get(day_branch_a) == day_branch_b:
        score += 10
    elif CHUNG.get(day_branch_a) == day_branch_b:
        score -= 10

    SAMHAP = [{"申","子","辰"}, {"寅","午","戌"}, {"巳","酉","丑"}, {"亥","卯","未"}]
    for group in SAMHAP:
        if day_branch_a in group and day_branch_b in group:
            score += 5
            break

    score = max(0, min(100, score))

    if score >= 80:
        grade = "최상"
        desc = "두 사람의 기운이 매우 잘 맞습니다. 서로를 성장시키는 인연입니다."
    elif score >= 65:
        grade = "상"
        desc = "서로 보완해주는 좋은 궁합입니다. 대화와 이해가 중요합니다."
    elif score >= 50:
        grade = "중"
        desc = "무난한 궁합입니다. 서로 다른 점을 인정하고 존중하는 것이 필요합니다."
    elif score >= 35:
        grade = "하"
        desc = "에너지 방향이 달라 갈등이 생기기 쉽습니다. 서로에 대한 이해와 배려가 특히 중요합니다."
    else:
        grade = "최하"
        desc = "두 사람의 기운이 상충합니다. 극복하기 위해 많은 노력과 대화가 필요합니다."

    return {
        "score": score, "grade": grade, "summary": desc,
        "day_stem_a": day_stem_a, "day_stem_b": day_stem_b,
        "day_branch_a": day_branch_a, "day_branch_b": day_branch_b,
        "stem_element_a": stem_elem_a, "stem_element_b": stem_elem_b,
        "branch_element_a": branch_elem_a, "branch_element_b": branch_elem_b,
    }
