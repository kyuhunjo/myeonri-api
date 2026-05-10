from __future__ import annotations

"""
사주 사계 엔진 (Saju Calculation Engine)
- 오행: 목(木), 화(火), 토(土), 금(金), 수(水)
- 상생: 목→화→토→금→수→목
- 상극: 목→토→수→화→금→목
"""

# ── 천간 (Heavenly Stems) ──
HEAVENLY_STEMS = [
    {"index": 0, "hanja": "甲", "hangul": "갑", "element": "목", "yinyang": "양"},
    {"index": 1, "hanja": "乙", "hangul": "을", "element": "목", "yinyang": "음"},
    {"index": 2, "hanja": "丙", "hangul": "병", "element": "화", "yinyang": "양"},
    {"index": 3, "hanja": "丁", "hangul": "정", "element": "화", "yinyang": "음"},
    {"index": 4, "hanja": "戊", "hangul": "무", "element": "토", "yinyang": "양"},
    {"index": 5, "hanja": "己", "hangul": "기", "element": "토", "yinyang": "음"},
    {"index": 6, "hanja": "庚", "hangul": "경", "element": "금", "yinyang": "양"},
    {"index": 7, "hanja": "辛", "hangul": "신", "element": "금", "yinyang": "음"},
    {"index": 8, "hanja": "壬", "hangul": "임", "element": "수", "yinyang": "양"},
    {"index": 9, "hanja": "癸", "hangul": "계", "element": "수", "yinyang": "음"},
]

HEAVENLY_BY_HANJA = {s["hanja"]: s for s in HEAVENLY_STEMS}
HEAVENLY_BY_INDEX = {s["index"]: s for s in HEAVENLY_STEMS}

# ── 지지 (Earthly Branches) ──
EARTHLY_BRANCHES = [
    {"index": 0, "hanja": "子", "hangul": "자", "element": "수", "yinyang": "양", "zodiac": "쥐"},
    {"index": 1, "hanja": "丑", "hangul": "축", "element": "토", "yinyang": "음", "zodiac": "소"},
    {"index": 2, "hanja": "寅", "hangul": "인", "element": "목", "yinyang": "양", "zodiac": "호랑이"},
    {"index": 3, "hanja": "卯", "hangul": "묘", "element": "목", "yinyang": "음", "zodiac": "토끼"},
    {"index": 4, "hanja": "辰", "hangul": "진", "element": "토", "yinyang": "양", "zodiac": "용"},
    {"index": 5, "hanja": "巳", "hangul": "사", "element": "화", "yinyang": "음", "zodiac": "뱀"},
    {"index": 6, "hanja": "午", "hangul": "오", "element": "화", "yinyang": "양", "zodiac": "말"},
    {"index": 7, "hanja": "未", "hangul": "미", "element": "토", "yinyang": "음", "zodiac": "양"},
    {"index": 8, "hanja": "申", "hangul": "신", "element": "금", "yinyang": "양", "zodiac": "원숭이"},
    {"index": 9, "hanja": "酉", "hangul": "유", "element": "금", "yinyang": "음", "zodiac": "닭"},
    {"index": 10, "hanja": "戌", "hangul": "술", "element": "토", "yinyang": "양", "zodiac": "개"},
    {"index": 11, "hanja": "亥", "hangul": "해", "element": "수", "yinyang": "음", "zodiac": "돼지"},
]

EARTHLY_BY_HANJA = {b["hanja"]: b for b in EARTHLY_BRANCHES}
EARTHLY_BY_INDEX = {b["index"]: b for b in EARTHLY_BRANCHES}

# ── 오행 순환 (상생/상극) ──
# 생: generate (내가 낳는 것)
# 피생: generated (나를 낳아주는 것)
# 극: control (내가 제어하는 것)
# 피극: controlled (나를 제어하는 것)

ELEMENT_CYCLE = ["목", "화", "토", "금", "수"]
ELEMENT_INDEX = {e: i for i, e in enumerate(ELEMENT_CYCLE)}

def get_generated(element: str) -> str:
    """상생: 내가 낳는 것"""
    idx = ELEMENT_INDEX[element]
    return ELEMENT_CYCLE[(idx + 1) % 5]

def get_generator(element: str) -> str:
    """피생: 나를 낳아주는 것"""
    idx = ELEMENT_INDEX[element]
    return ELEMENT_CYCLE[(idx - 1) % 5]

def get_controlled(element: str) -> str:
    """상극: 내가 제어하는 것"""
    idx = ELEMENT_INDEX[element]
    return ELEMENT_CYCLE[(idx + 2) % 5]

def get_controller(element: str) -> str:
    """피극: 나를 제어하는 것"""
    idx = ELEMENT_INDEX[element]
    return ELEMENT_CYCLE[(idx - 2) % 5]


def get_sibsin(day_stem_hanja: str, target_stem_hanja: str) -> str:
    """
    십신(十神) 계산
    day_stem: 일간 (기준, "나")
    target_stem: 비교 대상 천간
    """
    day = HEAVENLY_BY_HANJA[day_stem_hanja]
    target = HEAVENLY_BY_HANJA[target_stem_hanja]

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
    """지지의 지장간을 고려한 십신 계산 (간소화: 지지의 오행 기준)"""
    day = HEAVENLY_BY_HANJA[day_stem_hanja]
    branch = EARTHLY_BY_HANJA[branch_hanja]

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


def get_branch_by_hour(hour: int, minute: int = 0) -> int:
    """
    시간 → 지지 인덱스
    자시(子時) = 23:00~00:59 → index 0
    축시(丑時) = 01:00~02:59 → index 1
    ...
    해시(亥時) = 21:00~22:59 → index 11
    """
    total_minutes = hour * 60 + minute
    # 자시는 23:00~00:59 (전날 기준)
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


def calculate_saju_from_calenda(
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
    day_stem_hanja = ilju_hanja[0]  # 첫 글자가 천간

    # 3. 시주 계산
    branch_idx = get_branch_by_hour(hour, minute)
    day_stem_idx = next(s["index"] for s in HEAVENLY_STEMS if s["hanja"] == day_stem_hanja)
    siju_stem_idx = get_siju_stem(day_stem_idx, branch_idx)

    siju_hanja = HEAVENLY_BY_INDEX[siju_stem_idx]["hanja"] + EARTHLY_BY_INDEX[branch_idx]["hanja"]
    siju_hangul = HEAVENLY_BY_INDEX[siju_stem_idx]["hangul"] + EARTHLY_BY_INDEX[branch_idx]["hangul"]

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
            sibsin[key] = {"gan": "나", "ji": get_sibsin_for_branch(day_stem_hanja, ji)}
        else:
            sibsin[key] = {
                "gan": get_sibsin(day_stem_hanja, gan),
                "ji": get_sibsin_for_branch(day_stem_hanja, ji),
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


# ── 궁합 (Compatibility) ──


def calc_compatibility(saju_a: dict, saju_b: dict) -> dict:
    """두 사람의 사주 데이터로 궁합 점수와 해설 계산"""
    from copy import deepcopy

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
        """오행 점수: 상생 +3, 동일 +1, 상극 -1"""
        if e1 == e2:
            return 1
        if get_generated(e1) == e2 or get_generator(e1) == e2:
            return 3
        return -1

    day_stem_a = _get_day_stem(saju_a)
    day_stem_b = _get_day_stem(saju_b)
    day_branch_a = _get_day_branch(saju_a)
    day_branch_b = _get_day_branch(saju_b)

    stem_info_a = HEAVENLY_BY_HANJA.get(day_stem_a, {})
    stem_info_b = HEAVENLY_BY_HANJA.get(day_stem_b, {})
    branch_info_a = EARTHLY_BY_HANJA.get(day_branch_a, {})
    branch_info_b = EARTHLY_BY_HANJA.get(day_branch_b, {})

    # 점수 계산
    stem_elem_a = stem_info_a.get("element", "")
    stem_elem_b = stem_info_b.get("element", "")
    branch_elem_a = branch_info_a.get("element", "")
    branch_elem_b = branch_info_b.get("element", "")

    score = 50  # 기본 50점

    # 1. 일간 오행 관계 (최대 ±15)
    score += _element_score(stem_elem_a, stem_elem_b) * 5

    # 2. 일지 오행 관계 (최대 ±15)
    score += _element_score(branch_elem_a, branch_elem_b) * 5

    # 3. 일간-상대일지 상생 (최대 ±10)
    score += _element_score(stem_elem_a, branch_elem_b) * 3
    score += _element_score(stem_elem_b, branch_elem_a) * 3

    # 4. 육합/충 (최대 ±10)
    LHA = {"子":"丑","丑":"子","寅":"亥","亥":"寅","卯":"戌","戌":"卯",
           "辰":"酉","酉":"辰","巳":"申","申":"巳","午":"未","未":"午"}
    CHUNG = {"子":"午","午":"子","丑":"未","未":"丑","寅":"申","申":"寅",
             "卯":"酉","酉":"卯","辰":"戌","戌":"辰","巳":"亥","亥":"巳"}
    if LHA.get(day_branch_a) == day_branch_b:
        score += 10  # 육합
    elif CHUNG.get(day_branch_a) == day_branch_b:
        score -= 10  # 충

    # 5. 삼합 (최대 +5)
    SAMHAP = [{"申","子","辰"}, {"寅","午","戌"}, {"巳","酉","丑"}, {"亥","卯","未"}]
    for group in SAMHAP:
        if day_branch_a in group and day_branch_b in group:
            score += 5
            break

    score = max(0, min(100, score))

    # 등급
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
        "score": score,
        "grade": grade,
        "summary": desc,
        "day_stem_a": day_stem_a,
        "day_stem_b": day_stem_b,
        "day_branch_a": day_branch_a,
        "day_branch_b": day_branch_b,
        "stem_element_a": stem_elem_a,
        "stem_element_b": stem_elem_b,
        "branch_element_a": branch_elem_a,
        "branch_element_b": branch_elem_b,
    }
